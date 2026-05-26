// Track recently-opened workflows in localStorage so the user can jump back
// without rummaging through templates or workspace files.

const STORAGE_KEY = 'bionodulo.recentWorkflows';
const MAX_ENTRIES = 12;

export interface RecentWorkflow {
  id: string;
  name: string;
  source: 'template' | 'import' | 'collab' | 'workspace' | 'manual';
  openedAt: number;
  filename?: string;
  thumbnailUrl?: string;
  nodeCount?: number;
}

type Listener = () => void;
const listeners = new Set<Listener>();

function readStorage(): RecentWorkflow[] {
  if (typeof window === 'undefined') return [];
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed
      .filter((entry: unknown): entry is RecentWorkflow => (
        Boolean(entry)
        && typeof entry === 'object'
        && typeof (entry as RecentWorkflow).id === 'string'
        && typeof (entry as RecentWorkflow).name === 'string'
        && typeof (entry as RecentWorkflow).openedAt === 'number'
      ))
      .slice(0, MAX_ENTRIES);
  } catch {
    return [];
  }
}

function writeStorage(entries: RecentWorkflow[]) {
  if (typeof window === 'undefined') return;
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(entries.slice(0, MAX_ENTRIES)));
  } catch {
    // Storage may be full or disabled; recents are a convenience only.
  }
}

export function getRecentWorkflows(): RecentWorkflow[] {
  return readStorage().sort((a, b) => b.openedAt - a.openedAt);
}

export function rememberRecentWorkflow(entry: Omit<RecentWorkflow, 'openedAt'> & { openedAt?: number }): void {
  const stamped: RecentWorkflow = { ...entry, openedAt: entry.openedAt ?? Date.now() };
  const existing = readStorage().filter(item => item.id !== stamped.id);
  writeStorage([stamped, ...existing]);
  listeners.forEach(listener => listener());
}

export function forgetRecentWorkflow(id: string): void {
  const next = readStorage().filter(item => item.id !== id);
  writeStorage(next);
  listeners.forEach(listener => listener());
}

export function clearRecentWorkflows(): void {
  writeStorage([]);
  listeners.forEach(listener => listener());
}

export function subscribeRecentWorkflows(listener: Listener): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}
