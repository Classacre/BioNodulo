import React, { useState, useEffect, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { apiGet, apiPost, apiDelete } from '../api/client';
import { toast } from '../components/ui';
import Dialog from '../components/ui/Dialog';

interface ShareDialogProps {
  workflowId: string | null;
  isOpen: boolean;
  onClose: () => void;
  collabEnabled?: boolean;
  inviteToken?: string | null;
  shareLink?: string;
  onCreateRoom?: () => Promise<void>;
}

interface ShareEntry {
  id: string;
  user_id: string;
  role: 'editor' | 'viewer';
  name?: string;
}

function isLocalShareLink(link: string): boolean {
  if (!link) return false;
  try {
    const host = new URL(link).hostname.toLowerCase();
    return host === 'localhost' || host === '127.0.0.1' || host === '0.0.0.0' || host === '::1';
  } catch {
    return false;
  }
}

const ShareDialog: React.FC<ShareDialogProps> = ({
  workflowId,
  isOpen,
  onClose,
  collabEnabled = false,
  inviteToken = null,
  shareLink = '',
  onCreateRoom,
}) => {
  const { t } = useTranslation();
  const [userId, setUserId] = useState('');
  const [role, setRole] = useState<'editor' | 'viewer'>('editor');
  const [shares, setShares] = useState<ShareEntry[]>([]);
  const [loading, setLoading] = useState(false);
  const [creatingLink, setCreatingLink] = useState(false);

  const refreshShares = useCallback(async (id: string) => {
    try {
      const data = await apiGet<{ shares?: ShareEntry[] }>(`/api/collab/shares/${id}`);
      setShares(Array.isArray(data.shares) ? data.shares : []);
    } catch {
      setShares([]);
    }
  }, []);

  useEffect(() => {
    if (!isOpen || !workflowId) return;
    setLoading(true);
    refreshShares(workflowId).finally(() => setLoading(false));
  }, [isOpen, workflowId, refreshShares]);

  const handleShare = useCallback(async () => {
    if (!workflowId || !userId.trim()) return;
    try {
      await apiPost('/api/collab/share', { workflow_id: workflowId, user_id: userId.trim(), role });
      setUserId('');
      await refreshShares(workflowId);
    } catch { /* surfaced via dialog state */ }
  }, [workflowId, userId, role, refreshShares]);

  const handleRevoke = useCallback(async (shareId: string) => {
    if (!workflowId || !shareId) return;
    try {
      await apiDelete(`/api/collab/share/${shareId}`);
      setShares(prev => prev.filter(s => s.id !== shareId));
    } catch { /* surfaced via dialog state */ }
  }, [workflowId]);

  const roomLink = shareLink || (workflowId
    ? `${window.location.origin}${window.location.pathname}?workflow=${encodeURIComponent(workflowId)}`
    : '');
  const localShareLink = isLocalShareLink(roomLink);

  const handleCreateLink = useCallback(async () => {
    if (!onCreateRoom) return;
    setCreatingLink(true);
    try {
      await onCreateRoom();
    } finally {
      setCreatingLink(false);
    }
  }, [onCreateRoom]);

  const handleCopyLink = useCallback(async () => {
    if (!roomLink) return;
    try {
      if (!navigator.clipboard) throw new Error('Clipboard unavailable');
      await navigator.clipboard.writeText(roomLink);
      toast.success(t('collab.linkCopied'));
    } catch {
      toast.info(t('collab.copyLinkFallback'));
    }
  }, [roomLink, t]);

  if (!isOpen) return null;

  return (
    <Dialog
      title={t('collab.shareDialogTitle')}
      onClose={onClose}
      width={420}
      maxHeight="90vh"
      style={{ maxWidth: '90vw' }}
      footer={<button className="btn btn-sm" onClick={onClose}>{t('common.close')}</button>}
    >
        {!collabEnabled && (
          <div style={{
            padding: '9px 10px',
            borderRadius: 6,
            border: '1px solid var(--border)',
            background: 'var(--surface-2)',
            fontSize: 12,
            color: 'var(--muted)',
            marginBottom: 12,
          }}>
            {t('collab.shareOfflineNotice')}
          </div>
        )}

        <div style={{ display: 'flex', gap: 8, marginBottom: 16 }}>
          <input
            type="text"
            placeholder={t('collab.userIdOrEmailPlaceholder')}
            value={userId}
            onChange={e => setUserId(e.target.value)}
            disabled={!collabEnabled}
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
            disabled={!collabEnabled}
            style={{
              padding: '6px 10px',
              borderRadius: 6,
              border: '1px solid var(--border)',
              background: 'var(--surface-2)',
              color: 'var(--text)',
              fontSize: 13,
            }}
          >
            <option value="editor">{t('collab.shareRoleEditor')}</option>
            <option value="viewer">{t('collab.shareRoleViewer')}</option>
          </select>
          <button className="btn btn-primary btn-sm" onClick={handleShare} disabled={!collabEnabled || !userId.trim()}>
            {t('collab.invite')}
          </button>
        </div>

        <div style={{ marginBottom: 12 }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8, marginBottom: 6 }}>
            <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--muted)' }}>
              {t('collab.roomLink')}
            </div>
            {inviteToken ? (
              <button className="btn btn-sm" type="button" onClick={handleCopyLink}>{t('common.copy')}</button>
            ) : (
              <button className="btn btn-primary btn-sm" type="button" onClick={handleCreateLink} disabled={!onCreateRoom || creatingLink}>
                {creatingLink ? t('collab.creatingLink') : t('collab.createLink')}
              </button>
            )}
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
            {inviteToken ? roomLink : t('collab.createShareLinkHint')}
          </div>
          <div style={{ marginTop: 5, fontSize: 11, color: 'var(--muted)' }}>
            {localShareLink
              ? t('collab.localLinkWarning')
              : t('collab.temporaryLinkHint')}
          </div>
        </div>

        <div style={{ fontSize: 12, fontWeight: 600, marginBottom: 6, color: 'var(--muted)' }}>
          {t('collab.sharedWith')}
        </div>
        {loading ? (
          <div style={{ fontSize: 12, color: 'var(--muted)', padding: '8px 0' }}>{t('common.loading')}</div>
        ) : shares.length === 0 ? (
          <div style={{ fontSize: 12, color: 'var(--muted)', padding: '8px 0' }}>{t('collab.noSharesYet')}</div>
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
                    {s.role === 'editor' ? t('collab.shareRoleEditor') : t('collab.shareRoleViewer')}
                  </span>
                </div>
                <button className="btn btn-xs" onClick={() => handleRevoke(s.id)} style={{ color: '#ef4444' }}>
                  {t('collab.revoke')}
                </button>
              </div>
            ))}
          </div>
        )}
    </Dialog>
  );
};

export default ShareDialog;
