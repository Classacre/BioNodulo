import { useState, useEffect, useCallback, useMemo } from 'react';
import { getToken } from './auth';
import type { AuditEntry } from './types';
import Icon from '../components/ui/Icon';

const API_BASE = '/api/collab';
const PAGE_SIZE = 50;

interface AuditLogProps {
  workflowId: string;
  isOpen: boolean;
  onClose: () => void;
}

const ACTION_COLORS: Record<string, string> = {
  node_create: '#22c55e',
  node_delete: '#ef4444',
  node_update: '#3b82f6',
  node_move: '#8b5cf6',
  edge_create: '#22c55e',
  edge_delete: '#ef4444',
  comment_create: '#f59e0b',
  comment_resolve: '#10b981',
  version_save: '#6366f1',
  version_restore: '#8b5cf6',
  share: '#ec4899',
  join: '#06b6d4',
  leave: '#94a3b8',
};

function getActionColor(action: string): string {
  return ACTION_COLORS[action] || '#94a3b8';
}

function formatDate(ts: string): string {
  const d = new Date(ts);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
}

export default function AuditLog({ workflowId, isOpen, onClose }: AuditLogProps) {
  const [entries, setEntries] = useState<AuditEntry[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [filterUser, setFilterUser] = useState('');
  const [filterAction, setFilterAction] = useState('');
  const [filterFrom, setFilterFrom] = useState('');
  const [filterTo, setFilterTo] = useState('');

  const fetchAudit = useCallback(async () => {
    if (!workflowId) return;
    setLoading(true);
    try {
      const token = getToken();
      const params = new URLSearchParams();
      if (filterUser) params.set('user_id', filterUser);
      if (filterAction) params.set('action', filterAction);
      if (filterFrom) params.set('from_date', filterFrom);
      if (filterTo) params.set('to_date', filterTo);
      const headers: Record<string, string> = {};
      if (token) headers['Authorization'] = `Bearer ${token}`;
      const res = await fetch(`${API_BASE}/workflows/${workflowId}/audit?${params.toString()}`, { headers });
      if (!res.ok) throw new Error(`Failed to fetch audit log: ${res.status}`);
      const data = await res.json() as { entries: AuditEntry[]; count: number };
      setEntries(data.entries ?? []);
      setError(null);
      setPage(1);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load audit log');
    } finally {
      setLoading(false);
    }
  }, [workflowId, filterUser, filterAction, filterFrom, filterTo]);

  useEffect(() => {
    if (!isOpen) return;
    fetchAudit();
  }, [isOpen, fetchAudit]);

  const uniqueUsers = useMemo(() => {
    const map = new Map<string, string>();
    entries.forEach(e => map.set(e.user_id, e.user_name));
    return Array.from(map.entries());
  }, [entries]);

  const uniqueActions = useMemo(() => {
    const set = new Set<string>();
    entries.forEach(e => set.add(e.action));
    return Array.from(set);
  }, [entries]);

  // Summary stats
  const stats = useMemo(() => {
    if (entries.length === 0) return null;
    const actionCounts: Record<string, number> = {};
    entries.forEach(e => { actionCounts[e.action] = (actionCounts[e.action] || 0) + 1; });
    const mostCommon = Object.entries(actionCounts).sort((a, b) => b[1] - a[1])[0];
    return { total: entries.length, uniqueUsers: uniqueUsers.length, mostCommon };
  }, [entries, uniqueUsers.length]);

  // Pagination
  const totalPages = Math.max(1, Math.ceil(entries.length / PAGE_SIZE));
  const paginated = entries.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);

  const handleExportCsv = async () => {
    try {
      const token = getToken();
      const params = new URLSearchParams();
      if (filterUser) params.set('user_id', filterUser);
      if (filterAction) params.set('action', filterAction);
      if (filterFrom) params.set('from_date', filterFrom);
      if (filterTo) params.set('to_date', filterTo);
      const headers: Record<string, string> = {};
      if (token) headers['Authorization'] = `Bearer ${token}`;
      const res = await fetch(`${API_BASE}/workflows/${workflowId}/audit/export?${params.toString()}`, { headers });
      if (!res.ok) throw new Error(`Export failed: ${res.status}`);
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `audit-${workflowId}.csv`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Export failed');
    }
  };

  if (!isOpen) return null;

  return (
    <div style={{
      position: 'fixed', top: 0, right: 0, width: 320, height: '100vh',
      background: 'var(--surface)', borderLeft: '1px solid var(--border)',
      zIndex: 50, display: 'flex', flexDirection: 'column', transition: 'transform 0.2s ease',
      boxShadow: '-4px 0 12px rgba(0,0,0,0.15)',
    }}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '12px 14px', borderBottom: '1px solid var(--border)' }}>
        <strong style={{ fontSize: 14 }}>Audit Log</strong>
        <div style={{ display: 'flex', gap: 6 }}>
          <button className="btn btn-xs" onClick={handleExportCsv} style={{ fontSize: 10 }}>Export CSV</button>
          <button className="btn btn-icon btn-xs" onClick={onClose} title="Close"><Icon name="close" size={12} /></button>
        </div>
      </div>

      {/* Summary stats */}
      {stats && (
        <div style={{ display: 'flex', gap: 8, padding: '8px 14px', borderBottom: '1px solid var(--border)', fontSize: 10, color: 'var(--muted)' }}>
          <span>{stats.total} actions</span>
          <span>•</span>
          <span>{stats.uniqueUsers} users</span>
          <span>•</span>
          <span>Top: {stats.mostCommon?.[0]} ({stats.mostCommon?.[1]})</span>
        </div>
      )}

      {/* Filters */}
      <div style={{ padding: '8px 14px', borderBottom: '1px solid var(--border)', display: 'flex', flexDirection: 'column', gap: 6 }}>
        <select value={filterUser} onChange={e => setFilterUser(e.target.value)} style={{ fontSize: 11, padding: '4px 6px', borderRadius: 4, border: '1px solid var(--border)', background: 'var(--surface-2)', color: 'var(--text)' }}>
          <option value="">All users</option>
          {uniqueUsers.map(([id, name]) => <option key={id} value={id}>{name}</option>)}
        </select>
        <select value={filterAction} onChange={e => setFilterAction(e.target.value)} style={{ fontSize: 11, padding: '4px 6px', borderRadius: 4, border: '1px solid var(--border)', background: 'var(--surface-2)', color: 'var(--text)' }}>
          <option value="">All actions</option>
          {uniqueActions.map(a => <option key={a} value={a}>{a}</option>)}
        </select>
        <div style={{ display: 'flex', gap: 4 }}>
          <input type="date" value={filterFrom} onChange={e => setFilterFrom(e.target.value)} style={{ flex: 1, fontSize: 10, padding: '3px', borderRadius: 4, border: '1px solid var(--border)', background: 'var(--surface-2)', color: 'var(--text)' }} />
          <input type="date" value={filterTo} onChange={e => setFilterTo(e.target.value)} style={{ flex: 1, fontSize: 10, padding: '3px', borderRadius: 4, border: '1px solid var(--border)', background: 'var(--surface-2)', color: 'var(--text)' }} />
        </div>
        <button className="btn btn-xs" onClick={fetchAudit} style={{ fontSize: 10 }}>Apply Filters</button>
      </div>

      {error && <div style={{ padding: '8px 14px', fontSize: 11, color: '#ef4444', background: '#ef444410' }}>{error}</div>}

      {/* Table */}
      <div style={{ flex: 1, overflowY: 'auto' }}>
        {loading && entries.length === 0 && <div style={{ padding: 20, textAlign: 'center', fontSize: 12, color: 'var(--muted)' }}>Loading audit log...</div>}
        {entries.length === 0 && !loading && <div style={{ padding: 20, textAlign: 'center', fontSize: 12, color: 'var(--muted)' }}>No audit entries found.</div>}
        {/* Table header */}
        {entries.length > 0 && (
          <div style={{ display: 'flex', padding: '6px 14px', fontSize: 10, fontWeight: 600, color: 'var(--muted)', borderBottom: '1px solid var(--border)', background: 'var(--surface-2)', position: 'sticky', top: 0 }}>
            <span style={{ width: 110, flexShrink: 0 }}>Time</span>
            <span style={{ width: 70, flexShrink: 0 }}>User</span>
            <span style={{ width: 90, flexShrink: 0 }}>Action</span>
            <span style={{ flex: 1 }}>Target</span>
          </div>
        )}
        {paginated.map(entry => (
          <div key={entry.id} style={{ display: 'flex', padding: '6px 14px', fontSize: 10, borderBottom: '1px solid var(--border)', alignItems: 'center' }}>
            <span style={{ width: 110, flexShrink: 0, color: 'var(--muted)' }}>{formatDate(entry.performed_at)}</span>
            <span style={{ width: 70, flexShrink: 0, fontWeight: 600, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{entry.user_name}</span>
            <span style={{
              width: 90, flexShrink: 0, fontWeight: 600,
              color: getActionColor(entry.action), background: `${getActionColor(entry.action)}15`,
              padding: '1px 6px', borderRadius: 4, fontSize: 9, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
            }}>
              {entry.action}
            </span>
            <span style={{ flex: 1, paddingLeft: 8, color: 'var(--text)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
              {entry.target_type}:{entry.target_id.slice(0, 12)}
            </span>
          </div>
        ))}
      </div>

      {/* Pagination */}
      {entries.length > PAGE_SIZE && (
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '8px 14px', borderTop: '1px solid var(--border)', fontSize: 11 }}>
          <button className="btn btn-xs" onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page <= 1} style={{ fontSize: 10 }}>← Prev</button>
          <span style={{ color: 'var(--muted)' }}>{page} / {totalPages}</span>
          <button className="btn btn-xs" onClick={() => setPage(p => Math.min(totalPages, p + 1))} disabled={page >= totalPages} style={{ fontSize: 10 }}>Next →</button>
        </div>
      )}
    </div>
  );
}
