import { useState, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import Icon from '../ui/Icon';
import type { HostStatus } from '../../types';
import { apiPost } from '../../api/client';
import { logError } from '../../state/logging';

interface Props {
  status: HostStatus;
  onDismiss: () => void;
  onOpenConsole: () => void;
  onRecheck: () => void;
}

export default function HostPrerequisitesBanner({ status, onDismiss, onOpenConsole, onRecheck }: Props) {
  const { t } = useTranslation();
  const [expanded, setExpanded] = useState(false);
  const [installing, setInstalling] = useState(false);
  const [installMsg, setInstallMsg] = useState<string | null>(null);
  const [installMsgKind, setInstallMsgKind] = useState<'success' | 'error' | null>(null);

  const handleInstall = useCallback(async () => {
    setInstalling(true);
    setInstallMsg(null);
    setInstallMsgKind(null);
    onOpenConsole();
    try {
      const data = await apiPost<{ success?: boolean; already_installed?: boolean; message?: string }>('/host_status/install-pixi');
      if (data.success) {
        setInstallMsg(data.already_installed ? t('hostStatus.alreadyInstalled') : t('hostStatus.installedSuccessfully'));
        setInstallMsgKind('success');
      } else {
        setInstallMsg(t('hostStatus.installFailed'));
        setInstallMsgKind('error');
      }
    } catch (err) {
      logError('hostStatus.installPixi', err);
      setInstallMsg(t('hostStatus.installRequestFailed'));
      setInstallMsgKind('error');
    } finally {
      setInstalling(false);
      onRecheck();
    }
  }, [onOpenConsole, onRecheck, t]);

  const missingRequired = status.missing_required || [];

  return (
    <div className="dep-banner" style={{ borderLeft: '3px solid var(--danger)' }}>
      <div className="dep-banner-row">
        <span className="dep-banner-icon">
          <Icon name="warning" size={16} />
        </span>
        <span className="dep-banner-text">
          <strong>{t('hostStatus.prerequisiteMissingTitle')}</strong>{' '}
          {status.message || t('hostStatus.requiredToolsMissing', { count: missingRequired.length })}
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
                  <Icon name="spinner" size={12} /> {t('hostStatus.installing')}
                </>
              ) : (
                <>
                  <Icon name="download" size={12} /> {t('hostStatus.autoInstallPixi')}
                </>
              )}
            </button>
          )}
          <button className="btn btn-sm" onClick={() => setExpanded(v => !v)}>
            {expanded ? t('common.hide') : t('resolveReport.details')}
          </button>
          <button className="btn btn-sm btn-ghost" onClick={onDismiss} title={t('common.dismiss')} aria-label={t('common.dismiss')}>
            <Icon name="close" size={12} />
          </button>
        </div>
      </div>

      {installMsg && (
        <div className="dep-banner-details" style={{ borderTop: '1px solid var(--border)' }}>
          <span style={{ color: installMsgKind === 'error' ? 'var(--danger)' : 'var(--success)', fontSize: 12 }}>
            {installMsg}
          </span>
        </div>
      )}

      {expanded && (
        <div className="dep-banner-details">
          <div className="dep-banner-section">
            <h4>{t('hostStatus.hostChecks')}</h4>
            <ul>
              {Object.entries(status.checks).map(([name, check]) => (
                <li key={name}>
                  <span style={{ color: check.available ? 'var(--success)' : (check.required ? 'var(--danger)' : 'var(--warning)') }}>
                    {check.available ? '✓' : '✗'} {name}
                  </span>
                  <span className="dep-banner-source"> — {check.description}</span>
                  {!check.available && check.required && !check.auto_installable && (
                    <span className="dep-banner-msg">{t('hostStatus.installManually')}</span>
                  )}
                  {!check.available && check.auto_installable && (
                    <span className="dep-banner-msg">{t('hostStatus.canAutoInstall')}</span>
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
