import type { ObjectInfo, NodeMetadata, Workflow, WorkflowNode, WorkflowEdge, WorkflowGroup } from './types';

export function clamp(n: number, min: number, max: number) {
  return Math.min(max, Math.max(min, n));
}

export function groupNodesByCategory(objectInfo: ObjectInfo | NodeMetadata[]): Record<string, NodeMetadata[]> {
  const groups: Record<string, NodeMetadata[]> = {};
  const values = Array.isArray(objectInfo) ? objectInfo : Object.values(objectInfo);
  for (const meta of values) {
    const cat = meta.category || 'Other';
    if (!groups[cat]) groups[cat] = [];
    groups[cat].push(meta);
  }
  for (const cat of Object.keys(groups)) {
    groups[cat].sort((a, b) => a.display_name.localeCompare(b.display_name));
  }
  return groups;
}

export function filterNodes(objectInfo: ObjectInfo, query: string): NodeMetadata[] {
  const q = query.toLowerCase().trim();
  if (!q) return Object.values(objectInfo);
  return Object.values(objectInfo).filter(n =>
    n.display_name.toLowerCase().includes(q) ||
    n.id.toLowerCase().includes(q) ||
    (n.search_aliases || []).some(a => a.toLowerCase().includes(q)) ||
    (n.description || '').toLowerCase().includes(q) ||
    (n.category || '').toLowerCase().includes(q)
  );
}

export function valuesFromUnknownRecord<T>(value: unknown): T[] {
  if (Array.isArray(value)) return value as T[];
  if (value && typeof value === 'object') return Object.values(value as Record<string, T>);
  return [];
}

export function defaultsFor(meta: NodeMetadata): Record<string, unknown> {
  const defs: Record<string, unknown> = {};
  const inputs = meta.input_types;
  for (const section of ['required', 'optional'] as const) {
    if (!inputs?.[section]) continue;
    for (const [key, spec] of Object.entries(inputs[section])) {
      if (spec.default !== undefined) defs[key] = spec.default;
      else if (spec.type === 'INT') defs[key] = spec.min ?? 0;
      else if (spec.type === 'BOOLEAN') defs[key] = false;
      else if (spec.type === 'FLOAT') defs[key] = spec.min ?? 0;
      else if (spec.options) defs[key] = spec.options[0];
      else defs[key] = '';
    }
  }
  return defs;
}

export function edgeColorForSource(type: string): string {
  if (!type) return '#94a3b8';
  const upper = String(type).toUpperCase();
  if (upper in EDGE_TYPE_COLORS) return EDGE_TYPE_COLORS[upper];
  // Stable deterministic fallback so unknown types always get a consistent
  // hue across renders (and across users sharing a workflow).
  return EDGE_FALLBACK_PALETTE[hashString(upper) % EDGE_FALLBACK_PALETTE.length];
}

// Stable colors for known bioinformatics data types. Sequencing reads lean
// warm; alignment formats lean blue; variants lean red; quantification lean
// purple; numeric scalars get desaturated jewel tones.
const EDGE_TYPE_COLORS: Record<string, string> = {
  FASTQ: '#f59e0b', FASTQ_LIST: '#f59e0b', FASTQ_PAIRED: '#f59e0b',
  FASTA: '#8b5cf6', FASTA_LIST: '#8b5cf6', BIOSEQ: '#8b5cf6', BIOSEQ_LIST: '#8b5cf6',
  BAM: '#3b82f6', BAM_INDEXED: '#2563eb', SAM: '#60a5fa', CRAM: '#1d4ed8',
  VCF: '#ef4444', VCF_INDEXED: '#dc2626', BCF: '#f43f5e',
  GFF: '#10b981', GTF: '#10b981', BED: '#22c55e', BEDGRAPH: '#84cc16', BIGWIG: '#65a30d',
  ASSEMBLY: '#22c55e', ASSEMBLY_DIR: '#16a34a',
  PHYLOGENY_TREE: '#14b8a6', NEWICK: '#14b8a6', MSA: '#0d9488',
  INDEX_DIR: '#06b6d4', KRAKEN2_DB: '#0891b2',
  BWA_INDEX: '#06b6d4', HISAT2_INDEX: '#06b6d4', BOWTIE2_INDEX: '#06b6d4',
  KALLISTO_INDEX: '#06b6d4', SALMON_INDEX: '#06b6d4',
  QC_REPORT_DIR: '#ec4899', MULTIQC_REPORT: '#ec4899',
  HTML_REPORT: '#f97316', PDF: '#f97316', PNG: '#fb7185', IMAGE: '#fb7185',
  CSV: '#a855f7', TSV: '#a855f7', COUNT_MATRIX: '#a855f7', SAMPLE_SHEET: '#a855f7',
  DIRECTORY: '#64748b', OUTPUT_DIR: '#475569', FILE: '#94a3b8',
  STRING: '#334155', INT: '#6366f1', FLOAT: '#f43f5e', BOOLEAN: '#eab308',
};

const EDGE_FALLBACK_PALETTE = [
  '#94a3b8', '#a78bfa', '#fb923c', '#34d399', '#fbbf24',
  '#f472b6', '#60a5fa', '#a3e635', '#22d3ee', '#fda4af',
];

function hashString(value: string): number {
  let hash = 5381;
  for (let i = 0; i < value.length; i += 1) {
    hash = ((hash << 5) + hash + value.charCodeAt(i)) | 0;
  }
  return Math.abs(hash);
}

export function workflowFromCanvas(nodes: unknown[], edges: unknown[], groups: unknown[]): Workflow {
  return {
    version: '2.0',
    app: 'bionodulo',
    name: 'Untitled Workflow',
    description: '',
    nodes: nodes as WorkflowNode[],
    edges: edges as WorkflowEdge[],
    groups: groups as WorkflowGroup[],
    outputs: {},
  };
}

export function parseParamValue(val: string, type: string): unknown {
  if (type === 'INT') return parseInt(val, 10) || 0;
  if (type === 'FLOAT') return parseFloat(val) || 0;
  if (type === 'BOOLEAN') return val === 'true' || val === '1';
  return val;
}

export function normalizeEnvironment(env?: Record<string, unknown>) {
  return env || {};
}

export function workflowDependencies(wf: Workflow): Record<string, string> {
  return wf.dependencies || {};
}

export function saveToFile(content: string, filename: string, mime = 'application/octet-stream') {
  const blob = new Blob([content], { type: mime });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}
