import { useState, useCallback } from 'react';
import type { Workflow, RunRecord, ResolveReport } from '../types';

function emptyWorkflow(): Workflow {
  return {
    version: 'Alpha 1.1', app: 'bionodulo', name: 'Untitled', description: '',
    nodes: [], edges: [], groups: [], outputs: {},
  };
}

export function useWorkflow() {
  const [workflows, setWorkflows] = useState<Workflow[]>([emptyWorkflow()]);
  const [activeIndex, setActiveIndex] = useState(0);
  const [validation, setValidation] = useState<{ valid: boolean; errors: string[] }>({ valid: true, errors: [] });
  const [resolveReport, setResolveReport] = useState<ResolveReport | null>(null);

  const clearResolveReport = useCallback(() => {
    setResolveReport(null);
  }, []);
  const [runs, setRuns] = useState<RunRecord[]>([]);

  const activeWorkflow = workflows[activeIndex] || emptyWorkflow();

  const setWorkflow = useCallback((index: number, updater: (w: Workflow) => Workflow) => {
    setWorkflows(prev => prev.map((w, i) => i === index ? updater(w) : w));
  }, []);

  const updateWorkflow = useCallback((index: number, partial: Partial<Workflow>) => {
    setWorkflows(prev => prev.map((w, i) => i === index ? { ...w, ...partial } : w));
  }, []);

  const addTab = useCallback(() => {
    setWorkflows(prev => [...prev, emptyWorkflow()]);
    setActiveIndex(prev => prev + 1);
  }, []);

  const addWorkflow = useCallback((wf: Workflow) => {
    setWorkflows(prev => [...prev, wf]);
    setActiveIndex(prev => prev + 1);
  }, []);

  const closeTab = useCallback((index: number) => {
    setWorkflows(prev => {
      const next = prev.filter((_, i) => i !== index);
      if (next.length === 0) next.push(emptyWorkflow());
      return next;
    });
    setActiveIndex(prev => Math.min(prev, workflows.length - 2));
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
      const r = await fetch('/api/workflow/validate', {
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
    try {
      const r = await fetch('/api/manager/resolve', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ workflow: wf }),
      });
      if (r.ok) {
        const data = await r.json() as ResolveReport;
        console.log('[useWorkflow.resolve] got report:', data.summary, 'has_issues:', data.has_issues);
        setResolveReport(data);
        return data;
      }
      console.warn('[useWorkflow.resolve] server returned', r.status, await r.text());
    } catch (err) {
      console.error('[useWorkflow.resolve] fetch failed:', err);
    }
    setResolveReport(null);
    return null;
  }, []);

  const submitRun = useCallback(async (wf: Workflow, options?: Record<string, unknown>) => {
    try {
      const r = await fetch('/api/runs', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ workflow: wf, options: options || {} }),
      });
      if (r.ok) {
        const data = await r.json();
        return data as RunRecord;
      }
    } catch {
      // Create mock run record
      const run: RunRecord = {
        run_id: `mock-${Date.now()}`, status: 'completed',
        workflow_name: wf.name || 'Untitled', node_statuses: [],
        node_outputs: {}, execution_plan: [], previews: {}, artifacts: {},
        start_time: new Date().toISOString(),
        end_time: new Date().toISOString(),
      };
      setRuns(prev => [run, ...prev]);
      return run;
    }
  }, []);

  const exportWorkflow = useCallback(async (wf: Workflow, format: string) => {
    try {
      const r = await fetch('/api/workflow/export', {
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
      const r = await fetch('/api/workflow/import', {
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
  };
}
