// Per-user node bookmarks. Lets users star nodes from the palette and
// surface them in a dedicated "Bookmarks" section at the top of the
// NodeLibraryPanel — saves the "where was that node again?" cost on
// repeatedly-used workflows.
//
// We keep this separate from useNodeUsageStats (auto-tracked frequency)
// because:
//   - bookmarks are an explicit user signal, not derived
//   - users may want a niche node visible even if they've only used it
//     once, or hide a frequently-used node they don't actually like
// The two stores compose in the palette: Bookmarks first, then Most Used,
// then the regular categorised tree.

const STORAGE_KEY = 'bionodulo.nodeBookmarks';

type Listener = () => void;
const listeners = new Set<Listener>();

function readSet(): Set<string> {
  if (typeof localStorage === 'undefined') return new Set();
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return new Set();
    const parsed = JSON.parse(raw) as unknown;
    if (!Array.isArray(parsed)) return new Set();
    return new Set(parsed.filter((value): value is string => typeof value === 'string'));
  } catch {
    return new Set();
  }
}

function writeSet(set: Set<string>): void {
  if (typeof localStorage === 'undefined') return;
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(Array.from(set)));
  } catch {
    /* quota; bookmarks aren't critical */
  }
  listeners.forEach(listener => listener());
}

export function isNodeBookmarked(type: string): boolean {
  return readSet().has(type);
}

export function listNodeBookmarks(): string[] {
  return Array.from(readSet()).sort();
}

export function toggleNodeBookmark(type: string): boolean {
  const set = readSet();
  const next = !set.has(type);
  if (next) set.add(type);
  else set.delete(type);
  writeSet(set);
  return next;
}

export function setNodeBookmark(type: string, enabled: boolean): void {
  const set = readSet();
  if (enabled && set.has(type)) return;
  if (!enabled && !set.has(type)) return;
  if (enabled) set.add(type);
  else set.delete(type);
  writeSet(set);
}

export function clearNodeBookmarks(): void {
  writeSet(new Set());
}

export function subscribeNodeBookmarks(listener: Listener): () => void {
  listeners.add(listener);
  return () => { listeners.delete(listener); };
}
