import { useState, useEffect, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import type { WorkflowVersion, VersionDiffResult } from './types';
import VersionDiff from './VersionDiff';
import Icon from '../components/ui/Icon';
import { confirmDialog, promptDialog } from '../components/ui';
import { apiDelete, apiGet, apiPost } from '../api/client';

const API_BASE = 'api/collab';

interface VersionHistoryProps {
  workflowId: string;
  isOpen: boolean;
  onClose: () => void;
  onRestore: (versionJson: unknown) => void;
}

function timeAgo(ts: string, translate: (key: string, options?: Record<string, unknown>) => string): string {
  const s = Math.floor((Date.now() - new Date(ts).getTime()) / 1000);
  if (s < 60) return translate('collab.timeJustNow');
  if (s < 3600) return translate('collab.timeMinutesAgo', { count: Math.floor(s / 60) });
  if (s < 86400) return translate('collab.timeHoursAgo', { count: Math.floor(s / 3600) });
  return translate('collab.timeDaysAgo', { count: Math.floor(s / 86400) });
}

export default function VersionHistory({ workflowId, isOpen, onClose, onRestore }: VersionHistoryProps) {
  const { t } = useTranslation();
  const [versions, setVersions] = useState<WorkflowVersion[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [diffData, setDiffData] = useState<{ a: WorkflowVersion; b: WorkflowVersion; diff: VersionDiffResult } | null>(null);

  const fetchVersions = useCallback(async () => {
    if (!workflowId) return;
    setLoading(true);
    try {
      const data = await apiGet<{ versions: WorkflowVersion[]; count: number }>(
        `${API_BASE}/workflows/${workflowId}/versions`,
      );
      setVersions(data.versions ?? []);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : t('collab.versionHistoryLoadError'));
    } finally {
      setLoading(false);
    }
  }, [workflowId, t]);

  useEffect(() => {
    if (!isOpen) return;
    fetchVersions();
  }, [isOpen, fetchVersions]);

  const handleSaveVersion = async () => {
    const name = await promptDialog({
      title: t('collab.versionHistorySavePromptTitle'),
      message: t('collab.versionHistorySavePromptMessage'),
      inputLabel: t('collab.versionHistorySavePromptInputLabel'),
      placeholder: t('collab.versionHistorySavePromptPlaceholder'),
      confirmLabel: t('collab.versionHistorySavePromptConfirm'),
    });
    if (name === null) return;
    setSaving(true);
    try {
      await apiPost(`${API_BASE}/workflows/${workflowId}/versions`, { name: name || null });
      fetchVersions();
    } catch (err) {
      setError(err instanceof Error ? err.message : t('collab.versionHistorySaveError'));
    } finally {
      setSaving(false);
    }
  };

  const handleRestore = async (versionId: string) => {
    const ok = await confirmDialog({
      title: t('collab.versionHistoryRestoreConfirmTitle'),
      message: t('collab.versionHistoryRestoreConfirmMessage'),
      confirmLabel: t('collab.versionHistoryRestore'),
      tone: 'warning',
    });
    if (!ok) return;
    try {
      const data = await apiPost<{ snapshot: unknown }>(`${API_BASE}/versions/${versionId}/restore`);
      onRestore(data.snapshot);
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : t('collab.versionHistoryRestoreError'));
    }
  };

  const handleDelete = async (versionId: string) => {
    const ok = await confirmDialog({
      title: t('collab.versionHistoryDeleteConfirmTitle'),
      message: t('collab.versionHistoryDeleteConfirmMessage'),
      confirmLabel: t('common.delete'),
      tone: 'danger',
    });
    if (!ok) return;
    try {
      await apiDelete(`${API_BASE}/versions/${versionId}`);
      fetchVersions();
    } catch (err) {
      setError(err instanceof Error ? err.message : t('collab.versionHistoryDeleteError'));
    }
  };

  const handleDiff = async (a: WorkflowVersion, b: WorkflowVersion) => {
    try {
      const diff = await apiGet<VersionDiffResult>(`${API_BASE}/versions/${a.id}/diff/${b.id}`);
      setDiffData({ a, b, diff });
    } catch (err) {
      setError(err instanceof Error ? err.message : t('collab.versionHistoryDiffLoadError'));
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
          <strong style={{ fontSize: 14 }}>{t('collab.versionHistoryTitle')}</strong>
          <div style={{ display: 'flex', gap: 6 }}>
            <button className="btn btn-sm" onClick={handleSaveVersion} disabled={saving} style={{ fontSize: 10 }}>
              {saving ? t('collab.versionHistorySaving') : t('collab.versionHistorySaveAction')}
            </button>
            <button className="btn btn-icon btn-xs" onClick={onClose} title={t('common.close')}><Icon name="close" size={12} /></button>
          </div>
        </div>

        {error && <div style={{ padding: '8px 14px', fontSize: 11, color: '#ef4444', background: '#ef444410' }}>{error}</div>}

        {/* Version list */}
        <div style={{ flex: 1, overflowY: 'auto', padding: '8px 0' }}>
          {loading && versions.length === 0 && <div style={{ padding: 20, textAlign: 'center', fontSize: 12, color: 'var(--muted)' }}>{t('collab.versionHistoryLoading')}</div>}
          {versions.length === 0 && !loading && <div style={{ padding: 20, textAlign: 'center', fontSize: 12, color: 'var(--muted)' }}>{t('collab.versionHistoryEmpty')}</div>}
          {versions.map((v, idx) => (
            <div key={v.id} style={{ padding: '10px 14px', borderBottom: '1px solid var(--border)' }}>
              <div style={{ display: 'flex', alignItems: 'flex-start', gap: 8 }}>
                {/* Auto-save icon */}
                <div style={{ marginTop: 2, fontSize: 12, color: v.auto_save ? '#94a3b8' : '#3b82f6' }} title={v.auto_save ? t('collab.versionHistoryAutoSaved') : t('collab.versionHistoryManualSave')}>
                  <Icon name={v.auto_save ? 'clock' : 'check'} size={12} />
                </div>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 12, fontWeight: 600, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                    {v.name || (v.auto_save
                      ? t('collab.versionHistoryAutoSaveName', { count: versions.length - idx })
                      : t('collab.versionHistoryVersionName', { count: versions.length - idx }))}
                  </div>
                  <div style={{ fontSize: 10, color: 'var(--muted)', marginTop: 2 }}>
                    {v.user_name} • {timeAgo(v.created_at, t)} • {t('collab.versionHistoryMeta', { nodes: v.node_count, edges: v.edge_count })}
                  </div>
                </div>
              </div>
              {/* Actions */}
              <div style={{ display: 'flex', gap: 4, marginTop: 6, paddingLeft: 20 }}>
                <button className="btn btn-xs" onClick={() => handleRestore(v.id)} style={{ fontSize: 9, padding: '2px 8px' }}>{t('collab.versionHistoryRestore')}</button>
                {idx < versions.length - 1 && (
                  <button className="btn btn-xs" onClick={() => handleDiff(versions[idx + 1], v)} style={{ fontSize: 9, padding: '2px 8px' }}>{t('collab.versionHistoryDiff')}</button>
                )}
                <button className="btn btn-xs" onClick={() => handleDelete(v.id)} style={{ fontSize: 9, padding: '2px 8px', color: '#ef4444' }}>{t('common.delete')}</button>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Diff overlay */}
      {diffData && (
        <VersionDiff
          versionA={{ id: diffData.a.id, name: diffData.a.name || t('collab.versionHistoryAutoSaveFallback') }}
          versionB={{ id: diffData.b.id, name: diffData.b.name || t('collab.versionHistoryAutoSaveFallback') }}
          diff={diffData.diff}
          isOpen={!!diffData}
          onClose={() => setDiffData(null)}
        />
      )}
    </>
  );
}
