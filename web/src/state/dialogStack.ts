// Dialog stacking registry.
//
// Tracks open dialogs in mount order so that:
//   - z-index can ladder (each new dialog renders above the previous)
//   - Escape only closes the topmost dialog
//   - focus restoration moves to the previously-active dialog on close, not
//     necessarily to whatever had focus before *any* dialog opened
//
// The store is intentionally module-scoped — there is exactly one active
// dialog stack per app, and the Dialog component reads/writes it from its
// lifecycle hooks.

const BASE_Z_INDEX = 1000;
const Z_INDEX_STEP = 10;

type Listener = () => void;
const stack: string[] = [];
const listeners = new Set<Listener>();

function emit(): void {
  listeners.forEach(listener => {
    try { listener(); } catch { /* ignore */ }
  });
}

export function pushDialog(id: string): void {
  if (stack.includes(id)) return;
  stack.push(id);
  emit();
}

export function popDialog(id: string): void {
  const index = stack.indexOf(id);
  if (index === -1) return;
  stack.splice(index, 1);
  emit();
}

export function isTopDialog(id: string): boolean {
  return stack[stack.length - 1] === id;
}

export function dialogDepth(id: string): number {
  const index = stack.indexOf(id);
  return index === -1 ? 0 : index;
}

export function dialogZIndex(id: string): number {
  return BASE_Z_INDEX + dialogDepth(id) * Z_INDEX_STEP;
}

export function getOpenDialogs(): readonly string[] {
  return stack.slice();
}

export function hasOpenDialog(): boolean {
  return stack.length > 0;
}

export function subscribeDialogStack(listener: Listener): () => void {
  listeners.add(listener);
  return () => { listeners.delete(listener); };
}
