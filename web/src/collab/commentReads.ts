/**
 * Which comment threads this user has not read yet.
 *
 * Comments carry `resolved`, which is a property of the thread, not of the
 * reader: a resolved thread can still contain something you have never seen,
 * and an unresolved one can be entirely your own writing. "Unread" needs a
 * per-reader answer, so it is tracked here rather than inferred from `resolved`.
 *
 * Read state is local to the browser on purpose. It is a reading aid, not
 * shared state — syncing it would mean writing to the collab document every
 * time someone glances at a thread, and being marked read on one machine is not
 * evidence you read it on another.
 */
import type { Comment } from './types';

const STORAGE_KEY = 'bionodulo.comments.lastSeen';

type SeenMap = Record<string, number>;

function readSeen(): SeenMap {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return {};
    const parsed = JSON.parse(raw) as unknown;
    return parsed && typeof parsed === 'object' ? (parsed as SeenMap) : {};
  } catch {
    // Private mode, a locked-down profile, or corrupt JSON: treat everything as
    // unread rather than suppressing the indicator entirely.
    return {};
  }
}

function writeSeen(map: SeenMap): void {
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(map));
  } catch {
    /* Nothing to do; the badge simply keeps showing. */
  }
}

/** Record that the user has just looked at a node's thread. */
export function markThreadRead(nodeId: string, at: number = Date.now()): void {
  if (!nodeId) return;
  const seen = readSeen();
  seen[nodeId] = at;
  writeSeen(seen);
}

/** Timestamp the user last opened a thread, or 0 if never. */
export function lastSeenAt(nodeId: string): number {
  const value = readSeen()[nodeId];
  return typeof value === 'number' && Number.isFinite(value) ? value : 0;
}

function timestampOf(comment: Comment): number {
  const parsed = Date.parse(comment.created_at);
  return Number.isFinite(parsed) ? parsed : 0;
}

/**
 * Whether a thread holds anything this user has not seen.
 *
 * Your own comments never count: writing something is not a reason to be
 * nagged about it. A comment with an unparseable timestamp is treated as read,
 * so bad data cannot leave a pin bouncing forever.
 */
export function threadHasUnread(
  nodeId: string,
  thread: Comment[],
  currentUserId: string,
  seenAt: number = lastSeenAt(nodeId),
): boolean {
  const stack = [...thread];
  while (stack.length) {
    const comment = stack.pop()!;
    if (comment.replies?.length) stack.push(...comment.replies);
    if (comment.user_id === currentUserId) continue;
    if (timestampOf(comment) > seenAt) return true;
  }
  return false;
}
