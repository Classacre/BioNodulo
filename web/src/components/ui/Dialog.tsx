// Generic dialog primitive used by feature modals (Export, Import, Output
// Diff, ...). Codifies the conventions that were copy-pasted across modal
// files: an overlay div that closes on backdrop click, an inner content div
// with role="dialog"/aria-modal, focus trap with ESC handling, and stacked
// z-index so a child dialog renders above its parent.

import { useEffect, useId, useMemo, useRef, useState, type CSSProperties, type ReactNode } from 'react';
import { useTranslation } from 'react-i18next';
import { useFocusTrap } from '../../hooks/ui';
import {
  pushDialog,
  popDialog,
  dialogZIndex,
  isTopDialog,
  subscribeDialogStack,
} from '../../state/dialogStack';

export interface DialogProps {
  /** Visible label / aria-label. */
  title: string;
  /** Optional sub-header content (description, tabs, ...). */
  header?: ReactNode;
  /** Footer row, typically Cancel / Confirm buttons. */
  footer?: ReactNode;
  children: ReactNode;
  /** Called when the user dismisses the dialog (backdrop, ESC, X button). */
  onClose: () => void;
  /** Suppress backdrop-click close. ESC still works unless `dismissable=false`. */
  dismissOnBackdrop?: boolean;
  /** Disable all close paths (use for confirm-required flows). */
  dismissable?: boolean;
  /** Width in px. Defaults to 600. */
  width?: number;
  /** Max height. Defaults to '80vh'. */
  maxHeight?: string | number;
  /** Hide the close (×) button. */
  hideCloseButton?: boolean;
  /** Extra className on the inner content. */
  className?: string;
  /** Extra inline styles on the inner content. */
  style?: CSSProperties;
}

export function Dialog({
  title,
  header,
  footer,
  children,
  onClose,
  dismissOnBackdrop = true,
  dismissable = true,
  width = 600,
  maxHeight = '80vh',
  hideCloseButton = false,
  className,
  style,
}: DialogProps) {
  const { t } = useTranslation();
  const dialogRef = useRef<HTMLDivElement>(null);
  const id = useId();

  // Register with the stack on mount; pop on unmount.
  useEffect(() => {
    pushDialog(id);
    return () => popDialog(id);
  }, [id]);

  // Re-render when stack changes so isTopDialog/dialogZIndex stay live.
  const [stackVersion, setStackVersion] = useState(0);
  useEffect(() => subscribeDialogStack(() => setStackVersion(v => v + 1)), []);

  const isTop = isTopDialog(id);
  const zIndex = useMemo(() => dialogZIndex(id), [id, stackVersion]);

  // Only the topmost dialog should respond to Escape so a stack of modals
  // closes one layer at a time rather than collapsing en masse.
  const handleEscape = dismissable && isTop ? onClose : undefined;
  useFocusTrap(dialogRef, true, handleEscape);

  const handleBackdrop = () => {
    if (!dismissable || !dismissOnBackdrop || !isTop) return;
    onClose();
  };

  return (
    <div
      className="modal-overlay"
      onClick={handleBackdrop}
      style={{ zIndex }}
    >
      <div
        ref={dialogRef}
        className={`modal-content ${className || ''}`.trim()}
        role="dialog"
        aria-modal="true"
        aria-label={title}
        style={{ width, maxHeight, ...(style || {}) }}
        onClick={e => e.stopPropagation()}
      >
        <div className="modal-header" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <span>{title}</span>
          {!hideCloseButton && dismissable && (
            <button
              type="button"
              className="btn btn-icon btn-sm"
              onClick={onClose}
              aria-label={t('common.close')}
              style={{ background: 'transparent', border: 'none', cursor: 'pointer', fontSize: 16, color: 'var(--muted)' }}
            >
              ×
            </button>
          )}
        </div>
        {header && <div className="modal-subheader">{header}</div>}
        <div className="modal-body">{children}</div>
        {footer && <div className="modal-footer">{footer}</div>}
      </div>
    </div>
  );
}

export default Dialog;
