// Local subgraph "blueprint" library. Saved subgraph nodes get persisted to
// localStorage and surfaced in the node library under a Subgraphs section so
// users can drag them onto any workflow.
//
// A blueprint is just a captured snapshot of one subgraph node — the embedded
// inner workflow plus its synthesized port shape. Instantiating a blueprint
// creates a fresh subgraph node with a new id but the same contents.

import type { Workflow, WorkflowNode } from '../types';
import type { SubgraphPort } from '../utils/subgraph';

const STORAGE_KEY = 'bionodulo.subgraphLibrary';
const MAX_ENTRIES = 100;

export interface SubgraphBlueprint {
  id: string;
  name: string;
  description?: string;
  createdAt: number;
  workflow: Workflow;
  inputPorts: SubgraphPort[];
  outputPorts: SubgraphPort[];
  /** Optional thumbnail PNG dataURL captured at save time. */
  thumbnail?: string;
}

type Listener = () => void;
const listeners = new Set<Listener>();

function emit() {
  for (const listener of listeners) listener();
}

function readStorage(): SubgraphBlueprint[] {
  if (typeof window === 'undefined') return [];
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed
      .filter((entry: unknown): entry is SubgraphBlueprint => (
        Boolean(entry)
        && typeof entry === 'object'
        && typeof (entry as SubgraphBlueprint).id === 'string'
        && typeof (entry as SubgraphBlueprint).name === 'string'
        && (entry as SubgraphBlueprint).workflow !== undefined
      ))
      .slice(0, MAX_ENTRIES);
  } catch {
    return [];
  }
}

function writeStorage(entries: SubgraphBlueprint[]) {
  if (typeof window === 'undefined') return;
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(entries.slice(0, MAX_ENTRIES)));
  } catch {
    // ignore quota errors; library is a convenience.
  }
}

export function listBlueprints(): SubgraphBlueprint[] {
  return readStorage().sort((a, b) => b.createdAt - a.createdAt);
}

export function saveBlueprint(blueprint: Omit<SubgraphBlueprint, 'createdAt' | 'id'> & { id?: string }): SubgraphBlueprint {
  const id = blueprint.id ?? `bp_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`;
  const stamped: SubgraphBlueprint = { ...blueprint, id, createdAt: Date.now() };
  const next = [stamped, ...readStorage().filter(item => item.id !== id)];
  writeStorage(next);
  emit();
  return stamped;
}

export function deleteBlueprint(id: string): void {
  const next = readStorage().filter(item => item.id !== id);
  writeStorage(next);
  emit();
}

export function subscribeBlueprints(listener: Listener): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

/**
 * Instantiate a blueprint as a fresh subgraph node ready to drop on the
 * canvas. The new node has a new id but the same embedded workflow + ports.
 */
export function instantiateBlueprint(blueprint: SubgraphBlueprint, position: [number, number]): WorkflowNode {
  const id = `subgraph_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`;
  const inputTypesRequired: Record<string, [string, Record<string, unknown>]> = {};
  for (const port of blueprint.inputPorts) {
    inputTypesRequired[port.name] = [port.type, { description: `${port.innerNodeId}.${port.innerSlot}` }];
  }
  return {
    id,
    type: 'subgraph',
    position,
    params: {
      workflow: blueprint.workflow,
      input_ports: blueprint.inputPorts,
      output_ports: blueprint.outputPorts,
      blueprint_id: blueprint.id,
    } as unknown as Record<string, unknown>,
    node_info: {
      id: 'subgraph',
      display_name: blueprint.name,
      category: 'Subgraph',
      input_types: { required: inputTypesRequired as never },
      return_types: blueprint.outputPorts.map(p => p.type) as never,
      return_names: blueprint.outputPorts.map(p => p.name) as never,
    } as WorkflowNode['node_info'],
    ui: { title: blueprint.name, color: '#6366f1', shape: 'card' },
  };
}
