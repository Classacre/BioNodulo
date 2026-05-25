import { useState, useEffect, useCallback, useRef } from 'react';
import Icon from '../ui/Icon';
import { confirmDialog } from '../ui';

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

export default function EnvironmentPanel({ onClose }: EnvironmentPanelProps) {
  const [envs, setEnvs] = useState<EnvInfo[]>([]);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState('');
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [menuOpenId, setMenuOpenId] = useState<string | null>(null);
  const [renamingId, setRenamingId] = useState<string | null>(null);
  const [renameValue, setRenameValue] = useState('');
  const menuRef = useRef<HTMLDivElement>(null);

  const fetchEnvs = useCallback(async () => {
    setLoading(true);
    try {
      const r = await fetch('/api/manager/environments');
      if (r.ok) {
        const data = await r.json();
        setEnvs(data.environments || []);
      }
    } catch { /* offline */ }
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
      const r = await fetch(`/api/manager/environments/${encodeURIComponent(id)}/rename`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: renameValue.trim() }),
      });
      if (r.ok) {
        setMessage(`Renamed to '${renameValue.trim()}'`);
        fetchEnvs();
      } else {
        const data = await r.json();
        setMessage(data.detail || 'Rename failed');
      }
    } catch {
      setMessage('Network error');
    }
    setRenamingId(null);
  };

  const handleDelete = async (env: EnvInfo) => {
    setMenuOpenId(null);
    const ok = await confirmDialog({
      title: 'Delete environment?',
      message: `Delete environment '${env.name}'? This cannot be undone.`,
      confirmLabel: 'Delete',
      tone: 'danger',
    });
    if (!ok) return;
    try {
      const r = await fetch(`/api/manager/environments/${encodeURIComponent(env.id)}`, { method: 'DELETE' });
      if (r.ok) {
        setMessage(`Deleted environment '${env.name}'`);
        fetchEnvs();
      } else {
        const data = await r.json();
        setMessage(data.detail || 'Delete failed');
      }
    } catch {
      setMessage('Network error');
    }
  };

  const handleDuplicate = async (env: EnvInfo) => {
    setMenuOpenId(null);
    try {
      const r = await fetch(`/api/manager/environments/${encodeURIComponent(env.id)}/duplicate`, {
        method: 'POST',
      });
      if (!r.ok) {
        const data = await r.json();
        setMessage(data.detail || 'Duplicate failed');
        return;
      }
      const data = await r.json();
      setMessage(data.message || `Duplicated '${env.name}'`);
      fetchEnvs();
    } catch {
      setMessage('Network error');
    }
  };

  const handleRemovePackage = async (env: EnvInfo, pkg: PackageInfo) => {
    const ok = await confirmDialog({
      title: 'Remove package?',
      message: `Remove package '${pkg.name}' from environment '${env.name}'?`,
      confirmLabel: 'Remove',
      tone: 'warning',
    });
    if (!ok) return;
    try {
      const r = await fetch(
        `/api/manager/environments/${encodeURIComponent(env.id)}/packages/${encodeURIComponent(pkg.name)}/remove`,
        { method: 'POST' }
      );
      if (!r.ok) {
        const data = await r.json();
        setMessage(data.detail || 'Remove failed');
        return;
      }
      const data = await r.json();
      setMessage(data.message || `Removed '${pkg.name}'`);
      fetchEnvs();
    } catch {
      setMessage('Network error');
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
        <span>Environments</span>
        <button className="btn btn-icon" onClick={onClose}><Icon name="close" size={14} /></button>
      </div>

      {message && (
        <div className={`env-message ${message.includes('failed') || message.includes('error') ? 'err' : 'ok'}`}>
          {message}
        </div>
      )}

      <div className="rail-panel-body" style={{ padding: 0 }}>
        {loading && envs.length === 0 && (
          <div style={{ padding: 20, textAlign: 'center', color: 'var(--muted)', fontSize: 12 }}>
            <Icon name="spinner" size={14} /> Loading environments...
          </div>
        )}

        {envs.length === 0 && !loading && (
          <div style={{ padding: 20, textAlign: 'center', color: 'var(--muted)', fontSize: 12 }}>
            No environments yet.<br />
            Run a workflow to create one.
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
                title={expandedId === env.id ? 'Collapse packages' : 'Show packages'}
              >
                <Icon name={expandedId === env.id ? 'chevronDown' : 'chevronRight'} size={12} />
              </button>

              {/* Burger menu */}
              <div style={{ display: 'flex', alignItems: 'center', position: 'relative', flexShrink: 0 }} ref={menuOpenId === env.id ? menuRef : undefined}>
                <button
                  className="btn btn-icon btn-sm"
                  style={{ padding: 4 }}
                  onClick={() => setMenuOpenId(menuOpenId === env.id ? null : env.id)}
                  title="Options"
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
                      <Icon name="edit" size={12} /> Rename
                    </div>
                    <div
                      className="dropdown-item"
                      style={{ display: 'flex', alignItems: 'center', gap: 8, whiteSpace: 'nowrap', fontSize: 12 }}
                      onClick={() => handleDuplicate(env)}
                    >
                      <Icon name="copy" size={12} /> Duplicate
                    </div>
                    <div
                      className="dropdown-item"
                      style={{ display: 'flex', alignItems: 'center', gap: 8, whiteSpace: 'nowrap', fontSize: 12, color: 'var(--danger)' }}
                      onClick={() => handleDelete(env)}
                    >
                      <Icon name="trash" size={12} /> Delete
                    </div>
                  </div>
                )}
              </div>
            </div>

            {/* Expanded packages */}
            {expandedId === env.id && (
              <div style={{ padding: '0 12px 12px 12px' }}>
                <div style={{ fontSize: 11, color: 'var(--muted)', marginBottom: 6 }}>
                  {env.package_count} package{env.package_count === 1 ? '' : 's'}
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
                        title={`Remove ${pkg.name}`}
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
