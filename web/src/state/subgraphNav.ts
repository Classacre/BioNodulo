// Subgraph drill-down navigation state.
//
// A stack of { nodeId, title } from the root workflow down to the subgraph the
// canvas is currently inside (ComfyUI-style). nodeIds are the RAW ids at each
// level (never the namespaced canvas ids). The stack is owned by one workflow
// tab: when the active workflow id changes the stack is treated as empty, so
// switching tabs never leaves the canvas stranded inside another workflow's
// subgraph.

import { atom } from 'jotai';

export interface SubgraphNavLevel {
  nodeId: string;
  title: string;
}

export interface SubgraphNavState {
  /** Workflow (tab) id this stack belongs to. */
  owner: string | null;
  stack: SubgraphNavLevel[];
}

/** Matches the engine's own nesting bound; the UI guards long before it. */
export const MAX_NAV_DEPTH = 100;

export const subgraphNavAtom = atom<SubgraphNavState>({ owner: null, stack: [] });

/** Effective stack for a workflow id — empty when the stack belongs elsewhere. */
export function navStackFor(state: SubgraphNavState, workflowId: string | null): SubgraphNavLevel[] {
  if (!workflowId || state.owner !== workflowId) return [];
  return state.stack;
}

/** Push one level (enter a subgraph). No-ops past MAX_NAV_DEPTH. */
export const enterSubgraphAtom = atom(
  null,
  (_get, set, payload: { owner: string; level: SubgraphNavLevel }) => {
    set(subgraphNavAtom, (prev) => {
      const stack = prev.owner === payload.owner ? prev.stack : [];
      if (stack.length >= MAX_NAV_DEPTH) return prev;
      return { owner: payload.owner, stack: [...stack, payload.level] };
    });
  },
);

/**
 * Jump to a stack depth: `depth` is how many levels REMAIN (0 = root). Used by
 * the breadcrumb (root crumb -> 0, crumb i -> i + 1) and the back button
 * (depth = current length - 1).
 */
export const jumpToDepthAtom = atom(
  null,
  (_get, set, payload: { owner: string; depth: number }) => {
    set(subgraphNavAtom, (prev) => {
      if (prev.owner !== payload.owner) return prev;
      const depth = Math.max(0, Math.min(payload.depth, prev.stack.length));
      if (depth === prev.stack.length) return prev;
      return { ...prev, stack: prev.stack.slice(0, depth) };
    });
  },
);

/** Pop one level (Esc). */
export const exitSubgraphAtom = atom(null, (get, set, owner: string) => {
  const stack = get(subgraphNavAtom).stack;
  set(jumpToDepthAtom, { owner, depth: stack.length - 1 });
});

export const resetSubgraphNavAtom = atom(null, (_get, set) => {
  set(subgraphNavAtom, { owner: null, stack: [] });
});

// ---------------------------------------------------------------------------
// Per-level viewport cache (zoom/pan restored when navigating back) and IO
// panel positions. Module-level: UI conveniences, not document state, so they
// deliberately live outside the undo history and the saved workflow.

export interface CachedViewport {
  x: number;
  y: number;
  zoom: number;
}

const viewportCache = new Map<string, CachedViewport>();
const panelPositionCache = new Map<string, { inputs?: [number, number]; outputs?: [number, number] }>();

function navKey(owner: string | null, path: string[]): string {
  return `${owner ?? ''}::${path.join('.')}`;
}

export function cacheViewport(owner: string | null, path: string[], viewport: CachedViewport): void {
  viewportCache.set(navKey(owner, path), viewport);
}

export function readCachedViewport(owner: string | null, path: string[]): CachedViewport | null {
  return viewportCache.get(navKey(owner, path)) ?? null;
}

export function cachePanelPositions(
  owner: string | null,
  path: string[],
  positions: { inputs?: [number, number]; outputs?: [number, number] },
): void {
  panelPositionCache.set(navKey(owner, path), {
    ...panelPositionCache.get(navKey(owner, path)),
    ...positions,
  });
}

export function readPanelPositions(
  owner: string | null,
  path: string[],
): { inputs?: [number, number]; outputs?: [number, number] } | null {
  return panelPositionCache.get(navKey(owner, path)) ?? null;
}
