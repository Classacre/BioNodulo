import type { NodeMetadata, ObjectInfo } from '../types';
import { normalizeNodeKnowledge } from './nodeKnowledge';

export type RelationKind = 'format' | 'category' | 'citation' | 'tool' | 'topic' | 'operation'
  | 'alternative_to' | 'complements' | 'documented_successor' | 'superseded_by';
export interface ToolRelation {
  source: string;
  target: string;
  kind: RelationKind;
  value: string;
  sourcePort?: string;
  targetPort?: string;
  evidence?: { url: string; checked_at: string; note: string };
}
export interface ToolGraphIndex {
  nodes: ObjectInfo;
  categories: Map<string, string[]>;
  inputs: Map<string, Array<{ id: string; port: string }>>;
  outputs: Map<string, Array<{ id: string; port: string }>>;
  citations: Map<string, string[]>;
  tools: Map<string, string[]>;
  topics: Map<string, string[]>;
  operations: Map<string, string[]>;
  documented: Map<string, ToolRelation[]>;
}
// Primitive parameters and unconstrained paths would connect almost everything.
const genericTypes = new Set([
  '', '*', 'ANY', 'STRING', 'STR', 'INT', 'INTEGER', 'FLOAT', 'NUMBER', 'BOOLEAN', 'BOOL',
  'FILE', 'FILES', 'FILE_LIST', 'FILE[]', 'DIRECTORY', 'FOLDER', 'PATH', 'JSON', 'OBJECT', 'DICT', 'LIST', 'COMBO', 'TXT', 'TEXT', 'TABLE',
]);
export function graphPortType(type: string): string | undefined {
  const normalized = type.trim().toUpperCase();
  return genericTypes.has(normalized) ? undefined : normalized;
}
export function graphPortTypes(type: string): string[] {
  // The registry encodes declared union types with '|'. Keep list cardinality
  // and compressed formats distinct; do not invent conversion edges.
  return [...new Set(type.split('|').map(graphPortType).filter((value): value is string => Boolean(value)))];
}
export function normalizeDoi(value: string): string {
  return value.trim().replace(/^https?:\/\/(?:dx\.)?doi\.org\//i, '').replace(/^doi:\s*/i, '').toLowerCase();
}
function push<T>(map: Map<string, T[]>, key: string, value: T) {
  const bucket = map.get(key);
  if (bucket) bucket.push(value);
  else map.set(key, [value]);
}
export function buildToolGraphIndex(objectInfo: ObjectInfo): ToolGraphIndex {
  const index: ToolGraphIndex = {
    nodes: {}, categories: new Map(), inputs: new Map(), outputs: new Map(),
    citations: new Map(), tools: new Map(), topics: new Map(), operations: new Map(), documented: new Map(),
  };
  // Use registry keys, not display names or aliases, as workflow identities.
  for (const [id, raw] of Object.entries(objectInfo).sort(([a], [b]) => a.localeCompare(b))) {
    if (!raw.builtin || raw.registry_origin || raw.declarative_runtime?.kind === 'biotools-reference') continue;
    const meta = { ...raw, id, knowledge: normalizeNodeKnowledge(raw.knowledge) };
    index.nodes[id] = meta;
    push(index.categories, meta.category || 'Other', id);
    for (const [port, spec] of Object.entries({ ...meta.input_types?.required, ...meta.input_types?.optional })) {
      for (const type of graphPortTypes(spec.type)) push(index.inputs, type, { id, port });
    }
    for (const [i, type] of (meta.return_types || []).entries()) {
      for (const format of graphPortTypes(type)) push(index.outputs, format, { id, port: meta.return_names?.[i] || String(i) });
    }
    for (const doi of new Set((meta.citation_dois || []).map(normalizeDoi).filter(Boolean))) push(index.citations, doi, id);
    if (meta.knowledge?.tool_id) push(index.tools, meta.knowledge.tool_id, id);
    for (const term of meta.knowledge?.topics || []) push(index.topics, term.uri, id);
    for (const term of meta.knowledge?.operations || []) push(index.operations, term.uri, id);
  }
  for (const meta of Object.values(index.nodes)) {
    for (const relation of meta.knowledge?.relations || []) {
      if (!index.nodes[relation.target_node_id] || relation.target_node_id === meta.id) continue;
      const edge: ToolRelation = {
        source: meta.id, target: relation.target_node_id, kind: relation.kind,
        value: relation.evidence.note, evidence: relation.evidence,
        sourcePort: relation.source_port, targetPort: relation.target_port,
      };
      push(index.documented, meta.id, edge);
      push(index.documented, relation.target_node_id, edge);
    }
  }
  return index;
}

export function relatedTools(index: ToolGraphIndex, id: string): ToolRelation[] {
  const meta = index.nodes[id];
  if (!meta) return [];
  const relations: ToolRelation[] = [...(index.documented.get(id) || [])];
  const addShared = (kind: RelationKind, value: string, ids: string[] | undefined) => {
    for (const target of ids || []) if (target !== id) relations.push({ source: id, target, kind, value });
  };
  for (const [port, spec] of Object.entries({ ...meta.input_types?.required, ...meta.input_types?.optional })) {
    for (const type of graphPortTypes(spec.type)) {
      for (const upstream of index.outputs.get(type) || []) {
        if (upstream.id !== id) relations.push({ source: upstream.id, target: id, kind: 'format', value: type, sourcePort: upstream.port, targetPort: port });
      }
    }
  }
  for (const [i, format] of (meta.return_types || []).entries()) {
    for (const type of graphPortTypes(format)) {
      for (const downstream of index.inputs.get(type) || []) {
        if (downstream.id !== id) relations.push({ source: id, target: downstream.id, kind: 'format', value: type, sourcePort: meta.return_names?.[i] || String(i), targetPort: downstream.port });
      }
    }
  }
  addShared('category', meta.category || 'Other', index.categories.get(meta.category || 'Other'));
  for (const doi of new Set((meta.citation_dois || []).map(normalizeDoi))) addShared('citation', doi, index.citations.get(doi));
  if (meta.knowledge?.tool_id) addShared('tool', meta.knowledge.tool_id, index.tools.get(meta.knowledge.tool_id));
  for (const term of meta.knowledge?.topics || []) addShared('topic', term.label, index.topics.get(term.uri));
  for (const term of meta.knowledge?.operations || []) addShared('operation', term.label, index.operations.get(term.uri));
  const key = (r: ToolRelation) => JSON.stringify([r.source, r.target, r.kind, r.value, r.sourcePort, r.targetPort]);
  return [...new Map(relations.map(r => [key(r), r])).values()].sort((a, b) => key(a).localeCompare(key(b)));
}

export function neighborId(relation: ToolRelation, focus: string): string {
  return relation.source === focus ? relation.target : relation.source;
}

export function graphCoverage(index: ToolGraphIndex) {
  const nodes = Object.values(index.nodes);
  return {
    nodes: nodes.length,
    categories: index.categories.size,
    withReferences: nodes.filter(m => m.citation_dois?.length || m.citation_urls?.length || m.citation_text).length,
    withSourceChecks: nodes.filter(m => m.knowledge?.citation_evidence?.length).length,
    withKnowledge: nodes.filter(m => m.knowledge).length,
  };
}

export function isDeprecated(meta: NodeMetadata): boolean {
  return Boolean(meta.deprecated || meta.lifecycle?.deprecated || meta.lifecycle?.status === 'deprecated');
}
