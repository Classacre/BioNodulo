import { useState, useCallback, useEffect, useRef } from 'react';
import type { Workflow, RunRecord, ResolveReport } from '../types';
import { getToken } from '../collab/auth';
import { appPath } from '../utils/appBase';

function createWorkflowId(): string {
  if (typeof crypto !== 'undefined' && crypto.randomUUID) {
    return crypto.randomUUID();
  }
  return `wf-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
}

function normalizeWorkflow(wf: Workflow): Workflow {
  return { ...wf, id: wf.id || createWorkflowId() };
}

function emptyWorkflow(): Workflow {
  return {
    id: createWorkflowId(), version: '2.0', app: 'bionodulo', name: 'Untitled', description: '',
    nodes: [], edges: [], groups: [], outputs: {},
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

  useEffect(() => {
    saveLocalWorkflows(workflows, activeIndex);
  }, [workflows, activeIndex]);

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
      const r = await fetch(appPath('/api/workflow/validate'), {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ workflow: wf }),
      });
      if (r.ok) {
        const data = await r.json();
        setValidation(data);
        return data;
      }
    } catch { /* offline */ }
    setValidation({ valid: true, errors: [] });
    return { valid: true, errors: [] };
  }, []);

  const resolve = useCallback(async (wf: Workflow) => {
    const requestId = ++resolveRequestIdRef.current;
    try {
      const r = await fetch(appPath('/api/manager/resolve'), {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ workflow: wf }),
      });
      if (r.ok) {
        const data = await r.json() as ResolveReport;
        if (requestId === resolveRequestIdRef.current) {
          setResolveReport(data);
        }
        return data;
      }
    } catch (err) {
      void err;
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
  }) => {
    const token = getToken();
    const r = await fetch(appPath('/api/runs'), {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify({
        workflow: wf,
        workflow_id: wf.id || null,
        name: options?.name || wf.name || 'Untitled',
        no_cache: options?.no_cache || false,
        environment: options?.environment || null,
        force_nodes: options?.force_nodes || [],
        target_nodes: options?.target_nodes || [],
      }),
    });
    if (!r.ok) {
      const text = await r.text();
      throw new Error(`Run submission failed: ${r.status} ${text}`);
    }
    const data = await r.json();
    return data as RunRecord;
  }, []);

  const exportWorkflow = useCallback(async (wf: Workflow, format: string) => {
    try {
      const r = await fetch(appPath('/api/workflow/export'), {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ workflow: wf, format }),
      });
      if (r.ok) return await r.json();
    } catch { /* offline */ }
    // Fallback: export as JSON
    return { content: JSON.stringify(wf, null, 2), filename: `${wf.name || 'workflow'}.${format === 'json' ? 'json' : format}` };
  }, []);

  const importWorkflow = useCallback(async (source: string, format: string) => {
    try {
      const r = await fetch(appPath('/api/workflow/import'), {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ source, format }),
      });
      if (r.ok) {
        const data = await r.json();
        return data.workflow as Workflow;
      }
    } catch {
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
