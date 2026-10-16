// Track recently-opened workflows in localStorage so the user can jump back
// without rummaging through templates or workspace files.

import { browserStorageKey, LOCAL_BROWSER_STORAGE_SCOPE, type BrowserStorageScope } from '../utils/browserStorageScope';

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
  /** Free-form user tags so a workflow can be grouped/filtered in recents. */
  tags?: string[];
}

type Listener = () => void;
const listeners = new Set<Listener>();

function readStorage(scope = LOCAL_BROWSER_STORAGE_SCOPE): RecentWorkflow[] {
  if (typeof window === 'undefined') return [];
  const key = browserStorageKey(STORAGE_KEY, scope);
  if (!key) return [];
  try {
    const raw = window.localStorage.getItem(key);
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

function writeStorage(entries: RecentWorkflow[], scope: BrowserStorageScope) {
  if (typeof window === 'undefined') return;
  const key = browserStorageKey(STORAGE_KEY, scope);
  if (!key) return;
  try {
    window.localStorage.setItem(key, JSON.stringify(entries.slice(0, MAX_ENTRIES)));
  } catch {
    // Storage may be full or disabled; recents are a convenience only.
  }
}

export function getRecentWorkflows(scope = LOCAL_BROWSER_STORAGE_SCOPE): RecentWorkflow[] {
  return readStorage(scope).sort((a, b) => b.openedAt - a.openedAt);
}

export function rememberRecentWorkflow(entry: Omit<RecentWorkflow, 'openedAt'> & { openedAt?: number }, scope = LOCAL_BROWSER_STORAGE_SCOPE): void {
  const stamped: RecentWorkflow = { ...entry, openedAt: entry.openedAt ?? Date.now() };
  const existing = readStorage(scope).filter(item => item.id !== stamped.id);
  writeStorage([stamped, ...existing], scope);
  listeners.forEach(listener => listener());
}

/**
 * Set the tags on an existing recent entry without bumping its position in
 * the list. Returns false if the entry isn't tracked yet (the caller should
 * fall back to rememberRecentWorkflow).
 */
export function setRecentTags(id: string, tags: string[], scope = LOCAL_BROWSER_STORAGE_SCOPE): boolean {
  const entries = readStorage(scope);
  const next = entries.map(entry => entry.id === id ? { ...entry, tags: tags.slice() } : entry);
  if (next.every((entry, i) => entry === entries[i])) return false;
  writeStorage(next, scope);
  listeners.forEach(listener => listener());
  return true;
}

/**
 * Refresh the thumbnail (and optionally other display-only fields) on an
 * existing recent entry without bumping its position in the list. Used by
 * autosave so the recents thumbnail tracks the live workflow as the user
 * edits it.
 */
export function refreshRecentThumbnail(id: string, thumbnailUrl: string, extras?: Partial<Pick<RecentWorkflow, 'name' | 'nodeCount'>>, scope = LOCAL_BROWSER_STORAGE_SCOPE): void {
  const entries = readStorage(scope);
  let changed = false;
  const next = entries.map(entry => {
    if (entry.id !== id) return entry;
    changed = true;
    return { ...entry, thumbnailUrl, ...(extras || {}) };
  });
  if (!changed) return;
  writeStorage(next, scope);
  listeners.forEach(listener => listener());
}

export function forgetRecentWorkflow(id: string, scope = LOCAL_BROWSER_STORAGE_SCOPE): void {
  const next = readStorage(scope).filter(item => item.id !== id);
  writeStorage(next, scope);
  listeners.forEach(listener => listener());
}

export function clearRecentWorkflows(scope = LOCAL_BROWSER_STORAGE_SCOPE): void {
  writeStorage([], scope);
  listeners.forEach(listener => listener());
}

export function subscribeRecentWorkflows(listener: Listener): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}
