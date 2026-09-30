// Pure helpers for the DOI→workflow flow: map an AI-suggested tool name onto a
// real node type from the loaded registry, and wire "A -> B" suggestions into
// type-compatible edges. Kept React-free so the logic is unit-testable.
import type { NodeMetadata, ObjectInfo, WorkflowEdge, WorkflowNode } from '../types';

export interface SuggestedNode {
  name: string;
  category: string;
  reason: string;
  /** Exact registry ID supplied by the analysis service, when validated there. */
  nodeType?: string | null;
}

export interface SuggestedConnection {
  from: string;
  to: string;
  output: string;
  input: string;
}

export interface NodeTypeMatch {
  /** Registry node type id, or 'note' when nothing matched. */
  type: string;
  meta: NodeMetadata | null;
  /** True when the suggestion is prose-only (rendered as a note node). */
  fellBackToNote: boolean;
}

const NOTE_NODE_TYPE = 'note';

function normalize(text: string): string {
  return text.toLowerCase().replace(/[^a-z0-9]+/g, ' ').trim();
}

/**
 * Find the registry node type that best matches a suggested tool name.
 * Only a registered id or display name identifies a runnable tool. Descriptions,
 * categories, aliases, and approximate similarity can describe a method without
 * identifying an executable implementation.
 */
export function matchToolToNodeType(
  name: string,
  _category: string | undefined,
  objectInfo: ObjectInfo,
  nodeType?: string | null,
): NodeTypeMatch {
  const note = (): NodeTypeMatch => ({ type: NOTE_NODE_TYPE, meta: objectInfo[NOTE_NODE_TYPE] ?? null, fellBackToNote: true });
  if (nodeType !== undefined) {
    return typeof nodeType === 'string' && nodeType !== NOTE_NODE_TYPE && Object.prototype.hasOwnProperty.call(objectInfo, nodeType)
      ? { type: nodeType, meta: objectInfo[nodeType], fellBackToNote: false }
      : note();
  }
  const entries = Object.entries(objectInfo);
  const wanted = normalize(name);
  const wantedCompact = wanted.replace(/ /g, '');

  if (wanted) {
    const matches = entries.filter(([type, meta]) =>
      normalize(type).replace(/ /g, '') === wantedCompact ||
      normalize(meta.display_name).replace(/ /g, '') === wantedCompact);
    if (matches.length === 1) return { type: matches[0][0], meta: matches[0][1], fellBackToNote: false };
  }
  return note();
}

/** Slug a suggested name into a stable node id fragment. */
export function slugify(text: string, index: number): string {
  const slug = text
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 40);
  return `${slug || 'step'}-${index}`;
}

/** Parse a suggested connection "A -> B" (also accepts →, ⇒, —>). */
export function parseConnection(raw: string): [string, string] | null {
  const parts = raw.split(/\s*(?:->|→|⇒|—>)\s*/);
  if (parts.length !== 2 || !parts[0].trim() || !parts[1].trim()) return null;
  return [parts[0].trim(), parts[1].trim()];
}

export interface PlacedNode {
  node: WorkflowNode;
  /** The suggested name this node was placed for (edge matching keys on it). */
  label: string;
}

function matchPlaced(label: string, placed: PlacedNode[]): PlacedNode | null {
  const wanted = normalize(label).replace(/ /g, '');
  if (!wanted) return null;
  const matches = placed.filter(p => normalize(p.label).replace(/ /g, '') === wanted);
  return matches.length === 1 ? matches[0] : null;
}

interface Port {
  name: string;
  type: string;
}

function outputsOf(meta: NodeMetadata | undefined | null): Port[] {
  if (!meta) return [];
  return (meta.return_types ?? []).map((type, i) => ({
    name: meta.return_names?.[i] || type,
    type,
  }));
}

function inputsOf(meta: NodeMetadata | undefined | null): Port[] {
  if (!meta) return [];
  const required = Object.entries(meta.input_types?.required ?? {});
  const optional = Object.entries(meta.input_types?.optional ?? {});
  return [...required, ...optional].map(([name, spec]) => ({
    name,
    type: String((spec as { type?: unknown })?.type ?? ''),
  }));
}

function typesCompatible(outType: string, inType: string): boolean {
  const a = outType.toUpperCase();
  const b = inType.toUpperCase();
  if (!a || !b) return false;
  return a === b || a === '*' || b === '*' || a === 'ANY' || b === 'ANY';
}

function compatiblePortPairs(fromMeta: NodeMetadata | undefined | null, toMeta: NodeMetadata | undefined | null): Array<{ out: Port; inp: Port }> {
  const pairs: Array<{ out: Port; inp: Port }> = [];
  for (const out of outputsOf(fromMeta)) {
    for (const inp of inputsOf(toMeta)) {
      if (typesCompatible(out.type, inp.type)) pairs.push({ out, inp });
    }
  }
  return pairs;
}

/**
 * Wire explicit port connections, or legacy "A -> B" links only when exactly
 * one compatible output/input pair exists. Ambiguity stays visible as an
 * unconnected step instead of guessing which scientific input was intended.
 */
export function wireSuggestion(
  placed: PlacedNode[],
  connections: Array<string | SuggestedConnection>,
  objectInfo: ObjectInfo,
): WorkflowEdge[] {
  const edges: WorkflowEdge[] = [];
  const reaches = (start: string, goal: string): boolean => {
    const pending = [start];
    const visited = new Set<string>();
    while (pending.length) {
      const current = pending.pop()!;
      if (current === goal) return true;
      if (visited.has(current)) continue;
      visited.add(current);
      for (const edge of edges) if (edge.from.node === current) pending.push(edge.to.node);
    }
    return false;
  };
  for (const raw of connections) {
    const parsed = typeof raw === 'string' ? parseConnection(raw) : null;
    if (typeof raw === 'string' && !parsed) continue;
    if (typeof raw !== 'string' && (!raw || typeof raw.from !== 'string' || typeof raw.to !== 'string' ||
      typeof raw.output !== 'string' || typeof raw.input !== 'string')) continue;
    const fromLabel = parsed ? parsed[0] : (raw as SuggestedConnection).from;
    const toLabel = parsed ? parsed[1] : (raw as SuggestedConnection).to;
    const from = matchPlaced(fromLabel, placed);
    const to = matchPlaced(toLabel, placed);
    if (!from || !to || from.node.id === to.node.id) continue;
    if (reaches(to.node.id, from.node.id)) continue;

    const fromMeta = objectInfo[from.node.type];
    const toMeta = objectInfo[to.node.type];
    const pairs = compatiblePortPairs(fromMeta, toMeta);
    const pair = parsed ? (pairs.length === 1 ? pairs[0] : null)
      : pairs.find(({ out, inp }) => out.name === (raw as SuggestedConnection).output && inp.name === (raw as SuggestedConnection).input);
    if (!pair) continue;
    if (edges.some(edge => edge.to.node === to.node.id && edge.to.input === pair.inp.name)) continue;

    edges.push({
      id: `doi-e${edges.length}`,
      from: { node: from.node.id, output: pair.out.name },
      to: { node: to.node.id, input: pair.inp.name },
    });
  }
  return edges;
}
