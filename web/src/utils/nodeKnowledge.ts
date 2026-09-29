// Optional descriptive evidence; never an execution or scientific compatibility contract.
export interface KnowledgeTerm { uri: string; label: string }
export interface KnowledgeEvidence { url: string; checked_at: string; note: string }
export interface KnowledgeRelation {
  target_node_id: string;
  kind: 'alternative_to' | 'complements' | 'documented_successor' | 'superseded_by';
  evidence: KnowledgeEvidence;
  source_port?: string;
  target_port?: string;
}
export interface KnowledgeCitationEvidence {
  identifier: string;
  source_url: string;
  checked_at: string;
  note: string;
}
export interface NodeKnowledge {
  schema_version: 1;
  tool_id?: string;
  topics?: KnowledgeTerm[];
  operations?: KnowledgeTerm[];
  relations?: KnowledgeRelation[];
  citation_evidence?: KnowledgeCitationEvidence[];
  reviewed_at?: string;
  introduced_at?: string;
}

const relationKinds = new Set(['alternative_to', 'complements', 'documented_successor', 'superseded_by']);
const dnsHost = /^(?=.{1,253}$)[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)+$/;

function record(value: unknown, allowed: string[], required: string[] = []): Record<string, unknown> {
  if (!value || typeof value !== 'object' || Array.isArray(value)) throw new Error('Expected object');
  const data = value as Record<string, unknown>;
  if (Object.keys(data).some(key => !allowed.includes(key)) || required.some(key => !(key in data))) {
    throw new Error('Invalid object fields');
  }
  return data;
}

function text(value: unknown, max = 2048): string {
  if (typeof value !== 'string' || !value || value !== value.trim() || value.length > max
    || [...value].some(character => character.charCodeAt(0) < 32 || character.charCodeAt(0) === 127)) {
    throw new Error('Invalid text');
  }
  return value;
}

function url(value: unknown): string {
  const source = text(value);
  if (source.includes('\\')) throw new Error('Unsafe URL');
  const parsed = new URL(source);
  const host = parsed.hostname.toLowerCase();
  if (!['http:', 'https:'].includes(parsed.protocol) || parsed.username || parsed.password
    || !dnsHost.test(host) || host.endsWith('.localhost') || host.endsWith('.local') || host.endsWith('.internal')
    || /^\d+\.\d+\.\d+\.\d+$/.test(host)) throw new Error('Unsafe URL');
  return source;
}

function isoDate(value: unknown): string {
  const source = text(value, 10);
  if (!/^\d{4}-\d{2}-\d{2}$/.test(source)) throw new Error('Invalid date');
  const parsed = new Date(source);
  if (Number.isNaN(parsed.valueOf()) || parsed.toISOString().slice(0, 10) !== source) throw new Error('Invalid date');
  return source;
}

function array(value: unknown): unknown[] {
  if (!Array.isArray(value) || value.length > 1024) throw new Error('Invalid array');
  return value;
}

function terms(value: unknown, kind: 'topic' | 'operation'): KnowledgeTerm[] {
  const result = array(value).map(item => {
    const entry = record(item, ['uri', 'label'], ['uri', 'label']);
    const uri = url(entry.uri);
    if (!new RegExp(`^https?://edamontology\\.org/${kind}_[0-9]{4,}$`).test(uri)) throw new Error('Invalid EDAM URI');
    return { uri, label: text(entry.label, 256) };
  });
  if (new Set(result.map(item => item.uri)).size !== result.length) throw new Error('Duplicate EDAM URI');
  return result;
}

function evidence(value: unknown): KnowledgeEvidence {
  const entry = record(value, ['url', 'checked_at', 'note'], ['url', 'checked_at', 'note']);
  return { url: url(entry.url), checked_at: isoDate(entry.checked_at), note: text(entry.note) };
}

function parseKnowledge(value: unknown): NodeKnowledge {
  const data = record(value, [
    'schema_version', 'tool_id', 'topics', 'operations', 'relations',
    'citation_evidence', 'reviewed_at', 'introduced_at',
  ], ['schema_version']);
  if (data.schema_version !== 1) throw new Error('Unsupported knowledge schema');
  const result: NodeKnowledge = { schema_version: 1 };
  if ('tool_id' in data) result.tool_id = url(data.tool_id);
  if ('topics' in data) result.topics = terms(data.topics, 'topic');
  if ('operations' in data) result.operations = terms(data.operations, 'operation');
  if ('reviewed_at' in data) result.reviewed_at = isoDate(data.reviewed_at);
  if ('introduced_at' in data) result.introduced_at = isoDate(data.introduced_at);
  if ('relations' in data) {
    result.relations = array(data.relations).map(item => {
      const entry = record(item, ['target_node_id', 'kind', 'evidence', 'source_port', 'target_port'],
        ['target_node_id', 'kind', 'evidence']);
      const kind = text(entry.kind, 64);
      if (!relationKinds.has(kind)) throw new Error('Unknown relation kind');
      const relation: KnowledgeRelation = {
        target_node_id: text(entry.target_node_id, 128), kind: kind as KnowledgeRelation['kind'],
        evidence: evidence(entry.evidence),
      };
      if ('source_port' in entry) relation.source_port = text(entry.source_port, 128);
      if ('target_port' in entry) relation.target_port = text(entry.target_port, 128);
      return relation;
    });
    const keys = result.relations.map(item => JSON.stringify([
      item.target_node_id, item.kind, item.source_port, item.target_port,
    ]));
    if (new Set(keys).size !== keys.length) throw new Error('Duplicate relation');
  }
  if ('citation_evidence' in data) {
    result.citation_evidence = array(data.citation_evidence).map(item => {
      const entry = record(item, ['identifier', 'source_url', 'checked_at', 'note'],
        ['identifier', 'source_url', 'checked_at', 'note']);
      return {
        identifier: text(entry.identifier, 256), source_url: url(entry.source_url),
        checked_at: isoDate(entry.checked_at), note: text(entry.note),
      };
    });
    const keys = result.citation_evidence.map(item => JSON.stringify([item.identifier.toLowerCase(), item.source_url]));
    if (new Set(keys).size !== keys.length) throw new Error('Duplicate citation evidence');
  }
  return result;
}

export function normalizeNodeKnowledge(value: unknown): NodeKnowledge | undefined {
  try { return parseKnowledge(value); } catch { return undefined; }
}

export function safeKnowledgeUrl(value: string | undefined): string | undefined {
  try { return url(value); } catch { return undefined; }
}
