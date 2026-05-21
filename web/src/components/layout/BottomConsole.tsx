import { useState, useRef, useEffect } from 'react';
import type { LogEntry, RunRecord, NodeStatus } from '../../types';
import Icon from '../ui/Icon';

type ConsoleTab = 'logs' | 'queue' | 'history' | 'previews';

interface BottomConsoleProps {
  logs: LogEntry[];
  queue: RunRecord[];
  history: RunRecord[];
  onClose: () => void;
  onOpenLightbox?: (images: { src: string; alt: string; filename: string }[], startIndex: number) => void;
  onClearLogs?: () => void;
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

export default function BottomConsole({ logs, queue, history, onClose, onOpenLightbox, onClearLogs }: BottomConsoleProps) {
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
            : queue.map(r => (
              <div key={r.run_id} className="console-log-line">
                [{r.status}] {r.workflow_name} ({r.node_statuses?.length || 0} nodes)
              </div>
            ))
        )}
        {tab === 'history' && (
          history.length === 0
            ? <div style={{ color: 'var(--muted)' }}>No completed runs yet.</div>
            : history.map(r => (
              <div key={r.run_id} className={`console-log-line ${r.status === 'error' ? 'error' : 'success'}`}>
                [{r.status}] {r.workflow_name} - {r.end_time ? new Date(r.end_time).toLocaleString() : 'in progress'}
              </div>
            ))
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
      </div>
    </div>
  );
}
