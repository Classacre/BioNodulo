import { useCallback, useEffect, useMemo, useState } from 'react';
import Fuse from 'fuse.js';
import type { NodeMetadata, ObjectInfo } from '../types';

const DEFAULT_RECENT_NODE_KEY = 'bionodulo.recentNodes';
const DEFAULT_USAGE_STATS_KEY = 'bionodulo.nodeUsageStats';

export interface NodeSearchResult {
  meta: NodeMetadata;
  score: number;
  rank: number;
}

interface RecentNodeOptions {
  limit?: number;
  storageKey?: string;
}

function nodeSort(a: NodeMetadata, b: NodeMetadata): number {
  const category = (a.category || 'Other').localeCompare(b.category || 'Other');
  if (category !== 0) return category;
  return a.display_name.localeCompare(b.display_name);
}

function readRecentNodeIds(storageKey: string, limit: number): string[] {
  if (typeof window === 'undefined') return [];
  try {
    const raw = window.localStorage.getItem(storageKey);
    const parsed = raw ? JSON.parse(raw) : [];
    return Array.isArray(parsed)
      ? parsed.filter((id): id is string => typeof id === 'string').slice(0, limit)
      : [];
  } catch {
    return [];
  }
}

function persistRecentNodeIds(storageKey: string, ids: string[]): void {
  if (typeof window === 'undefined') return;
  try {
    window.localStorage.setItem(storageKey, JSON.stringify(ids));
  } catch {
    // Recent nodes are a convenience only; storage failures should not block node insertion.
  }
}

export function useNodeSearch(
  objectInfo: ObjectInfo,
  query: string,
  compatibleInputType?: string,
): NodeSearchResult[] {
  const nodes = useMemo(() => Object.values(objectInfo).sort(nodeSort), [objectInfo]);
  const normalizedQuery = query.trim();
  const targetType = compatibleInputType?.toUpperCase();

  // Precompute which nodes accept the dangling link's source type so the
  // ranking pass can boost them without re-scanning input_types per result.
  const compatibleNodeIds = useMemo(() => {
    if (!targetType) return null;
    const ids = new Set<string>();
    for (const meta of nodes) {
      const required = meta.input_types?.required ?? {};
      const optional = meta.input_types?.optional ?? {};
      const specs = [...Object.values(required), ...Object.values(optional)];
      const compatible = specs.some((spec) => {
        const t = String(spec.type ?? '').toUpperCase();
        return t === targetType || t === '*' || t === 'ANY';
      });
      if (compatible) ids.add(meta.id);
    }
    return ids;
  }, [nodes, targetType]);

  const fuse = useMemo(() => new Fuse(nodes, {
    includeScore: true,
    ignoreLocation: true,
    minMatchCharLength: 2,
    threshold: 0.36,
    keys: [
      { name: 'display_name', weight: 0.34 },
      { name: 'id', weight: 0.24 },
      { name: 'search_aliases', weight: 0.18 },
      { name: 'category', weight: 0.14 },
      { name: 'description', weight: 0.08 },
      { name: 'requires_external_tools', weight: 0.02 },
    ],
  }), [nodes]);

  return useMemo(() => {
    // Empty-query path: when a compatible type is known, surface compatible
    // nodes first so the palette opens straight onto useful options.
    if (!normalizedQuery) {
      if (compatibleNodeIds) {
        const ordered = [...nodes].sort((a, b) => {
          const ac = compatibleNodeIds.has(a.id) ? 0 : 1;
          const bc = compatibleNodeIds.has(b.id) ? 0 : 1;
          if (ac !== bc) return ac - bc;
          return nodeSort(a, b);
        });
        return ordered.map((meta, rank) => ({
          meta,
          rank,
          score: compatibleNodeIds.has(meta.id) ? -0.2 : 0,
        }));
      }
      return nodes.map((meta, rank) => ({ meta, rank, score: 0 }));
    }

    const q = normalizedQuery.toLowerCase();
    return fuse.search(normalizedQuery)
      .map((result, rank) => {
        const meta = result.item;
        const name = meta.display_name.toLowerCase();
        const id = meta.id.toLowerCase();
        const exactBoost = name.startsWith(q) || id.startsWith(q) ? -0.08 : 0;
        const containsBoost = name.includes(q) || id.includes(q) ? -0.03 : 0;
        // Type-compat boost: Fuse uses lower-is-better, so we subtract.
        // Tuned to 0.18 so a strong typed match outranks a weak string match
        // (Fuse threshold is 0.36) without overpowering an exact-name hit.
        const typeBoost = compatibleNodeIds?.has(meta.id) ? -0.18 : 0;
        return {
          meta,
          rank,
          score: Math.max(0, (result.score ?? 0) + exactBoost + containsBoost + typeBoost),
        };
      })
      .sort((a, b) => a.score - b.score || a.meta.display_name.localeCompare(b.meta.display_name));
  }, [fuse, nodes, normalizedQuery, compatibleNodeIds]);
}

export function useRecentNodes(
  objectInfo: ObjectInfo,
  { limit = 6, storageKey = DEFAULT_RECENT_NODE_KEY }: RecentNodeOptions = {},
) {
  const [recentIds, setRecentIds] = useState<string[]>(() => readRecentNodeIds(storageKey, limit));
  const availableIds = useMemo(() => new Set(Object.keys(objectInfo)), [objectInfo]);

  useEffect(() => {
    setRecentIds(prev => {
      const next = prev.filter(id => availableIds.has(id)).slice(0, limit);
      if (next.length === prev.length && next.every((id, idx) => id === prev[idx])) return prev;
      persistRecentNodeIds(storageKey, next);
      return next;
    });
  }, [availableIds, limit, storageKey]);

  const recentNodes = useMemo(
    () => recentIds.map(id => objectInfo[id]).filter((meta): meta is NodeMetadata => Boolean(meta)),
    [objectInfo, recentIds],
  );

  const rememberNode = useCallback((meta: NodeMetadata) => {
    setRecentIds(prev => {
      const next = [meta.id, ...prev.filter(id => id !== meta.id)].slice(0, limit);
      persistRecentNodeIds(storageKey, next);
      return next;
    });
  }, [limit, storageKey]);

  const clearRecentNodes = useCallback(() => {
    persistRecentNodeIds(storageKey, []);
    setRecentIds([]);
  }, [storageKey]);

  return { recentNodes, rememberNode, clearRecentNodes };
}

// ---------------------------------------------------------------------------
// Node usage frequency tracking
//
// Tracks how often each node has been added. Distinct from "recent" which is
// strictly insertion-ordered; this hook exposes a top-N "most used" list that
// gives discovery surfaces ([Node Library, Command Palette]) a way to
// highlight workflow-defining nodes for the current user.
// ---------------------------------------------------------------------------

export interface NodeUsageEntry {
  meta: NodeMetadata;
  count: number;
  lastUsedAt: number;
}

interface NodeUsageStatsRecord {
  count: number;
  lastUsedAt: number;
}

type StoredStats = Record<string, NodeUsageStatsRecord>;

interface UsageStatsOptions {
  limit?: number;
  storageKey?: string;
}

function readUsageStats(storageKey: string): StoredStats {
  if (typeof window === 'undefined') return {};
  try {
    const raw = window.localStorage.getItem(storageKey);
    const parsed = raw ? JSON.parse(raw) : {};
    if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) return {};
    const result: StoredStats = {};
    for (const [key, value] of Object.entries(parsed as Record<string, unknown>)) {
      if (typeof key !== 'string') continue;
      const record = value as Partial<NodeUsageStatsRecord> | null;
      if (!record || typeof record !== 'object') continue;
      const count = typeof record.count === 'number' && record.count > 0 ? Math.floor(record.count) : 0;
      const lastUsedAt = typeof record.lastUsedAt === 'number' ? record.lastUsedAt : 0;
      if (count > 0) result[key] = { count, lastUsedAt };
    }
    return result;
  } catch {
    return {};
  }
}

function persistUsageStats(storageKey: string, stats: StoredStats): void {
  if (typeof window === 'undefined') return;
  try {
    window.localStorage.setItem(storageKey, JSON.stringify(stats));
  } catch {
    // Usage stats are decoration only; failing to persist is non-fatal.
  }
}

export function useNodeUsageStats(
  objectInfo: ObjectInfo,
  { limit = 6, storageKey = DEFAULT_USAGE_STATS_KEY }: UsageStatsOptions = {},
) {
  const [stats, setStats] = useState<StoredStats>(() => readUsageStats(storageKey));

  // Prune entries for nodes that no longer exist in the registry.
  useEffect(() => {
    setStats(prev => {
      let changed = false;
      const next: StoredStats = {};
      for (const [id, record] of Object.entries(prev)) {
        if (objectInfo[id]) {
          next[id] = record;
        } else {
          changed = true;
        }
      }
      if (!changed) return prev;
      persistUsageStats(storageKey, next);
      return next;
    });
  }, [objectInfo, storageKey]);

  const frequentNodes = useMemo<NodeUsageEntry[]>(() => {
    return Object.entries(stats)
      .map(([id, record]) => ({ meta: objectInfo[id], ...record }))
      .filter((entry): entry is NodeUsageEntry => Boolean(entry.meta))
      // Sort by count desc, then by recency to break ties consistently.
      .sort((a, b) => b.count - a.count || b.lastUsedAt - a.lastUsedAt)
      .slice(0, limit);
  }, [stats, objectInfo, limit]);

  const recordNodeUsage = useCallback((meta: NodeMetadata) => {
    setStats(prev => {
      const existing = prev[meta.id];
      const next: StoredStats = {
        ...prev,
        [meta.id]: {
          count: (existing?.count ?? 0) + 1,
          lastUsedAt: Date.now(),
        },
      };
      persistUsageStats(storageKey, next);
      return next;
    });
  }, [storageKey]);

  const getNodeUsageCount = useCallback((nodeId: string): number => {
    return stats[nodeId]?.count ?? 0;
  }, [stats]);

  const clearUsageStats = useCallback(() => {
    persistUsageStats(storageKey, {});
    setStats({});
  }, [storageKey]);

  return { frequentNodes, recordNodeUsage, getNodeUsageCount, clearUsageStats };
}
