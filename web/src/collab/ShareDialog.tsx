import React, { useState, useEffect, useCallback } from 'react';
import { getToken } from './auth';

interface ShareDialogProps {
  workflowId: string | null;
  isOpen: boolean;
  onClose: () => void;
}

interface ShareEntry {
  id: string;
  user_id: string;
  role: 'editor' | 'viewer';
  name?: string;
}

const ShareDialog: React.FC<ShareDialogProps> = ({ workflowId, isOpen, onClose }) => {
  const [userId, setUserId] = useState('');
  const [role, setRole] = useState<'editor' | 'viewer'>('editor');
  const [shares, setShares] = useState<ShareEntry[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!isOpen || !workflowId) return;
    setLoading(true);
    const token = getToken();
    fetch(`/api/collab/shares/${workflowId}`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    })
      .then(r => r.ok ? r.json() : null)
      .then(data => {
        if (data && Array.isArray(data.shares)) {
          setShares(data.shares as ShareEntry[]);
        } else {
          setShares([]);
        }
      })
      .catch(() => setShares([]))
      .finally(() => setLoading(false));
  }, [isOpen, workflowId]);

  const handleShare = useCallback(async () => {
    if (!workflowId || !userId.trim()) return;
    const token = getToken();
    const r = await fetch('/api/collab/share', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify({ workflow_id: workflowId, user_id: userId.trim(), role }),
    });
    if (r.ok) {
      setUserId('');
      // Refresh the shares list
      const token2 = getToken();
      fetch(`/api/collab/shares/${workflowId}`, {
        headers: token2 ? { Authorization: `Bearer ${token2}` } : {},
      })
        .then(r => r.ok ? r.json() : null)
        .then(data => {
          if (data && Array.isArray(data.shares)) {
            setShares(data.shares as ShareEntry[]);
          }
        })
        .catch(() => {});
    }
  }, [workflowId, userId, role]);

  const handleRevoke = useCallback(async (shareId: string) => {
    if (!workflowId || !shareId) return;
    const token = getToken();
    const r = await fetch(`/api/collab/share/${shareId}`, {
      method: 'DELETE',
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
    if (r.ok) {
      setShares(prev => prev.filter(s => s.id !== shareId));
    }
  }, [workflowId]);

  const roomLink = workflowId
    ? `${window.location.origin}${window.location.pathname}?workflow=${encodeURIComponent(workflowId)}`
    : '';

  if (!isOpen) return null;

  return (
    <div className="modal-overlay" style={{
      position: 'fixed',
      inset: 0,
      background: 'rgba(0,0,0,0.4)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      zIndex: 300,
    }} onClick={onClose}>
      <div className="modal" style={{
        background: 'var(--surface)',
        border: '1px solid var(--border)',
        borderRadius: 10,
        width: 420,
        maxWidth: '90vw',
        padding: 20,
        boxShadow: '0 8px 32px rgba(0,0,0,0.2)',
      }} onClick={e => e.stopPropagation()}>
        <h3 style={{ margin: '0 0 16px', fontSize: 16 }}>Share Workflow</h3>

        <div style={{ display: 'flex', gap: 8, marginBottom: 16 }}>
          <input
            type="text"
            placeholder="User ID or email"
            value={userId}
            onChange={e => setUserId(e.target.value)}
            style={{
              flex: 1,
              padding: '6px 10px',
              borderRadius: 6,
              border: '1px solid var(--border)',
              background: 'var(--surface-2)',
              color: 'var(--text)',
              fontSize: 13,
            }}
          />
          <select
            value={role}
            onChange={e => setRole(e.target.value as 'editor' | 'viewer')}
            style={{
              padding: '6px 10px',
              borderRadius: 6,
              border: '1px solid var(--border)',
              background: 'var(--surface-2)',
              color: 'var(--text)',
              fontSize: 13,
            }}
          >
            <option value="editor">Editor</option>
            <option value="viewer">Viewer</option>
          </select>
          <button className="btn btn-primary btn-sm" onClick={handleShare} disabled={!userId.trim()}>
            Invite
          </button>
        </div>

        <div style={{ marginBottom: 12 }}>
          <div style={{ fontSize: 12, fontWeight: 600, marginBottom: 6, color: 'var(--muted)' }}>
            Collaboration room link
          </div>
          <div style={{
            padding: '7px 8px',
            border: '1px solid var(--border)',
            borderRadius: 6,
            background: 'var(--surface-2)',
            fontSize: 11,
            color: 'var(--muted)',
            wordBreak: 'break-all',
          }}>
            {roomLink}
          </div>
          <div style={{ marginTop: 5, fontSize: 11, color: 'var(--muted)' }}>
            Open-room hosts can join from this link. Restricted hosts still require an invite.
          </div>
        </div>

        <div style={{ fontSize: 12, fontWeight: 600, marginBottom: 6, color: 'var(--muted)' }}>
          Shared with
        </div>
        {loading ? (
          <div style={{ fontSize: 12, color: 'var(--muted)', padding: '8px 0' }}>Loading…</div>
        ) : shares.length === 0 ? (
          <div style={{ fontSize: 12, color: 'var(--muted)', padding: '8px 0' }}>No shares yet</div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {shares.map(s => (
              <div key={s.id} style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                padding: '6px 8px',
                borderRadius: 6,
                background: 'var(--surface-2)',
                fontSize: 12,
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <span style={{ fontWeight: 500 }}>{s.name || s.user_id}</span>
                  <span style={{
                    textTransform: 'uppercase',
                    fontSize: 10,
                    fontWeight: 700,
                    padding: '1px 6px',
                    borderRadius: 4,
                    background: s.role === 'editor' ? '#dbeafe' : '#f3f4f6',
                    color: s.role === 'editor' ? '#2563eb' : '#4b5563',
                  }}>
                    {s.role}
                  </span>
                </div>
                <button className="btn btn-xs" onClick={() => handleRevoke(s.id)} style={{ color: '#ef4444' }}>
                  Revoke
                </button>
              </div>
            ))}
          </div>
        )}

        <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: 16 }}>
          <button className="btn btn-sm" onClick={onClose}>Close</button>
        </div>
      </div>
    </div>
  );
};

export default ShareDialog;
