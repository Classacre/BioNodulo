// The DOI→workflow flow: analyse a paper via the website API, then build the
// suggested workflow LIVE in the editor — summary note first, then each node,
// then edges — so the visitor watches the graph assemble. React-free: App.tsx
// supplies the workflow/UI primitives via DoiFlowDeps, which also makes the
// flow unit-testable with mocked fetches.
import type { ObjectInfo, Workflow, WorkflowNode } from '../types';
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

function gridPosition(index: number): [number, number] {
  const col = index % 4;
  const row = Math.floor(index / 4);
  return [100 + col * 280, 260 + row * 200];
}

function failureMessageKey(message: string): string {
  if (message === 'network') return 'doiFlow.errorNetwork';
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
  const stageDelay = deps.stageDelayMs ?? 450;

  notify.loading(t('doiFlow.analyzing', { defaultValue: 'Analysing paper…' }), TOAST_ID);

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
  let outcome = await callAnalyze(fetchImpl, doi);
  if (outcome.kind === 'needsUpload') {
    const uploaded = await new Promise<AnalyzeOutcome>((resolve) => {
      deps.setUploadRequest({
        doi,
        paperTitle: outcome.kind === 'needsUpload' ? outcome.paper.title ?? doi : doi,
        onFile: (file) => {
          deps.setUploadRequest(null);
          notify.loading(t('doiFlow.analyzingUpload', { defaultValue: 'Analysing uploaded PDF…' }), TOAST_ID);
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
  const analysis = outcome.analysis;
  const paperTitle = analysis.paper?.title || doi;
  const suggestion = analysis.workflowSuggestion ?? {};
  const recommended = suggestion.recommendedNodes ?? [];

  // --- Not bioinformatics / nothing to build: say so, visibly, and stop.
  if (analysis.bioinformaticsRelevant === false || recommended.length === 0) {
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

  // --- Build live: title, summary note, staged nodes, staged edges.
  deps.renameActive(paperTitle);
  notify.loading(t('doiFlow.building', { defaultValue: 'Building workflow…' }), TOAST_ID);

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
      nodes: [...wf.nodes, makeNoteNode(summaryText, [100, 20], 'summary', t('doiFlow.summaryNoteTitle', { defaultValue: 'Paper summary' }))],
    }));
    await sleep(stageDelay);
  }

  const placed: PlacedNode[] = [];
  for (let i = 0; i < recommended.length; i++) {
    const rec = recommended[i];
    const match = matchToolToNodeType(rec.name, rec.category, deps.objectInfo);
    const node: WorkflowNode = {
      id: slugify(rec.name, i),
      type: match.type,
      position: gridPosition(i),
      params: match.fellBackToNote ? { text: `${rec.name}\n\n${rec.reason}` } : {},
      ...(rec.name ? { ui: { title: rec.name } } : {}),
    };
    placed.push({ node, label: rec.name });
    deps.setWorkflow((wf) => ({ ...wf, nodes: [...wf.nodes, node] }));
    await sleep(stageDelay);
  }
  deps.fitView();

  const edges = wireSuggestion(placed, suggestion.suggestedConnections ?? [], deps.objectInfo);
  for (const edge of edges) {
    deps.setWorkflow((wf) => ({ ...wf, edges: [...wf.edges, edge] }));
    await sleep(Math.max(150, Math.round(stageDelay * 0.7)));
  }

  deps.fitView();
  notify.success(
    t('doiFlow.doneTitle', { defaultValue: 'Workflow built' }),
    TOAST_ID,
    t('doiFlow.doneMessage', { defaultValue: 'Review the suggested nodes before running — papers omit details.' }),
  );
}
