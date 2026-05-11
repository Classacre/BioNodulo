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
}

export default function BottomConsole({ visible, logs, queue, history, onClose }: BottomConsoleProps) {
  const [tab, setTab] = useState<ConsoleTab>('logs');
  if (!visible) return null;

  return (
    <div className="bottom-console">
      <div className="console-tabs">
        <button className={`console-tab ${tab === 'logs' ? 'active' : ''}`} onClick={() => setTab('logs')}>
          Logs {logs.length > 0 && `(${logs.length})`}
        </button>
        <button className={`console-tab ${tab === 'queue' ? 'active' : ''}`} onClick={() => setTab('queue')}>
          Queue ({queue.length})
        </button>
        <button className={`console-tab ${tab === 'history' ? 'active' : ''}`} onClick={() => setTab('history')}>
          History ({history.length})
        </button>
        <button className={`console-tab ${tab === 'previews' ? 'active' : ''}`} onClick={() => setTab('previews')}>
          Previews
        </button>
        <div style={{ flex: 1 }} />
        <button className="btn btn-icon btn-sm" onClick={onClose} title="Close console">
          <Icon name="close" size={14} />
        </button>
      </div>
      <div className="console-body">
        {tab === 'logs' && (
          logs.length === 0
            ? <div style={{ color: 'var(--muted)' }}>No logs yet. Run a workflow to see logs.</div>
            : logs.map((l, i) => (
              <div key={i} className={`console-log-line ${l.level}`}>
                [{l.timestamp.slice(11, 19)}] [{l.node_id}] {l.message}
              </div>
            ))
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
            {history.length === 0 ? (
              <div style={{ color: 'var(--muted)' }}>No completed runs yet.</div>
            ) : (
              history.flatMap(r =>
                Object.entries(r.previews || {}).map(([nodeId, path]) => (
                  <div key={`${r.run_id}-${nodeId}`} style={{ textAlign: 'center' }}>
                    <img
                      src={`/api/previews/${r.run_id}/${nodeId}?path=${encodeURIComponent(path)}`}
                      alt={`Preview ${nodeId}`}
                      style={{ maxHeight: 180, maxWidth: 280, borderRadius: 6, border: '1px solid var(--border)' }}
                      onError={e => { (e.target as HTMLImageElement).style.display = 'none'; }}
                    />
                    <div style={{ fontSize: 10, color: 'var(--muted)', marginTop: 4 }}>{nodeId}</div>
                  </div>
                ))
              )
            )}
          </div>
        )}
      </div>
    </div>
  );
}
