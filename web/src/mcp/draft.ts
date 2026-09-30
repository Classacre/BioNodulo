import type { Workflow } from '../types';
import { record } from './host';

export interface CloudWorkflow {
  id: string;
  name: string;
  description?: string | null;
  definition: unknown;
  updatedAt: string;
}
export interface DraftState {
  saved: CloudWorkflow | null;
  draft: Workflow;
  dirty: boolean;
  conflict: CloudWorkflow | null;
  past: Workflow[];
  future: Workflow[];
}
export function newWorkflow(): Workflow {
  return {
    version: '1.0',
    app: 'BioNodulo',
    name: 'Untitled workflow',
    description: '',
    nodes: [],
    edges: [],
    groups: [],
    outputs: {},
  };
}
export function readWorkflow(value: unknown): Workflow {
  const data = record(value);
  if (!Array.isArray(data.nodes) || !Array.isArray(data.edges))
    throw new Error('A workflow must contain nodes and edges arrays.');
  const ids = new Set<string>();
  for (const item of data.nodes) {
    const node = record(item);
    if (
      typeof node.id !== 'string' ||
      ids.has(node.id) ||
      typeof node.type !== 'string' ||
      !Array.isArray(node.position) ||
      node.position.length !== 2 ||
      !node.position.every(Number.isFinite)
    )
      throw new Error('Invalid or duplicate workflow node.');
    ids.add(node.id);
  }
  for (const item of data.edges) {
    const edge = record(item);
    if (
      typeof edge.id !== 'string' ||
      !ids.has(String(record(edge.from).node)) ||
      !ids.has(String(record(edge.to).node))
    )
      throw new Error('A workflow edge references a missing node.');
  }
  return { ...newWorkflow(), ...data, nodes: data.nodes, edges: data.edges } as Workflow;
}
export function fromSaved(saved: CloudWorkflow): DraftState {
  return {
    saved,
    draft: {
      ...readWorkflow(saved.definition),
      name: saved.name,
      description: saved.description ?? '',
    },
    dirty: false,
    conflict: null,
    past: [],
    future: [],
  };
}
export function initialDraft(): DraftState {
  return { saved: null, draft: newWorkflow(), dirty: false, conflict: null, past: [], future: [] };
}
export type DraftAction =
  | { type: 'replace'; saved: CloudWorkflow }
  | { type: 'new' }
  | { type: 'edit'; patch: Partial<Workflow> }
  | { type: 'remote'; saved: CloudWorkflow }
  | { type: 'saved'; saved: CloudWorkflow; submitted: Workflow }
  | { type: 'undo' | 'redo' };
export function draftReducer(state: DraftState, action: DraftAction): DraftState {
  switch (action.type) {
    case 'new':
      return initialDraft();
    case 'replace':
      return fromSaved(action.saved);
    case 'edit': {
      const draft = { ...state.draft, ...action.patch };
      if (JSON.stringify(draft) === JSON.stringify(state.draft)) return state;
      return {
        ...state,
        draft,
        dirty: true,
        past: [...state.past, state.draft].slice(-50),
        future: [],
      };
    }
    case 'remote':
      if (action.saved.id !== state.saved?.id || action.saved.updatedAt === state.saved.updatedAt)
        return state;
      // A poll started before Save can return after Save's newer response.
      if (Date.parse(action.saved.updatedAt) < Date.parse(state.saved.updatedAt)) return state;
      return state.dirty ? { ...state, conflict: action.saved } : fromSaved(action.saved);
    case 'saved': {
      // A response to Save must not discard edits made while the request ran.
      const unchanged = JSON.stringify(state.draft) === JSON.stringify(action.submitted);
      return unchanged
        ? fromSaved(action.saved)
        : { ...state, saved: action.saved, dirty: true, conflict: null };
    }
    case 'undo': {
      const previous = state.past[state.past.length - 1];
      return previous
        ? {
            ...state,
            draft: previous,
            dirty: true,
            past: state.past.slice(0, -1),
            future: [state.draft, ...state.future],
          }
        : state;
    }
    case 'redo': {
      const next = state.future[0];
      return next
        ? {
            ...state,
            draft: next,
            dirty: true,
            past: [...state.past, state.draft],
            future: state.future.slice(1),
          }
        : state;
    }
  }
}

/** Files selected in the embedded UI are verified upload keys. The manifest
 * binds each original graph path to its upload; the server rechecks ownership. */
export function uploadBindings(
  workflow: Workflow,
  teamId?: string,
): Record<string, { uploadKey: string; kind: 'file' }> {
  const artifacts: Record<string, { uploadKey: string; kind: 'file' }> = {};
  if (!teamId) return artifacts;
  const visit = (value: unknown) => {
    if (typeof value === 'string' && value.startsWith(`uploads/${teamId}/`))
      artifacts[value] = { uploadKey: value, kind: 'file' };
    else if (Array.isArray(value)) value.forEach(visit);
    else if (value && typeof value === 'object') Object.values(value).forEach(visit);
  };
  for (const node of workflow.nodes) visit(node.params);
  return artifacts;
}
