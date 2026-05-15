import { useState } from 'react';
import type { LogEntry, RunRecord } from '../../types';
import Icon from '../ui/Icon';

type ConsoleTab = 'logs' | 'queue' | 'history' | 'previews';

interface BottomConsoleProps {
  visible: boolean;
  logs: LogEntry[];
  queue: RunRecord[];
  history: RunRecord[];
  onClose: () => void;
  onOpenLightbox?: (images: { src: string; alt: string; filename: string }[], startIndex: number) => void;
}

const IMAGE_EXTS = new Set(['.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp', '.bmp']);

function isImagePath(path: string): boolean {
  const lower = path.toLowerCase();
  return Array.from(IMAGE_EXTS).some(ext => lower.endsWith(ext));
}

function LogLine({ entry }: { entry: LogEntry }) {
  const [expanded, setExpanded] = useState(false);
  const hasDetail = !!entry.detail && entry.detail.length > 0;

  return (
    <div className={`console-log-line ${entry.level}`}>
      <div className="console-log-main">
        <span className="console-log-ts">[{entry.timestamp.slice(11, 19)}]</span>
        <span className="console-log-node">[{entry.node_id}]</span>
        <span className="console-log-msg">{entry.message}</span>
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
        <pre className="console-log-detail">{entry.detail}</pre>
      )}
    </div>
  );
}

export default function BottomConsole({ visible, logs, queue, history, onClose, onOpenLightbox }: BottomConsoleProps) {
  const [tab, setTab] = useState<ConsoleTab>('logs');
  const [showVerbose, setShowVerbose] = useState(true);
  if (!visible) return null;

  // Separate host messages from verbose subprocess output
  const hostLogs = logs.filter(l => !l.message.startsWith('[solver]'));
  const solverLogs = logs.filter(l => l.message.startsWith('[solver]'));

  // Build log lines with detail accumulation: each host line gets all solver lines
  // that appeared since the previous host line, collapsed by default when job is done
  const displayLogs: LogEntry[] = hostLogs.map((hostLog, idx) => {
    const nextHostIdx = idx + 1 < hostLogs.length ? logs.indexOf(hostLogs[idx + 1]) : logs.length;
    const hostIdx = logs.indexOf(hostLog);
    const detailLines = logs
      .slice(hostIdx + 1, nextHostIdx)
      .filter(l => l.message.startsWith('[solver]'))
      .map(l => l.message.replace('[solver] ', ''));
    if (detailLines.length === 0) return hostLog;
    return { ...hostLog, detail: detailLines.join('\n') };
  });

  // Build flat list of image previews for the lightbox
  const imagePreviews: { src: string; alt: string; filename: string; runId: string; nodeId: string }[] = [];
  for (const r of history) {
    for (const [nodeId, path] of Object.entries(r.previews || {})) {
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
      <div className="console-body">
        {tab === 'logs' && (
          hostLogs.length === 0 && solverLogs.length === 0
            ? <div style={{ color: 'var(--muted)' }}>No logs yet. Run a workflow to see logs.</div>
            : (
              <>
                {displayLogs.map((l, i) => (
                  <LogLine key={i} entry={{
                    ...l,
                    detail: showVerbose ? l.detail : undefined,
                  }} />
                ))}
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
                [{r.status}] {r.workflow_name} ({r.node_statuses.length} nodes)
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
