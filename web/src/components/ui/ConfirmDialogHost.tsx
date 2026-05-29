import { useEffect, useMemo, useState } from 'react';
import { createPortal } from 'react-dom';
import { useTranslation } from 'react-i18next';
import '../../i18n';
import { resolveDialog, useDialogQueue } from '../../state/dialogs';
import { useFoundationStyles } from './FoundationStyles';

export function ConfirmDialogHost() {
  useFoundationStyles();
  const { t } = useTranslation();
  const queue = useDialogQueue();
  const dialog = queue[0];
  const [promptValue, setPromptValue] = useState('');
  const title = useMemo(() => {
    if (!dialog) return '';
    if (dialog.title) return dialog.title;
    if (dialog.kind === 'alert') return t('dialogs.alertTitle');
    if (dialog.kind === 'prompt') return t('dialogs.promptTitle');
    return t('dialogs.confirmTitle');
  }, [dialog, t]);

  useEffect(() => {
    setPromptValue(dialog?.kind === 'prompt' ? dialog.defaultValue ?? '' : '');
  }, [dialog?.id, dialog?.kind, dialog?.defaultValue]);

  useEffect(() => {
    if (!dialog) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.preventDefault();
        resolveDialog(dialog.id, dialog.kind === 'prompt' ? null : false);
      }
      if (event.key === 'Enter' && dialog.kind === 'alert') {
        event.preventDefault();
        resolveDialog(dialog.id, true);
      }
      if (event.key === 'Enter' && dialog.kind === 'prompt') {
        event.preventDefault();
        resolveDialog(dialog.id, promptValue);
      }
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [dialog, promptValue]);

  if (typeof document === 'undefined' || !dialog) return null;

  const confirmLabel = dialog.confirmLabel ?? (dialog.kind === 'alert' ? t('common.ok') : dialog.kind === 'prompt' ? t('common.save') : t('common.confirm'));
  const cancelLabel = dialog.cancelLabel ?? t('common.cancel');
  const primaryClass = dialog.tone === 'danger'
    ? 'bn-ui-button bn-ui-button-danger'
    : 'bn-ui-button bn-ui-button-primary';

  return createPortal(
    <div className="bn-ui-overlay" role="presentation" onMouseDown={() => resolveDialog(dialog.id, dialog.kind === 'prompt' ? null : false)}>
      <section
        aria-describedby={`bn-dialog-message-${dialog.id}`}
        aria-labelledby={`bn-dialog-title-${dialog.id}`}
        aria-modal="true"
        className="bn-ui-dialog"
        onMouseDown={event => event.stopPropagation()}
        role="dialog"
      >
        <header className="bn-ui-dialog-header">
          <div className="bn-ui-dialog-title" id={`bn-dialog-title-${dialog.id}`}>{title}</div>
        </header>
        <div className="bn-ui-dialog-body" id={`bn-dialog-message-${dialog.id}`}>
          {dialog.message}
          {dialog.kind === 'prompt' ? (
            <label className="bn-ui-dialog-field">
              {dialog.inputLabel ? <span>{dialog.inputLabel}</span> : null}
              <input
                autoFocus
                className="bn-ui-dialog-input"
                onChange={event => setPromptValue(event.target.value)}
                placeholder={dialog.placeholder}
                value={promptValue}
              />
            </label>
          ) : null}
        </div>
        <footer className="bn-ui-dialog-footer">
          {dialog.kind !== 'alert' ? (
            <button className="bn-ui-button" onClick={() => resolveDialog(dialog.id, dialog.kind === 'prompt' ? null : false)} type="button">
              {cancelLabel}
            </button>
          ) : null}
          <button className={primaryClass} onClick={() => resolveDialog(dialog.id, dialog.kind === 'prompt' ? promptValue : true)} type="button">
            {confirmLabel}
          </button>
        </footer>
      </section>
    </div>,
    document.body,
  );
}

export default ConfirmDialogHost;
