import { useState, useCallback, useEffect, useLayoutEffect, useRef, type SetStateAction } from 'react';
import { useAtomValue } from 'jotai';
import type { Workflow, RunRecord, ResolveReport } from '../../types';
import { apiPost, apiRequest } from '../../api/client';
import {
  listCloudWorkflows,
  getCloudWorkflow,
  createCloudWorkflow,
  saveCloudWorkflow,
  workflowDefinition,
  submitCloudRun,
  type CloudRunInputs,
  type CloudWriteContext,
  rowToWorkflow,
  type WorkflowRow,
} from '../../api/website';
import { cloudConfigAtom } from '../../state/appAtoms';
import { readOpenWorkflowRecord, readOpenWorkflows, writeOpenWorkflows } from '../../state/openWorkflows';
import i18n from '../../i18n';
import { logError } from '../../state/logging';
import { collectLocalInputArtifacts } from '../../utils/workflowFiles';
import { isCuratedTemplateInputArtifact } from '../../localTemplates';
import { getMcpRuntime } from '../../mcp/runtime';
import { toast } from '../../components/ui';
import { normalizeWorkflowPortAliases } from '../../utils/workflowPortCompatibility';

function createWorkflowId(): string {
  if (typeof crypto !== 'undefined' && crypto.randomUUID) {
    return crypto.randomUUID();
  }
  return `wf-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
}

/**
 * Drop edges the canvas cannot draw.
 *
 * An edge is `{ from: {node, output}, to: {node, input} }`. Anything else --
 * a `{source, target}` pair from an importer, an edge left behind by a deleted
 * node -- used to reach the renderer and throw on `edge.from.node`, which
 * unmounts the whole editor and leaves a blank page. One malformed edge should
 * cost that edge, not the workflow.
 */
function usableEdges(wf: Workflow): Workflow['edges'] {
  if (!Array.isArray(wf.edges)) return [];
  const nodeIds = new Set((Array.isArray(wf.nodes) ? wf.nodes : []).map(n => n?.id));
  const kept = wf.edges.filter(edge => {
    const from = edge?.from;
    const to = edge?.to;
    if (!from || !to || typeof from.node !== 'string' || typeof to.node !== 'string') return false;
    return nodeIds.has(from.node) && nodeIds.has(to.node);
  });
  if (kept.length !== wf.edges.length) {
    logError(
      'workflow.edges.dropped',
      new Error(`Dropped ${wf.edges.length - kept.length} unusable edge(s) from "${wf.name || wf.id}"`),
    );
  }
  return kept;
}

let edgeIdSeq = 0;

/**
 * Assign an id to every edge that lacks one.
 *
 * Edge ids key the React list, the Yjs collab doc, and delete/reconnect
 * operations. Templates and imports can carry id-less edges; those rendered
 * fine locally, but `workflowToDoc` silently skipped them, so loading the
 * official Biopython template inside a collab session lost its four preview
 * links and the run then failed validation with "missing required input
 * 'file'". Normalize at the state boundary so no entry path can reintroduce
 * an id-less edge.
 */
function withEdgeIds(edges: Workflow['edges']): Workflow['edges'] {
  const taken = new Set(edges.map(e => e.id).filter(Boolean));
  return edges.map(edge => {
    if (edge.id) return edge;
    let id = '';
    do {
      edgeIdSeq += 1;
      id = `e_auto_${edgeIdSeq}`;
    } while (taken.has(id));
    taken.add(id);
    return { ...edge, id };
  });
}

function normalizeWorkflow(wf: Workflow): Workflow {
  return normalizeWorkflowPortAliases({
    ...wf,
    id: wf.id || createWorkflowId(),
    nodes: Array.isArray(wf.nodes) ? wf.nodes.filter(n => n && typeof n.id === 'string') : [],
    edges: withEdgeIds(usableEdges(wf)),
    parameters: Array.isArray(wf.parameters) ? wf.parameters : [],
  });
}

function emptyWorkflow(): Workflow {
  return {
    id: createWorkflowId(), version: '2.0', app: 'bionodulo', name: i18n.t('common.untitled'), description: '',
    nodes: [], edges: [], groups: [], outputs: {}, parameters: [],
  };
}

/** Stable key of exactly what saveCloudWorkflow PUTs. Used to skip the
 * redundant re-save of a workflow that was just created and never edited. */
function workflowSaveKey(wf: Workflow): string {
  return JSON.stringify({
    name: wf.name || 'Untitled',
    description: wf.description || null,
    definition: workflowDefinition(wf),
  });
}

const LOCAL_WORKFLOWS_KEY = 'bionodulo.local.workflows';
const CLOUD_DRAFTS_KEY = 'bionodulo.cloud.drafts';

function cloudScopeId(userId?: string, teamId?: string): string | null {
  if (!userId || !teamId) return null;
  const encode = (id: string) => encodeURIComponent(id).replace(/\./g, '%2E');
  return `${encode(userId)}.${encode(teamId)}`;
}
type CloudSaveState = { key: string; phase: 'pending' | 'saving' | 'error' | 'creating'; conflict?: boolean };
type ParkedCloudSession = {
  workflows: Workflow[]; activeIndex: number; serverIds: Set<string>;
  pristine: Map<string, string>; saved: Map<string, string>;
  saveStates: Record<string, CloudSaveState>; restored: boolean; loaded: boolean;
  tabRecordReady: boolean; loadError: boolean; createdIds: Map<string, string>;
  closedDraftIds: Set<string>;
};

function createRequestId(): string {
  if (typeof crypto !== 'undefined' && crypto.randomUUID) return crypto.randomUUID();
  // The API accepts an RFC 4122 UUID even on insecure local development hosts.
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, digit => {
    const random = Math.floor(Math.random() * 16);
    return (digit === 'x' ? random : (random & 3) | 8).toString(16);
  });
}

function isSubstantiveDraft(wf: Workflow): boolean {
  return Boolean(wf.cloudPending || wf.nodes?.length || wf.edges?.length || wf.groups?.length
    || wf.parameters?.length || wf.description?.trim() || wf.name !== i18n.t('common.untitled'));
}

function readCloudDrafts(storageKey: string | null): Workflow[] {
  if (!storageKey) return [];
  try {
    const parsed = JSON.parse(localStorage.getItem(storageKey) || '[]') as unknown;
    if (!Array.isArray(parsed)) return [];
    return parsed.filter((value): value is Workflow => Boolean(value && typeof value === 'object'
      && typeof value.id === 'string' && Array.isArray(value.nodes) && Array.isArray(value.edges)))
      .map(normalizeWorkflow);
  } catch { return []; }
}

function writeCloudDrafts(storageKey: string | null, drafts: Workflow[]): boolean {
  if (!storageKey) return false;
  try {
    localStorage.setItem(storageKey, JSON.stringify(drafts));
    return true;
  } catch (err) {
    logError('cloud.workflows.drafts', err);
    return false;
  }
}

function latestRunStatus<T extends string>(previous: T | undefined, incoming: T | undefined): T | undefined {
  const rank = (status: string) => status === 'pending' ? 0 : status === 'running' ? 1 : 2;
  return previous && incoming && rank(previous) > rank(incoming) ? previous : incoming ?? previous;
}

// Socket events can arrive before the HTTP submission response registers the
// run. Keep those updates and merge registration without resetting progress.
function mergeRunRecord(previous: RunRecord | undefined, incoming: Partial<RunRecord> & Pick<RunRecord, 'run_id'>): RunRecord {
  const cloudRun = incoming.options?.cloud === true || previous?.options?.cloud === true
    || incoming.cloud_workflow_context !== undefined;
  const shortId = incoming.run_id.length > 12 ? `${incoming.run_id.slice(0, 8)}...${incoming.run_id.slice(-4)}` : incoming.run_id;
  const fallbackName = cloudRun
    ? i18n.t('console.cloudRunFallbackName', { defaultValue: 'Cloud run {{id}}', id: shortId }) : i18n.t('common.untitled');
  const replaceCloudPlan = incoming.cloud_workflow_context !== undefined && incoming.execution_plan !== undefined;
  const plan = replaceCloudPlan
    ? [...new Set(incoming.execution_plan)]
    : [...new Set([...(previous?.execution_plan ?? []), ...(incoming.execution_plan ?? [])])];
  const planIds = new Set(plan);
  const nodes = new Map((previous?.node_statuses ?? [])
    .filter(node => !replaceCloudPlan || planIds.has(node.node_id)).map(node => [node.node_id, node]));
  for (const node of incoming.node_statuses ?? []) {
    const existing = nodes.get(node.node_id);
    nodes.set(node.node_id, replaceCloudPlan ? node
      : { ...existing, ...node, status: latestRunStatus(existing?.status, node.status)! });
  }
  return {
    ...previous,
    ...incoming,
    run_id: incoming.run_id,
    workflow_name: incoming.workflow_name || previous?.workflow_name || fallbackName,
    status: latestRunStatus(previous?.status, incoming.status) ?? 'pending',
    node_statuses: [...nodes.values()],
    execution_plan: plan,
    node_outputs: { ...previous?.node_outputs, ...incoming.node_outputs },
    previews: { ...previous?.previews, ...incoming.previews },
    artifacts: { ...previous?.artifacts, ...incoming.artifacts },
    start_time: incoming.status === 'pending' && previous?.start_time
      ? previous.start_time : incoming.start_time ?? previous?.start_time,
  };
}

function upsertRun(runs: RunRecord[], incoming: Partial<RunRecord> & Pick<RunRecord, 'run_id'>): RunRecord[] {
  const previous = runs.find(run => run.run_id === incoming.run_id);
  const merged = mergeRunRecord(previous, incoming);
  return previous
    ? runs.map(run => run.run_id === incoming.run_id ? merged : run)
    : [merged, ...runs];
}

function loadLocalWorkflows(): { workflows: Workflow[]; activeIndex: number } {
  try {
    const raw = localStorage.getItem(LOCAL_WORKFLOWS_KEY);
    if (!raw) return { workflows: [emptyWorkflow()], activeIndex: 0 };
    const parsed = JSON.parse(raw) as { workflows?: Workflow[]; activeIndex?: number };
    const workflows = Array.isArray(parsed.workflows)
      ? parsed.workflows.map(normalizeWorkflow).filter(wf => Array.isArray(wf.nodes) && Array.isArray(wf.edges))
      : [];
    if (workflows.length === 0) return { workflows: [emptyWorkflow()], activeIndex: 0 };
    const activeIndex = Math.max(0, Math.min(parsed.activeIndex ?? 0, workflows.length - 1));
    return { workflows, activeIndex };
  } catch {
    return { workflows: [emptyWorkflow()], activeIndex: 0 };
  }
}

function saveLocalWorkflows(workflows: Workflow[], activeIndex: number) {
  try {
    localStorage.setItem(LOCAL_WORKFLOWS_KEY, JSON.stringify({
      version: 1,
      savedAt: new Date().toISOString(),
      activeIndex,
      workflows: workflows.map(normalizeWorkflow),
    }));
  } catch {
    // Browser storage can be unavailable in private mode or quota exhaustion.
  }
}

export function useWorkflow() {
  const initial = useState(() => getMcpRuntime() ? { workflows: [emptyWorkflow()], activeIndex: 0 } : loadLocalWorkflows())[0];
  const initialLocalKeys = useRef(new Map(initial.workflows.map(wf => [wf.id, workflowSaveKey(wf)])));
  const [workflows, setWorkflows] = useState<Workflow[]>(initial.workflows);
  const [activeIndex, setActiveIndexState] = useState(initial.activeIndex);
  const selectionEpochRef = useRef(0);
  const setActiveIndex = useCallback((next: SetStateAction<number>) => {
    selectionEpochRef.current += 1;
    setActiveIndexState(next);
  }, []);
  const activeWorkflowIdRef = useRef(workflows[activeIndex]?.id);
  activeWorkflowIdRef.current = workflows[activeIndex]?.id;
  const [validation, setValidation] = useState<{ valid: boolean; errors: string[] }>({ valid: true, errors: [] });
  const [resolveReport, setResolveReport] = useState<ResolveReport | null>(null);
  const resolveRequestIdRef = useRef(0);

  const clearResolveReport = useCallback(() => {
    setResolveReport(null);
  }, []);
  const [runs, setRuns] = useState<RunRecord[]>([]);

  // Shared cloud editor: persist workflows to the website DB instead of
  // localStorage, and submit runs to the cloud Batch runner. Gated on
  // editorMode (from /api/config); default off = unchanged local behaviour.
  const cloudConfig = useAtomValue(cloudConfigAtom);
  const editorMode = Boolean(cloudConfig?.editorMode);
  const cloudScope = cloudScopeId(cloudConfig?.user?.id, cloudConfig?.team?.id);
  const cloudDraftKey = cloudScope ? `${CLOUD_DRAFTS_KEY}.${cloudScope}` : null;
  const cloudWriteContextRef = useRef<CloudWriteContext | null>(null);
  cloudWriteContextRef.current = cloudConfig?.user?.id && cloudConfig?.team?.id ? {
    expectedUserId: cloudConfig.user.id,
    expectedTeamId: cloudConfig.team.id,
  } : null;
  const cloudScopeRef = useRef(cloudDraftKey);
  const cloudConfigScopeRef = useRef(cloudDraftKey);
  cloudConfigScopeRef.current = cloudDraftKey;
  const cloudScopeChanging = cloudScopeRef.current !== cloudDraftKey;
  const generationRef = useRef({ owner: editorMode ? cloudDraftKey : null, value: 0 });
  const generationOwner = editorMode ? cloudDraftKey : null;
  if (generationRef.current.owner !== generationOwner) {
    generationRef.current = { owner: generationOwner, value: generationRef.current.value + 1 };
  }
  const cloudGeneration = generationRef.current.value;
  const mountedRef = useRef(true);
  useLayoutEffect(() => {
    mountedRef.current = true;
    return () => { mountedRef.current = false; };
  }, []);
  const isCurrentCloudGeneration = useCallback((generation: number, scope: string | null) => (
    mountedRef.current && generationRef.current.value === generation
    && cloudScopeRef.current === scope && cloudConfigScopeRef.current === scope
  ), []);
  const parkedCloudSessions = useRef(new Map<string, ParkedCloudSession>());
  const hiddenWorkflow = useRef(emptyWorkflow());
  // started = dedups the load; loaded = true ONLY after the DB workflow is set,
  // so the debounced save never fires against the stale local placeholder
  // (which has a client id the DB doesn't know → 404).
  const cloudLoadStartedRef = useRef(false);
  const cloudLoadedRef = useRef(false);
  const cloudTabRecordReadyRef = useRef(false);
  // State, not just the ref: the effect that records open tabs has to re-run
  // when restoration finishes, and a ref assignment does not schedule a render.
  const [cloudRestored, setCloudRestored] = useState(false);
  const [cloudLoadError, setCloudLoadError] = useState(false);
  const cloudServerIdsRef = useRef(new Set<string>());
  const cloudSaveTimers = useRef(new Map<string, ReturnType<typeof setTimeout>>());
  const cloudScheduledKeys = useRef(new Map<string, string>());
  const cloudSavedKeys = useRef(new Map<string, string>());
  const cloudQueuedKeys = useRef(new Map<string, string>());
  const cloudSaveChains = useRef(new Map<string, Promise<void>>());
  const cloudLatestKeys = useRef(new Map<string, string>());
  const cloudCreateRequests = useRef(new Map<string, Promise<void>>());
  const cloudCreateFailed = useRef(new Set<string>());
  const cloudCreatedIds = useRef(new Map<string, string>());
  const cloudClosedDraftIds = useRef(new Set<string>());
  const [cloudSaveStates, setCloudSaveStates] = useState<Record<string, CloudSaveState>>({});
  // Exact confirmed server payload, initially from loading/creating the row.
  // Advance it after every successful PUT so an Undo to an older initial
  // snapshot is dirty after another revision has been saved.
  const cloudPristineRef = useRef(new Map<string, string>());

  // Local persistence (skipped in cloud editor mode).
  useEffect(() => {
    if (editorMode) return;
    saveLocalWorkflows(workflows, activeIndex);
  }, [workflows, activeIndex, editorMode]);

  useLayoutEffect(() => {
    if (!editorMode || !cloudScopeChanging) return;
    const previousScope = cloudScopeRef.current;
    const drafts = workflows.filter(wf => wf.id && !cloudServerIdsRef.current.has(wf.id)
      && isSubstantiveDraft(wf)
      && (previousScope || initialLocalKeys.current.get(wf.id) !== workflowSaveKey(wf)));
    // Persistence is best effort. Its failure must never expose the old graph
    // in a new scope; the parked session remains recoverable in this page.
    if (previousScope) {
      writeCloudDrafts(previousScope, drafts);
      parkedCloudSessions.current.set(previousScope, {
        workflows, activeIndex, serverIds: new Set(cloudServerIdsRef.current),
        pristine: new Map(cloudPristineRef.current), saved: new Map(cloudSavedKeys.current),
        saveStates: cloudSaveStates, restored: cloudRestored, loaded: cloudLoadedRef.current,
        tabRecordReady: cloudTabRecordReadyRef.current, loadError: cloudLoadError,
        createdIds: new Map(cloudCreatedIds.current), closedDraftIds: new Set(cloudClosedDraftIds.current),
      });
    }
    const parked = cloudDraftKey ? parkedCloudSessions.current.get(cloudDraftKey) : undefined;
    // Only newly imported/edited pre-identity drafts may follow initial account
    // discovery. Unchanged desktop history is never assigned a cloud owner.
    const bootstrapDrafts = !previousScope && cloudDraftKey ? drafts : [];
    if (bootstrapDrafts.length) writeCloudDrafts(cloudDraftKey, bootstrapDrafts);
    cloudScopeRef.current = cloudDraftKey;
    for (const timer of cloudSaveTimers.current.values()) clearTimeout(timer);
    cloudSaveTimers.current.clear();
    cloudScheduledKeys.current.clear();
    cloudQueuedKeys.current.clear();
    cloudSaveChains.current.clear();
    cloudLatestKeys.current.clear();
    cloudCreateRequests.current.clear();
    cloudCreateFailed.current.clear();
    cloudSavedKeys.current = new Map(parked?.saved);
    cloudServerIdsRef.current = new Set(parked?.serverIds);
    cloudPristineRef.current = new Map(parked?.pristine);
    cloudCreatedIds.current = new Map(parked?.createdIds);
    cloudClosedDraftIds.current = new Set(parked?.closedDraftIds);
    cloudLoadStartedRef.current = Boolean(parked?.restored);
    cloudLoadedRef.current = Boolean(parked?.loaded);
    cloudTabRecordReadyRef.current = Boolean(parked?.tabRecordReady);
    const recovered = parked?.workflows ?? (bootstrapDrafts.length ? bootstrapDrafts : [emptyWorkflow()]);
    const saveStates = { ...parked?.saveStates };
    for (const wf of recovered) {
      if (!wf.id) continue;
      const key = workflowSaveKey(wf);
      const serverBacked = cloudServerIdsRef.current.has(wf.id);
      if ((!serverBacked && isSubstantiveDraft(wf)) || (serverBacked
        && cloudPristineRef.current.get(wf.id) !== key && cloudSavedKeys.current.get(wf.id) !== key)) {
        saveStates[wf.id] = { key, phase: 'error' };
        if (!serverBacked && parked) cloudCreateFailed.current.add(wf.id);
      }
    }
    setCloudSaveStates(saveStates);
    setCloudRestored(Boolean(parked?.restored));
    setCloudLoadError(Boolean(parked?.loadError));
    setValidation({ valid: true, errors: [] });
    setResolveReport(null);
    resolveRequestIdRef.current += 1;
    setWorkflows(recovered);
    setActiveIndexState(Math.max(0, Math.min(parked?.activeIndex ?? 0, recovered.length - 1)));
  }, [editorMode, cloudDraftKey, cloudScopeChanging, workflows, activeIndex, cloudSaveStates, cloudRestored, cloudLoadError]);

  // Cloud load: on first entry to editor mode, open the team's recent workflows
  // as tabs (the deep-linked one focused first). Workflows are managed in-app via
  // tabs now, so we hydrate several rather than a single one.
  useEffect(() => {
    if (!editorMode || !cloudScope || cloudScopeChanging || cloudLoadStartedRef.current) return;
    cloudLoadStartedRef.current = true;
    const idsAtRestoreStart = new Set(workflows.map(wf => wf.id));
    const selectionAtRestoreStart = selectionEpochRef.current;
    const persistedDrafts = readCloudDrafts(cloudDraftKey);
    const persistedIds = new Set(persistedDrafts.map(wf => wf.id));
    const savedDrafts = [...persistedDrafts, ...workflows.filter(wf => wf.cloudRequestId
      && !cloudServerIdsRef.current.has(wf.id!) && !persistedIds.has(wf.id))];
    (async () => {
      try {
        const requested = getMcpRuntime()?.initialContext?.workflow_id ||
          (typeof window !== 'undefined'
            ? new URLSearchParams(window.location.search).get('workflow')
            : null);

        const list = await listCloudWorkflows();
        if (!isCurrentCloudGeneration(cloudGeneration, cloudDraftKey)) return;
        const known = new Set(list.map(summary => summary.id));
        const remembered = readOpenWorkflowRecord(cloudScope);

        // Restore exactly the tabs that were open, plus any deep link. Only a
        // browser that has never recorded a set falls back to recent work --
        // otherwise closing a tab would be undone on the next visit.
        const ids: string[] = [];
        if (requested) ids.push(requested);
        if (remembered === null) {
          // A browser that has never recorded a set gets the single most recent
          // workflow, not a wall of them. Opening eight tabs nobody asked for is
          // slow, buries the one that was wanted, and is what made closing tabs
          // feel futile.
          const mostRecent = list[0];
          if (mostRecent && !ids.includes(mostRecent.id)) ids.push(mostRecent.id);
        } else {
          for (const id of remembered.openIds) {
            // Drop anything deleted elsewhere; restoring it would 404.
            if (known.has(id) && !ids.includes(id)) ids.push(id);
          }
        }
        // An empty team opens a local placeholder. Creating a server row here
        // would add another unwanted blank workflow on every visit.
        if (ids.length === 0) {
          setWorkflows(prev => {
            const addedDuringRestore = prev.filter(wf => !idsAtRestoreStart.has(wf.id));
            const seen = new Set(addedDuringRestore.map(wf => wf.id));
            const drafts = savedDrafts.filter(wf => !seen.has(wf.id));
            const next = [...addedDuringRestore, ...drafts];
            setActiveIndexState(Math.max(0, next.length - 1));
            return next.length ? next : [emptyWorkflow()];
          });
          cloudTabRecordReadyRef.current = true;
          setCloudLoadError(false);
          setCloudRestored(true);
          return;
        }

        const loaded = await Promise.all(
          ids.map(id => getCloudWorkflow(id).then(normalizeWorkflow).catch(() => null)),
        );
        if (!isCurrentCloudGeneration(cloudGeneration, cloudDraftKey)) return;
        const tabs = loaded.filter((w): w is Workflow => w !== null);
        if (tabs.length === 0) {
          // A transient fetch failure must not replace the remembered tabs
          // with the local placeholder on the next visit.
          setWorkflows(prev => {
            const seen = new Set(prev.map(wf => wf.id));
            return [...prev, ...savedDrafts.filter(wf => !seen.has(wf.id))];
          });
          setCloudLoadError(true);
          setCloudRestored(true);
          return;
        }
        // Select the deep-linked workflow by identity, not by position.
        // Failed fetches are dropped from `tabs`, so if the requested one did
        // not load, index 0 is somebody's unrelated recent workflow -- the
        // editor then silently opens the wrong thing and looks like it ignored
        // the link.
        const requestedIndex = requested ? tabs.findIndex(w => w.id === requested) : -1;
        const rememberedIndex = remembered?.activeId ? tabs.findIndex(w => w.id === remembered.activeId) : -1;
        if (requested && requestedIndex === -1) {
          logError(
            'cloud.workflows.deeplink',
            new Error(`Requested workflow ${requested} could not be opened`),
          );
        }
        setWorkflows(prev => {
          // A new tab may have been created while the async restore fetched
          // rows. Preserve it rather than replacing it with the old snapshot.
          const restoredIds = new Set(tabs.map(wf => wf.id));
          const addedDuringRestore = prev.filter(wf => !idsAtRestoreStart.has(wf.id) && !restoredIds.has(wf.id));
          const seen = new Set([...tabs, ...addedDuringRestore].map(wf => wf.id));
          const drafts = savedDrafts.filter(wf => !seen.has(wf.id));
          const next = [...tabs, ...addedDuringRestore, ...drafts];
          const newerSelection = selectionEpochRef.current !== selectionAtRestoreStart
            ? next.findIndex(wf => wf.id === activeWorkflowIdRef.current) : -1;
          // A newer explicit action wins over the initial URL; the URL still
          // takes precedence over the older remembered selection/drafts.
          setActiveIndexState(newerSelection >= 0 ? newerSelection
            : addedDuringRestore.length ? tabs.length + addedDuringRestore.length - 1
              : requestedIndex >= 0 ? requestedIndex
                : drafts.length ? tabs.length + drafts.length - 1
                  : rememberedIndex >= 0 ? rememberedIndex : 0);
          return next;
        });
        for (const wf of tabs) if (wf.id) {
          cloudServerIdsRef.current.add(wf.id);
          cloudPristineRef.current.set(wf.id, workflowSaveKey(wf));
        }
        cloudLoadedRef.current = true;
        cloudTabRecordReadyRef.current = tabs.length === ids.length;
        setCloudLoadError(tabs.length !== ids.length);
        setCloudRestored(true);
      } catch (err) {
        if (!isCurrentCloudGeneration(cloudGeneration, cloudDraftKey)) return;
        logError('cloud.workflows.load', err);
        setWorkflows(prev => {
          const seen = new Set(prev.map(wf => wf.id));
          return [...prev, ...savedDrafts.filter(wf => !seen.has(wf.id))];
        });
        setCloudLoadError(true);
        // Let a DOI import fall back to a local draft if cloud restoration
        // fails; otherwise it remains queued forever behind cloudRestored.
        setCloudRestored(true);
      }
    })();
  }, [editorMode, workflows, cloudDraftKey, cloudScope, cloudScopeChanging, cloudGeneration, isCurrentCloudGeneration]);

  // Remember which tabs are open, so the next visit restores this set and not
  // whatever happens to be recent. Guarded on cloudLoadedRef so the initial
  // placeholder or a partial/failed restore does not overwrite the record.
  useEffect(() => {
    if (!editorMode || cloudScopeChanging || !cloudRestored || !cloudTabRecordReadyRef.current) return;
    writeOpenWorkflows(
      workflows.filter(w => w.id && !w.cloudPending && cloudServerIdsRef.current.has(w.id))
        .map(w => w.id as string),
      cloudScope,
      workflows[activeIndex]?.id ?? null,
    );
  }, [workflows, activeIndex, editorMode, cloudRestored, cloudScopeChanging, cloudScope]);

  // Keep unresolved cloud drafts and their idempotency keys across reloads.
  // Server-backed tabs are recorded separately in openWorkflows.
  useEffect(() => {
    if (!editorMode || cloudScopeChanging || !cloudRestored) return;
    writeCloudDrafts(cloudDraftKey, workflows.filter(wf => wf.id && !cloudServerIdsRef.current.has(wf.id)
      && isSubstantiveDraft(wf)));
  }, [workflows, editorMode, cloudRestored, cloudDraftKey, cloudScopeChanging]);

  const startCloudCreation = useCallback((wf: Workflow, retry = false): Promise<void> | undefined => {
    const tempId = wf.id;
    if (!isCurrentCloudGeneration(cloudGeneration, cloudDraftKey)) return;
    if (!tempId || cloudServerIdsRef.current.has(tempId) || cloudCreatedIds.current.has(tempId)) return;
    const inFlight = cloudCreateRequests.current.get(tempId);
    if (inFlight) return inFlight;
    if (cloudCreateFailed.current.has(tempId) && !retry) return;
    cloudCreateFailed.current.delete(tempId);
    const draft = { ...wf, cloudRequestId: wf.cloudRequestId || createRequestId() };
    // Persist the key and document before POST. If its response is lost or the
    // page reloads, replaying this key resolves the same server row.
    const stored = readCloudDrafts(cloudDraftKey).filter(item => item.id !== tempId);
    if (!writeCloudDrafts(cloudDraftKey, [...stored, draft])) {
      cloudCreateFailed.current.add(tempId);
      setCloudSaveStates(prev => ({ ...prev,
        [tempId]: { key: workflowSaveKey(draft), phase: 'error' },
      }));
      return;
    }
    if (!wf.cloudRequestId) {
      setWorkflows(prev => prev.map(item => item.id === tempId
        ? { ...item, cloudRequestId: draft.cloudRequestId } : item));
    }
    setCloudSaveStates(prev => ({ ...prev,
      [tempId]: { key: workflowSaveKey(draft), phase: 'creating' },
    }));
    const request = createCloudWorkflow(draft.name || i18n.t('common.untitled'), {
      clientRequestId: draft.cloudRequestId!, workflow: draft,
      ...cloudWriteContextRef.current,
    }).then(created => {
      if (!isCurrentCloudGeneration(cloudGeneration, cloudDraftKey)) return;
      if (!created.id) throw new Error('Cloud workflow has no ID');
      cloudCreatedIds.current.set(tempId, created.id);
      cloudServerIdsRef.current.add(created.id);
      cloudLoadedRef.current = true;
      cloudPristineRef.current.set(created.id, workflowSaveKey(created));
      setCloudLoadError(false);
      setWorkflows(prev => {
        const draftIndex = prev.findIndex(item => item.id === tempId);
        if (draftIndex < 0) return prev;
        const latestDraft = { ...prev[draftIndex], id: created.id,
          cloudPending: false, cloudRequestId: undefined };
        const existingIndex = prev.findIndex(item => item.id === created.id);
        if (existingIndex < 0) return prev.map((item, index) => index === draftIndex ? latestDraft : item);
        const existingAfterRemoval = existingIndex > draftIndex ? existingIndex - 1 : existingIndex;
        const next = prev.filter((_, index) => index !== draftIndex);
        next[existingAfterRemoval] = latestDraft;
        setActiveIndex(current => current === draftIndex ? existingAfterRemoval
          : current > draftIndex ? current - 1 : current);
        return next;
      });
      setCloudSaveStates(prev => {
        if (!prev[tempId]) return prev;
        const next = { ...prev };
        delete next[tempId];
        return next;
      });
      if (!cloudTabRecordReadyRef.current && !cloudClosedDraftIds.current.has(tempId)) {
        const selectedId = activeWorkflowIdRef.current === tempId ? created.id : activeWorkflowIdRef.current;
        writeOpenWorkflows([...(readOpenWorkflows(cloudScope) || []), created.id], cloudScope, selectedId ?? null);
      }
    }).catch(err => {
      if (!isCurrentCloudGeneration(cloudGeneration, cloudDraftKey)) return;
      cloudCreateFailed.current.add(tempId);
      logError('cloud.workflows.createDraft', err);
      setCloudSaveStates(prev => ({ ...prev,
        [tempId]: { key: workflowSaveKey(draft), phase: 'error' },
      }));
    }).finally(() => {
      if (isCurrentCloudGeneration(cloudGeneration, cloudDraftKey)
        && cloudCreateRequests.current.get(tempId) === request) cloudCreateRequests.current.delete(tempId);
    });
    cloudCreateRequests.current.set(tempId, request);
    return request;
  }, [cloudDraftKey, cloudScope, cloudGeneration, isCurrentCloudGeneration, setActiveIndex]);

  const scheduleCloudSave = useCallback((wf: Workflow, immediate = false) => {
    if (!isCurrentCloudGeneration(cloudGeneration, cloudDraftKey)) return;
    const id = wf.id;
    if (!id || wf.cloudPending) return;
    const key = workflowSaveKey(wf);
    const scopeAtSchedule = cloudScopeRef.current;
    const generationAtSchedule = cloudGeneration;
    const writeContext = cloudWriteContextRef.current;
    cloudLatestKeys.current.set(id, key);
    const oldTimer = cloudSaveTimers.current.get(id);
    if (oldTimer) clearTimeout(oldTimer);
    cloudSaveTimers.current.delete(id);
    cloudScheduledKeys.current.delete(id);
    setCloudSaveStates(prev => prev[id]?.key === key && prev[id].phase === 'pending'
      ? prev : { ...prev, [id]: { key, phase: 'pending' } });
    cloudScheduledKeys.current.set(id, key);
    cloudSaveTimers.current.set(id, setTimeout(() => {
      cloudSaveTimers.current.delete(id);
      cloudScheduledKeys.current.delete(id);
      cloudQueuedKeys.current.set(id, key);
      const previous = cloudSaveChains.current.get(id) ?? Promise.resolve();
      const next = previous.then(async () => {
        if (!isCurrentCloudGeneration(generationAtSchedule, scopeAtSchedule)) return;
        if (cloudLatestKeys.current.get(id) === key) {
          setCloudSaveStates(prev => prev[id]?.key === key
            ? { ...prev, [id]: { key, phase: 'saving' } } : prev);
        }
        try {
          if (!writeContext) throw new Error('Cloud write identity unavailable');
          await saveCloudWorkflow(wf, writeContext);
          if (!isCurrentCloudGeneration(generationAtSchedule, scopeAtSchedule)) return;
          cloudPristineRef.current.set(id, key);
          cloudSavedKeys.current.set(id, key);
          if (cloudLatestKeys.current.get(id) === key) {
            setCloudSaveStates(prev => {
              if (prev[id]?.key !== key) return prev;
              const nextStates = { ...prev };
              delete nextStates[id];
              return nextStates;
            });
          }
        } catch (err) {
          if (!isCurrentCloudGeneration(generationAtSchedule, scopeAtSchedule)) return;
          logError('cloud.workflows.save', err);
          if (cloudLatestKeys.current.get(id) === key) {
            setCloudSaveStates(prev => prev[id]?.key === key
              ? { ...prev, [id]: { key, phase: 'error' } } : prev);
          }
        } finally {
          if (isCurrentCloudGeneration(generationAtSchedule, scopeAtSchedule)
            && cloudQueuedKeys.current.get(id) === key) cloudQueuedKeys.current.delete(id);
        }
      });
      cloudSaveChains.current.set(id, next);
    }, immediate ? 0 : 1200));
  }, [cloudGeneration, cloudDraftKey, isCurrentCloudGeneration]);

  // Cloud save: debounce each tab independently. Switching tabs must not
  // cancel the previous tab's pending save, and writes for one tab finish in
  // edit order even if a slower request overlaps the next debounce.
  useEffect(() => {
    if (!editorMode || cloudScopeChanging) return;
    const visibleIds = new Set(workflows.map(wf => wf.id).filter((id): id is string => Boolean(id)));
    setCloudSaveStates(prev => {
      const stale = Object.keys(prev).filter(id => !visibleIds.has(id));
      if (stale.length === 0) return prev;
      const nextStates = { ...prev };
      for (const id of stale) delete nextStates[id];
      return nextStates;
    });
    for (const wf of workflows) {
      if (!wf.id) continue;
      const id = wf.id;
      const key = workflowSaveKey(wf);
      if (!cloudServerIdsRef.current.has(id)) {
        if (cloudRestored && isSubstantiveDraft(wf)) {
          if (cloudCreateFailed.current.has(id)) {
            setCloudSaveStates(prev => prev[id]?.phase === 'error' ? prev
              : { ...prev, [id]: { key, phase: 'error' } });
          } else {
            startCloudCreation(wf);
          }
        }
        continue;
      }
      // cloudPending = row still being created server-side; its temp id would 404.
      if (wf.cloudPending) continue;
      if (!cloudLoadedRef.current) continue;
      cloudLatestKeys.current.set(id, key);
      if (cloudScheduledKeys.current.get(id) !== key) {
        const previousTimer = cloudSaveTimers.current.get(id);
        if (previousTimer) clearTimeout(previousTimer);
        cloudSaveTimers.current.delete(id);
        cloudScheduledKeys.current.delete(id);
      }
      if (((cloudPristineRef.current.get(id) === key || cloudSavedKeys.current.get(id) === key)
        && !cloudQueuedKeys.current.has(id))
        || cloudScheduledKeys.current.get(id) === key || cloudQueuedKeys.current.get(id) === key) {
        if (!cloudQueuedKeys.current.has(id) && cloudScheduledKeys.current.get(id) !== key) {
          setCloudSaveStates(prev => {
            if (!prev[id] || prev[id].key === key) return prev;
            const nextStates = { ...prev };
            delete nextStates[id];
            return nextStates;
          });
        }
        continue;
      }
      // Failed saves wait for an explicit retry; unrelated renders must not
      // silently clear the error or start an unbounded retry loop.
      if (cloudSaveStates[id]?.key === key && cloudSaveStates[id].phase === 'error') continue;
      scheduleCloudSave(wf);
    }
  }, [workflows, editorMode, cloudScopeChanging, cloudRestored, cloudSaveStates, scheduleCloudSave, startCloudCreation]);

  const retryCloudSave = useCallback((id: string) => {
    if (!isCurrentCloudGeneration(cloudGeneration, cloudDraftKey)) return;
    const wf = workflows.find(item => item.id === id);
    if (!wf) return;
    if (cloudScopeChanging) {
      setWorkflows(previous => [...previous]);
      return;
    }
    if (cloudServerIdsRef.current.has(id)) scheduleCloudSave(wf, true);
    else void startCloudCreation(wf, true);
  }, [workflows, cloudScopeChanging, scheduleCloudSave, startCloudCreation, cloudGeneration, cloudDraftKey, isCurrentCloudGeneration]);

  const addRun = useCallback((run: RunRecord) => {
    setRuns(prev => upsertRun(prev, run));
  }, []);

  const updateRun = useCallback((runId: string, patch: Partial<RunRecord>) => {
    setRuns(prev => upsertRun(prev, { ...patch, run_id: runId }));
  }, []);

  const activeWorkflow = workflows[activeIndex] || emptyWorkflow();
  const currentWorkflows = useRef(workflows);
  currentWorkflows.current = workflows;

  // Host edits use the same persisted cloud workflow. Adopt newer revisions
  // only when this tab is clean; protect an edited draft and its save baseline.
  useEffect(() => {
    const runtime = getMcpRuntime();
    const id = activeWorkflow.id;
    if (!runtime || !cloudRestored || !id || !cloudServerIdsRef.current.has(id)) return;
    const teamId = runtime.teamId;
    let stopped = false, pending = false;
    const adopt = (row: WorkflowRow) => {
      if (stopped || !isCurrentCloudGeneration(cloudGeneration, cloudDraftKey) || runtime.teamId !== teamId) return;
      if (!row.updatedAt || row.id !== id) throw new Error('Invalid cloud workflow revision');
      const remote = normalizeWorkflow(rowToWorkflow(row));
      const key = workflowSaveKey(remote);
      const timer = cloudSaveTimers.current.get(id);
      if (timer) clearTimeout(timer);
      cloudSaveTimers.current.delete(id);
      cloudScheduledKeys.current.delete(id);
      cloudLatestKeys.current.set(id, key);
      cloudPristineRef.current.set(id, key);
      cloudSavedKeys.current.set(id, key);
      runtime.acceptRevision(id, row.updatedAt);
      setWorkflows(previous => previous.map(wf => wf.id === id ? remote : wf));
      setCloudSaveStates(previous => { const next = { ...previous }; delete next[id]; return next; });
      toast.dismiss(`cloud-save-${id}`);
    };
    const poll = async () => {
      if (stopped || pending || document.visibilityState === 'hidden') return;
      const baseline = runtime.revisions.get(id);
      if (!baseline) return;
      pending = true;
      try {
        const row = await runtime.host.tool<WorkflowRow>('get_workflow', { workflow_id: id, team_id: teamId });
        if (stopped || !isCurrentCloudGeneration(cloudGeneration, cloudDraftKey) || runtime.teamId !== teamId || runtime.revisions.get(id) !== baseline || row.updatedAt === baseline
          || Date.parse(row.updatedAt || '') < Date.parse(baseline)) return;
        const current = currentWorkflows.current.find(wf => wf.id === id);
        if (!current) return;
        const key = workflowSaveKey(current);
        const dirty = (cloudPristineRef.current.get(id) !== key && cloudSavedKeys.current.get(id) !== key)
          || cloudQueuedKeys.current.has(id);
        if (!dirty) { adopt(row); return; }
        const timer = cloudSaveTimers.current.get(id);
        if (timer) clearTimeout(timer);
        cloudSaveTimers.current.delete(id);
        cloudScheduledKeys.current.delete(id);
        setCloudSaveStates(previous => previous[id]?.conflict && previous[id]?.key === key ? previous : { ...previous, [id]: { key, phase: 'error', conflict: true } });
        toast.show({ id: `cloud-save-${id}`, title: 'Cloud workflow changed',
          message: 'The host or another editor saved a newer revision. Your draft is preserved. Export it or load the latest version before continuing.',
          tone: 'warning', duration: 0, actions: [{ label: 'Load latest', onClick: () => {
            void runtime.host.tool<WorkflowRow>('get_workflow', { workflow_id: id, team_id: teamId }).then(adopt).catch(error => {
              logError('mcp.workflow.reload', error);
              toast.error('Could not load the latest cloud workflow', { message: error instanceof Error ? error.message : 'Try again. Your draft is preserved.' });
            });
          } }],
        });
      } catch (error) { logError('mcp.workflow.poll', error); }
      finally { pending = false; }
    };
    const timer = window.setInterval(() => { void poll(); }, 8_000);
    document.addEventListener('visibilitychange', poll);
    return () => { stopped = true; window.clearInterval(timer); document.removeEventListener('visibilitychange', poll); };
  }, [activeWorkflow.id, cloudRestored, cloudGeneration, cloudDraftKey, isCurrentCloudGeneration]);

  const setWorkflow = useCallback((index: number, updater: (w: Workflow) => Workflow) => {
    setWorkflows(prev => prev.map((w, i) => i === index ? normalizeWorkflow(updater(w)) : w));
  }, []);

  const updateWorkflow = useCallback((index: number, partial: Partial<Workflow>) => {
    setWorkflows(prev => prev.map((w, i) => i === index ? normalizeWorkflow({ ...w, ...partial }) : w));
  }, []);

  const addTab = useCallback(() => {
    setWorkflows(prev => {
      setActiveIndex(prev.length);
      return [...prev, emptyWorkflow()];
    });
  }, [setActiveIndex]);

  const addWorkflow = useCallback((wf: Workflow) => {
    // Imported JSON can carry an existing server id, while converters can
    // assign the same placeholder id to repeated imports. Every cloud copy
    // needs its own client tab id until POST returns its distinct server id.
    const added = editorMode ? { ...wf, id: createWorkflowId(),
      cloudPending: false, cloudRequestId: createRequestId() } : wf;
    setWorkflows(prev => {
      setActiveIndex(prev.length);
      return [...prev, normalizeWorkflow(added)];
    });
    return added.id;
  }, [editorMode, setActiveIndex]);

  const addCloudWorkflow = useCallback((wf: Workflow) => {
    if (!wf.id) throw new Error('A cloud workflow must have a server ID');
    cloudServerIdsRef.current.add(wf.id);
    cloudLoadedRef.current = true;
    setWorkflows(prev => {
      setActiveIndex(prev.length);
      return [...prev, normalizeWorkflow(wf)];
    });
  }, [setActiveIndex]);

  // Open a DB-backed cloud workflow as a tab. If it's already open, just focus
  // it; otherwise fetch it and append a tab. No-op outside editor mode.
  const openCloudWorkflow = useCallback(async (id: string): Promise<boolean> => {
    if (!editorMode || !id || !isCurrentCloudGeneration(cloudGeneration, cloudDraftKey)) return false;
    const already = currentWorkflows.current.findIndex(w => w.id === id);
    if (already >= 0) {
      setActiveIndex(already);
      return true;
    }
    try {
      const wf = normalizeWorkflow(await getCloudWorkflow(id));
      if (!isCurrentCloudGeneration(cloudGeneration, cloudDraftKey)) return false;
      cloudPristineRef.current.set(id, workflowSaveKey(wf));
      cloudServerIdsRef.current.add(id);
      cloudLoadedRef.current = true;
      setCloudLoadError(false);
      setWorkflows(prev => {
        const existing = prev.findIndex(w => w.id === id);
        if (existing >= 0) { setActiveIndex(existing); return prev; }
        setActiveIndex(prev.length);
        return [...prev, wf];
      });
      return true;
    } catch (err) {
      if (!isCurrentCloudGeneration(cloudGeneration, cloudDraftKey)) return false;
      logError('cloud.workflows.open', err);
      return false;
    }
  }, [editorMode, cloudGeneration, cloudDraftKey, isCurrentCloudGeneration, setActiveIndex]);

  // Create a fresh cloud workflow and open it as a new tab. The tab appears
  // IMMEDIATELY with a temp id (cloudPending) — the server round trip then
  // swaps in the real id while keeping any edits made in the meantime. This is
  // what makes new tabs feel instant in the cloud editor; the old flow awaited
  // POST + GET serially before the tab rendered at all.
  const newCloudWorkflow = useCallback(async () => {
    if (!editorMode || !isCurrentCloudGeneration(cloudGeneration, cloudDraftKey)) return;
    const placeholder: Workflow = { ...emptyWorkflow(), cloudPending: true,
      cloudRequestId: createRequestId() };
    // A fast POST can settle before React commits the placeholder render.
    // Preserve its selection when the partial-restore fallback records its ID.
    activeWorkflowIdRef.current = placeholder.id;
    setWorkflows(prev => {
      setActiveIndex(prev.length);
      return [...prev, placeholder];
    });
    await startCloudCreation(placeholder);
  }, [editorMode, startCloudCreation, cloudGeneration, cloudDraftKey, isCurrentCloudGeneration, setActiveIndex]);

  const closeTab = useCallback((index: number) => {
    const closingId = workflows[index]?.id;
    if (closingId) {
      cloudClosedDraftIds.current.add(closingId);
      cloudCreateFailed.current.delete(closingId);
      writeCloudDrafts(cloudDraftKey, readCloudDrafts(cloudDraftKey).filter(wf => wf.id !== closingId));
      const timer = cloudSaveTimers.current.get(closingId);
      if (timer) clearTimeout(timer);
      cloudSaveTimers.current.delete(closingId);
      cloudScheduledKeys.current.delete(closingId);
      cloudLatestKeys.current.delete(closingId);
      setCloudSaveStates(prev => {
        if (!prev[closingId]) return prev;
        const next = { ...prev };
        delete next[closingId];
        return next;
      });
    }
    let nextLen = 0;
    setWorkflows(prev => {
      const next = prev.filter((_, i) => i !== index);
      // An empty editor is a local blank draft until New creates a server row.
      if (next.length === 0) next.push(emptyWorkflow());
      nextLen = next.length;
      return next;
    });
    // Clamp against the ACTUAL post-close length (captured in the updater),
    // not the render-closure `workflows.length` which lags one render behind
    // and could leave activeIndex pointing a tab off after rapid closes.
    setActiveIndex(prev => Math.max(0, Math.min(prev, nextLen - 1)));
  }, [workflows, cloudDraftKey, setActiveIndex]);

  const reorderWorkflows = useCallback((from: number, to: number) => {
    setWorkflows(prev => {
      const next = [...prev];
      const [removed] = next.splice(from, 1);
      next.splice(to, 0, removed);
      return next;
    });
    setActiveIndex(prev => {
      if (prev === from) return to;
      if (from < to && prev > from && prev <= to) return prev - 1;
      if (from > to && prev < from && prev >= to) return prev + 1;
      return prev;
    });
  }, [setActiveIndex]);

  const validate = useCallback(async (wf: Workflow) => {
    try {
      const data = await apiPost<{ valid: boolean; errors: string[] }>('/workflow/validate', { workflow: wf });
      if (editorMode && !isCurrentCloudGeneration(cloudGeneration, cloudDraftKey)) {
        return { valid: false, errors: ['The account or team changed. Validate this workflow again.'] };
      }
      setValidation(data);
      return data;
    } catch (error) {
      if (editorMode && !isCurrentCloudGeneration(cloudGeneration, cloudDraftKey)) {
        return { valid: false, errors: ['The account or team changed. Validate this workflow again.'] };
      }
      if (getMcpRuntime()) {
        const failed = { valid: false, errors: [error instanceof Error ? error.message : 'Cloud validation failed.'] };
        setValidation(failed);
        return failed;
      }
    }
    setValidation({ valid: true, errors: [] });
    return { valid: true, errors: [] };
  }, [editorMode, cloudGeneration, cloudDraftKey, isCurrentCloudGeneration]);

  const resolve = useCallback(async (wf: Workflow) => {
    const requestId = ++resolveRequestIdRef.current;
    try {
      const data = await apiPost<ResolveReport>('/manager/resolve', { workflow: wf });
      if (editorMode && !isCurrentCloudGeneration(cloudGeneration, cloudDraftKey)) return null;
      if (requestId === resolveRequestIdRef.current) {
        setResolveReport(data);
      }
      return data;
    } catch (err) {
      if (editorMode && !isCurrentCloudGeneration(cloudGeneration, cloudDraftKey)) return null;
      logError('workflow.resolve', err);
    }
    if (requestId === resolveRequestIdRef.current) {
      setResolveReport(null);
    }
    return null;
  }, [editorMode, cloudGeneration, cloudDraftKey, isCurrentCloudGeneration]);

  const submitRun = useCallback(async (wf: Workflow, options?: {
    no_cache?: boolean;
    name?: string;
    environment?: string;
    force_nodes?: string[];
    target_nodes?: string[];
    parameters?: Record<string, unknown>;
    dry_run?: boolean;
    resume_checkpoint?: Record<string, unknown>;
    /** Cloud compute selection (preset or custom CPU/RAM) for the Batch run. */
    compute?: { resourceProfile?: string; compute?: { vcpu: number; ramGb: number } };
    /** Local "Run on Cloud": take the cloud submit path even when not in editor
     *  mode (persist to the team DB + submit to Batch instead of the local host). */
    forceCloud?: boolean;
    /** Cloud run inputs (e.g. uploaded-file key map from the pre-flight). */
    inputs?: CloudRunInputs;
  }) => {
    const ensureOwner = () => {
      if (editorMode && !isCurrentCloudGeneration(cloudGeneration, cloudDraftKey)) {
        throw new Error('The account or team changed. Run this workflow again from its original account.');
      }
    };
    ensureOwner();
    if ((editorMode || options?.forceCloud) && options?.dry_run) {
      throw new Error('Dry-run execution previews are available in the desktop app. Use cloud validation before submitting a cloud run.');
    }
    // Cloud editor OR local "Run on Cloud": persist the current definition, then
    // submit to the cloud Batch runner. Dry-run previews still use the local
    // editing backend.
    if ((editorMode || options?.forceCloud) && !options?.dry_run) {
      const unsupportedOptions = [
        options?.target_nodes?.length ? 'target_nodes' : null,
        options?.force_nodes?.length ? 'force_nodes' : null,
        options?.resume_checkpoint !== undefined ? 'resume_checkpoint' : null,
        options?.environment ? 'environment' : null,
        options?.no_cache === true ? 'no_cache' : null,
      ].filter((option): option is string => option !== null);
      if (unsupportedOptions.length > 0) {
        throw new Error(
          `Cloud runs do not yet support these execution options: ${unsupportedOptions.join(', ')}`,
        );
      }
      const stagedPaths = new Set([
        ...Object.keys(options?.inputs?.artifacts ?? {}),
        ...Object.keys(options?.inputs?.files ?? {}),
      ]);
      const unstagedPaths = collectLocalInputArtifacts(wf, options?.parameters ?? {}, {}, { includeCloudUploads: true })
        .filter(artifact => !isCuratedTemplateInputArtifact(artifact))
        .map(artifact => artifact.path)
        .filter(path => !stagedPaths.has(path));
      if (unstagedPaths.length > 0) {
        throw new Error(
          `Cloud run has unstaged local input paths: ${unstagedPaths.join(', ')}`,
        );
      }
      // Ensure the workflow exists in the DB (it normally does after load), then
      // persist the latest definition and submit to the cloud Batch runner.
      // A local workflow id is generated client-side and does not identify a DB
      // row. Forced cloud runs therefore always create a server-owned workflow.
      let id = options?.forceCloud && !editorMode ? undefined : wf.id;
      const writeContext = cloudWriteContextRef.current;
      if (editorMode && !writeContext) throw new Error('Cloud write identity unavailable');
      if (!id) id = (await (writeContext
        ? createCloudWorkflow(wf.name || i18n.t('common.untitled'), writeContext)
        : createCloudWorkflow(wf.name || i18n.t('common.untitled')))).id as string;
      ensureOwner();
      const persisted = { ...wf, id };
      try {
        await (writeContext ? saveCloudWorkflow(persisted, writeContext) : saveCloudWorkflow(persisted));
      } catch (err) {
        logError('cloud.run.save', err);
        throw err;
      }
      ensureOwner();
      const res = await submitCloudRun(
        id,
        options?.compute,
        options?.inputs,
        options?.parameters,
      );
      ensureOwner();
      return {
        run_id: res.runId,
        status: 'submitted',
        cloud: true,
        dashboard_url: res.dashboardUrl,
        name: options?.name,
        workflow_name: wf.name,
      } as unknown as RunRecord;
    }
    const r = await apiRequest('/runs', {
      method: 'POST',
      json: {
        workflow: wf,
        workflow_id: wf.id || null,
        name: options?.name || wf.name || i18n.t('common.untitled'),
        no_cache: options?.no_cache || false,
        environment: options?.environment || null,
        force_nodes: options?.force_nodes || [],
        target_nodes: options?.target_nodes || [],
        parameters: options?.parameters || {},
        ...(options?.dry_run !== undefined ? { dry_run: options.dry_run } : {}),
        ...(options?.resume_checkpoint !== undefined ? { resume_checkpoint: options.resume_checkpoint } : {}),
      },
    });
    const data = await r.json();
    return data as RunRecord;
  }, [editorMode, cloudGeneration, cloudDraftKey, isCurrentCloudGeneration]);

  const exportWorkflow = useCallback(async (wf: Workflow, format: string) => {
    return await apiPost('/workflow/export', { workflow: wf, format });
  }, []);

  const importWorkflow = useCallback(async (source: string, format: string) => {
    try {
      const data = await apiPost<{ workflow?: Workflow }>('/workflow/import', { source: format, content: source });
      return data.workflow ? normalizeWorkflowPortAliases(data.workflow) : null;
    } catch (err) {
      logError('workflow.import', err);
      // Try parsing as JSON directly
      try { return normalizeWorkflowPortAliases(JSON.parse(source) as Workflow); } catch { /* not JSON */ }
    }
    return null;
  }, []);

  return {
    workflows: editorMode && cloudScopeChanging ? [hiddenWorkflow.current] : workflows,
    activeIndex: editorMode && cloudScopeChanging ? 0 : activeIndex,
    activeWorkflow: editorMode && cloudScopeChanging ? hiddenWorkflow.current : activeWorkflow,
    validation: editorMode && cloudScopeChanging ? { valid: true, errors: [] } : validation, runs,
    setWorkflow, updateWorkflow, addTab, addWorkflow, addCloudWorkflow, closeTab, reorderWorkflows, setActiveIndex,
    openCloudWorkflow, newCloudWorkflow,
    cloudSaveStates: editorMode && cloudScopeChanging ? {} : cloudSaveStates, retryCloudSave,
    validate, resolve, resolveReport: editorMode && cloudScopeChanging ? null : resolveReport, clearResolveReport, submitRun, exportWorkflow, importWorkflow,
    addRun, updateRun, setRuns,
    cloudRestored: !cloudScopeChanging && cloudRestored,
    cloudLoadError: !cloudScopeChanging && cloudLoadError,
  };
}
