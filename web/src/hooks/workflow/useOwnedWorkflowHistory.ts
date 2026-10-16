import { useCallback, useEffect, useRef } from 'react';
import type { Workflow } from '../../types';

export type WorkflowHistorySnapshot = Pick<Workflow, 'nodes' | 'edges' | 'groups' | 'parameters'> & {
  viewport?: { x: number; y: number; scale: number };
};

interface HistorySession {
  owner: unknown;
  documentId: string;
  valid: boolean;
  workflow: Workflow | null;
  snapshots: WorkflowHistorySnapshot[];
  index: number;
  pending: Partial<Workflow>;
}

/** Opaque epoch: returning to the same owner never revives an older closure. */
export function useOwnershipEpoch(identity: string, accountId: string | null, invite: unknown): object {
  const current = useRef({ identity, accountId, invite });
  if (current.current.identity !== identity || current.current.accountId !== accountId || current.current.invite !== invite) {
    current.current = { identity, accountId, invite };
  }
  return current.current;
}

function snapshot(workflow: Workflow): WorkflowHistorySnapshot {
  return { nodes: workflow.nodes, edges: workflow.edges, groups: workflow.groups, parameters: workflow.parameters };
}

function signature(value: WorkflowHistorySnapshot): string {
  return JSON.stringify([
    value.nodes.map(node => [node.id, node.type, node.position, node.params, node.ui]),
    value.edges.map(edge => [edge.from.node, edge.from.output, edge.to.node, edge.to.input]),
    value.groups.map(group => [group.id, group.name, group.position, group.width, group.height, group.color, group.collapsed]),
    value.parameters ?? [],
  ]);
}

/** Volatile history belongs to one owner epoch and one stable document ID. */
export function useOwnedWorkflowHistory({ owner, documentId, workflow, getViewport, apply }: {
  owner: unknown;
  documentId: string;
  workflow: Workflow;
  getViewport: () => WorkflowHistorySnapshot['viewport'];
  apply: (value: WorkflowHistorySnapshot) => void;
}) {
  const current = useRef<HistorySession | null>(null);
  if (!current.current || current.current.owner !== owner || current.current.documentId !== documentId) {
    // Invalidate during render: old DOM listeners/timers can fire before effect
    // cleanup. Replacing A with a fresh A after B must not revive A's closures.
    if (current.current) {
      current.current.valid = false;
      current.current.pending = {};
      current.current.snapshots = [];
      current.current.index = -1;
      current.current.workflow = null;
    }
    current.current = { owner, documentId, valid: true, workflow,
      snapshots: [snapshot(workflow)], index: 0, pending: {} };
  }
  const session = current.current;
  session.workflow = workflow;
  const latest = useRef({ getViewport, apply });
  latest.current = { getViewport, apply };

  const isCurrent = useCallback(() => current.current === session && session.valid, [session]);
  const queuePatch = useCallback((patch: Partial<Workflow>): boolean => {
    if (!isCurrent() || !session.workflow) return false;
    // Seed from the loaded graph immediately before its first edit, rather
    // than an earlier same-ID bootstrap placeholder. Viewport alone adds no step.
    if (session.snapshots.length === 1 && session.index === 0 && !Object.keys(session.pending).length) {
      session.snapshots[0] = { ...snapshot(session.workflow), viewport: latest.current.getViewport() };
    }
    session.pending = { ...session.pending, ...patch };
    return true;
  }, [isCurrent, session]);

  const pushHistory = useCallback(() => {
    if (!isCurrent() || !session.workflow || !Object.keys(session.pending).length) return;
    const nextWorkflow = { ...session.workflow, ...session.pending };
    session.pending = {};
    session.workflow = nextWorkflow;
    const next = { ...snapshot(nextWorkflow), viewport: latest.current.getViewport() };
    const tip = session.snapshots[session.index];
    if (tip && signature(tip) === signature(next)) {
      if (next.viewport) tip.viewport = next.viewport;
      return;
    }
    session.snapshots = session.snapshots.slice(0, session.index + 1);
    session.snapshots.push(next);
    if (session.snapshots.length > 50) session.snapshots.shift();
    session.index = session.snapshots.length - 1;
  }, [isCurrent, session]);

  const commitPatch = useCallback((patch: Partial<Pick<Workflow, 'nodes' | 'edges' | 'groups' | 'parameters'>>): boolean => {
    if (!isCurrent()) return false;
    // A discrete action must not merge into an earlier, still-debounced edit.
    pushHistory();
    if (!queuePatch(patch)) return false;
    pushHistory();
    latest.current.apply(session.snapshots[session.index]);
    return true;
  }, [isCurrent, pushHistory, queuePatch, session]);

  const move = useCallback((direction: -1 | 1) => {
    if (!isCurrent()) return;
    // Undo immediately after an edit must work before the 350 ms debounce.
    pushHistory();
    const index = session.index + direction;
    if (!isCurrent() || index < 0 || index >= session.snapshots.length) return;
    session.index = index;
    const value = session.snapshots[index];
    session.pending = {};
    session.workflow = { ...session.workflow!, ...value };
    latest.current.apply(value);
  }, [isCurrent, pushHistory, session]);
  const undo = useCallback(() => move(-1), [move]);
  const redo = useCallback(() => move(1), [move]);

  useEffect(() => {
    if (!Object.keys(session.pending).length) return;
    const timer = setTimeout(pushHistory, 350);
    return () => clearTimeout(timer);
  }, [workflow.nodes, workflow.edges, workflow.groups, workflow.parameters, session, pushHistory]);

  useEffect(() => {
    session.valid = true;
    window.addEventListener('mouseup', pushHistory);
    window.addEventListener('keyup', pushHistory);
    return () => {
      session.valid = false;
      window.removeEventListener('mouseup', pushHistory);
      window.removeEventListener('keyup', pushHistory);
    };
  }, [session, pushHistory]);

  return { queuePatch, pushHistory, commitPatch, undo, redo, isCurrent };
}
