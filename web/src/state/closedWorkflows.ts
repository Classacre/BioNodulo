/**
 * Workflows the user has closed, so reopening the app does not bring them back.
 *
 * The cloud editor hydrates tabs from the team's most-recently-updated
 * workflows. Closing a tab only removed it from React state, so the next visit
 * opened it again — the editor had no memory of the decision, and a user with
 * many workflows was handed back a wall of tabs they had already dismissed.
 *
 * Dismissal is per-browser rather than stored on the workflow: closing a tab is
 * a statement about your own screen, not about the workflow, and a teammate
 * should not lose a tab because you closed yours.
 */

const STORAGE_KEY = 'bionodulo.workflows.closed';

/** Bound the list so a long-lived browser cannot grow it without limit. */
const MAX_REMEMBERED = 200;

function read(): string[] {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw) as unknown;
    return Array.isArray(parsed) ? parsed.filter((id): id is string => typeof id === 'string') : [];
  } catch {
    // Private mode or corrupt JSON: behave as though nothing was closed, which
    // shows too many tabs rather than hiding work.
    return [];
  }
}

function write(ids: string[]): void {
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(ids.slice(-MAX_REMEMBERED)));
  } catch {
    /* Nothing to do; the tab simply reappears next visit. */
  }
}

/** Remember that the user closed this workflow's tab. */
export function rememberClosed(id: string): void {
  if (!id) return;
  const ids = read().filter(existing => existing !== id);
  ids.push(id);
  write(ids);
}

/**
 * Forget the dismissal, because the user has deliberately opened it again.
 *
 * Without this, reopening a workflow from the Open dialog would work for the
 * session and then silently vanish on the next visit.
 */
export function forgetClosed(id: string): void {
  if (!id) return;
  write(read().filter(existing => existing !== id));
}

export function isClosed(id: string): boolean {
  return read().includes(id);
}

/** Ids to skip when restoring tabs. */
export function closedIds(): Set<string> {
  return new Set(read());
}
