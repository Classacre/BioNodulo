// WebSocket message dispatch for workflow runtime events.
//
// Extracted from App.tsx — the ~180-line message handler that reacts to
// install logs, execution lifecycle events, preview events, and queue events.
//
// Each handler is small and side-effectful (logs, run state, toasts, follow-up
// API fetch on queue_finish), so this stays a hook rather than a pure reducer.

import { useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { apiGet } from '../../api/client';
import { toast } from '../../state/notifications';
import type { LogEntry, RunRecord, NodeStatus } from '../../types';
import { nodeDownloadProgressAtom } from '../../state/runAtoms';
import { useSetAtom } from 'jotai';

function workflowStatusLabel(t: (key: string) => string, status: unknown): string {
  switch (status) {
    case 'completed':
      return t('console.actions.workflowStatusCompleted');
    case 'failed':
      return t('console.actions.workflowStatusFailed');
    case 'cancelled':
      return t('console.actions.workflowStatusCancelled');
    case 'error':
      return t('console.actions.workflowStatusError');
    default:
      return String(status || '');
  }
}

function reconcileRunSnapshot(
  runId: string,
  finalStatus: RunRecord['status'],
  timestamp: string,
  updateRun: (runId: string, partial: Partial<RunRecord>) => void,
): void {
  // Terminal queue events can overtake individual node events. The persisted
  // run is authoritative, including detailed node_results on servers whose
  // top-level progress snapshot is incomplete.
  apiGet<Record<string, unknown>>(`/api/runs/${runId}`)
    .then(runData => {
      if (!runData) return;
      const result = runData.result as Record<string, unknown> | undefined;
      const progress: Partial<RunRecord> = { status: finalStatus, end_time: timestamp };
      const nodeStatuses = new Map<string, NodeStatus>();
      if (Array.isArray(runData.node_statuses)) {
        for (const node of runData.node_statuses as NodeStatus[]) nodeStatuses.set(node.node_id, node);
      }
      // Older servers omitted failures and cache hits from the top-level
      // summary. Detailed results override it when both sources name a node.
      if (result?.node_results && typeof result.node_results === 'object') {
        for (const [nodeId, raw] of Object.entries(result.node_results)) {
          if (!raw || typeof raw !== 'object') continue;
          const node = raw as Record<string, unknown>;
          const status = node.status === 'failed' ? 'error' : node.status;
          if (typeof status !== 'string' || !['pending', 'running', 'cached', 'completed', 'error', 'skipped'].includes(status)) continue;
          nodeStatuses.set(nodeId, {
            ...nodeStatuses.get(nodeId), node_id: nodeId, status: status as NodeStatus['status'],
            ...(typeof node.error === 'string' ? { error: node.error } : {}),
          });
        }
      }
      if (Array.isArray(runData.node_statuses) || nodeStatuses.size > 0) progress.node_statuses = [...nodeStatuses.values()];
      if (Array.isArray(runData.execution_plan)) {
        progress.execution_plan = [...new Set([...runData.execution_plan as string[], ...nodeStatuses.keys()])];
      } else if (nodeStatuses.size > 0) {
        progress.execution_plan = [...nodeStatuses.keys()];
      }
      updateRun(runId, progress);
      if (!result) return;
      const previews: Record<string, string> = {};
      const previewList = result.previews as Array<{ node_id?: string; path?: string }> | undefined;
      if (previewList) {
        for (const preview of previewList) {
          if (preview.node_id && preview.path) previews[preview.node_id] = preview.path;
        }
      }
      const artifacts: Record<string, string> = {};
      const artifactList = result.artifacts as Array<{ node_id?: string; path?: string }> | undefined;
      if (artifactList) {
        for (const artifact of artifactList) {
          if (artifact.node_id && artifact.path) artifacts[artifact.node_id] = artifact.path;
        }
      }
      updateRun(runId, { previews, artifacts });
    })
    .catch(() => {
      /* Run details are best-effort; immediate terminal state remains valid. */
    });
}

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
  const setNodeDownloadProgress = useSetAtom(nodeDownloadProgressAtom);
  const { t } = useTranslation();

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
        const totalNodes = Number(payload.total_nodes || 0);
        addLog({
          run_id: runId,
          node_id: 'engine',
          level: 'info',
          message: t('console.actions.workflowStartedLog', {
            count: totalNodes,
            nodeWord: t(totalNodes === 1 ? 'console.nodesCount' : 'console.nodesCount_plural'),
          }),
          timestamp: ts,
        });
      } else if (data.type === 'node_download_progress') {
        // Rendered as a bar on the node itself. Cleared on completion so a
        // finished node does not keep a stale bar.
        const nodeId = String(payload.node_id);
        setNodeDownloadProgress(prev => {
          if (payload.done) {
            if (!(nodeId in prev)) return prev;
            const next = { ...prev };
            delete next[nodeId];
            return next;
          }
          return {
            ...prev,
            [nodeId]: {
              downloaded: Number(payload.downloaded_bytes) || 0,
              total: Number(payload.total_bytes) || 0,
              url: payload.url ? String(payload.url) : undefined,
            },
          };
        });
      } else if (data.type === 'node_start') {
        updateNodeRunStatus(runId, String(payload.node_id), 'running');
        recordNodeStart(String(payload.node_id), payload.progress as string | undefined);
        addLog({
          run_id: runId,
          node_id: String(payload.node_id),
          level: 'info',
          message: t('console.actions.nodeStartedLog', {
            progress: payload.progress,
            type: payload.node_type,
          }),
          timestamp: ts,
        });
      } else if (data.type === 'node_complete') {
        updateNodeRunStatus(runId, String(payload.node_id), 'completed');
        clearNodeRunProgress(String(payload.node_id));
        addLog({
          run_id: runId,
          node_id: String(payload.node_id),
          level: 'success',
          message: t('console.actions.nodeCompletedLog'),
          timestamp: ts,
        });
      } else if (data.type === 'node_error') {
        const errorMessage = String(payload.error || t('console.actions.nodeErrorFallback'));
        updateNodeRunStatus(
          runId,
          String(payload.node_id),
          'error',
          errorMessage,
        );
        clearNodeRunProgress(String(payload.node_id));
        addLog({
          run_id: runId,
          node_id: String(payload.node_id),
          level: 'error',
          message: t('console.actions.nodeErrorLog', { message: errorMessage }),
          timestamp: ts,
        });
      } else if (data.type === 'node_skip') {
        updateNodeRunStatus(runId, String(payload.node_id), 'skipped');
        clearNodeRunProgress(String(payload.node_id));
        addLog({
          run_id: runId,
          node_id: String(payload.node_id),
          level: 'warn',
          message: t('console.actions.nodeSkippedLog', { reason: payload.reason }),
          timestamp: ts,
        });
      } else if (data.type === 'node_bypass') {
        updateNodeRunStatus(runId, String(payload.node_id), 'skipped');
        clearNodeRunProgress(String(payload.node_id));
        addLog({
          run_id: runId,
          node_id: String(payload.node_id),
          level: 'warn',
          message: t('console.actions.nodeBypassedLog'),
          timestamp: ts,
        });
      } else if (data.type === 'node_cache_hit') {
        updateNodeRunStatus(runId, String(payload.node_id), 'cached');
        clearNodeRunProgress(String(payload.node_id));
        addLog({
          run_id: runId,
          node_id: String(payload.node_id),
          level: 'info',
          message: t('console.actions.nodeCacheHitLog'),
          timestamp: ts,
        });
      } else if (data.type === 'complete') {
        addLog({
          run_id: runId,
          node_id: 'engine',
          level: payload.status === 'completed' ? 'success' : 'error',
          message: t('console.actions.workflowCompletedLog', {
            status: workflowStatusLabel(t, payload.status),
          }),
          timestamp: ts,
        });
      } else if (data.type === 'error') {
        addLog({
          run_id: runId,
          node_id: 'engine',
          level: 'error',
          message: t('console.actions.workflowErrorLog', { message: payload.message }),
          timestamp: ts,
        });
      } else if (data.type === 'cancelled') {
        addLog({
          run_id: runId,
          node_id: String(payload.node_id || 'engine'),
          level: 'warn',
          message: t('console.actions.workflowCancelledLog'),
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
          message: t('console.actions.queueRunSubmittedLog'),
          timestamp: ts,
        });
      } else if (data.type === 'queue_start') {
        addLog({
          run_id: String(payload.run_id),
          node_id: 'queue',
          level: 'info',
          message: t('console.actions.queueRunStartedLog'),
          timestamp: ts,
        });
        updateRun(String(payload.run_id), { status: 'running', start_time: ts });
      } else if (data.type === 'queue_finish') {
        addLog({
          run_id: String(payload.run_id),
          node_id: 'queue',
          level: 'success',
          message: t('console.actions.queueRunFinishedLog', {
            status: workflowStatusLabel(t, payload.status),
          }),
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
          const wfName = failedRun?.workflow_name || t('console.actions.workflowFallback');
          toast.error(t('console.actions.runFailedTitle'), {
            message: t('console.actions.runFailedMessage', {
              name: wfName,
              detail: t('console.actions.consoleDetailsFallback'),
            }),
          });
        }
        reconcileRunSnapshot(finishedRunId, finalStatus, ts, updateRun);
      } else if (data.type === 'queue_error') {
        addLog({
          run_id: String(payload.run_id),
          node_id: 'queue',
          level: 'error',
          message: t('console.actions.runErrorLog', { message: payload.error }),
          timestamp: ts,
        });
        updateRun(String(payload.run_id), { status: 'error', end_time: ts });
        // queue_error fires for errors that don't go through queue_finish
        // (early validation failures, executor crashes). Always toast.
        const erroredRunId = String(payload.run_id);
        const erroredRun = runs.find(r => r.run_id === erroredRunId);
        const wfName = erroredRun?.workflow_name || t('console.actions.workflowFallback');
        const errMsg =
          typeof payload.error === 'string' && payload.error
            ? payload.error.split('\n')[0].slice(0, 160)
            : t('console.actions.consoleDetailsFallback');
        toast.error(t('console.actions.runFailedTitle'), {
          message: t('console.actions.runFailedMessage', { name: wfName, detail: errMsg }),
        });
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
        // The sweep above is only a temporary fallback. Restore completed
        // upstream nodes and the exact failed node from persisted run details.
        reconcileRunSnapshot(erroredRunId, 'error', ts, updateRun);
      } else if (data.type === 'queue_interrupt') {
        addLog({
          run_id: String(payload.run_id),
          node_id: 'queue',
          level: 'warn',
          message: t('console.actions.runInterruptedLog'),
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
    t,
  ]);
}
