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
  const colors: Record<string, string> = {
    FASTQ: '#f59e0b', FASTQ_LIST: '#f59e0b', FASTA: '#8b5cf6',
    BAM: '#3b82f6', SAM: '#60a5fa', VCF: '#ef4444', GFF: '#10b981',
    DIRECTORY: '#64748b', FILE: '#94a3b8', STRING: '#334155',
    QC_REPORT_DIR: '#ec4899', MULTIQC_REPORT: '#ec4899', HTML_REPORT: '#f97316',
    INDEX_DIR: '#06b6d4', SAMPLE_SHEET: '#a855f7', ASSEMBLY: '#22c55e',
    PHYLOGENY_TREE: '#14b8a6', INT: '#6366f1', BOOLEAN: '#eab308',
    FLOAT: '#f43f5e',
  };
  return colors[type] || '#94a3b8';
}

export function workflowFromCanvas(nodes: unknown[], edges: unknown[], groups: unknown[]): Workflow {
  return {
    version: 'Alpha 1.1',
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
