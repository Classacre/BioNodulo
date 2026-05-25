import { useState, useRef, useEffect } from 'react';
import type { LogEntry, RunRecord, NodeStatus } from '../../types';
import Icon from '../ui/Icon';

type ConsoleTab = 'logs' | 'queue' | 'history' | 'previews' | 'report';
export type QueueMoveDirection = 'up' | 'down';

interface BottomConsoleProps {
  logs: LogEntry[];
  queue: RunRecord[];
  history: RunRecord[];
  onClose: () => void;
  onOpenLightbox?: (images: { src: string; alt: string; filename: string }[], startIndex: number) => void;
  onClearLogs?: () => void;
  onCancelRun?: (run: RunRecord) => void;
  onRetryRun?: (run: RunRecord) => void;
  onMoveRun?: (run: RunRecord, direction: QueueMoveDirection) => void;
  onClearQueue?: () => void;
  batchCount?: number;
}

const IMAGE_EXTS = new Set(['.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp', '.bmp']);

function isImagePath(path: string): boolean {
  const lower = path.toLowerCase();
  return Array.from(IMAGE_EXTS).some(ext => lower.endsWith(ext));
}

function LogLine({ entry }: { entry: LogEntry }) {
  const [expanded, setExpanded] = useState(false);
  const level = entry.level || 'info';
  const timestamp = typeof entry.timestamp === 'string' ? entry.timestamp : '';
  const nodeId = typeof entry.node_id === 'string' ? entry.node_id : 'unknown';
  const message = typeof entry.message === 'string' ? entry.message : '';
  const detail = typeof entry.detail === 'string' ? entry.detail : '';
  const hasDetail = detail.length > 0;

  return (
    <div className={`console-log-line ${level}`}>
      <div className="console-log-main">
        <span className="console-log-ts">[{timestamp ? timestamp.slice(11, 19) : '--:--:--'}]</span>
        <span className="console-log-node">[{nodeId}]</span>
        <span className="console-log-msg">{message}</span>
        {hasDetail && (
          <button
            className="console-log-toggle"
            onClick={() => setExpanded(v => !v)}
            title={expanded ? 'Hide details' : 'Show details'}
          >
            <Icon name={expanded ? 'chevronUp' : 'chevronDown'} size={10} />
          </button>
        )}
      </div>
      {expanded && hasDetail && (
        <pre className="console-log-detail">{detail}</pre>
      )}
    </div>
  );
}

function groupLogsByRun(logs: LogEntry[]): Map<string, LogEntry[]> {
  const groups = new Map<string, LogEntry[]>();
  for (const log of logs) {
    const runId = log.run_id || 'unknown';
    const existing = groups.get(runId);
    if (existing) {
      existing.push(log);
    } else {
      groups.set(runId, [log]);
    }
  }
  return groups;
}

const COMPLETE_NODE_STATUSES = new Set<NodeStatus['status']>(['completed', 'cached', 'skipped']);

interface RunProgress {
  total: number;
  completed: number;
  running: number;
  pending: number;
  failed: number;
  percent: number;
}

function progressForRun(run: RunRecord): RunProgress {
  const statuses = Array.isArray(run.node_statuses) ? run.node_statuses : [];
  const total = Math.max(run.execution_plan?.length || 0, statuses.length);
  const completed = statuses.filter(node => COMPLETE_NODE_STATUSES.has(node.status)).length;
  const running = statuses.filter(node => node.status === 'running').length;
  const failed = statuses.filter(node => node.status === 'error').length;
  const pending = Math.max(0, total - completed - running - failed);

  let percent = total > 0 ? Math.round(((completed + running * 0.5) / total) * 100) : 0;
  if (run.status === 'completed') percent = 100;
  if (run.status === 'running' && total === 0) percent = 8;
  if (run.status === 'error' && total === 0) percent = 100;
  if (run.status === 'cancelled') percent = Math.max(percent, 5);

  return { total, completed, running, pending, failed, percent: Math.min(100, Math.max(0, percent)) };
}

function shortRunId(runId: string): string {
  return runId.length > 12 ? `${runId.slice(0, 8)}...${runId.slice(-4)}` : runId;
}

function RunProgressBar({ progress, status }: { progress: RunProgress; status: RunRecord['status'] }) {
  return (
    <div className={`queue-progress is-${status}`} title={`${progress.percent}% complete`}>
      <div className="queue-progress-fill" style={{ width: `${progress.percent}%` }} />
    </div>
  );
}

function RunActionButton({
  title,
  icon,
  onClick,
  disabled = false,
}: {
  title: string;
  icon: string;
  onClick: () => void;
  disabled?: boolean;
}) {
  return (
    <button
      className="btn btn-icon btn-sm queue-action-btn"
      type="button"
      title={title}
      onClick={onClick}
      disabled={disabled}
    >
      <Icon name={icon} size={12} />
    </button>
  );
}

function QueueRunCard({
  run,
  index,
  totalRuns,
  onCancelRun,
  onRetryRun,
  onMoveRun,
}: {
  run: RunRecord;
  index: number;
  totalRuns: number;
  onCancelRun?: (run: RunRecord) => void;
  onRetryRun?: (run: RunRecord) => void;
  onMoveRun?: (run: RunRecord, direction: QueueMoveDirection) => void;
}) {
  const progress = progressForRun(run);
  const canCancel = run.status === 'pending' || run.status === 'running';
  const canRetry = run.status === 'error' || run.status === 'cancelled';
  const canMove = run.status === 'pending';

  return (
    <div className={`queue-run-card is-${run.status}`}>
      <div className="queue-run-main">
        <div className="queue-run-title-row">
          <span className={`queue-status-pill is-${run.status}`}>{run.status}</span>
          <strong className="queue-run-name">{run.workflow_name || 'Untitled workflow'}</strong>
          <span className="queue-run-id" title={run.run_id}>{shortRunId(run.run_id)}</span>
        </div>
        <RunProgressBar progress={progress} status={run.status} />
        <div className="queue-run-meta">
          <span>{progress.total > 0 ? `${progress.completed}/${progress.total} nodes` : 'No node plan'}</span>
          {progress.running > 0 && <span>{progress.running} running</span>}
          {progress.pending > 0 && <span>{progress.pending} pending</span>}
          {progress.failed > 0 && <span className="queue-run-error">{progress.failed} failed</span>}
        </div>
      </div>
      <div className="queue-run-actions">
        {onMoveRun && (
          <>
            <RunActionButton title="Move earlier" icon="chevronUp" onClick={() => onMoveRun(run, 'up')} disabled={!canMove || index === 0} />
            <RunActionButton title="Move later" icon="chevronDown" onClick={() => onMoveRun(run, 'down')} disabled={!canMove || index === totalRuns - 1} />
          </>
        )}
        {onRetryRun && canRetry && (
          <RunActionButton title="Retry run" icon="play" onClick={() => onRetryRun(run)} />
        )}
        {onCancelRun && canCancel && (
          <RunActionButton title="Cancel run" icon="stop" onClick={() => onCancelRun(run)} />
        )}
      </div>
    </div>
  );
}

function HistoryRunCard({ run, onRetryRun }: { run: RunRecord; onRetryRun?: (run: RunRecord) => void }) {
  const progress = progressForRun(run);
  const canRetry = run.status === 'error' || run.status === 'cancelled' || run.status === 'completed';
  return (
    <div className={`queue-run-card history-run-card is-${run.status}`}>
      <div className="queue-run-main">
        <div className="queue-run-title-row">
          <span className={`queue-status-pill is-${run.status}`}>{run.status}</span>
          <strong className="queue-run-name">{run.workflow_name || 'Untitled workflow'}</strong>
          <span className="queue-run-id" title={run.run_id}>{shortRunId(run.run_id)}</span>
        </div>
        <RunProgressBar progress={progress} status={run.status} />
        <div className="queue-run-meta">
          <span>{run.end_time ? new Date(run.end_time).toLocaleString() : 'in progress'}</span>
          <span>{progress.total > 0 ? `${progress.completed}/${progress.total} nodes` : 'No node plan'}</span>
        </div>
      </div>
      {onRetryRun && canRetry && (
        <div className="queue-run-actions">
          <RunActionButton title="Retry run" icon="play" onClick={() => onRetryRun(run)} />
        </div>
      )}
    </div>
  );
}

function ReportPanel({ history }: { history: RunRecord[] }) {
  const completed = history.filter(r => r.status === 'completed' || r.status === 'error' || r.status === 'cancelled');
  const [selectedRunId, setSelectedRunId] = useState<string | null>(completed[0]?.run_id ?? null);
  const [reportHtml, setReportHtml] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (selectedRunId === null && completed.length > 0) {
      setSelectedRunId(completed[0].run_id);
    }
  }, [completed, selectedRunId]);

  useEffect(() => {
    if (!selectedRunId) {
      setReportHtml(null);
      return;
    }
    let cancelled = false;
    setLoading(true);
    setError(null);
    fetch(`/api/runs/${encodeURIComponent(selectedRunId)}/report`)
      .then(async response => {
        if (!response.ok) throw new Error(`Report unavailable (HTTP ${response.status})`);
        const text = await response.text();
        if (!cancelled) setReportHtml(text);
      })
      .catch(err => {
        if (!cancelled) setError(err instanceof Error ? err.message : String(err));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => { cancelled = true; };
  }, [selectedRunId]);

  const downloadManifest = () => {
    if (!selectedRunId) return;
    const url = `/api/runs/${encodeURIComponent(selectedRunId)}/manifest`;
    const link = document.createElement('a');
    link.href = url;
    link.download = `bionodulo-manifest-${selectedRunId}.json`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  if (completed.length === 0) {
    return (
      <div style={{ color: 'var(--muted)', padding: 12 }}>
        Provenance reports become available once a run completes or fails.
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8, height: '100%' }}>
      <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
        <label style={{ fontSize: 11, color: 'var(--muted)' }}>Run:</label>
        <select
          value={selectedRunId ?? ''}
          onChange={event => setSelectedRunId(event.target.value || null)}
          style={{
            minWidth: 240,
            padding: '4px 8px',
            border: '1px solid var(--border)',
            borderRadius: 6,
            background: 'var(--surface-2)',
            color: 'var(--text)',
            fontSize: 12,
          }}
        >
          {completed.map(run => (
            <option key={run.run_id} value={run.run_id}>
              {run.workflow_name || run.run_id} - {run.status}
            </option>
          ))}
        </select>
        <button
          className="btn btn-sm"
          onClick={downloadManifest}
          disabled={!selectedRunId}
          title="Download JSON provenance manifest"
        >
          <Icon name="export" size={12} /> Manifest (JSON)
        </button>
        {selectedRunId && (
          <a
            className="btn btn-sm"
            href={`/api/runs/${encodeURIComponent(selectedRunId)}/report`}
            target="_blank"
            rel="noreferrer"
            title="Open report in a new tab"
          >
            <Icon name="link" size={12} /> Open report
          </a>
        )}
      </div>
      <div style={{ flex: 1, border: '1px solid var(--border)', borderRadius: 6, overflow: 'hidden', minHeight: 200 }}>
        {loading && (
          <div style={{ padding: 12, color: 'var(--muted)' }}>Loading provenance report...</div>
        )}
        {error && !loading && (
          <div style={{ padding: 12, color: 'var(--danger, #dc3545)' }}>{error}</div>
        )}
        {!loading && !error && reportHtml && (
          <iframe
            title="Run report"
            srcDoc={reportHtml}
            sandbox=""
            style={{ width: '100%', height: '100%', minHeight: 200, border: 'none', background: 'white' }}
          />
        )}
      </div>
    </div>
  );
}

export default function BottomConsole({
  logs,
  queue,
  history,
  onClose,
  onOpenLightbox,
  onClearLogs,
  onCancelRun,
  onRetryRun,
  onMoveRun,
  onClearQueue,
  batchCount,
}: BottomConsoleProps) {
  const [tab, setTab] = useState<ConsoleTab>('logs');
  const [showVerbose, setShowVerbose] = useState(true);
  const [expandedRuns, setExpandedRuns] = useState<Set<string>>(new Set());
  const [expandedNodes, setExpandedNodes] = useState<Set<string>>(new Set());
  const logsBodyRef = useRef<HTMLDivElement>(null);
  const userScrolledUpRef = useRef(false);


  // Defensive: ensure logs is an array of valid objects
  const safeLogs = Array.isArray(logs) ? logs.filter((l): l is LogEntry => l != null && typeof l === 'object') : [];

  // Separate host messages from verbose subprocess output
  const hostLogs: LogEntry[] = [];
  const solverLogs: LogEntry[] = [];
  for (const log of safeLogs) {
    const msg = log.message || '';
    if (msg.startsWith('[solver]')) solverLogs.push(log);
    else hostLogs.push(log);
  }

  // Build display logs: each host log accumulates trailing solver lines
  const displayLogs: LogEntry[] = [];
  let pendingDetails: string[] = [];
  for (const log of safeLogs) {
    const msg = log.message || '';
    if (msg.startsWith('[solver]')) {
      pendingDetails.push(msg.replace('[solver] ', ''));
      continue;
    }
    if (pendingDetails.length > 0 && displayLogs.length > 0) {
      const last = displayLogs[displayLogs.length - 1];
      displayLogs[displayLogs.length - 1] = { ...last, detail: pendingDetails.join('\n') };
      pendingDetails = [];
    }
    displayLogs.push(log);
  }
  if (pendingDetails.length > 0 && displayLogs.length > 0) {
    const last = displayLogs[displayLogs.length - 1];
    displayLogs[displayLogs.length - 1] = { ...last, detail: pendingDetails.join('\n') };
  }

  const groupedLogs = groupLogsByRun(displayLogs);
  const groupedEntries = Array.from(groupedLogs.entries());
  const hasPixiInstallLogs = groupedLogs.has('install-pixi');

  const toggleRun = (runId: string) => {
    setExpandedRuns(prev => {
      const next = new Set(prev);
      if (next.has(runId)) next.delete(runId);
      else next.add(runId);
      return next;
    });
  };

  const toggleNode = (runId: string, nodeId: string) => {
    const key = `${runId}:${nodeId}`;
    setExpandedNodes(prev => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  };

  // Auto-expand live nodes without overriding a group the user opened.
  useEffect(() => {
    const nextExpanded = new Set<string>();
    const allRuns = new Map<string, RunRecord>();
    for (const r of queue) allRuns.set(r.run_id, r);
    for (const r of history) allRuns.set(r.run_id, r);

    for (const [runId, runLogs] of groupedEntries) {
      const run = allRuns.get(runId);
      const statusMap = new Map<string, NodeStatus['status']>();
      if (run?.node_statuses) {
        for (const ns of run.node_statuses) statusMap.set(ns.node_id, ns.status);
      }
      const nodeIds = new Set(runLogs.map(l => l.node_id || 'unknown'));
      for (const nodeId of nodeIds) {
        const key = `${runId}:${nodeId}`;
        const status = statusMap.get(nodeId);
        if (status === 'running' || status === 'pending') {
          nextExpanded.add(key);
        } else if (status) {
          // completed, error, cached, skipped → collapsed (don't add)
        } else {
          // No status known: infer from log levels
          const nodeLogLevels = runLogs.filter(l => (l.node_id || 'unknown') === nodeId).map(l => l.level);
          const hasCompletion = nodeLogLevels.some(l => l === 'success' || l === 'error');
          if (!hasCompletion) nextExpanded.add(key);
        }
      }
    }
    setExpandedNodes(prev => {
      const next = new Set(prev);
      nextExpanded.forEach(key => next.add(key));
      if (prev.size === next.size && [...prev].every(k => next.has(k))) return prev;
      return next;
    });
  }, [groupedEntries, queue, history]);

  // Pixi installation is triggered from a banner. Keep its live logs visible
  // so the error output does not hide behind a collapsed run while it streams.
  useEffect(() => {
    if (!hasPixiInstallLogs) return;
    setExpandedRuns(prev => {
      if (prev.has('install-pixi')) return prev;
      const next = new Set(prev);
      next.add('install-pixi');
      return next;
    });
    setExpandedNodes(prev => {
      if (prev.has('install-pixi:host')) return prev;
      const next = new Set(prev);
      next.add('install-pixi:host');
      return next;
    });
  }, [hasPixiInstallLogs]);

  // Auto-scroll when logs change (only if user is near bottom)
  useEffect(() => {
    const container = logsBodyRef.current;
    if (!container) return;
    if (!userScrolledUpRef.current) {
      container.scrollTop = container.scrollHeight;
    }
  }, [safeLogs.length]);

  // Auto-scroll to bottom when logs tab becomes active
  useEffect(() => {
    const container = logsBodyRef.current;
    if (!container) return;
    if (tab === 'logs') {
      container.scrollTop = container.scrollHeight;
      userScrolledUpRef.current = false;
    }
  }, [tab]);

  const handleScroll = () => {
    const container = logsBodyRef.current;
    if (!container) return;
    const threshold = 50;
    const isNearBottom = container.scrollHeight - container.scrollTop - container.clientHeight < threshold;
    userScrolledUpRef.current = !isNearBottom;
  };

  // Build flat list of image previews for the lightbox
  const imagePreviews: { src: string; alt: string; filename: string; runId: string; nodeId: string }[] = [];
  for (const r of history) {
    const previews = r.previews || {};
    for (const [nodeId, path] of Object.entries(previews)) {
      if (isImagePath(path)) {
        const filename = path.split('/').pop() || `${nodeId}.png`;
        imagePreviews.push({
          src: `/api/previews/${r.run_id}/${nodeId}?path=${encodeURIComponent(path)}`,
          alt: `Preview ${nodeId}`,
          filename,
          runId: r.run_id,
          nodeId,
        });
      }
    }
  }

  const handleDoubleClick = (idx: number) => {
    if (onOpenLightbox) {
      onOpenLightbox(
        imagePreviews.map(img => ({ src: img.src, alt: img.alt, filename: img.filename })),
        idx
      );
    }
  };

  const allRunIds = groupedEntries.map(([runId]) => runId);
  const queueStats = queue.reduce((stats, run) => {
    stats.totalNodes += Math.max(run.execution_plan?.length || 0, run.node_statuses?.length || 0);
    if (run.status === 'running') stats.running += 1;
    else if (run.status === 'pending') stats.pending += 1;
    else if (run.status === 'error') stats.failed += 1;
    return stats;
  }, { running: 0, pending: 0, failed: 0, totalNodes: 0 });
  const visibleBatchCount = batchCount ?? queue.length;

  return (
    <div className="bottom-console">
      <div className="console-tabs">
        <button className={`console-tab ${tab === 'logs' ? 'active' : ''}`} onClick={() => setTab('logs')}>
          Logs {hostLogs.length > 0 && `(${hostLogs.length})`}
        </button>
        <button className={`console-tab ${tab === 'queue' ? 'active' : ''}`} onClick={() => setTab('queue')}>
          Queue ({queue.length})
        </button>
        <button className={`console-tab ${tab === 'history' ? 'active' : ''}`} onClick={() => setTab('history')}>
          History ({history.length})
        </button>
        <button className={`console-tab ${tab === 'previews' ? 'active' : ''}`} onClick={() => setTab('previews')}>
          Previews {imagePreviews.length > 0 && `(${imagePreviews.length})`}
        </button>
        <button className={`console-tab ${tab === 'report' ? 'active' : ''}`} onClick={() => setTab('report')}>
          Report
        </button>
        <div style={{ flex: 1 }} />
        {tab === 'logs' && allRunIds.length > 0 && (
          <>
            <button
              className="btn btn-sm btn-ghost"
              onClick={() => setExpandedRuns(new Set(allRunIds))}
              title="Expand all log groups"
            >
              Expand All
            </button>
            <button
              className="btn btn-sm btn-ghost"
              onClick={() => setExpandedRuns(new Set())}
              title="Collapse all log groups"
            >
              Collapse All
            </button>
          </>
        )}
        {tab === 'logs' && safeLogs.length > 0 && onClearLogs && (
          <button className="btn btn-sm btn-ghost" onClick={onClearLogs} title="Clear all logs">
            Clear
          </button>
        )}
        {tab === 'queue' && queue.length > 0 && onClearQueue && (
          <button className="btn btn-sm btn-ghost" onClick={onClearQueue} title="Clear queued runs">
            Clear Queue
          </button>
        )}
        {tab === 'logs' && solverLogs.length > 0 && (
          <button
            className="btn btn-sm btn-ghost"
            onClick={() => setShowVerbose(v => !v)}
            title={showVerbose ? 'Hide solver details' : 'Show solver details'}
          >
            {showVerbose ? 'Hide verbose' : 'Show verbose'}
          </button>
        )}
        <button className="btn btn-icon btn-sm" onClick={onClose} title="Close console">
          <Icon name="close" size={14} />
        </button>
      </div>
      <div className="console-body" ref={logsBodyRef} onScroll={handleScroll}>
        {tab === 'logs' && (
          hostLogs.length === 0 && solverLogs.length === 0
            ? <div style={{ color: 'var(--muted)' }}>No logs yet. Run a workflow to see logs.</div>
            : (
              <>
                {groupedEntries.map(([runId, runLogs]) => {
                  const isExpanded = expandedRuns.has(runId);
                  // Group run logs by node_id
                  const nodeGroups = new Map<string, LogEntry[]>();
                  for (const l of runLogs) {
                    const nid = l.node_id || 'unknown';
                    const existing = nodeGroups.get(nid);
                    if (existing) existing.push(l);
                    else nodeGroups.set(nid, [l]);
                  }
                  return (
                    <div key={runId} className="console-log-group">
                      <button
                        className="console-log-group-header"
                        onClick={() => toggleRun(runId)}
                        title={isExpanded ? 'Collapse' : 'Expand'}
                      >
                        <Icon name={isExpanded ? 'chevronDown' : 'chevronRight'} size={12} />
                        <span className="console-log-group-title">{runId}</span>
                        <span className="console-log-group-count">({runLogs.length} lines, {nodeGroups.size} nodes)</span>
                      </button>
                      {isExpanded && (
                        <div className="console-log-group-body">
                          {Array.from(nodeGroups.entries()).map(([nodeId, nodeLogs]) => {
                            const nodeKey = `${runId}:${nodeId}`;
                            const isNodeExpanded = expandedNodes.has(nodeKey);
                            return (
                              <div key={nodeId} className="console-log-node-group">
                                <button
                                  className="console-log-node-header"
                                  onClick={() => toggleNode(runId, nodeId)}
                                  title={isNodeExpanded ? 'Collapse node' : 'Expand node'}
                                >
                                  <Icon name={isNodeExpanded ? 'chevronDown' : 'chevronRight'} size={10} />
                                  <span className="console-log-node-title">{nodeId}</span>
                                  <span className="console-log-node-count">({nodeLogs.length})</span>
                                </button>
                                {isNodeExpanded && (
                                  <div className="console-log-node-body">
                                    {nodeLogs.map((l, i) => (
                                      <LogLine key={i} entry={{
                                        ...l,
                                        detail: showVerbose ? l.detail : undefined,
                                      }} />
                                    ))}
                                  </div>
                                )}
                              </div>
                            );
                          })}
                        </div>
                      )}
                    </div>
                  );
                })}
                {!showVerbose && solverLogs.length > 0 && (
                  <div style={{ color: 'var(--muted)', fontSize: 11, padding: '4px 0' }}>
                    {solverLogs.length} solver line(s) hidden — click "Show verbose" to reveal
                  </div>
                )}
              </>
            )
        )}
        {tab === 'queue' && (
          queue.length === 0
            ? <div style={{ color: 'var(--muted)' }}>Queue is empty.</div>
            : (
              <div className="queue-panel">
                <div className="queue-summary">
                  <span className="queue-summary-item"><strong>{visibleBatchCount}</strong> batch</span>
                  <span className="queue-summary-item"><strong>{queueStats.running}</strong> running</span>
                  <span className="queue-summary-item"><strong>{queueStats.pending}</strong> pending</span>
                  <span className="queue-summary-item"><strong>{queueStats.totalNodes}</strong> nodes</span>
                  {queueStats.failed > 0 && <span className="queue-summary-item is-error"><strong>{queueStats.failed}</strong> failed</span>}
                </div>
                <div className="queue-run-list">
                  {queue.map((r, index) => (
                    <QueueRunCard
                      key={r.run_id}
                      run={r}
                      index={index}
                      totalRuns={queue.length}
                      onCancelRun={onCancelRun}
                      onRetryRun={onRetryRun}
                      onMoveRun={onMoveRun}
                    />
                  ))}
                </div>
              </div>
            )
        )}
        {tab === 'history' && (
          history.length === 0
            ? <div style={{ color: 'var(--muted)' }}>No completed runs yet.</div>
            : (
              <div className="queue-run-list history-run-list">
                {history.map(r => (
                  <HistoryRunCard key={r.run_id} run={r} onRetryRun={onRetryRun} />
                ))}
              </div>
            )
        )}
        {tab === 'previews' && (
          <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', overflowY: 'auto' }}>
            {imagePreviews.length === 0 ? (
              <div style={{ color: 'var(--muted)' }}>No image previews yet. Run a workflow that generates plots.</div>
            ) : (
              imagePreviews.map((img, idx) => (
                <div
                  key={`${img.runId}-${img.nodeId}`}
                  style={{ textAlign: 'center', cursor: 'pointer' }}
                  onDoubleClick={() => handleDoubleClick(idx)}
                  title="Double-click to view fullscreen"
                >
                  <img
                    src={img.src}
                    alt={img.alt}
                    style={{ maxHeight: 180, maxWidth: 280, borderRadius: 6, border: '1px solid var(--border)' }}
                    onError={e => { (e.target as HTMLImageElement).style.display = 'none'; }}
                  />
                  <div style={{ fontSize: 10, color: 'var(--muted)', marginTop: 4 }}>{img.nodeId}</div>
                </div>
              ))
            )}
          </div>
        )}
        {tab === 'report' && (
          <ReportPanel history={history} />
        )}
      </div>
    </div>
  );
}
