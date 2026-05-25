import { useState, useEffect, useCallback } from 'react';
import { getToken } from './auth';
import type { WorkflowVersion, VersionDiffResult } from './types';
import VersionDiff from './VersionDiff';
import Icon from '../components/ui/Icon';
import { confirmDialog, promptDialog } from '../components/ui';

const API_BASE = '/api/collab';

interface VersionHistoryProps {
  workflowId: string;
  isOpen: boolean;
  onClose: () => void;
  onRestore: (versionJson: unknown) => void;
}

function timeAgo(ts: string): string {
  const s = Math.floor((Date.now() - new Date(ts).getTime()) / 1000);
  if (s < 60) return 'just now';
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
  return `${Math.floor(s / 86400)}d ago`;
}

export default function VersionHistory({ workflowId, isOpen, onClose, onRestore }: VersionHistoryProps) {
  const [versions, setVersions] = useState<WorkflowVersion[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [diffData, setDiffData] = useState<{ a: WorkflowVersion; b: WorkflowVersion; diff: VersionDiffResult } | null>(null);

  const fetchVersions = useCallback(async () => {
    if (!workflowId) return;
    setLoading(true);
    try {
      const token = getToken();
      const headers: Record<string, string> = {};
      if (token) headers['Authorization'] = `Bearer ${token}`;
      const res = await fetch(`${API_BASE}/workflows/${workflowId}/versions`, { headers });
      if (!res.ok) throw new Error(`Failed to fetch versions: ${res.status}`);
      const data = await res.json() as { versions: WorkflowVersion[]; count: number };
      setVersions(data.versions ?? []);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load versions');
    } finally {
      setLoading(false);
    }
  }, [workflowId]);

  useEffect(() => {
    if (!isOpen) return;
    fetchVersions();
  }, [isOpen, fetchVersions]);

  const handleSaveVersion = async () => {
    const name = await promptDialog({
      title: 'Save version',
      message: 'Name this workflow version.',
      inputLabel: 'Version name',
      placeholder: 'Optional',
      confirmLabel: 'Save Version',
    });
    if (name === null) return;
    setSaving(true);
    try {
      const token = getToken();
      const headers: Record<string, string> = { 'Content-Type': 'application/json' };
      if (token) headers['Authorization'] = `Bearer ${token}`;
      const res = await fetch(`${API_BASE}/workflows/${workflowId}/versions`, {
        method: 'POST',
        headers,
        body: JSON.stringify({ name: name || null }),
      });
      if (!res.ok) throw new Error(`Failed to save version: ${res.status}`);
      fetchVersions();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save version');
    } finally {
      setSaving(false);
    }
  };

  const handleRestore = async (versionId: string) => {
    const ok = await confirmDialog({
      title: 'Restore version?',
      message: 'Restore this version? This will create a new branch of the current workflow.',
      confirmLabel: 'Restore',
      tone: 'warning',
    });
    if (!ok) return;
    try {
      const token = getToken();
      const headers: Record<string, string> = {};
      if (token) headers['Authorization'] = `Bearer ${token}`;
      const res = await fetch(`${API_BASE}/versions/${versionId}/restore`, {
        method: 'POST',
        headers,
      });
      if (!res.ok) throw new Error(`Failed to restore: ${res.status}`);
      const data = await res.json() as { snapshot: unknown };
      onRestore(data.snapshot);
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to restore version');
    }
  };

  const handleDelete = async (versionId: string) => {
    const ok = await confirmDialog({
      title: 'Delete version?',
      message: 'Delete this version?',
      confirmLabel: 'Delete',
      tone: 'danger',
    });
    if (!ok) return;
    try {
      const token = getToken();
      const headers: Record<string, string> = {};
      if (token) headers['Authorization'] = `Bearer ${token}`;
      const res = await fetch(`${API_BASE}/versions/${versionId}`, {
        method: 'DELETE',
        headers,
      });
      if (!res.ok) throw new Error(`Failed to delete: ${res.status}`);
      fetchVersions();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete version');
    }
  };

  const handleDiff = async (a: WorkflowVersion, b: WorkflowVersion) => {
    try {
      const token = getToken();
      const headers: Record<string, string> = {};
      if (token) headers['Authorization'] = `Bearer ${token}`;
      const res = await fetch(`${API_BASE}/versions/${a.id}/diff/${b.id}`, { headers });
      if (!res.ok) throw new Error(`Failed to fetch diff: ${res.status}`);
      const diff = await res.json() as VersionDiffResult;
      setDiffData({ a, b, diff });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load diff');
    }
  };

  if (!isOpen) return null;

  return (
    <>
      <div style={{
        position: 'fixed', top: 0, right: 0, width: 320, height: '100vh',
        background: 'var(--surface)', borderLeft: '1px solid var(--border)',
        zIndex: 50, display: 'flex', flexDirection: 'column', transition: 'transform 0.2s ease',
        boxShadow: '-4px 0 12px rgba(0,0,0,0.15)',
      }}>
        {/* Header */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '12px 14px', borderBottom: '1px solid var(--border)' }}>
          <strong style={{ fontSize: 14 }}>Version History</strong>
          <div style={{ display: 'flex', gap: 6 }}>
            <button className="btn btn-sm" onClick={handleSaveVersion} disabled={saving} style={{ fontSize: 10 }}>
              {saving ? 'Saving...' : '+ Save'}
            </button>
            <button className="btn btn-icon btn-xs" onClick={onClose} title="Close"><Icon name="close" size={12} /></button>
          </div>
        </div>

        {error && <div style={{ padding: '8px 14px', fontSize: 11, color: '#ef4444', background: '#ef444410' }}>{error}</div>}

        {/* Version list */}
        <div style={{ flex: 1, overflowY: 'auto', padding: '8px 0' }}>
          {loading && versions.length === 0 && <div style={{ padding: 20, textAlign: 'center', fontSize: 12, color: 'var(--muted)' }}>Loading versions...</div>}
          {versions.length === 0 && !loading && <div style={{ padding: 20, textAlign: 'center', fontSize: 12, color: 'var(--muted)' }}>No saved versions yet.</div>}
          {versions.map((v, idx) => (
            <div key={v.id} style={{ padding: '10px 14px', borderBottom: '1px solid var(--border)' }}>
              <div style={{ display: 'flex', alignItems: 'flex-start', gap: 8 }}>
                {/* Auto-save icon */}
                <div style={{ marginTop: 2, fontSize: 12, color: v.auto_save ? '#94a3b8' : '#3b82f6' }} title={v.auto_save ? 'Auto-saved' : 'Manual save'}>
                  <Icon name={v.auto_save ? 'clock' : 'check'} size={12} />
                </div>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 12, fontWeight: 600, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                    {v.name || (v.auto_save ? `Auto-save #${versions.length - idx}` : `Version ${versions.length - idx}`)}
                  </div>
                  <div style={{ fontSize: 10, color: 'var(--muted)', marginTop: 2 }}>
                    {v.user_name} • {timeAgo(v.created_at)} • {v.node_count} nodes, {v.edge_count} edges
                  </div>
                </div>
              </div>
              {/* Actions */}
              <div style={{ display: 'flex', gap: 4, marginTop: 6, paddingLeft: 20 }}>
                <button className="btn btn-xs" onClick={() => handleRestore(v.id)} style={{ fontSize: 9, padding: '2px 8px' }}>Restore</button>
                {idx < versions.length - 1 && (
                  <button className="btn btn-xs" onClick={() => handleDiff(versions[idx + 1], v)} style={{ fontSize: 9, padding: '2px 8px' }}>Diff</button>
                )}
                <button className="btn btn-xs" onClick={() => handleDelete(v.id)} style={{ fontSize: 9, padding: '2px 8px', color: '#ef4444' }}>Delete</button>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Diff overlay */}
      {diffData && (
        <VersionDiff
          versionA={{ id: diffData.a.id, name: diffData.a.name || 'Auto-save' }}
          versionB={{ id: diffData.b.id, name: diffData.b.name || 'Auto-save' }}
          diff={diffData.diff}
          isOpen={!!diffData}
          onClose={() => setDiffData(null)}
        />
      )}
    </>
  );
}
