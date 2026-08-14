// The DOI→workflow flow: analyse a paper via the website API, then build the
// suggested workflow LIVE in the editor — summary note first, then each node,
// then edges — so the visitor watches the graph assemble. React-free: App.tsx
// supplies the workflow/UI primitives via DoiFlowDeps, which also makes the
// flow unit-testable with mocked fetches.
import type { ObjectInfo, Workflow, WorkflowNode } from '../types';
import { dagreLayout } from '../utils/dagreLayout';
import { matchToolToNodeType, slugify, wireSuggestion, type PlacedNode, type SuggestedNode } from './nodeMatching';

export interface DoiAnalysisPaper {
  title: string;
  authors?: string[];
  doi?: string | null;
  url?: string | null;
}

export interface DoiAnalysis {
  summary?: string;
  bioinformaticsRelevant?: boolean;
  workflowSuggestion?: {
    description?: string;
    recommendedNodes?: SuggestedNode[];
    suggestedConnections?: string[];
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
  fitView: () => void;
  setUploadRequest: (req: DoiUploadRequest | null) => void;
  /** Append a line to the translucent progress overlay (empty string clears). */
  onProgress: (line: string) => void;
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
  | { kind: 'fail'; message: string };

async function callAnalyze(
  fetchImpl: typeof fetch,
  doi: string,
): Promise<AnalyzeOutcome> {
  let res: Response;
  try {
    res = await fetchImpl(`${WEBSITE_API}/ai/analyze`, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ doi }),
    });
  } catch {
    return { kind: 'fail', message: 'network' };
  }
  if (res.status === 409) {
    const body = (await res.json().catch(() => ({}))) as { paper?: DoiAnalysisPaper };
    return { kind: 'needsUpload', paper: body.paper ?? { title: doi } };
  }
  if (!res.ok) {
    const body = (await res.json().catch(() => ({}))) as { error?: string };
    return { kind: 'fail', message: body.error || `http-${res.status}` };
  }
  const body = (await res.json().catch(() => null)) as { result?: DoiAnalysis } | null;
  if (!body?.result) return { kind: 'fail', message: 'bad-response' };
  return { kind: 'ok', analysis: body.result };
}

async function callUpload(
  fetchImpl: typeof fetch,
  doi: string,
  file: File,
): Promise<AnalyzeOutcome> {
  const form = new FormData();
  form.append('file', file);
  form.append('doi', doi);
  let res: Response;
  try {
    res = await fetchImpl(`${WEBSITE_API}/ai/upload`, { method: 'POST', body: form });
  } catch {
    return { kind: 'fail', message: 'network' };
  }
  if (!res.ok) {
    const body = (await res.json().catch(() => ({}))) as { error?: string };
    return { kind: 'fail', message: body.error || `http-${res.status}` };
  }
  const body = (await res.json().catch(() => null)) as { result?: DoiAnalysis } | null;
  if (!body?.result) return { kind: 'fail', message: 'bad-response' };
  return { kind: 'ok', analysis: body.result };
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
  if (message.startsWith('http-429')) return 'doiFlow.errorQuota';
  if (message.startsWith('http-404')) return 'doiFlow.errorNotFound';
  return 'doiFlow.errorGeneric';
}

/**
 * Guarantee connectivity: chain every still-unconnected pipeline node onto the
 * previous one (suggestion order). Ports are chosen type-compatible first, and
 * otherwise the first real port pair — note nodes are skipped (no outputs).
 */
function ensureConnected(
  placed: PlacedNode[],
  edges: Workflow['edges'],
  objectInfo: ObjectInfo,
): Workflow['edges'] {
  const hasEdge = (a: string, b: string) =>
    edges.some((e) => e.from.node === a && e.to.node === b);
  const extra: Workflow['edges'] = [];
  const pipeline = placed.filter((p) => p.node.type !== 'note');
  for (let i = 1; i < pipeline.length; i++) {
    const from = pipeline[i - 1].node;
    const to = pipeline[i].node;
    if (hasEdge(from.id, to.id)) continue;
    const fromMeta = objectInfo[from.type];
    const toMeta = objectInfo[to.type];
    const outs = (fromMeta?.return_types ?? []).map((type, j) => ({
      name: fromMeta?.return_names?.[j] || type,
      type,
    }));
    const ins = [
      ...Object.entries(toMeta?.input_types?.required ?? {}),
      ...Object.entries(toMeta?.input_types?.optional ?? {}),
    ].map(([name, spec]) => ({ name, type: String((spec as { type?: unknown })?.type ?? '') }));
    if (!outs.length || !ins.length) continue;
    const compatible = outs.flatMap((out) =>
      ins.filter((inp) => {
        const a = out.type.toUpperCase();
        const b = inp.type.toUpperCase();
        return a === b || a === '*' || b === '*' || a === 'ANY' || b === 'ANY';
      }).map((inp) => ({ out, inp })),
    )[0];
    const pair = compatible ?? { out: outs[0], inp: ins[0] };
    extra.push({
      id: `doi-chain-${from.id}-${to.id}`,
      from: { node: from.id, output: pair.out.name },
      to: { node: to.id, input: pair.inp.name },
    });
  }
  return [...edges, ...extra];
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
  let outcome = await callAnalyze(fetchImpl, doi);
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
    notify.error(
      t(failureMessageKey(outcome.message), {
        defaultValue: 'We could not build a workflow from this paper.',
      }),
      TOAST_ID,
      t('doiFlow.errorHint', { defaultValue: 'You can try another DOI, or upload the PDF if you have it.' }),
    );
    deps.setWorkflow((wf) => ({
      ...wf,
      nodes: [
        ...wf.nodes,
        makeNoteNode(
          t('doiFlow.errorNote', {
            defaultValue:
              'This DOI could not be turned into a workflow automatically.\n\nTry another paper, or open the DOI link again and upload the PDF when asked.',
          }),
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
  // staged edges. Edges and layout are computed UP FRONT so nodes appear
  // already organised, and every pipeline node ends up connected.
  deps.renameActive(paperTitle);
  notify.loading(t('doiFlow.building', { defaultValue: 'Building workflow…' }), TOAST_ID);
  progress('doiFlow.stepPlan', 'Planning the pipeline…');

  const planned = recommended.map((rec, i) => {
    const match = matchToolToNodeType(rec.name, rec.category, deps.objectInfo);
    const node: WorkflowNode = {
      id: slugify(rec.name, i),
      type: match.type,
      position: [0, 0], // laid out below
      params: match.fellBackToNote ? { text: `${rec.name}\n\n${rec.reason}` } : {},
      ...(rec.name ? { ui: { title: rec.name } } : {}),
    };
    return { node, label: rec.name } satisfies PlacedNode;
  });

  const suggestedEdges = wireSuggestion(planned, suggestion.suggestedConnections ?? [], deps.objectInfo);
  const allEdges = ensureConnected(planned, suggestedEdges, deps.objectInfo);

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
    analysis.paper?.doi ? `DOI: ${analysis.paper.doi}` : '',
    '',
    (analysis.summary || '').trim(),
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
  deps.onProgress('');
  notify.success(
    t('doiFlow.doneTitle', { defaultValue: 'Workflow built' }),
    TOAST_ID,
    t('doiFlow.doneMessage', { defaultValue: 'Review the suggested nodes before running — papers omit details.' }),
  );
}
