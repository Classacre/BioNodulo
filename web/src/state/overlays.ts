// Tracks mounted modal/dropdown/popover overlays so global shortcut handlers
// can skip while the user is interacting with one. The bridge installed in
// App.tsx watches the DOM and updates the count.

let overlayCount = 0;

function setOverlayCount(next: number): void {
  overlayCount = Math.max(0, next);
}

export function hasOpenOverlay(): boolean {
  return overlayCount > 0;
}

const DOM_OVERLAY_SELECTORS = ['.modal-overlay', '.bn-ui-overlay', '[data-overlay="true"]'].join(',');

export function installDomOverlayBridge(): () => void {
  if (typeof document === 'undefined' || typeof MutationObserver === 'undefined') {
    return () => undefined;
  }
  const refresh = () => {
    setOverlayCount(document.querySelectorAll(DOM_OVERLAY_SELECTORS).length);
  };
  refresh();
  const observer = new MutationObserver(refresh);
  observer.observe(document.body, { childList: true, subtree: true });
  return () => observer.disconnect();
}
