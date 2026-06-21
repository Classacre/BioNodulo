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
  const cloudLoadedRef = useRef(false);
  const cloudSaveTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Local persistence (skipped in cloud editor mode).
  useEffect(() => {
    if (editorMode) return;
    saveLocalWorkflows(workflows, activeIndex);
  }, [workflows, activeIndex, editorMode]);

  // Cloud load: on first entry to editor mode, load the team's workflow from
  // the DB (or create one), replacing the local placeholder.
  useEffect(() => {
    if (!editorMode || cloudLoadedRef.current) return;
    cloudLoadedRef.current = true;
    (async () => {
      try {
        // Open a specific workflow when deep-linked (?workflow=<id>), else the
        // team's most recent, else create a fresh one.
        const requested =
          typeof window !== 'undefined'
            ? new URLSearchParams(window.location.search).get('workflow')
            : null;
        let wf: Workflow | null = null;
        if (requested) {
          wf = await getCloudWorkflow(requested).catch(() => null);
        }
        if (!wf) {
          const list = await listCloudWorkflows();
          const id = list.length > 0 ? list[0].id : await createCloudWorkflow(i18n.t('common.untitled'));
          wf = await getCloudWorkflow(id);
        }
        setWorkflows([normalizeWorkflow(wf)]);
        setActiveIndex(0);
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

  const closeTab = useCallback((index: number) => {
    setWorkflows(prev => {
      const next = prev.filter((_, i) => i !== index);
      if (next.length === 0) next.push(emptyWorkflow());
      return next;
    });
    setActiveIndex(prev => Math.max(0, Math.min(prev, Math.max(0, workflows.length - 2))));
  }, [workflows.length]);

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
  }) => {
    // Cloud editor: persist the current definition, then submit to the cloud
    // Batch runner. Dry-run previews still use the local editing backend.
    if (editorMode && !options?.dry_run) {
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
      const res = await submitCloudRun(id, options?.environment);
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
    validate, resolve, resolveReport, clearResolveReport, submitRun, exportWorkflow, importWorkflow,
    addRun, updateRun, setRuns,
  };
}
