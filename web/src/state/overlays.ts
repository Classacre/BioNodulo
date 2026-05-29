// Tracks how many modal/dropdown/popover overlays are currently open so global
// shortcut handlers can skip when the user is interacting with one. Overlays
// can register either explicitly via `pushOverlay()` or implicitly by mounting
// a DOM node with `.modal-overlay` / `[data-overlay]` — the bridge installed
// in App.tsx watches the DOM and reflects the count automatically.

let overlayCount = 0;
const listeners = new Set<(count: number) => void>();

function emit() {
  for (const listener of listeners) listener(overlayCount);
}

export function pushOverlay(): () => void {
  overlayCount += 1;
  emit();
  let released = false;
  return () => {
    if (released) return;
    released = true;
    overlayCount = Math.max(0, overlayCount - 1);
    emit();
  };
}

export function setOverlayCount(next: number): void {
  if (next === overlayCount) return;
  overlayCount = Math.max(0, next);
  emit();
}

export function hasOpenOverlay(): boolean {
  return overlayCount > 0;
}

export function getOverlayCount(): number {
  return overlayCount;
}

export function subscribeOverlays(listener: (count: number) => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
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
