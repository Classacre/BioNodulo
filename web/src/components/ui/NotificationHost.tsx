import { useEffect, useState } from 'react';
import { createPortal } from 'react-dom';
import { useTranslation } from 'react-i18next';
import '../../i18n';
import Icon from './Icon';
import { useFoundationStyles } from './FoundationStyles';
import {
  dismissNotification,
  type NotificationRecord,
  useNotifications,
} from '../../state/notifications';

function clamp(value: number) {
  return Math.max(0, Math.min(100, value));
}

function getProgress(notification: NotificationRecord, now: number) {
  if (typeof notification.progress === 'number') return clamp(notification.progress);
  if (!notification.expiresAt || !notification.duration) return null;
  return clamp(((notification.duration - Math.max(0, notification.expiresAt - now)) / notification.duration) * 100);
}

function toneIcon(tone: NotificationRecord['tone']) {
  if (tone === 'success') return 'check';
  if (tone === 'warning' || tone === 'error') return 'warning';
  if (tone === 'loading') return 'spinner';
  return 'circle';
}

export interface NotificationHostProps {
  maxVisible?: number;
}

export function NotificationHost({ maxVisible = 5 }: NotificationHostProps) {
  useFoundationStyles();
  const { t } = useTranslation();
  const notifications = useNotifications();
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    if (!notifications.some(notification => notification.expiresAt || typeof notification.progress === 'number')) return;
    const interval = window.setInterval(() => setNow(Date.now()), 120);
    return () => window.clearInterval(interval);
  }, [notifications]);

  if (typeof document === 'undefined' || notifications.length === 0) return null;

  return createPortal(
    <div className="bn-ui-toast-viewport" role="region" aria-live="polite" aria-label={t('notifications.region')}>
      {notifications.slice(0, maxVisible).map(notification => {
        const progress = getProgress(notification, now);
        return (
          <section className="bn-ui-toast" data-tone={notification.tone} key={notification.id}>
            <div className="bn-ui-toast-row">
              <span className="bn-ui-toast-icon" aria-hidden="true">
                <Icon name={toneIcon(notification.tone)} size={16} />
              </span>
              <div>
                <div className="bn-ui-toast-title">{notification.title}</div>
                {notification.message ? <div className="bn-ui-toast-message">{notification.message}</div> : null}
                {notification.actions.length ? (
                  <div className="bn-ui-toast-actions">
                    {notification.actions.map(action => (
                      <button
                        className="bn-ui-button bn-ui-button-ghost"
                        key={action.label}
                        onClick={() => {
                          action.onClick(notification.id);
                          if (action.dismiss !== false) dismissNotification(notification.id);
                        }}
                        type="button"
                      >
                        {action.label}
                      </button>
                    ))}
                  </div>
                ) : null}
              </div>
              {notification.dismissible ? (
                <button
                  aria-label={t('common.dismiss')}
                  className="bn-ui-icon-button"
                  onClick={() => dismissNotification(notification.id)}
                  type="button"
                >
                  <Icon name="close" size={14} />
                </button>
              ) : <span />}
            </div>
            {progress !== null ? (
              <div className="bn-ui-toast-progress" aria-hidden="true">
                <span style={{ width: `${progress}%` }} />
              </div>
            ) : null}
          </section>
        );
      })}
    </div>,
    document.body,
  );
}

export default NotificationHost;
