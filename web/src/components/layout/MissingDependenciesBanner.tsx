import { useState, useCallback, useEffect, useRef } from 'react';
import Icon from '../ui/Icon';
import type { ResolveReport, InstallJobStatus, Workflow } from '../../types';
import { apiGet, apiPost } from '../../api/client';

interface Props {
  report: ResolveReport;
  workflow: Workflow;
  onDismiss: () => void;
  onOpenConsole: () => void;
  onResolve: () => void;
}

export default function MissingDependenciesBanner({ report, workflow, onDismiss, onOpenConsole, onResolve }: Props) {
  const [expanded, setExpanded] = useState(false);
  const [installing, setInstalling] = useState(false);
  const [jobStatus, setJobStatus] = useState<InstallJobStatus | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const totalMissing =
    report.missing_nodes.length +
    report.missing_executables.length +
    report.missing_packages.length +
    report.missing_r_packages.length;

  const startInstall = useCallback(async () => {
    setInstalling(true);
    onOpenConsole();
    try {
      let jobId: string | undefined;
      try {
        const data = await apiPost<{ job_id?: string }>('/manager/ensure-workflow-env', { workflow });
        jobId = data.job_id;
      } catch {
        setInstalling(false);
        return;
      }
      if (!jobId) {
        setInstalling(false);
        onResolve();
        return;
      }
      pollRef.current = setInterval(async () => {
        try {
          const status = await apiGet<InstallJobStatus>(`/manager/status/${jobId}`);
          {
            setJobStatus(status);
            if (status.status === 'completed' || status.status === 'failed' || status.status === 'cancelled') {
              if (pollRef.current) clearInterval(pollRef.current);
              pollRef.current = null;
              setInstalling(false);
              setTimeout(() => onResolve(), 1000);
            }
          }
        } catch { /* ignore */ }
      }, 1500);
    } catch {
      setInstalling(false);
    }
  }, [workflow, onOpenConsole, onResolve]);

  useEffect(() => {
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, []);

  const summary = report.summary || `${totalMissing} missing`;

  return (
    <div className="dep-banner">
      <div className="dep-banner-row">
        <span className="dep-banner-icon">
          <Icon name="warning" size={16} />
        </span>
        <span className="dep-banner-text">
          <strong>Missing dependencies:</strong> {summary}
          {report.env_id && (
            <span style={{ fontSize: 11, color: 'var(--muted)', marginLeft: 8 }}>
              env: {report.env_id.slice(0, 8)} {report.env_ready ? '(ready)' : '(not ready)'}
            </span>
          )}
        </span>
        <div className="dep-banner-actions">
          {!report.env_ready && (
            <button className="btn btn-primary btn-sm" onClick={startInstall} disabled={installing}>
              {installing ? <><Icon name="spinner" size={12} /> Installing...</> : <><Icon name="download" size={12} /> Install Env</>}
            </button>
          )}
          {report.env_ready && (
            <span className="dep-badge ok" style={{ fontSize: 12 }}>Env ready</span>
          )}
          <button className="btn btn-sm" onClick={() => setExpanded(v => !v)}>
            {expanded ? 'Hide' : 'Details'}
          </button>
          <button className="btn btn-sm btn-ghost" onClick={onDismiss} title="Dismiss">
            <Icon name="close" size={12} />
          </button>
        </div>
      </div>

      {installing && jobStatus && (
        <div className="dep-banner-details" style={{ borderTop: '1px solid var(--border)' }}>
          <span style={{ fontSize: 12, color: 'var(--muted)' }}>
            <Icon name="spinner" size={12} /> {jobStatus.current_step || 'Installing...'} {jobStatus.message}
          </span>
        </div>
      )}

      {expanded && (
        <div className="dep-banner-details">
          {report.required_packages.length > 0 && (
            <div className="dep-banner-section">
              <h4>Required Packages ({report.required_packages.length})</h4>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
                {report.required_packages.map(p => (
                  <code key={p} style={{ fontSize: 11, padding: '2px 6px', background: 'var(--surface)', borderRadius: 4 }}>{p}</code>
                ))}
              </div>
            </div>
          )}

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
