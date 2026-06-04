// Pluggable history store for workflow editors.
//
// Replaces the old naive JSON-stringify-deep-clone version. App.tsx already
// has an inline equivalent of this hook hard-wired into its render loop; the
// goal here is to ship a reusable equivalent so future components (subgraph
// editors, snippet editors, plugins) can wire their own undo/redo without
// re-implementing the same dedup + viewport + transaction logic.
//
// Differences from the old hook
// -----------------------------
// 1. structuredClone instead of JSON.parse(JSON.stringify(...)). Faster, and
//    correctly preserves undefined / Date / Map / Set values that may live
//    in node params.
// 2. Stable signature dedup. push() is a no-op when the candidate matches
//    the current tip — selection toggles and drag-end events no longer
//    flood the history stack.
// 3. Viewport captured in every snapshot. undo/redo restore the pan+zoom
//    the user had when they made the change.
// 4. begin() / commit() transactions. Many sequential push() calls inside
//    a transaction collapse into a single snapshot at commit so the user
//    undoes the whole gesture at once (e.g. paste-many, drag-many).
//
// The hook stays UI-agnostic — the consumer reads the next snapshot from
// `undo()` / `redo()` and is responsible for applying it (including the
// viewport restore).

import { useCallback, useEffect, useRef, useState } from 'react';
import type { Workflow } from '../../types';

export interface Viewport {
  x: number;
  y: number;
  scale: number;
}

export interface HistorySnapshot {
  workflow: Workflow;
  viewport: Viewport | undefined;
  sig: string;
}

export interface UseHistoryOptions {
  /** Maximum number of stack entries to retain. Defaults to 50. */
  limit?: number;
  /** Override the signature function (mostly useful for tests). */
  signatureFn?: (workflow: Workflow) => string;
}

export interface UseHistoryReturn {
  /** Push a new snapshot. No-op when the signature matches the current tip. */
  push: (workflow: Workflow, viewport?: Viewport) => void;
  /** Begin a transaction. All pushes until commit() collapse into one. */
  begin: () => () => void;
  /** Pop the previous snapshot. Returns it (or null if at the bottom). */
  undo: () => HistorySnapshot | null;
  /** Re-apply the next snapshot. Returns it (or null at the top). */
  redo: () => HistorySnapshot | null;
  canUndo: boolean;
  canRedo: boolean;
}

function defaultSignature(workflow: Workflow): string {
  return JSON.stringify([
    workflow.nodes.map((n) => [n.id, n.type, n.position, n.params, n.ui]),
    workflow.edges.map((e) => [e.from.node, e.from.output, e.to.node, e.to.input]),
    (workflow.groups ?? []).map((g) => [g.id, g.name, g.position, g.width, g.height, g.color, g.collapsed]),
    workflow.parameters ?? [],
  ]);
}

function cloneWorkflow(workflow: Workflow): Workflow {
  if (typeof structuredClone === 'function') return structuredClone(workflow);
  // Older environments (jsdom < 24) — fall back to JSON for the tests.
  return JSON.parse(JSON.stringify(workflow)) as Workflow;
}

export function useHistory(initial: Workflow, options: UseHistoryOptions = {}): UseHistoryReturn {
  const limit = options.limit ?? 50;
  const sig = options.signatureFn ?? defaultSignature;

  const stackRef = useRef<HistorySnapshot[]>([
    { workflow: cloneWorkflow(initial), viewport: undefined, sig: sig(initial) },
  ]);
  const indexRef = useRef(0);
  const txnDepthRef = useRef(0);
  const txnPendingRef = useRef<HistorySnapshot | null>(null);

  // canUndo/canRedo are state so React re-renders the buttons that depend on them.
  const [canUndo, setCanUndo] = useState(false);
  const [canRedo, setCanRedo] = useState(false);

  const refresh = useCallback(() => {
    setCanUndo(indexRef.current > 0);
    setCanRedo(indexRef.current < stackRef.current.length - 1);
  }, []);

  const commitSnapshot = useCallback((snapshot: HistorySnapshot) => {
    const stack = stackRef.current;
    const tip = stack[indexRef.current];
    if (tip && tip.sig === snapshot.sig) {
      // No structural change — keep the existing tip but refresh its viewport
      // so a future undo lands on the latest pan/zoom.
      if (snapshot.viewport) tip.viewport = snapshot.viewport;
      return;
    }
    const next = stack.slice(0, indexRef.current + 1);
    next.push(snapshot);
    while (next.length > limit) next.shift();
    stackRef.current = next;
    indexRef.current = next.length - 1;
    refresh();
  }, [limit, refresh]);

  const push = useCallback((workflow: Workflow, viewport?: Viewport) => {
    const snapshot: HistorySnapshot = {
      workflow: cloneWorkflow(workflow),
      viewport,
      sig: sig(workflow),
    };
    if (txnDepthRef.current > 0) {
      // Inside a transaction — only the final state is committed.
      txnPendingRef.current = snapshot;
      return;
    }
    commitSnapshot(snapshot);
  }, [sig, commitSnapshot]);

  const begin = useCallback((): (() => void) => {
    txnDepthRef.current += 1;
    let committed = false;
    return () => {
      if (committed) return;
      committed = true;
      txnDepthRef.current = Math.max(0, txnDepthRef.current - 1);
      if (txnDepthRef.current === 0 && txnPendingRef.current) {
        const pending = txnPendingRef.current;
        txnPendingRef.current = null;
        commitSnapshot(pending);
      }
    };
  }, [commitSnapshot]);

  const undo = useCallback((): HistorySnapshot | null => {
    if (indexRef.current <= 0) return null;
    indexRef.current -= 1;
    refresh();
    return stackRef.current[indexRef.current] ?? null;
  }, [refresh]);

  const redo = useCallback((): HistorySnapshot | null => {
    if (indexRef.current >= stackRef.current.length - 1) return null;
    indexRef.current += 1;
    refresh();
    return stackRef.current[indexRef.current] ?? null;
  }, [refresh]);

  // Surface the initial canUndo/canRedo correctly even if the initial stack
  // happens to be longer than 1 (uncommon, but possible if a future caller
  // passes a hydrated stack).
  useEffect(() => {
    refresh();
  }, [refresh]);

  return { push, begin, undo, redo, canUndo, canRedo };
}
