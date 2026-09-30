// The DOI→workflow flow: analyse a paper via the website API, then build the
// suggested workflow LIVE in the editor — summary note first, then each node,
// then edges — so the visitor watches the graph assemble. React-free: App.tsx
// supplies the workflow/UI primitives via DoiFlowDeps, which also makes the
// flow unit-testable with mocked fetches.
import type { ObjectInfo, Workflow, WorkflowNode } from '../types';
import { dagreLayout } from '../utils/dagreLayout';
import { matchToolToNodeType, slugify, wireSuggestion, type PlacedNode, type SuggestedConnection, type SuggestedNode } from './nodeMatching';

export interface DoiAnalysisPaper {
  title: string;
  authors?: string[];
  doi?: string | null;
  url?: string | null;
  textSource?: 'full_text' | 'abstract';
  textUrl?: string | null;
  limitations?: string[];
  evidenceVersion?: string;
}

export interface DoiAnalysis {
  summary?: string;
  bioinformaticsRelevant?: boolean;
  methodology?: { tools?: string[]; databases?: string[]; pipeline?: string[] };
  workflowSuggestion?: {
    description?: string;
    recommendedNodes?: SuggestedNode[];
    suggestedConnections?: Array<string | SuggestedConnection>;
  };
  paper?: DoiAnalysisPaper;
}

export interface DoiUploadRequest {
  doi: string;
  paperTitle: string;
  onFile: (file: File) => void;
  onCancel: () => void;
}

export interface DoiFlowDeps {
  objectInfo: ObjectInfo;
  signedIn: boolean;
  /** Create a DB-backed cloud tab (POST /api/workflows + open). Throws on failure. */
  createCloudTab: (name: string) => Promise<void>;
  /** Append a local (unsaved) tab and focus it. */
  addLocalTab: (name: string) => void;
  renameActive: (name: string) => void;
  /** Read the latest active workflow (ref-backed, never stale mid-flow). */
  getWorkflow: () => Workflow;
  setWorkflow: (updater: (wf: Workflow) => Workflow) => void;
  /** Explicit final save for DB-backed tabs, including if the user changed tabs. */
  persistWorkflow?: () => Promise<void>;
  fitView: () => void;
  setUploadRequest: (req: DoiUploadRequest | null) => void;
  /** Append a line to the translucent progress overlay (empty string clears). */
  onProgress: (line: string) => void;
  onAnalysisMetrics?: (metrics: { model?: string; inputTokens?: number; outputTokens?: number }) => void;
  notify: {
    loading: (title: string, id: string) => void;
    success: (title: string, id?: string, message?: string) => void;
    info: (title: string, id?: string, message?: string) => void;
    error: (title: string, id?: string, message?: string) => void;
    dismiss: (id: string) => void;
    guestBanner: () => void;
  };
  t: (key: string, opts?: Record<string, unknown>) => string;
  /** Injectable for tests; defaults to window fetch against the website API. */
  fetchImpl?: typeof fetch;
  /** Injectable for tests; stage pacing in ms. */
  stageDelayMs?: number;
}

const TOAST_ID = 'doi-flow';
const WEBSITE_API = '/api';

/** Estimated node sizes for dagre (close to the canvas' rendered cards). */
const NODE_SIZE = { width: 240, height: 110 };
const NOTE_SIZE = { width: 320, height: 180 };

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

type AnalyzeOutcome =
  | { kind: 'ok'; analysis: DoiAnalysis }
  | { kind: 'needsUpload'; paper: DoiAnalysisPaper }
  | { kind: 'fail'; message: string; detail?: string };

function outcomeFromPayload(status: number, value: unknown, doi: string): AnalyzeOutcome {
  const body = value && typeof value === 'object' ? value as Record<string, unknown> : {};
  if (status === 409 && body.needsUpload === true) {
    const paper = body.paper && typeof body.paper === 'object' ? body.paper as DoiAnalysisPaper : { title: doi };
    return { kind: 'needsUpload', paper };
  }
  if (status < 200 || status >= 300) {
    return { kind: 'fail', message: `http-${status}` };
  }
  if (!body.result || typeof body.result !== 'object') return { kind: 'fail', message: 'bad-response' };
  return { kind: 'ok', analysis: body.result as DoiAnalysis };
}

async function readAnalysisStream(
  response: Response,
  doi: string,
  onEvent: (event: Record<string, unknown>) => void,
  signal: AbortSignal,
  onChunk: () => void,
): Promise<AnalyzeOutcome> {
  if (!response.body) return { kind: 'fail', message: 'bad-response' };
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  let pendingCR = false;
  let final: AnalyzeOutcome | null = null;
  const cancel = () => { void reader.cancel(); };
  signal.addEventListener('abort', cancel, { once: true });
  const append = (text: string) => {
    for (const char of text) {
      if (pendingCR) {
        buffer += '\n';
        pendingCR = false;
        if (char === '\n') continue;
      }
      if (char === '\r') pendingCR = true;
      else buffer += char;
    }
    if (buffer.length > 1_000_000) throw new Error('oversized-event');
  };
  const frame = (raw: string) => {
    const data = raw.split('\n').filter(line => line.startsWith('data:')).map(line => line.slice(5).trimStart()).join('\n');
    if (!data) return;
    const event = JSON.parse(data) as Record<string, unknown>;
    if (!event || typeof event !== 'object') throw new Error('invalid-event');
    if (event.type === 'final') {
      if (typeof event.status !== 'number') throw new Error('invalid-final');
      final = outcomeFromPayload(event.status, event.payload, doi);
    } else {
      onEvent(event);
    }
  };
  try {
    while (true) {
      if (signal.aborted) throw new DOMException('Aborted', 'AbortError');
      const { value, done } = await reader.read();
      if (signal.aborted) throw new DOMException('Aborted', 'AbortError');
      if (done) break;
      onChunk();
      append(decoder.decode(value, { stream: true }));
      let boundary = buffer.indexOf('\n\n');
      while (boundary >= 0) {
        frame(buffer.slice(0, boundary));
        if (final) return final;
        buffer = buffer.slice(boundary + 2);
        boundary = buffer.indexOf('\n\n');
      }
    }
    append(decoder.decode());
    if (pendingCR) buffer += '\n';
    if (buffer.trim()) frame(buffer);
    return final ?? { kind: 'fail', message: 'bad-response' };
  } finally {
    signal.removeEventListener('abort', cancel);
    try { await reader.cancel(); } catch { /* stream already closed */ }
    reader.releaseLock();
  }
}

async function callAnalyze(
  fetchImpl: typeof fetch,
  doi: string,
  onEvent: (event: Record<string, unknown>) => void,
): Promise<AnalyzeOutcome> {
  const controller = new AbortController();
  let timedOut = false;
  let idleTimer: ReturnType<typeof setTimeout> | undefined;
  const totalTimer = setTimeout(() => { timedOut = true; controller.abort(); }, 270_000);
  const resetIdle = (ms = 35_000) => {
    clearTimeout(idleTimer);
    idleTimer = setTimeout(() => { timedOut = true; controller.abort(); }, ms);
  };
  resetIdle(90_000);
  let res: Response;
  try {
    res = await fetchImpl(`${WEBSITE_API}/ai/analyze`, {
      method: 'POST',
      headers: { 'content-type': 'application/json', accept: 'text/event-stream' },
      body: JSON.stringify({ doi }),
      signal: controller.signal,
    });
    resetIdle();
    if ((res.headers.get('content-type') || '').includes('text/event-stream')) {
      // Heartbeat comments still reset the idle timer because they arrive as bytes.
      return await readAnalysisStream(res, doi, onEvent, controller.signal, resetIdle);
    }
    const body = await res.json().catch(() => null);
    return outcomeFromPayload(res.status, body, doi);
  } catch {
    return { kind: 'fail', message: timedOut ? 'timeout' : 'network' };
  } finally {
    clearTimeout(totalTimer);
    clearTimeout(idleTimer);
  }
}

async function callUpload(
  fetchImpl: typeof fetch,
  doi: string,
  file: File,
): Promise<AnalyzeOutcome> {
  const form = new FormData();
  form.append('file', file);
  form.append('doi', doi);
  const controller = new AbortController();
  let timedOut = false;
  const timer = setTimeout(() => { timedOut = true; controller.abort(); }, 270_000);
  try {
    const res = await fetchImpl(`${WEBSITE_API}/ai/upload`, { method: 'POST', body: form, signal: controller.signal });
    if (!res.ok) {
      const body = (await res.json().catch(() => ({}))) as { error?: string };
      const detail = [400, 413, 422, 429].includes(res.status) && typeof body.error === 'string'
        ? Array.from(body.error, char => {
          const code = char.charCodeAt(0);
          return code < 32 || code === 127 ? ' ' : char;
        }).join('').trim().slice(0, 200)
        : undefined;
      return { kind: 'fail', message: `upload-http-${res.status}`, detail };
    }
    const body = (await res.json().catch(() => null)) as { result?: DoiAnalysis } | null;
    if (!body?.result) return { kind: 'fail', message: 'bad-response' };
    return { kind: 'ok', analysis: body.result };
  } catch {
    return { kind: 'fail', message: timedOut ? 'upload-timeout' : 'network' };
  } finally {
    clearTimeout(timer);
  }
}

function makeNoteNode(text: string, position: [number, number], idSuffix: string, title?: string): WorkflowNode {
  return {
    id: `doi-note-${idSuffix}`,
    type: 'note',
    position,
    params: { text },
    ...(title ? { ui: { title } } : {}),
  };
}

function failureMessageKey(message: string): string {
  if (message === 'network') return 'doiFlow.errorNetwork';
  if (message === 'timeout') return 'doiFlow.errorNetwork';
  if (message === 'upload-timeout') return 'doiFlow.errorNetwork';
  if (message === 'upload-http-429') return 'doiFlow.errorQuota';
  if (message.startsWith('http-429')) return 'doiFlow.errorQuota';
  if (message.startsWith('http-404')) return 'doiFlow.errorNotFound';
  return 'doiFlow.errorGeneric';
}

/**
 * Run the full flow for one DOI. Resolves when the workflow is built (or the
 * visitor has been informed why it could not be).
 */
export async function runDoiFlow(doi: string, deps: DoiFlowDeps): Promise<void> {
  const { notify, t } = deps;
  const fetchImpl = deps.fetchImpl ?? fetch;
  const stageDelay = deps.stageDelayMs ?? 400;
  const progress = (key: string, defaultValue: string) =>
    deps.onProgress(t(key, { defaultValue }));

  notify.loading(t('doiFlow.analyzing', { defaultValue: 'Analysing paper…' }), TOAST_ID);
  progress('doiFlow.stepStart', 'Opening the paper link…');

  // --- Tab: DB-backed when signed in (auto-save persists the build), local
  // otherwise, with a persistent sign-in-to-save hint.
  let cloudTab = false;
  if (deps.signedIn) {
    try {
      await deps.createCloudTab(t('doiFlow.tabAnalysing', { defaultValue: 'Analysing paper…' }));
      cloudTab = true;
    } catch {
      cloudTab = false;
    }
  }
  if (!cloudTab) {
    deps.addLocalTab(t('doiFlow.tabAnalysing', { defaultValue: 'Analysing paper…' }));
    if (!deps.signedIn) notify.guestBanner();
  }

  // --- Analysis, with the closed-access detour through PDF upload.
  progress('doiFlow.stepAnalyze', 'Analysing the paper with AI…');
  let outcome = await callAnalyze(fetchImpl, doi, event => {
    if (event.type === 'stage') {
      const stages: Record<string, [string, string]> = {
        resolve: ['doiFlow.stepResolve', 'Resolving the DOI…'],
        fetch_text: ['doiFlow.stepRead', 'Reading the paper text…'],
        analyze: ['doiFlow.stepAnalyze', 'Analysing the paper with AI…'],
      };
      const stage = stages[String(event.stage)];
      if (stage) progress(stage[0], stage[1]);
    } else if (event.type === 'model' && typeof event.model === 'string') {
      deps.onAnalysisMetrics?.({ model: event.model.slice(0, 100) });
      deps.onProgress(`${t('doiFlow.stepModel', { defaultValue: 'Model analysing methods' })}: ${event.model.slice(0, 100)}`);
    } else if (event.type === 'tokens') {
      deps.onAnalysisMetrics?.({
        inputTokens: typeof event.inputTokens === 'number' ? event.inputTokens : undefined,
        outputTokens: typeof event.outputTokens === 'number' ? event.outputTokens : undefined,
      });
    }
    // Reasoning deltas are provider-internal and never displayed.
  });
  if (outcome.kind === 'needsUpload') {
    progress('doiFlow.stepNeedPdf', 'Full text is closed-access — waiting for the PDF…');
    const uploaded = await new Promise<AnalyzeOutcome>((resolve) => {
      deps.setUploadRequest({
        doi,
        paperTitle: outcome.kind === 'needsUpload' ? outcome.paper.title ?? doi : doi,
        onFile: (file) => {
          deps.setUploadRequest(null);
          progress('doiFlow.stepAnalyzeUpload', 'Analysing the uploaded PDF…');
          void callUpload(fetchImpl, doi, file).then(resolve);
        },
        onCancel: () => {
          deps.setUploadRequest(null);
          resolve({ kind: 'fail', message: 'upload-cancelled' });
        },
      });
    });
    outcome = uploaded;
  }

  if (outcome.kind === 'fail') {
    deps.onProgress(''); // clear the overlay
    if (outcome.message === 'upload-cancelled') {
      notify.dismiss(TOAST_ID);
      return;
    }
    const failureHint = outcome.detail || (outcome.message === 'upload-timeout'
      ? t('doiFlow.uploadTimeoutHint', { defaultValue: 'The PDF analysis timed out. Please try uploading it again.' })
      : t('doiFlow.errorHint', { defaultValue: 'You can try another DOI, or upload the PDF if you have it.' }));
    notify.error(
      t(failureMessageKey(outcome.message), {
        defaultValue: 'We could not build a workflow from this paper.',
      }),
      TOAST_ID,
      failureHint,
    );
    deps.setWorkflow((wf) => ({
      ...wf,
      nodes: [
        ...wf.nodes,
        makeNoteNode(
          `${t('doiFlow.errorNote', {
            defaultValue:
              'This DOI could not be turned into a workflow automatically.\n\nTry another paper, or open the DOI link again and upload the PDF when asked.',
          })}\n\n${failureHint}`,
          [100, 100],
          'error',
          t('doiFlow.errorNoteTitle', { defaultValue: 'Analysis failed' }),
        ),
      ],
    }));
    deps.fitView();
    return;
  }

  if (outcome.kind !== 'ok') return; // unreachable — 'fail' returns above
  const analysis: DoiAnalysis = outcome.analysis;
  const paperTitle = analysis.paper?.title || doi;
  const suggestion: NonNullable<DoiAnalysis['workflowSuggestion']> = analysis.workflowSuggestion ?? {};
  const recommended: SuggestedNode[] = suggestion.recommendedNodes ?? [];

  // --- Not bioinformatics / nothing to build: say so, visibly, and stop.
  if (analysis.bioinformaticsRelevant === false || recommended.length === 0) {
    deps.onProgress('');
    const notBio = analysis.bioinformaticsRelevant === false;
    notify.info(
      notBio
        ? t('doiFlow.notBioTitle', { defaultValue: 'This paper does not look bioinformatics-related' })
        : t('doiFlow.noWorkflowTitle', { defaultValue: 'No workflow could be derived from this paper' }),
      TOAST_ID,
      paperTitle,
    );
    deps.renameActive(paperTitle);
    deps.setWorkflow((wf) => ({
      ...wf,
      nodes: [
        ...wf.nodes,
        makeNoteNode(
          notBio
            ? t('doiFlow.notBioNote', {
                defaultValue:
                  'The AI read this paper and concluded it is not about computational biology or bioinformatics methods, so no workflow was built.',
              })
            : t('doiFlow.noWorkflowNote', {
                defaultValue:
                  'The AI could not derive a reproducible pipeline from this paper, so no workflow was built.',
              }),
          [100, 100],
          'inform',
          paperTitle,
        ),
      ],
    }));
    deps.fitView();
    return;
  }

  // --- Build live: title, summary note, staged nodes at dagre positions,
  // staged edges. Only explicit, valid suggested connections become edges;
  // matching port types alone do not establish a valid scientific workflow.
  deps.renameActive(paperTitle);
  notify.loading(t('doiFlow.building', { defaultValue: 'Building workflow…' }), TOAST_ID);
  progress('doiFlow.stepPlan', 'Planning the pipeline…');

  const planned = recommended.map((rec, i) => {
    const match = matchToolToNodeType(rec.name, rec.category, deps.objectInfo, rec.nodeType);
    const node: WorkflowNode = {
      id: slugify(rec.name, i),
      type: match.type,
      position: [0, 0], // laid out below
      params: match.fellBackToNote ? { text: `${rec.name}\n\n${rec.reason}` } : {},
      ...(rec.name ? { ui: { title: rec.name } } : {}),
    };
    return { node, label: rec.name } satisfies PlacedNode;
  });

  const allEdges = wireSuggestion(planned, suggestion.suggestedConnections ?? [], deps.objectInfo);
  const matchedCount = planned.filter(p => p.node.type !== 'note').length;
  const unmatched = planned.filter(p => p.node.type === 'note').map(p => p.label);
  const unconnected = planned.filter(p => p.node.type !== 'note').slice(1)
    .filter(p => !allEdges.some(edge => edge.to.node === p.node.id))
    .map(p => p.label);

  const positions = dagreLayout(
    planned.map((p) => ({ id: p.node.id, ...NODE_SIZE })),
    allEdges.map((e) => ({ from: e.from.node, to: e.to.node })),
    { direction: 'LR', nodeSep: 60, rankSep: 140 },
  );
  let minX = Infinity;
  let minY = Infinity;
  for (const pos of positions.values()) {
    minX = Math.min(minX, pos.x);
    minY = Math.min(minY, pos.y);
  }
  if (!Number.isFinite(minX)) minX = 100;
  if (!Number.isFinite(minY)) minY = 260;
  for (const p of planned) {
    const pos = positions.get(p.node.id);
    if (pos) p.node.position = [pos.x, pos.y];
  }

  const summaryText = [
    paperTitle,
    `DOI: ${analysis.paper?.doi || doi}`,
    analysis.paper?.authors?.length ? `Authors: ${analysis.paper.authors.join(', ')}` : '',
    analysis.paper?.textSource ? `Evidence source: ${analysis.paper.textSource === 'full_text' ? 'full text' : 'abstract only'}` : '',
    analysis.paper?.textUrl ? `Source: ${analysis.paper.textUrl}` : '',
    analysis.paper?.limitations?.length ? `Limits: ${analysis.paper.limitations.join('; ')}` : '',
    (analysis.summary || '').trim(),
    suggestion.description ? `Suggested approach: ${suggestion.description}` : '',
    analysis.methodology?.pipeline?.length ? `Paper methods:\n${analysis.methodology.pipeline.map((step, i) => `${i + 1}. ${step}`).join('\n')}` : '',
    `Registered tool coverage: ${matchedCount}/${planned.length} suggested steps. Review all inputs and parameters before running.`,
    unmatched.length ? `Unmatched suggestions (shown as notes): ${unmatched.join(', ')}` : '',
    unconnected.length ? `Unconnected steps (no valid suggested connection): ${unconnected.join(', ')}` : '',
    recommended.length ? `Why these steps:\n${recommended.map(rec => `- ${rec.name}: ${rec.reason || 'No rationale supplied'}`).join('\n')}` : '',
  ]
    .filter(Boolean)
    .join('\n');
  if (summaryText.trim()) {
    deps.setWorkflow((wf) => ({
      ...wf,
      nodes: [
        ...wf.nodes,
        makeNoteNode(
          summaryText,
          [minX, minY - (NOTE_SIZE.height + 60)],
          'summary',
          t('doiFlow.summaryNoteTitle', { defaultValue: 'Paper summary' }),
        ),
      ],
    }));
    await sleep(stageDelay);
  }

  for (const p of planned) {
    // Progress text carries the node name: build it directly, not via t().
    deps.onProgress(`${t('doiFlow.stepAdding', { defaultValue: 'Adding' })} ${p.label}…`);
    deps.setWorkflow((wf) => ({ ...wf, nodes: [...wf.nodes, p.node] }));
    await sleep(stageDelay);
  }
  deps.fitView();

  if (allEdges.length) {
    progress('doiFlow.stepWiring', 'Connecting the nodes…');
  }
  for (const edge of allEdges) {
    deps.setWorkflow((wf) => ({ ...wf, edges: [...wf.edges, edge] }));
    await sleep(Math.max(150, Math.round(stageDelay * 0.6)));
  }

  deps.fitView();
  deps.getWorkflow(); // The DOI tab may have been closed during the staged build.
  deps.onProgress('');
  try {
    await deps.persistWorkflow?.();
  } catch {
    notify.error(
      t('doiFlow.saveFailedTitle', { defaultValue: 'Workflow built, but saving failed' }),
      TOAST_ID,
      t('doiFlow.saveFailedHint', { defaultValue: 'Keep this tab open and retry saving before you leave.' }),
    );
    return;
  }
  if (matchedCount === 0) {
    notify.info(
      t('doiFlow.noMatchedToolsTitle', { defaultValue: 'Paper analysed; no registered tools matched' }),
      TOAST_ID,
      t('doiFlow.noMatchedToolsMessage', { defaultValue: 'The suggested steps are notes. Map them to installed tools before running.' }),
    );
  } else {
    notify.success(
      t('doiFlow.doneTitle', { defaultValue: 'Workflow draft built' }),
      TOAST_ID,
      t('doiFlow.doneMessage', { defaultValue: 'Review unmatched steps, inputs, and parameters before running.' }),
    );
  }
}
