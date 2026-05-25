import { useCallback, useEffect, useMemo, useState } from 'react';
import Fuse from 'fuse.js';
import type { NodeMetadata, ObjectInfo } from '../types';

const DEFAULT_RECENT_NODE_KEY = 'bionodulo.recentNodes';

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

export function useNodeSearch(objectInfo: ObjectInfo, query: string): NodeSearchResult[] {
  const nodes = useMemo(() => Object.values(objectInfo).sort(nodeSort), [objectInfo]);
  const normalizedQuery = query.trim();

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
    if (!normalizedQuery) {
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
        return {
          meta,
          rank,
          score: Math.max(0, (result.score ?? 0) + exactBoost + containsBoost),
        };
      })
      .sort((a, b) => a.score - b.score || a.meta.display_name.localeCompare(b.meta.display_name));
  }, [fuse, nodes, normalizedQuery]);
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
