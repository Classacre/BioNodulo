// Snippet library: a flat copy of one or more nodes + their interconnecting
// edges captured under a name. Unlike subgraph blueprints (which collapse a
// selection into one composite node), a snippet stamps the original nodes
// back onto the canvas with fresh ids — useful for "I want this exact 4-node
// QC sub-pipeline somewhere else in the workflow."
//
// Storage shape is intentionally similar to subgraphLibrary so the two can
// share UI conventions, but kept as a separate file because the semantics
// (flat paste vs collapsed encapsulation) are different enough that mixing
// them in one store would lead to surprising behaviour.

import type { WorkflowNode, WorkflowEdge } from '../types';
import { browserStorageKey, LOCAL_BROWSER_STORAGE_SCOPE, type BrowserStorageScope } from '../utils/browserStorageScope';

const STORAGE_KEY = 'bionodulo.workflowSnippets';
const MAX_ENTRIES = 100;

export interface WorkflowSnippet {
  id: string;
  name: string;
  description?: string;
  createdAt: number;
  nodes: WorkflowNode[];
  edges: WorkflowEdge[];
}

type Listener = () => void;
const listeners = new Set<Listener>();

function emit(): void {
  for (const listener of listeners) listener();
}

function readStorage(scope: BrowserStorageScope): WorkflowSnippet[] {
  if (typeof window === 'undefined') return [];
  const key = browserStorageKey(STORAGE_KEY, scope);
  if (!key) return [];
  try {
    const raw = window.localStorage.getItem(key);
    if (!raw) return [];
    const parsed = JSON.parse(raw) as unknown;
    if (!Array.isArray(parsed)) return [];
    return parsed
      .filter((entry): entry is WorkflowSnippet => (
        Boolean(entry)
        && typeof entry === 'object'
        && typeof (entry as WorkflowSnippet).id === 'string'
        && typeof (entry as WorkflowSnippet).name === 'string'
        && Array.isArray((entry as WorkflowSnippet).nodes)
      ))
      .slice(0, MAX_ENTRIES);
  } catch {
    return [];
  }
}

function writeStorage(entries: WorkflowSnippet[], scope: BrowserStorageScope): void {
  if (typeof window === 'undefined') return;
  const key = browserStorageKey(STORAGE_KEY, scope);
  if (!key) return;
  try {
    window.localStorage.setItem(key, JSON.stringify(entries.slice(0, MAX_ENTRIES)));
  } catch {
    /* quota; the library is a convenience */
  }
  emit();
}

export function listWorkflowSnippets(scope = LOCAL_BROWSER_STORAGE_SCOPE): WorkflowSnippet[] {
  return readStorage(scope).sort((a, b) => b.createdAt - a.createdAt);
}

export function saveWorkflowSnippet(snippet: Omit<WorkflowSnippet, 'id' | 'createdAt'>, scope = LOCAL_BROWSER_STORAGE_SCOPE): WorkflowSnippet {
  const entry: WorkflowSnippet = {
    ...snippet,
    id: `snippet_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`,
    createdAt: Date.now(),
  };
  const existing = readStorage(scope);
  writeStorage([entry, ...existing], scope);
  return entry;
}

export function deleteWorkflowSnippet(id: string, scope = LOCAL_BROWSER_STORAGE_SCOPE): void {
  const existing = readStorage(scope);
  writeStorage(existing.filter(entry => entry.id !== id), scope);
}

export function subscribeWorkflowSnippets(listener: Listener): () => void {
  listeners.add(listener);
  return () => { listeners.delete(listener); };
}

/**
 * Instantiate a snippet at the given world position. Returns the new nodes +
 * edges with fresh ids so caller can append them to its workflow state.
 */
export function instantiateSnippet(snippet: WorkflowSnippet, atWorld: { x: number; y: number }):
  { nodes: WorkflowNode[]; edges: WorkflowEdge[] } {
  // Re-id every node and remap edge endpoints so dropping the same snippet
  // multiple times doesn't collide. Anchor the paste at `atWorld` by shifting
  // every node by the same delta from the snippet's bounding-box origin.
  let minX = Infinity;
  let minY = Infinity;
  for (const node of snippet.nodes) {
    minX = Math.min(minX, node.position[0]);
    minY = Math.min(minY, node.position[1]);
  }
  if (!Number.isFinite(minX)) { minX = 0; minY = 0; }
  const dx = atWorld.x - minX;
  const dy = atWorld.y - minY;

  const idMap = new Map<string, string>();
  for (const node of snippet.nodes) {
    idMap.set(node.id, `${node.type}_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`);
  }

  const nodes: WorkflowNode[] = snippet.nodes.map(node => ({
    ...node,
    id: idMap.get(node.id)!,
    position: [node.position[0] + dx, node.position[1] + dy] as [number, number],
  }));

  const edges: WorkflowEdge[] = snippet.edges
    .filter(edge => idMap.has(edge.from.node) && idMap.has(edge.to.node))
    .map(edge => ({
      ...edge,
      id: `e_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`,
      from: { ...edge.from, node: idMap.get(edge.from.node)! },
      to: { ...edge.to, node: idMap.get(edge.to.node)! },
    }));

  return { nodes, edges };
}
