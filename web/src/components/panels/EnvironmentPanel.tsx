import { useState, useEffect, useCallback, useRef } from 'react';
import { useTranslation } from 'react-i18next';
import Icon from '../ui/Icon';
import { confirmDialog } from '../ui';
import { ApiError, apiDelete, apiGet, apiPost } from '../../api/client';
import { logError } from '../../state/logging';

interface PackageInfo {
  name: string;
  version: string;
}

interface EnvInfo {
  id: string;
  name: string;
  path: string;
  packages: PackageInfo[];
  package_count: number;
  ready: boolean;
  status: string;
}

interface EnvironmentPanelProps {
  onClose: () => void;
  currentWorkflow?: Record<string, any>;
}

function shortId(id: string) {
  if (id.length <= 8) return id;
  return `${id.slice(0, 3)}...${id.slice(-3)}`;
}

type MessageTone = 'ok' | 'err';

function apiErrorMessage(err: unknown, fallback: string, networkFallback: string): string {
  if (!(err instanceof ApiError)) return networkFallback;
  if (err.body && typeof err.body === 'object' && 'detail' in err.body) {
    const detail = (err.body as { detail?: unknown }).detail;
    if (typeof detail === 'string' && detail.trim()) return detail;
  }
  if (typeof err.body === 'string' && err.body.trim()) return err.body;
  return fallback;
}

export default function EnvironmentPanel({ onClose }: EnvironmentPanelProps) {
  const { t } = useTranslation();
  const [envs, setEnvs] = useState<EnvInfo[]>([]);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState('');
  const [messageTone, setMessageTone] = useState<MessageTone>('ok');
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [menuOpenId, setMenuOpenId] = useState<string | null>(null);
  const [renamingId, setRenamingId] = useState<string | null>(null);
  const [renameValue, setRenameValue] = useState('');
  const menuRef = useRef<HTMLDivElement>(null);

  const fetchEnvs = useCallback(async () => {
    setLoading(true);
    try {
      const data = await apiGet<{ environments?: EnvInfo[] }>('/manager/environments');
      setEnvs(data.environments || []);
    } catch (err) {
      logError('environment.list.load', err);
      /* offline / backend unavailable — keep prior list */
    }
    setLoading(false);
  }, []);

  useEffect(() => {
    fetchEnvs();
  }, [fetchEnvs]);

  // Close menu on outside click
  useEffect(() => {
    function onClick(e: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setMenuOpenId(null);
      }
    }
    document.addEventListener('mousedown', onClick);
    return () => document.removeEventListener('mousedown', onClick);
  }, []);

  const handleRename = async (id: string) => {
    if (!renameValue.trim()) {
      setRenamingId(null);
      return;
    }
    try {
      await apiPost(`/manager/environments/${encodeURIComponent(id)}/rename`, { name: renameValue.trim() });
      setMessage(t('environment.renamedTo', { name: renameValue.trim() }));
      setMessageTone('ok');
      fetchEnvs();
    } catch (err) {
      logError('environment.rename', err);
      setMessage(apiErrorMessage(err, t('environment.renameFailed'), t('errors.network')));
      setMessageTone('err');
    }
    setRenamingId(null);
  };

  const handleDelete = async (env: EnvInfo) => {
    setMenuOpenId(null);
    const ok = await confirmDialog({
      title: t('environment.deleteTitle'),
      message: t('environment.deleteMessage', { name: env.name }),
      confirmLabel: t('common.delete'),
      tone: 'danger',
    });
    if (!ok) return;
    try {
      await apiDelete(`/manager/environments/${encodeURIComponent(env.id)}`);
      setMessage(t('environment.deletedEnvironment', { name: env.name }));
      setMessageTone('ok');
      fetchEnvs();
    } catch (err) {
      logError('environment.delete', err);
      setMessage(apiErrorMessage(err, t('environment.deleteFailed'), t('errors.network')));
      setMessageTone('err');
    }
  };

  const handleDuplicate = async (env: EnvInfo) => {
    setMenuOpenId(null);
    try {
      const data = await apiPost<{ message?: string }>(`/manager/environments/${encodeURIComponent(env.id)}/duplicate`);
      setMessage(data.message || t('environment.duplicatedEnvironment', { name: env.name }));
      setMessageTone('ok');
      fetchEnvs();
    } catch (err) {
      logError('environment.duplicate', err);
      setMessage(apiErrorMessage(err, t('environment.duplicateFailed'), t('errors.network')));
      setMessageTone('err');
    }
  };

  const handleRemovePackage = async (env: EnvInfo, pkg: PackageInfo) => {
    const ok = await confirmDialog({
      title: t('environment.removePackageTitle'),
      message: t('environment.removePackageMessage', { packageName: pkg.name, environmentName: env.name }),
      confirmLabel: t('environment.removePackageConfirm'),
      tone: 'warning',
    });
    if (!ok) return;
    try {
      const data = await apiPost<{ message?: string }>(
        `/manager/environments/${encodeURIComponent(env.id)}/packages/${encodeURIComponent(pkg.name)}/remove`,
      );
      setMessage(data.message || t('environment.removedPackage', { name: pkg.name }));
      setMessageTone('ok');
      fetchEnvs();
    } catch (err) {
      logError('environment.package.remove', err);
      setMessage(apiErrorMessage(err, t('environment.removeFailed'), t('errors.network')));
      setMessageTone('err');
    }
  };

  const startRename = (env: EnvInfo) => {
    setRenamingId(env.id);
    setRenameValue(env.name);
    setMenuOpenId(null);
  };

  return (
    <div className="rail-panel">
      <div className="rail-panel-header">
        <span>{t('environment.managerTitle')}</span>
        <button className="btn btn-icon" onClick={onClose} title={t('common.close')} aria-label={t('common.close')}><Icon name="close" size={14} /></button>
      </div>

      {message && (
        <div className={`env-message ${messageTone}`}>
          {message}
        </div>
      )}

      <div className="rail-panel-body" style={{ padding: 0 }}>
        {loading && envs.length === 0 && (
          <div style={{ padding: 20, textAlign: 'center', color: 'var(--muted)', fontSize: 12 }}>
            <Icon name="spinner" size={14} /> {t('environment.loadingEnvironments')}
          </div>
        )}

        {envs.length === 0 && !loading && (
          <div style={{ padding: 20, textAlign: 'center', color: 'var(--muted)', fontSize: 12 }}>
            {t('environment.emptyTitle')}<br />
            {t('environment.emptyHint')}
          </div>
        )}

        {envs.map(env => (
          <div key={env.id} className="env-item" style={{ borderBottom: '1px solid var(--border)', display: 'block' }}>
            {/* Main row */}
            <div style={{ display: 'flex', alignItems: 'center', padding: '8px 12px', gap: 6 }}>
              {/* Name + short ID */}
              <div style={{ flex: 1, minWidth: 0, display: 'flex', alignItems: 'center', gap: 6, overflow: 'hidden' }}>
                {renamingId === env.id ? (
                  <input
                    autoFocus
                    className="text-input"
                    style={{ fontSize: 12, padding: '2px 6px', width: '100%' }}
                    value={renameValue}
                    onChange={e => setRenameValue(e.target.value)}
                    onBlur={() => handleRename(env.id)}
                    onKeyDown={e => { if (e.key === 'Enter') handleRename(env.id); if (e.key === 'Escape') setRenamingId(null); }}
                  />
                ) : (
                  <>
                    <span
                      style={{
                        fontWeight: 500,
                        fontSize: 13,
                        whiteSpace: 'nowrap',
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                      }}
                      title={env.name}
                    >
                      {env.name}
                    </span>
                    <code
                      style={{
                        fontSize: 10,
                        color: env.ready ? '#22c55e' : 'var(--danger)',
                        flexShrink: 0,
                      }}
                      title={env.id}
                    >
                      [{shortId(env.id)}]
                    </code>
                  </>
                )}
              </div>

              {/* Expand toggle */}
              <button
                className="btn btn-icon btn-sm"
                style={{ padding: 2, flexShrink: 0 }}
                onClick={() => setExpandedId(expandedId === env.id ? null : env.id)}
                title={expandedId === env.id ? t('environment.collapsePackages') : t('environment.showPackages')}
              >
                <Icon name={expandedId === env.id ? 'chevronDown' : 'chevronRight'} size={12} />
              </button>

              {/* Burger menu */}
              <div style={{ display: 'flex', alignItems: 'center', position: 'relative', flexShrink: 0 }} ref={menuOpenId === env.id ? menuRef : undefined}>
                <button
                  className="btn btn-icon btn-sm"
                  style={{ padding: 4 }}
                  onClick={() => setMenuOpenId(menuOpenId === env.id ? null : env.id)}
                  title={t('common.options')}
                >
                  <Icon name="menu" size={14} />
                </button>

                {menuOpenId === env.id && (
                  <div className="dropdown-menu" style={{ right: 0, top: '100%', marginTop: 4, minWidth: 140, zIndex: 10 }}>
                    <div
                      className="dropdown-item"
                      style={{ display: 'flex', alignItems: 'center', gap: 8, whiteSpace: 'nowrap', fontSize: 12 }}
                      onClick={() => startRename(env)}
                    >
                      <Icon name="edit" size={12} /> {t('environment.renameAction')}
                    </div>
                    <div
                      className="dropdown-item"
                      style={{ display: 'flex', alignItems: 'center', gap: 8, whiteSpace: 'nowrap', fontSize: 12 }}
                      onClick={() => handleDuplicate(env)}
                    >
                      <Icon name="copy" size={12} /> {t('common.duplicate')}
                    </div>
                    <div
                      className="dropdown-item"
                      style={{ display: 'flex', alignItems: 'center', gap: 8, whiteSpace: 'nowrap', fontSize: 12, color: 'var(--danger)' }}
                      onClick={() => handleDelete(env)}
                    >
                      <Icon name="trash" size={12} /> {t('common.delete')}
                    </div>
                  </div>
                )}
              </div>
            </div>

            {/* Expanded packages */}
            {expandedId === env.id && (
              <div style={{ padding: '0 12px 12px 12px' }}>
                <div style={{ fontSize: 11, color: 'var(--muted)', marginBottom: 6 }}>
                  {t('environment.packageCount', { count: env.package_count })}
                </div>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                  {env.packages.map((pkg) => (
                    <span
                      key={pkg.name}
                      style={{
                        fontSize: 11,
                        padding: '3px 8px',
                        background: 'var(--surface-2)',
                        borderRadius: 4,
                        border: '1px solid var(--border)',
                        color: 'var(--text)',
                        fontFamily: 'monospace',
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: 6,
                      }}
                    >
                      <span>{pkg.name} <span style={{ color: 'var(--muted)' }}>{pkg.version}</span></span>
                      <button
                        className="btn btn-icon btn-sm btn-ghost"
                        style={{ padding: 0, width: 14, height: 14, color: 'var(--danger)', lineHeight: 1 }}
                        onClick={() => handleRemovePackage(env, pkg)}
                        title={t('environment.removePackageTitleFor', { name: pkg.name })}
                      >
                        <Icon name="close" size={10} />
                      </button>
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
