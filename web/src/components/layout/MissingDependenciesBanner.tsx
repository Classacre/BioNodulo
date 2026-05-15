import { useState, useCallback, useEffect, useRef } from 'react';
import Icon from '../ui/Icon';
import type { ResolveReport, InstallJobStatus } from '../../types';

interface Props {
  report: ResolveReport;
  onDismiss: () => void;
  onOpenConsole: () => void;
  onResolve: () => void;
}

type EnvStrategy = 'shared' | 'isolated';

export default function MissingDependenciesBanner({ report, onDismiss, onOpenConsole, onResolve }: Props) {
  const [expanded, setExpanded] = useState(false);
  const [installing, setInstalling] = useState(false);
  const [jobStatus, setJobStatus] = useState<InstallJobStatus | null>(null);
  const [strategy, setStrategy] = useState<EnvStrategy>('shared');
  const [showStrategyMenu, setShowStrategyMenu] = useState(false);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const menuRef = useRef<HTMLDivElement>(null);

  const totalMissing =
    report.missing_nodes.length +
    report.missing_executables.length +
    report.missing_packages.length +
    report.missing_r_packages.length;

  // Close strategy menu on outside click
  useEffect(() => {
    function onClick(e: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setShowStrategyMenu(false);
      }
    }
    document.addEventListener('mousedown', onClick);
    return () => document.removeEventListener('mousedown', onClick);
  }, []);

  const startInstall = useCallback(async () => {
    setInstalling(true);
    onOpenConsole();
    try {
      const r = await fetch('/api/manager/install-deps', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ report, env_strategy: strategy }),
      });
      if (!r.ok) {
        setInstalling(false);
        return;
      }
      const data = await r.json();
      const jobId = data.job_id as string;

      // Poll for progress
      pollRef.current = setInterval(async () => {
        try {
          const sr = await fetch(`/api/manager/status/${jobId}`);
          if (sr.ok) {
            const status = await sr.json() as InstallJobStatus;
            setJobStatus(status);
            if (status.status === 'completed' || status.status === 'failed' || status.status === 'cancelled') {
              if (pollRef.current) clearInterval(pollRef.current);
              pollRef.current = null;
              setInstalling(false);
              // Small delay so the filesystem / conda index has time to settle
              setTimeout(() => onResolve(), 1000);
            }
          }
        } catch { /* ignore */ }
      }, 1500);
    } catch {
      setInstalling(false);
    }
  }, [report, onOpenConsole, onResolve, strategy]);

  useEffect(() => {
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, []);

  const summary = report.summary || `${totalMissing} missing`;

  const strategyLabel = strategy === 'shared'
    ? 'Install to bionodulo-tools'
    : 'Create isolated environments';

  return (
    <div className="dep-banner">
      <div className="dep-banner-row">
        <span className="dep-banner-icon">
          <Icon name="warning" size={16} />
        </span>
        <span className="dep-banner-text">
          <strong>Missing dependencies:</strong> {summary}
        </span>
        <div className="dep-banner-actions">
          {report.installable && !installing && (
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }} ref={menuRef}>
              <button className="btn btn-primary btn-sm" onClick={startInstall}>
                <Icon name="download" size={12} /> Auto Install
              </button>
              <button
                className="btn btn-sm btn-ghost"
                style={{ padding: '4px 6px', display: 'flex', alignItems: 'center', gap: 4 }}
                onClick={() => setShowStrategyMenu(v => !v)}
                title={strategyLabel}
              >
                <span style={{ fontSize: 11 }}>{strategyLabel}</span>
                <Icon name="chevronDown" size={12} />
              </button>
              {showStrategyMenu && (
                <div className="dropdown-menu" style={{ right: 0, top: '100%', marginTop: 4, minWidth: 220 }}>
                  <div
                    className={`dropdown-item ${strategy === 'shared' ? 'active' : ''}`}
                    onClick={() => { setStrategy('shared'); setShowStrategyMenu(false); }}
                  >
                    <div style={{ fontWeight: 500 }}>Install to bionodulo-tools</div>
                    <div style={{ fontSize: 11, color: 'var(--muted)' }}>Shared environment (faster for single tools)</div>
                  </div>
                  <div
                    className={`dropdown-item ${strategy === 'isolated' ? 'active' : ''}`}
                    onClick={() => { setStrategy('isolated'); setShowStrategyMenu(false); }}
                  >
                    <div style={{ fontWeight: 500 }}>Create isolated environments</div>
                    <div style={{ fontSize: 11, color: 'var(--muted)' }}>One env per category (avoids conflicts)</div>
                  </div>
                </div>
              )}
            </div>
          )}
          {installing && jobStatus && (
            <div className="dep-banner-progress">
              <span className="dep-banner-progress-text">
                <Icon name="spinner" size={12} /> {jobStatus.current_step || 'Installing...'}
              </span>
              <div className="dep-banner-progress-bar">
                <div
                  className="dep-banner-progress-fill"
                  style={{ width: `${jobStatus.percent}%` }}
                />
              </div>
            </div>
          )}
          <button className="btn btn-sm" onClick={() => setExpanded(v => !v)}>
            {expanded ? 'Hide' : 'Details'}
          </button>
          <button className="btn btn-sm btn-ghost" onClick={onDismiss} title="Dismiss">
            <Icon name="close" size={12} />
          </button>
        </div>
      </div>

      {expanded && (
        <div className="dep-banner-details">
          {report.missing_nodes.length > 0 && (
            <div className="dep-banner-section">
              <h4>Missing Nodes ({report.missing_nodes.length})</h4>
              <ul>
                {report.missing_nodes.map(n => (
                  <li key={n.node_type}>
                    <code>{n.node_type}</code>
                    {n.git_url && <span className="dep-banner-source"> — {n.git_url}</span>}
                    {n.message && <span className="dep-banner-msg">{n.message}</span>}
                  </li>
                ))}
              </ul>
            </div>
          )}
          {report.missing_executables.length > 0 && (
            <div className="dep-banner-section">
              <h4>Missing Tools ({report.missing_executables.length})</h4>
              <ul>
                {report.missing_executables.map(e => (
                  <li key={e.name}>
                    <code>{e.name}</code>
                    {e.conda_package && e.conda_package !== e.name && (
                      <span className="dep-banner-source"> (conda: {e.conda_package})</span>
                    )}
                    {e.recommended_env && e.recommended_env !== 'bionodulo-tools' && (
                      <span className="dep-banner-msg"> → {e.recommended_env}</span>
                    )}
                  </li>
                ))}
              </ul>
            </div>
          )}
          {report.missing_packages.length > 0 && (
            <div className="dep-banner-section">
              <h4>Missing Python Packages ({report.missing_packages.length})</h4>
              <ul>
                {report.missing_packages.map(p => (
                  <li key={p.name}>
                    <code>{p.name}</code>
                    <span className="dep-banner-source"> ({p.source})</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
          {report.missing_r_packages.length > 0 && (
            <div className="dep-banner-section">
              <h4>Missing R Packages ({report.missing_r_packages.length})</h4>
              <ul>
                {report.missing_r_packages.map(p => (
                  <li key={p.name}>
                    <code>{p.name}</code>
                    <span className="dep-banner-source"> ({p.source})</span>
                    {p.recommended_env && p.recommended_env !== 'bionodulo-tools' && (
                      <span className="dep-banner-msg"> → {p.recommended_env}</span>
                    )}
                  </li>
                ))}
              </ul>
            </div>
          )}
          {report.errors.length > 0 && (
            <div className="dep-banner-section">
              <h4>Errors</h4>
              <ul>
                {report.errors.map((err, i) => (
                  <li key={i} className="dep-banner-error">{err}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
