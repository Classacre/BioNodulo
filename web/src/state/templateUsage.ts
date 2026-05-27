// Client-side template usage tracker.
//
// The backend exposes `usage_count` per template (incremented when a template
// is loaded server-side), but local-only templates and offline sessions never
// touch the server — so popular templates the *current user* relies on would
// drift behind. This module keeps a per-template hit counter in localStorage
// that the Templates panel sums into the ranking score on top of the
// server-reported count.

const STORAGE_KEY = 'bionodulo.templateUsage';

interface UsageRecord {
  count: number;
  lastUsed: number;
}

type UsageMap = Record<string, UsageRecord>;
type Listener = () => void;
const listeners = new Set<Listener>();

function readMap(): UsageMap {
  if (typeof localStorage === 'undefined') return {};
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return {};
    const parsed = JSON.parse(raw) as unknown;
    if (!parsed || typeof parsed !== 'object') return {};
    return parsed as UsageMap;
  } catch {
    return {};
  }
}

function writeMap(map: UsageMap): void {
  if (typeof localStorage === 'undefined') return;
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(map));
  } catch {
    /* quota exceeded — usage stats are nice-to-have only */
  }
  listeners.forEach(listener => listener());
}

export function recordTemplateUse(templateId: string): void {
  if (!templateId) return;
  const map = readMap();
  const existing = map[templateId] || { count: 0, lastUsed: 0 };
  map[templateId] = { count: existing.count + 1, lastUsed: Date.now() };
  writeMap(map);
}

export function getTemplateUsageCount(templateId: string): number {
  return readMap()[templateId]?.count ?? 0;
}

export function getTemplateLastUsed(templateId: string): number {
  return readMap()[templateId]?.lastUsed ?? 0;
}

/**
 * Return the full usage map. Suitable for one-time reads in a useMemo —
 * subscribe via `subscribeTemplateUsage` if the consumer needs live updates.
 */
export function getTemplateUsageMap(): UsageMap {
  return readMap();
}

export function clearTemplateUsage(): void {
  writeMap({});
}

export function subscribeTemplateUsage(listener: Listener): () => void {
  listeners.add(listener);
  return () => { listeners.delete(listener); };
}
