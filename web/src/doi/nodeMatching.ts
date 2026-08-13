// Pure helpers for the DOI→workflow flow: map an AI-suggested tool name onto a
// real node type from the loaded registry, and wire "A -> B" suggestions into
// type-compatible edges. Kept React-free so the logic is unit-testable.
import Fuse from 'fuse.js';
import type { NodeMetadata, ObjectInfo, WorkflowEdge, WorkflowNode } from '../types';

export interface SuggestedNode {
  name: string;
  category: string;
  reason: string;
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
 * Order: exact id/display-name/alias hit → fuzzy (Fuse) hit → note fallback.
 */
export function matchToolToNodeType(
  name: string,
  category: string | undefined,
  objectInfo: ObjectInfo,
): NodeTypeMatch {
  const entries = Object.entries(objectInfo);
  const wanted = normalize(name);
  const wantedCompact = wanted.replace(/ /g, '');

  if (wanted) {
    for (const [type, meta] of entries) {
      if (normalize(type).replace(/ /g, '') === wantedCompact) {
        return { type, meta, fellBackToNote: false };
      }
      if (normalize(meta.display_name).replace(/ /g, '') === wantedCompact) {
        return { type, meta, fellBackToNote: false };
      }
      for (const alias of meta.search_aliases ?? []) {
        if (normalize(alias).replace(/ /g, '') === wantedCompact) {
          return { type, meta, fellBackToNote: false };
        }
      }
    }
  }

  const fuse = new Fuse(
    entries.map(([type, meta]) => ({ type, meta })),
    {
      includeScore: true,
      ignoreLocation: true,
      threshold: 0.3,
      keys: [
        { name: 'meta.display_name', weight: 0.4 },
        { name: 'type', weight: 0.3 },
        { name: 'meta.search_aliases', weight: 0.25 },
        { name: 'meta.category', weight: 0.05 },
      ],
    },
  );
  const query = category ? `${name} ${category}` : name;
  const [best] = fuse.search(query);
  if (best && (best.score ?? 1) <= 0.3) {
    return { type: best.item.type, meta: best.item.meta, fellBackToNote: false };
  }
  return { type: NOTE_NODE_TYPE, meta: objectInfo[NOTE_NODE_TYPE] ?? null, fellBackToNote: true };
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
  const score = (p: PlacedNode): number => {
    const candidate = normalize(p.label).replace(/ /g, '');
    if (candidate === wanted) return 0;
    if (candidate.includes(wanted) || wanted.includes(candidate)) return 1;
    return 2;
  };
  let best: PlacedNode | null = null;
  let bestScore = 2;
  for (const p of placed) {
    const s = score(p);
    if (s < bestScore) {
      best = p;
      bestScore = s;
    }
  }
  return best;
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
  return a === b || a === '*' || b === '*' || a === 'ANY' || b === 'ANY';
}

/**
 * Wire "A -> B" suggestions into edges between placed nodes. Picks the first
 * type-compatible output→input port pair; silently skips connections that
 * match no nodes or no compatible ports — a missing edge is recoverable, a
 * broken one crashes the canvas.
 */
export function wireSuggestion(
  placed: PlacedNode[],
  connections: string[],
  objectInfo: ObjectInfo,
): WorkflowEdge[] {
  const edges: WorkflowEdge[] = [];
  for (const raw of connections) {
    const parsed = parseConnection(raw);
    if (!parsed) continue;
    const [fromLabel, toLabel] = parsed;
    const from = matchPlaced(fromLabel, placed);
    const to = matchPlaced(toLabel, placed);
    if (!from || !to) continue;

    const fromMeta = objectInfo[from.node.type];
    const toMeta = objectInfo[to.node.type];
    const pair = ((): { out: Port; inp: Port } | null => {
      for (const out of outputsOf(fromMeta)) {
        for (const inp of inputsOf(toMeta)) {
          if (typesCompatible(out.type, inp.type)) return { out, inp };
        }
      }
      return null;
    })();
    if (!pair) continue;

    edges.push({
      id: `doi-e${edges.length}`,
      from: { node: from.node.id, output: pair.out.name },
      to: { node: to.node.id, input: pair.inp.name },
    });
  }
  return edges;
}
