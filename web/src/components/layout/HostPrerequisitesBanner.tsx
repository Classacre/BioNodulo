import { useState, useCallback } from 'react';
import Icon from '../ui/Icon';
import type { HostStatus } from '../../types';

interface Props {
  status: HostStatus;
  onDismiss: () => void;
  onOpenConsole: () => void;
  onRecheck: () => void;
}

export default function HostPrerequisitesBanner({ status, onDismiss, onOpenConsole, onRecheck }: Props) {
  const [expanded, setExpanded] = useState(false);
  const [installing, setInstalling] = useState(false);
  const [installMsg, setInstallMsg] = useState<string | null>(null);

  const handleInstall = useCallback(async () => {
    setInstalling(true);
    setInstallMsg(null);
    onOpenConsole();
    try {
      const r = await fetch('/api/host_status/install-pixi', { method: 'POST' });
      const data = await r.json();
      if (data.success) {
        setInstallMsg(data.already_installed ? 'Already installed' : 'Installed successfully — reload the page to activate.');
      } else {
        setInstallMsg(`Install failed: ${data.message}`);
      }
    } catch {
      setInstallMsg('Install request failed — check server logs.');
    } finally {
      setInstalling(false);
      onRecheck();
    }
  }, [onOpenConsole, onRecheck]);

  const missingRequired = status.missing_required || [];
  const missingOptional = status.missing_optional || [];

  return (
    <div className="dep-banner" style={{ borderLeft: '3px solid var(--danger)' }}>
      <div className="dep-banner-row">
        <span className="dep-banner-icon">
          <Icon name="warning" size={16} />
        </span>
        <span className="dep-banner-text">
          <strong>Host prerequisite missing:</strong>{' '}
          {status.message || `${missingRequired.length} required tool(s) missing`}
        </span>
        <div className="dep-banner-actions">
          {missingRequired.includes('pixi') && (
            <button
              className="btn btn-primary btn-sm"
              onClick={handleInstall}
              disabled={installing}
            >
              {installing ? (
                <>
                  <Icon name="spinner" size={12} /> Installing...
                </>
              ) : (
                <>
                  <Icon name="download" size={12} /> Auto Install Pixi
                </>
              )}
            </button>
          )}
          <button className="btn btn-sm" onClick={() => setExpanded(v => !v)}>
            {expanded ? 'Hide' : 'Details'}
          </button>
          <button className="btn btn-sm btn-ghost" onClick={onDismiss} title="Dismiss">
            <Icon name="close" size={12} />
          </button>
        </div>
      </div>

      {installMsg && (
        <div className="dep-banner-details" style={{ borderTop: '1px solid var(--border)' }}>
          <span style={{ color: installMsg.includes('failed') ? 'var(--danger)' : 'var(--success)', fontSize: 12 }}>
            {installMsg}
          </span>
        </div>
      )}

      {expanded && (
        <div className="dep-banner-details">
          <div className="dep-banner-section">
            <h4>Host Checks</h4>
            <ul>
              {Object.entries(status.checks).map(([name, check]) => (
                <li key={name}>
                  <span style={{ color: check.available ? 'var(--success)' : (check.required ? 'var(--danger)' : 'var(--warning)') }}>
                    {check.available ? '✓' : '✗'} {name}
                  </span>
                  <span className="dep-banner-source"> — {check.description}</span>
                  {!check.available && check.required && !check.auto_installable && (
                    <span className="dep-banner-msg">Install manually and ensure it is on PATH</span>
                  )}
                  {!check.available && check.auto_installable && (
                    <span className="dep-banner-msg">Can be auto-installed</span>
                  )}
                </li>
              ))}
            </ul>
          </div>
        </div>
      )}
    </div>
  );
}
