// Per-node-type parameter presets.
//
// Saves a named snapshot of a node's params keyed by its node type, so a
// user can capture "my aligner default args" once and apply them to any
// future instance of the same node. Distinct from workflow snippets:
//   - snippets   = a copy of one or more nodes + edges, dropped flat
//   - presets    = a param-bag applied onto an existing node in place
//
// We key by node type (not display name) because two custom nodes can
// share a display name when their internal ids differ.

const STORAGE_KEY = 'bionodulo.nodePresets';

export interface NodePreset {
  id: string;
  name: string;
  nodeType: string;
  params: Record<string, unknown>;
  createdAt: number;
}

type Map_ = Record<string, NodePreset[]>;
type Listener = () => void;
const listeners = new Set<Listener>();

function readMap(): Map_ {
  if (typeof localStorage === 'undefined') return {};
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return {};
    const parsed = JSON.parse(raw) as unknown;
    if (!parsed || typeof parsed !== 'object') return {};
    return parsed as Map_;
  } catch {
    return {};
  }
}

function writeMap(map: Map_): void {
  if (typeof localStorage === 'undefined') return;
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(map));
  } catch {
    /* quota; presets are a convenience */
  }
  listeners.forEach(listener => listener());
}

export function listPresetsForType(nodeType: string): NodePreset[] {
  const map = readMap();
  return (map[nodeType] || []).slice().sort((a, b) => b.createdAt - a.createdAt);
}

export function savePreset(nodeType: string, name: string, params: Record<string, unknown>): NodePreset {
  const preset: NodePreset = {
    id: `preset_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`,
    name,
    nodeType,
    params: JSON.parse(JSON.stringify(params)) as Record<string, unknown>,
    createdAt: Date.now(),
  };
  const map = readMap();
  map[nodeType] = [preset, ...(map[nodeType] || [])].slice(0, 30);
  writeMap(map);
  return preset;
}

export function deletePreset(nodeType: string, id: string): void {
  const map = readMap();
  if (!map[nodeType]) return;
  map[nodeType] = map[nodeType].filter(p => p.id !== id);
  if (map[nodeType].length === 0) delete map[nodeType];
  writeMap(map);
}

export function subscribeNodePresets(listener: Listener): () => void {
  listeners.add(listener);
  return () => { listeners.delete(listener); };
}
