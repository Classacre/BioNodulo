import { useState, useCallback, useEffect, useRef } from 'react';
import { useAtomValue } from 'jotai';
import type { Workflow, RunRecord, ResolveReport } from '../../types';
import { apiPost, apiRequest } from '../../api/client';
import {
  listCloudWorkflows,
  getCloudWorkflow,
  createCloudWorkflow,
  saveCloudWorkflow,
  submitCloudRun,
} from '../../api/website';
import { cloudConfigAtom } from '../../state/appAtoms';
import i18n from '../../i18n';
import { logError } from '../../state/logging';

function createWorkflowId(): string {
  if (typeof crypto !== 'undefined' && crypto.randomUUID) {
    return crypto.randomUUID();
  }
  return `wf-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
}

function normalizeWorkflow(wf: Workflow): Workflow {
  return {
    ...wf,
    id: wf.id || createWorkflowId(),
    parameters: Array.isArray(wf.parameters) ? wf.parameters : [],
  };
}

function emptyWorkflow(): Workflow {
  return {
    id: createWorkflowId(), version: '2.0', app: 'bionodulo', name: i18n.t('common.untitled'), description: '',
    nodes: [], edges: [], groups: [], outputs: {}, parameters: [],
  };
}

const LOCAL_WORKFLOWS_KEY = 'bionodulo.local.workflows';

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
  const initial = useState(loadLocalWorkflows)[0];
  const [workflows, setWorkflows] = useState<Workflow[]>(initial.workflows);
  const [activeIndex, setActiveIndex] = useState(initial.activeIndex);
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
  // started = dedups the load; loaded = true ONLY after the DB workflow is set,
  // so the debounced save never fires against the stale local placeholder
  // (which has a client id the DB doesn't know → 404).
  const cloudLoadStartedRef = useRef(false);
  const cloudLoadedRef = useRef(false);
  const cloudSaveTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Local persistence (skipped in cloud editor mode).
  useEffect(() => {
    if (editorMode) return;
    saveLocalWorkflows(workflows, activeIndex);
  }, [workflows, activeIndex, editorMode]);

  // Cloud load: on first entry to editor mode, open the team's recent workflows
  // as tabs (the deep-linked one focused first). Workflows are managed in-app via
  // tabs now, so we hydrate several rather than a single one.
  const CLOUD_TAB_LIMIT = 8;
  useEffect(() => {
    if (!editorMode || cloudLoadStartedRef.current) return;
    cloudLoadStartedRef.current = true;
    (async () => {
      try {
        const requested =
          typeof window !== 'undefined'
            ? new URLSearchParams(window.location.search).get('workflow')
            : null;

        const list = await listCloudWorkflows().catch(() => []);
        // Build the id set to open: deep-linked first, then most-recent, capped.
        const ids: string[] = [];
        if (requested) ids.push(requested);
        for (const summary of list) {
          if (ids.length >= CLOUD_TAB_LIMIT) break;
          if (!ids.includes(summary.id)) ids.push(summary.id);
        }
        // Nothing yet — create a fresh workflow so the editor isn't empty.
        if (ids.length === 0) {
          ids.push(await createCloudWorkflow(i18n.t('common.untitled')));
        }

        const loaded = await Promise.all(
          ids.map(id => getCloudWorkflow(id).then(normalizeWorkflow).catch(() => null)),
        );
        const tabs = loaded.filter((w): w is Workflow => w !== null);
        if (tabs.length === 0) return; // all fetches failed; keep placeholder
        setWorkflows(tabs);
        setActiveIndex(0);
        cloudLoadedRef.current = true;
      } catch (err) {
        logError('cloud.workflows.load', err);
      }
    })();
  }, [editorMode]);

  // Cloud save: debounced PUT of the active workflow's definition.
  useEffect(() => {
    if (!editorMode || !cloudLoadedRef.current) return;
    const wf = workflows[activeIndex];
    if (!wf?.id) return;
    if (cloudSaveTimer.current) clearTimeout(cloudSaveTimer.current);
    cloudSaveTimer.current = setTimeout(() => {
      saveCloudWorkflow(wf).catch(err => logError('cloud.workflows.save', err));
    }, 1200);
    return () => {
      if (cloudSaveTimer.current) clearTimeout(cloudSaveTimer.current);
    };
  }, [workflows, activeIndex, editorMode]);

  const addRun = useCallback((run: RunRecord) => {
    setRuns(prev => [run, ...prev]);
  }, []);

  const updateRun = useCallback((runId: string, patch: Partial<RunRecord>) => {
    setRuns(prev => prev.map(r => r.run_id === runId ? { ...r, ...patch } : r));
  }, []);

  const activeWorkflow = workflows[activeIndex] || emptyWorkflow();

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
  }, []);

  const addWorkflow = useCallback((wf: Workflow) => {
    setWorkflows(prev => {
      setActiveIndex(prev.length);
      return [...prev, normalizeWorkflow(wf)];
    });
  }, []);

  // Open a DB-backed cloud workflow as a tab. If it's already open, just focus
  // it; otherwise fetch it and append a tab. No-op outside editor mode.
  const openCloudWorkflow = useCallback(async (id: string) => {
    if (!editorMode || !id) return;
    let already = -1;
    setWorkflows(prev => {
      already = prev.findIndex(w => w.id === id);
      return prev;
    });
    if (already >= 0) {
      setActiveIndex(already);
      return;
    }
    try {
      const wf = normalizeWorkflow(await getCloudWorkflow(id));
      setWorkflows(prev => {
        const existing = prev.findIndex(w => w.id === id);
        if (existing >= 0) { setActiveIndex(existing); return prev; }
        setActiveIndex(prev.length);
        return [...prev, wf];
      });
    } catch (err) {
      logError('cloud.workflows.open', err);
    }
  }, [editorMode]);

  // Create a fresh cloud workflow and open it as a new tab.
  const newCloudWorkflow = useCallback(async () => {
    if (!editorMode) return;
    try {
      const id = await createCloudWorkflow(i18n.t('common.untitled'));
      const wf = normalizeWorkflow(await getCloudWorkflow(id));
      setWorkflows(prev => {
        setActiveIndex(prev.length);
        return [...prev, wf];
      });
    } catch (err) {
      logError('cloud.workflows.new', err);
    }
  }, [editorMode]);

  const closeTab = useCallback((index: number) => {
    let nextLen = 0;
    setWorkflows(prev => {
      const next = prev.filter((_, i) => i !== index);
      if (next.length === 0) next.push(emptyWorkflow());
      nextLen = next.length;
      return next;
    });
    // Clamp against the ACTUAL post-close length (captured in the updater),
    // not the render-closure `workflows.length` which lags one render behind
    // and could leave activeIndex pointing a tab off after rapid closes.
    setActiveIndex(prev => Math.max(0, Math.min(prev, nextLen - 1)));
  }, []);

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
  }, []);

  const validate = useCallback(async (wf: Workflow) => {
    try {
      const data = await apiPost<{ valid: boolean; errors: string[] }>('/workflow/validate', { workflow: wf });
      setValidation(data);
      return data;
    } catch { /* offline */ }
    setValidation({ valid: true, errors: [] });
    return { valid: true, errors: [] };
  }, []);

  const resolve = useCallback(async (wf: Workflow) => {
    const requestId = ++resolveRequestIdRef.current;
    try {
      const data = await apiPost<ResolveReport>('/manager/resolve', { workflow: wf });
      if (requestId === resolveRequestIdRef.current) {
        setResolveReport(data);
      }
      return data;
    } catch (err) {
      logError('workflow.resolve', err);
    }
    if (requestId === resolveRequestIdRef.current) {
      setResolveReport(null);
    }
    return null;
  }, []);

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
    inputs?: Record<string, unknown>;
  }) => {
    // Cloud editor OR local "Run on Cloud": persist the current definition, then
    // submit to the cloud Batch runner. Dry-run previews still use the local
    // editing backend.
    if ((editorMode || options?.forceCloud) && !options?.dry_run) {
      // Ensure the workflow exists in the DB (it normally does after load), then
      // persist the latest definition and submit to the cloud Batch runner.
      let id = wf.id;
      if (!id) id = await createCloudWorkflow(wf.name || i18n.t('common.untitled'));
      const persisted = { ...wf, id };
      try {
        await saveCloudWorkflow(persisted);
      } catch (err) {
        logError('cloud.run.save', err);
      }
      const res = await submitCloudRun(id, options?.compute, options?.inputs);
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
  }, [editorMode]);

  const exportWorkflow = useCallback(async (wf: Workflow, format: string) => {
    return await apiPost('/workflow/export', { workflow: wf, format });
  }, []);

  const importWorkflow = useCallback(async (source: string, format: string) => {
    try {
      const data = await apiPost<{ workflow?: Workflow }>('/workflow/import', { source: format, content: source });
      return data.workflow ?? null;
    } catch (err) {
      logError('workflow.import', err);
      // Try parsing as JSON directly
      try { return JSON.parse(source) as Workflow; } catch { /* not JSON */ }
    }
    return null;
  }, []);

  return {
    workflows, activeIndex, activeWorkflow, validation, runs,
    setWorkflow, updateWorkflow, addTab, addWorkflow, closeTab, reorderWorkflows, setActiveIndex,
    openCloudWorkflow, newCloudWorkflow,
    validate, resolve, resolveReport, clearResolveReport, submitRun, exportWorkflow, importWorkflow,
    addRun, updateRun, setRuns,
  };
}
