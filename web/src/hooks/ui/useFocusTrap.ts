import { useEffect, useRef, type RefObject } from 'react';

const FOCUSABLE_SELECTOR = [
  'a[href]:not([tabindex="-1"])',
  'button:not([disabled]):not([tabindex="-1"])',
  'input:not([disabled]):not([type="hidden"]):not([tabindex="-1"])',
  'select:not([disabled]):not([tabindex="-1"])',
  'textarea:not([disabled]):not([tabindex="-1"])',
  '[tabindex]:not([tabindex="-1"])',
  '[contenteditable="true"]:not([tabindex="-1"])',
].join(',');

function getFocusable(container: HTMLElement): HTMLElement[] {
  return Array.from(container.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR))
    .filter(el => !el.hasAttribute('inert') && el.offsetParent !== null);
}

/**
 * Trap keyboard focus inside `containerRef` while `active` is true. On
 * activation, focus moves into the container (first focusable element, or the
 * container itself). When the user reaches the end with Tab — or the start
 * with Shift+Tab — focus wraps to the other end. When the trap is released
 * (active flips to false or the component unmounts), focus is restored to
 * whichever element had it before.
 */
export function useFocusTrap(
  containerRef: RefObject<HTMLElement | null>,
  active: boolean,
  onEscape?: () => void,
): void {
  // Keep the escape handler in a ref so a parent re-render (which hands us a
  // fresh callback identity) does not re-run the trap effect: the cleanup
  // restores focus to whatever was focused before the dialog opened, which
  // used to steal focus from the dialog's inputs on every keystroke.
  const escapeRef = useRef(onEscape);
  useEffect(() => {
    escapeRef.current = onEscape;
  }, [onEscape]);

  useEffect(() => {
    if (!active) return;
    const container = containerRef.current;
    if (!container) return;
    const previouslyFocused = document.activeElement instanceof HTMLElement ? document.activeElement : null;

    // Defer focus assignment so the modal has had a chance to mount fully.
    const initialTimer = window.setTimeout(() => {
      const focusable = getFocusable(container);
      const target = focusable[0] ?? container;
      if (target instanceof HTMLElement) {
        if (!container.hasAttribute('tabindex') && target === container) {
          container.setAttribute('tabindex', '-1');
        }
        target.focus({ preventScroll: false });
      }
    }, 0);

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape' && escapeRef.current) {
        event.stopPropagation();
        event.preventDefault();
        escapeRef.current();
        return;
      }
      if (event.key !== 'Tab') return;
      const focusable = getFocusable(container);
      if (focusable.length === 0) {
        event.preventDefault();
        container.focus();
        return;
      }
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      const active = document.activeElement;
      if (event.shiftKey) {
        if (active === first || !container.contains(active)) {
          event.preventDefault();
          last.focus();
        }
      } else {
        if (active === last || !container.contains(active)) {
          event.preventDefault();
          first.focus();
        }
      }
    };

    container.addEventListener('keydown', onKeyDown);
    return () => {
      window.clearTimeout(initialTimer);
      container.removeEventListener('keydown', onKeyDown);
      if (previouslyFocused && document.body.contains(previouslyFocused)) {
        previouslyFocused.focus({ preventScroll: true });
      }
    };
  }, [active, containerRef]);
}
