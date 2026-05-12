import { useState, useCallback, useEffect, useRef } from 'react';
import Icon from '../ui/Icon';
import type { ResolveReport, InstallJobStatus } from '../../types';

interface Props {
  report: ResolveReport;
  onDismiss: () => void;
}

export default function MissingDependenciesBanner({ report, onDismiss }: Props) {
  const [expanded, setExpanded] = useState(false);
  const [installing, setInstalling] = useState(false);
  const [jobStatus, setJobStatus] = useState<InstallJobStatus | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const totalMissing =
    report.missing_nodes.length +
    report.missing_executables.length +
    report.missing_packages.length;

  const startInstall = useCallback(async () => {
    setInstalling(true);
    try {
      const r = await fetch('/api/manager/install-deps', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ report }),
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
            }
          }
        } catch { /* ignore */ }
      }, 1500);
    } catch {
      setInstalling(false);
    }
  }, [report]);

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
        </span>
        <div className="dep-banner-actions">
          {report.installable && !installing && (
            <button className="btn btn-primary btn-sm" onClick={startInstall}>
              <Icon name="download" size={12} /> Auto Install
            </button>
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
