// WebSocket message dispatch for workflow runtime events.
//
// Extracted from App.tsx — the ~180-line message handler that reacts to
// install logs, execution lifecycle events, preview events, and queue events.
//
// Each handler is small and side-effectful (logs, run state, toasts, follow-up
// API fetch on queue_finish), so this stays a hook rather than a pure reducer.

import { useEffect } from 'react';
import { apiGet } from '../../api/client';
import { toast } from '../../state/notifications';
import type { LogEntry, RunRecord, NodeStatus } from '../../types';

export interface UseWorkflowMessagesArgs {
  onMessage: (handler: (msg: unknown) => void) => () => void;
  addLog: (entry: LogEntry) => void;
  runs: RunRecord[];
  updateRun: (runId: string, partial: Partial<RunRecord>) => void;
  setRuns: React.Dispatch<React.SetStateAction<RunRecord[]>>;
  updateNodeRunStatus: (runId: string, nodeId: string, status: NodeStatus['status'], error?: string) => void;
  recordNodeStart: (nodeId: string, progress: string | undefined) => void;
  clearNodeRunProgress: (nodeId: string) => void;
}

export function useWorkflowMessages({
  onMessage,
  addLog,
  runs,
  updateRun,
  setRuns,
  updateNodeRunStatus,
  recordNodeStart,
  clearNodeRunProgress,
}: UseWorkflowMessagesArgs): void {
  useEffect(() => {
    const unsub = onMessage((msg: unknown) => {
      const data = msg as Record<string, unknown>;
      const payload =
        typeof data.data === 'object' && data.data !== null
          ? (data.data as Record<string, unknown>)
          : {};
      const ts = String(payload.timestamp || new Date().toISOString());

      // --- Install events (pixi + dependency installer) ---
      if (data.type === 'install.log') {
        addLog({
          run_id: 'install-pixi',
          node_id: 'host',
          level: (payload.level as LogEntry['level']) || 'info',
          message: String(payload.message || ''),
          timestamp: ts,
        });
        return;
      }
      if (data.type === 'install.progress') {
        addLog({
          run_id: String(payload.job_id || 'dependency-install'),
          node_id: 'host',
          level: (payload.level as LogEntry['level']) || 'info',
          message: String(payload.message || ''),
          timestamp: ts,
        });
        return;
      }

      // --- Workflow execution logs ---
      if (data.type === 'log' && payload.message) {
        addLog({
          run_id: String(payload.run_id || data.source || 'workflow'),
          node_id: String(payload.node_id || 'engine'),
          level: (payload.level as LogEntry['level']) || 'info',
          message: String(payload.message),
          timestamp: ts,
        });
        return;
      }

      // --- Execution lifecycle events ---
      const runId = String(payload.run_id || data.source || 'workflow');
      if (data.type === 'start') {
        addLog({
          run_id: runId,
          node_id: 'engine',
          level: 'info',
          message: `Workflow started (${payload.total_nodes} nodes)`,
          timestamp: ts,
        });
      } else if (data.type === 'node_start') {
        updateNodeRunStatus(runId, String(payload.node_id), 'running');
        recordNodeStart(String(payload.node_id), payload.progress as string | undefined);
        addLog({
          run_id: runId,
          node_id: String(payload.node_id),
          level: 'info',
          message: `Node start [${payload.progress}] ${payload.node_type}`,
          timestamp: ts,
        });
      } else if (data.type === 'node_complete') {
        updateNodeRunStatus(runId, String(payload.node_id), 'completed');
        clearNodeRunProgress(String(payload.node_id));
        addLog({
          run_id: runId,
          node_id: String(payload.node_id),
          level: 'success',
          message: `Node completed`,
          timestamp: ts,
        });
      } else if (data.type === 'node_error') {
        updateNodeRunStatus(
          runId,
          String(payload.node_id),
          'error',
          String(payload.error || 'Node error'),
        );
        clearNodeRunProgress(String(payload.node_id));
        addLog({
          run_id: runId,
          node_id: String(payload.node_id),
          level: 'error',
          message: `Node error: ${payload.error}`,
          timestamp: ts,
        });
      } else if (data.type === 'node_skip') {
        updateNodeRunStatus(runId, String(payload.node_id), 'skipped');
        clearNodeRunProgress(String(payload.node_id));
        addLog({
          run_id: runId,
          node_id: String(payload.node_id),
          level: 'warn',
          message: `Node skipped (${payload.reason})`,
          timestamp: ts,
        });
      } else if (data.type === 'node_bypass') {
        updateNodeRunStatus(runId, String(payload.node_id), 'skipped');
        clearNodeRunProgress(String(payload.node_id));
        addLog({
          run_id: runId,
          node_id: String(payload.node_id),
          level: 'warn',
          message: `Node bypassed`,
          timestamp: ts,
        });
      } else if (data.type === 'node_cache_hit') {
        updateNodeRunStatus(runId, String(payload.node_id), 'cached');
        clearNodeRunProgress(String(payload.node_id));
        addLog({
          run_id: runId,
          node_id: String(payload.node_id),
          level: 'info',
          message: `Cache hit — skipping execution`,
          timestamp: ts,
        });
      } else if (data.type === 'complete') {
        addLog({
          run_id: runId,
          node_id: 'engine',
          level: payload.status === 'completed' ? 'success' : 'error',
          message: `Workflow ${payload.status}`,
          timestamp: ts,
        });
      } else if (data.type === 'error') {
        addLog({
          run_id: runId,
          node_id: 'engine',
          level: 'error',
          message: `Workflow error: ${payload.message}`,
          timestamp: ts,
        });
      } else if (data.type === 'cancelled') {
        addLog({
          run_id: runId,
          node_id: String(payload.node_id || 'engine'),
          level: 'warn',
          message: `Workflow cancelled`,
          timestamp: ts,
        });
      }

      // --- Preview events ---
      else if (data.type === 'preview') {
        const previewRunId = String(payload.run_id || data.source || '');
        const nodeId = String(payload.node_id || '');
        const path = String(payload.path || '');
        if (previewRunId && nodeId && path) {
          updateRun(previewRunId, {
            previews: {
              ...(runs.find(r => r.run_id === previewRunId)?.previews || {}),
              [nodeId]: path,
            },
          });
        }
      }

      // --- Queue events ---
      else if (data.type === 'queue_submit') {
        addLog({
          run_id: String(payload.run_id),
          node_id: 'queue',
          level: 'info',
          message: `Run submitted`,
          timestamp: ts,
        });
      } else if (data.type === 'queue_start') {
        addLog({
          run_id: String(payload.run_id),
          node_id: 'queue',
          level: 'info',
          message: `Run started`,
          timestamp: ts,
        });
        updateRun(String(payload.run_id), { status: 'running', start_time: ts });
      } else if (data.type === 'queue_finish') {
        addLog({
          run_id: String(payload.run_id),
          node_id: 'queue',
          level: 'success',
          message: `Run finished (${payload.status})`,
          timestamp: ts,
        });
        const finalStatus =
          payload.status === 'completed'
            ? 'completed'
            : payload.status === 'failed'
              ? 'error'
              : 'cancelled';
        const finishedRunId = String(payload.run_id);
        updateRun(finishedRunId, { status: finalStatus, end_time: ts });
        // Once a run terminates, no node should remain in `running`. Sweep any
        // stragglers — promote them based on the run outcome. This prevents
        // the green "active" highlight from sticking on nodes after a finished
        // (completed/failed/cancelled) workflow when a `node_complete` event
        // is dropped or arrives out of order. `NodeStatus` has no `cancelled`
        // state, so cancelled runs flip their stragglers to `error`.
        const promotedStatus: 'completed' | 'error' =
          finalStatus === 'completed' ? 'completed' : 'error';
        setRuns(prev =>
          prev.map(run => {
            if (run.run_id !== finishedRunId) return run;
            const promoted = run.node_statuses.map(ns =>
              ns.status === 'running' ? { ...ns, status: promotedStatus } : ns,
            );
            return { ...run, node_statuses: promoted };
          }),
        );
        // A failed run drops out of the active queue automatically (the queue
        // view filters on pending/running) but stays in history. Surface a
        // toast so the user notices the failure without scanning the console.
        if (finalStatus === 'error') {
          const failedRun = runs.find(r => r.run_id === finishedRunId);
          const wfName = failedRun?.workflow_name || 'Workflow';
          toast.error('Run failed', {
            message: `${wfName} — see the console for details.`,
          });
        }
        // Fetch full run details to populate previews/artifacts
        apiGet<Record<string, unknown>>(`/api/runs/${finishedRunId}`)
          .then(runData => {
            if (!runData) return;
            const result = runData.result as Record<string, unknown> | undefined;
            if (!result) return;
            const previews: Record<string, string> = {};
            const previewList = result.previews as
              | Array<{ node_id?: string; path?: string }>
              | undefined;
            if (previewList) {
              for (const p of previewList) {
                if (p.node_id && p.path) previews[p.node_id] = p.path;
              }
            }
            const artifacts: Record<string, string> = {};
            const artifactList = result.artifacts as
              | Array<{ node_id?: string; path?: string }>
              | undefined;
            if (artifactList) {
              for (const a of artifactList) {
                if (a.node_id && a.path) artifacts[a.node_id] = a.path;
              }
            }
            updateRun(finishedRunId, { previews, artifacts });
          })
          .catch(() => {
            /* ignore — run details are best-effort */
          });
      } else if (data.type === 'queue_error') {
        addLog({
          run_id: String(payload.run_id),
          node_id: 'queue',
          level: 'error',
          message: `Run error: ${payload.error}`,
          timestamp: ts,
        });
        updateRun(String(payload.run_id), { status: 'error', end_time: ts });
        // queue_error fires for errors that don't go through queue_finish
        // (early validation failures, executor crashes). Always toast.
        const erroredRunId = String(payload.run_id);
        const erroredRun = runs.find(r => r.run_id === erroredRunId);
        const wfName = erroredRun?.workflow_name || 'Workflow';
        const errMsg =
          typeof payload.error === 'string' && payload.error
            ? payload.error.split('\n')[0].slice(0, 160)
            : 'see the console for details';
        toast.error('Run failed', { message: `${wfName} — ${errMsg}` });
        // Same defense as queue_finish: promote any stuck `running` nodes to
        // `error` so the canvas reflects the failure visually.
        setRuns(prev =>
          prev.map(run => {
            if (run.run_id !== erroredRunId) return run;
            const promoted = run.node_statuses.map(ns =>
              ns.status === 'running' ? { ...ns, status: 'error' as const } : ns,
            );
            return { ...run, node_statuses: promoted };
          }),
        );
      } else if (data.type === 'queue_interrupt') {
        addLog({
          run_id: String(payload.run_id),
          node_id: 'queue',
          level: 'warn',
          message: `Run interrupted`,
          timestamp: ts,
        });
        updateRun(String(payload.run_id), { status: 'cancelled', end_time: ts });
      }
    });
    return unsub;
  }, [
    onMessage,
    addLog,
    runs,
    updateRun,
    setRuns,
    updateNodeRunStatus,
    recordNodeStart,
    clearNodeRunProgress,
  ]);
}
