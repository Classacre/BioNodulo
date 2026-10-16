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

/** Bound corrupted records without dropping ordinary multi-document sessions. */
export const MAX_OPEN_WORKFLOWS = 64;
const MAX_RECORD_BYTES = 64 * 1024;

export interface OpenWorkflowRecord {
  version: 1;
  openIds: string[];
  activeId: string | null;
}

function validId(id: unknown): id is string {
  return typeof id === 'string' && id.length <= 256 && id.trim().length > 0;
}

function normalizeRecord(ids: unknown[], selected: unknown): OpenWorkflowRecord {
  const unique = [...new Set(ids.filter(validId))];
  const activeId = validId(selected) && unique.includes(selected) ? selected : null;
  const openIds = unique.slice(0, MAX_OPEN_WORKFLOWS);
  // Even a capped/corrupt oversized record must retain its selected document.
  if (activeId && !openIds.includes(activeId)) openIds[MAX_OPEN_WORKFLOWS - 1] = activeId;
  return { version: 1, openIds, activeId };
}

/** Read current records and the legacy ID-only arrays, without migrating on read. */
export function readOpenWorkflowRecord(scope?: string | null): OpenWorkflowRecord | null {
  if (scope === null) return null;
  try {
    const raw = window.localStorage.getItem(scope ? `${STORAGE_KEY}.${scope}` : STORAGE_KEY);
    if (raw === null || raw.length > MAX_RECORD_BYTES) return null;
    const parsed: unknown = JSON.parse(raw);
    if (Array.isArray(parsed)) return normalizeRecord(parsed, null);
    if (!parsed || typeof parsed !== 'object') return null;
    const record = parsed as Partial<OpenWorkflowRecord>;
    if (record.version !== 1 || !Array.isArray(record.openIds)) return null;
    return normalizeRecord(record.openIds, record.activeId);
  } catch {
    return null;
  }
}

/**
 * Ids that were open, oldest first, or `null` when nothing was ever recorded.
 *
 * `null` and `[]` mean different things: never-recorded means fall back to
 * showing recent work, whereas an empty list means the user closed everything
 * and should get an empty editor rather than a wall of restored tabs.
 */
export function readOpenWorkflows(scope?: string | null): string[] | null {
  return readOpenWorkflowRecord(scope)?.openIds ?? null;
}

/** Record the currently open tabs. Safe to call on every change. */
export function writeOpenWorkflows(ids: string[], scope?: string | null, activeId: string | null = null): void {
  if (scope === null) return;
  try {
    const record = normalizeRecord(ids, activeId);
    window.localStorage.setItem(scope ? `${STORAGE_KEY}.${scope}` : STORAGE_KEY, JSON.stringify(record));
  } catch {
    /* Nothing to do; the next visit falls back to recent work. */
  }
}
