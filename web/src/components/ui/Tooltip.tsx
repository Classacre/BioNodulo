import type { CSSProperties, ReactNode } from 'react';
import { useEffect, useId, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { useFoundationStyles } from './FoundationStyles';

export type TooltipPlacement = 'top' | 'right' | 'bottom' | 'left';

export interface TooltipProps {
  children: ReactNode;
  content: ReactNode;
  placement?: TooltipPlacement;
  delay?: number;
  disabled?: boolean;
  className?: string;
}

function getTooltipStyle(rect: DOMRect, placement: TooltipPlacement): CSSProperties {
  const gap = 8;
  if (placement === 'right') {
    return { left: rect.right + gap, top: rect.top + rect.height / 2, transform: 'translateY(-50%)' };
  }
  if (placement === 'bottom') {
    return { left: rect.left + rect.width / 2, top: rect.bottom + gap, transform: 'translateX(-50%)' };
  }
  if (placement === 'left') {
    return { left: rect.left - gap, top: rect.top + rect.height / 2, transform: 'translate(-100%, -50%)' };
  }
  return { left: rect.left + rect.width / 2, top: rect.top - gap, transform: 'translate(-50%, -100%)' };
}

export function Tooltip({
  children,
  content,
  placement = 'top',
  delay = 350,
  disabled = false,
  className = '',
}: TooltipProps) {
  useFoundationStyles();
  const id = useId();
  const triggerRef = useRef<HTMLSpanElement | null>(null);
  const timeoutRef = useRef<number | null>(null);
  const [open, setOpen] = useState(false);
  const [rect, setRect] = useState<DOMRect | null>(null);

  const show = () => {
    if (disabled) return;
    if (timeoutRef.current) window.clearTimeout(timeoutRef.current);
    timeoutRef.current = window.setTimeout(() => {
      const nextRect = triggerRef.current?.getBoundingClientRect();
      if (nextRect) {
        setRect(nextRect);
        setOpen(true);
      }
    }, delay);
  };

  const hide = () => {
    if (timeoutRef.current) window.clearTimeout(timeoutRef.current);
    timeoutRef.current = null;
    setOpen(false);
  };

  useEffect(() => {
    if (!open) return;
    const update = () => {
      const nextRect = triggerRef.current?.getBoundingClientRect();
      if (nextRect) setRect(nextRect);
    };
    window.addEventListener('scroll', update, true);
    window.addEventListener('resize', update);
    return () => {
      window.removeEventListener('scroll', update, true);
      window.removeEventListener('resize', update);
    };
  }, [open]);

  useEffect(() => () => {
    if (timeoutRef.current) window.clearTimeout(timeoutRef.current);
  }, []);

  return (
    <>
      <span
        aria-describedby={open ? id : undefined}
        className={`bn-ui-tooltip-trigger ${className}`.trim()}
        onBlur={hide}
        onFocus={show}
        onMouseEnter={show}
        onMouseLeave={hide}
        ref={triggerRef}
      >
        {children}
      </span>
      {open && rect && typeof document !== 'undefined'
        ? createPortal(
          <div className="bn-ui-tooltip" id={id} role="tooltip" style={getTooltipStyle(rect, placement)}>
            {content}
          </div>,
          document.body,
        )
        : null}
    </>
  );
}

export default Tooltip;
