/**
 * Which workflow tabs were open, so reopening the app restores that and nothing
 * else.
 *
 * The first attempt at this recorded *dismissals* and skipped them when
 * restoring. That could never be authoritative: anything closed before the
 * feature existed was never recorded, so those tabs kept coming back, and the
 * list only ever grew. Recording what is open inverts it — the restored set is
 * exactly the set that was there, and a tab closed at any point in the past is
 * simply absent from it.
 *
 * Per-browser, not stored on the workflow: which tabs you have open is a fact
 * about your screen, and a teammate should not gain or lose a tab because of
 * what you did on yours.
 */

const STORAGE_KEY = 'bionodulo.workflows.open';

/** Matches the editor's tab cap; a longer list is not restorable anyway. */
const MAX_TABS = 8;

/**
 * Ids that were open, oldest first, or `null` when nothing was ever recorded.
 *
 * `null` and `[]` mean different things: never-recorded means fall back to
 * showing recent work, whereas an empty list means the user closed everything
 * and should get an empty editor rather than a wall of restored tabs.
 */
export function readOpenWorkflows(): string[] | null {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (raw === null) return null;
    const parsed = JSON.parse(raw) as unknown;
    if (!Array.isArray(parsed)) return null;
    return parsed.filter((id): id is string => typeof id === 'string').slice(0, MAX_TABS);
  } catch {
    // Private mode or corrupt data: fall back to recent work rather than
    // showing an empty editor and looking like the workflows are gone.
    return null;
  }
}

/** Record the currently open tabs. Safe to call on every change. */
export function writeOpenWorkflows(ids: string[]): void {
  try {
    const unique = [...new Set(ids.filter(Boolean))].slice(0, MAX_TABS);
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(unique));
  } catch {
    /* Nothing to do; the next visit falls back to recent work. */
  }
}
