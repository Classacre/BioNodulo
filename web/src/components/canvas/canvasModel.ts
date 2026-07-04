// Pure (JSX-free, i18n-free) canvas model helpers shared by the React Flow
// WorkflowCanvas and the inspector/editor panels. Holds the node geometry /
// colour / layout logic as a single source of truth.
import type { WorkflowEdge, NodeMetadata, NodeStatus } from '../../types';
import { NODE_HEADER_H, calcRegularNodeHeight } from '../../utils/nodeLayout';

export const NODE_WIDTH = 220;
export const NODE_NOTE_WIDTH = 260;

export interface GraphNode {
  id: string;
  type: string;
  display_name: string;
  category: string;
  x: number;
  y: number;
  width: number;
  height: number;
  inputs: { name: string; type: string; connected: boolean }[];
  outputs: { name: string; type: string; connected: boolean }[];
  params: Record<string, unknown>;
  meta: NodeMetadata | null;
  color: string;
  muted: boolean;
  bypassed: boolean;
  selected: boolean;
  collapsed: boolean;
  pinned: boolean;
  shape: 'round' | 'box' | 'card';
  title: string;
  status?: NodeStatus['status'];
  visualOnly: boolean;
  inlinePreview: boolean;
  previewCollapsed: boolean;
  // Run-reactive: true while this node is showing an inline preview band
  // (a live preview exists for it and the inlinePreviews setting is on).
  showingPreview: boolean;
}

export interface WorkflowCanvasRef {
  fitView: () => void;
  focusNode: (nodeId: string) => void;
  setViewport: (viewport: { x: number; y: number; scale: number }) => void;
  getViewport: () => { x: number; y: number; scale: number };
  getSelectedNodeIds: () => string[];
  executeSelected: () => void;
  /** Project a screen (client) coordinate to flow/world coordinates — native
   *  React Flow projection, used e.g. by file-drop to place a node under the
   *  cursor. */
  screenToFlowPosition: (clientX: number, clientY: number) => { x: number; y: number };
  /** Wrap the current selection in a native group node. */
  createGroupFromSelection: () => void;
  /** Topological auto-layout: lays out all nodes in horizontal columns based
   *  on dependency depth. */
  autoLayout: () => void;
}

const COLORS: Record<string, string> = {
  Input: '#0d9488', 'Quality Control': '#ec4899', 'Read Preprocessing': '#f59e0b',
  Alignment: '#3b82f6', 'SAM/BAM Processing': '#60a5fa', 'Variant Calling': '#ef4444',
  Assembly: '#22c55e', Annotation: '#a855f7', Phylogenetics: '#14b8a6',
  'RNA-Seq': '#f97316', Metagenomics: '#8b5cf6', 'ChIP-Seq': '#06b6d4',
  'Single Cell': '#d946ef', HPC: '#6366f1', Utility: '#64748b',
};

// The Python registry emits lowercase categories like 'trimming', 'samtools',
// 'metagenomics' — these don't match the COLORS keys above, so before falling
// back to slate gray we run a substring search on category + id + display name.
// Order matters: first match wins, so put more specific keywords earlier.
const COLOR_KEYWORD_RULES: Array<[string, string]> = [
  ['input', '#0d9488'],
  ['qc', '#ec4899'],
  ['quality', '#ec4899'],
  ['preprocess', '#f59e0b'],
  ['trim', '#f59e0b'],
  ['cutadapt', '#f59e0b'],
  ['fastp', '#f59e0b'],
  ['samtools', '#60a5fa'],
  ['sam/bam', '#60a5fa'],
  ['align', '#3b82f6'],
  ['hisat', '#3b82f6'],
  ['bowtie', '#3b82f6'],
  ['bwa', '#3b82f6'],
  ['minimap', '#3b82f6'],
  ['star', '#3b82f6'],
  ['variant', '#ef4444'],
  ['gatk', '#ef4444'],
  ['bcftools', '#ef4444'],
  ['freebayes', '#ef4444'],
  ['vcftools', '#ef4444'],
  ['assembly', '#22c55e'],
  ['spades', '#22c55e'],
  ['canu', '#22c55e'],
  ['flye', '#22c55e'],
  ['unicycler', '#22c55e'],
  ['megahit', '#22c55e'],
  ['quast', '#22c55e'],
  ['annotation', '#a855f7'],
  ['prokka', '#a855f7'],
  ['bakta', '#a855f7'],
  ['eggnog', '#a855f7'],
  ['phylo', '#14b8a6'],
  ['mafft', '#14b8a6'],
  ['iqtree', '#14b8a6'],
  ['fasttree', '#14b8a6'],
  ['raxml', '#14b8a6'],
  ['clustalo', '#14b8a6'],
  ['single', '#d946ef'],
  ['cellranger', '#d946ef'],
  ['metag', '#8b5cf6'],
  ['kraken', '#8b5cf6'],
  ['bracken', '#8b5cf6'],
  ['metaphlan', '#8b5cf6'],
  ['humann', '#8b5cf6'],
  ['checkm', '#8b5cf6'],
  ['maxbin', '#8b5cf6'],
  ['quantif', '#a855f7'],
  ['count', '#a855f7'],
  ['featurecounts', '#a855f7'],
  ['kallisto', '#a855f7'],
  ['salmon', '#a855f7'],
  ['stringtie', '#a855f7'],
  ['differential', '#ef4444'],
  ['deseq', '#ef4444'],
  ['expression', '#a855f7'],
  ['peak', '#06b6d4'],
  ['macs', '#06b6d4'],
  ['chip', '#06b6d4'],
  ['deeptools', '#3b82f6'],
  ['bedtools', '#60a5fa'],
  ['hpc', '#6366f1'],
  ['biopython', '#a855f7'],
  ['biostrings', '#a855f7'],
  ['blast', '#a855f7'],
  ['plot', '#ec4899'],
  ['heatmap', '#ec4899'],
  ['viz', '#ec4899'],
  ['note', '#f59e0b'],
];

export function nodeColor(meta: NodeMetadata | null): string {
  if (!meta) return '#64748b';
  const category = meta.category || '';
  if (COLORS[category]) return COLORS[category];
  const haystack = `${category} ${meta.id || ''} ${meta.display_name || ''}`.toLowerCase();
  for (const [keyword, color] of COLOR_KEYWORD_RULES) {
    if (haystack.includes(keyword)) return color;
  }
  return '#64748b';
}

function calcNoteHeight(text: string, width: number): number {
  const maxCharsPerLine = Math.floor((width - 20) / 6.5);
  const lines = text.split('\n').reduce((total, line) => {
    return total + Math.max(1, Math.ceil(line.length / maxCharsPerLine));
  }, 0);
  return NODE_HEADER_H + Math.max(40, lines * 15 + 20);
}

export function calcNodeHeight(
  meta: NodeMetadata | null,
  collapsed: boolean,
  params?: Record<string, unknown>,
  width?: number,
): number {
  if (collapsed) return NODE_HEADER_H;
  if (meta?.id === 'note') {
    const text = String(params?.text || '');
    return calcNoteHeight(text, width || NODE_NOTE_WIDTH);
  }
  const base = calcRegularNodeHeight(meta, params);
  // Dedicated preview SINK nodes keep a fixed body. Producer nodes get their
  // (run-reactive) inline-preview band added separately once a preview exists.
  if (meta?.id === 'image_preview') return base + 120;
  if (meta?.id === 'html_preview') return base + 200;
  if (meta?.id === 'table_preview' || meta?.id === 'text_preview') return base + 180;
  return base;
}

export function arrangeNodesLayout(graphNodes: GraphNode[], edges: WorkflowEdge[]): Array<{ id: string; x: number; y: number }> {
  const adj = new Map<string, string[]>();
  const inDegree = new Map<string, number>();
  for (const n of graphNodes) {
    adj.set(n.id, []);
    inDegree.set(n.id, 0);
  }
  for (const e of edges) {
    adj.get(e.from.node)?.push(e.to.node);
    inDegree.set(e.to.node, (inDegree.get(e.to.node) || 0) + 1);
  }
  const queue: string[] = [];
  for (const [id, deg] of inDegree) {
    if (deg === 0) queue.push(id);
  }
  const topo: string[] = [];
  while (queue.length > 0) {
    const id = queue.shift()!;
    topo.push(id);
    for (const next of adj.get(id) || []) {
      const newDeg = (inDegree.get(next) || 0) - 1;
      inDegree.set(next, newDeg);
      if (newDeg === 0) queue.push(next);
    }
  }
  // Build incoming-edge adjacency once so layer assignment is O(V+E), not the
  // previous O(V·E) full-edge scan per topo node.
  const incoming = new Map<string, string[]>();
  for (const n of graphNodes) incoming.set(n.id, []);
  for (const e of edges) incoming.get(e.to.node)?.push(e.from.node);

  const layer = new Map<string, number>();
  for (const id of topo) {
    let maxLayer = 0;
    for (const from of incoming.get(id) || []) {
      maxLayer = Math.max(maxLayer, (layer.get(from) ?? 0) + 1);
    }
    layer.set(id, maxLayer);
  }
  // Nodes left out of the topo order are part of a cycle (their in-degree never
  // hit 0). Without handling them they'd all default to layer 0 and overlap.
  // Park them in a trailing layer past everything topologically resolved.
  const resolvedMax = layer.size > 0 ? Math.max(...layer.values()) : -1;
  const cyclicLayer = resolvedMax + 1;
  for (const n of graphNodes) {
    if (!layer.has(n.id)) layer.set(n.id, cyclicLayer);
  }

  const layerMap = new Map<number, GraphNode[]>();
  for (const n of graphNodes) {
    const l = layer.get(n.id) ?? 0;
    if (!layerMap.has(l)) layerMap.set(l, []);
    layerMap.get(l)!.push(n);
  }

  // Use per-node dimensions instead of fixed column/row sizes — otherwise
  // nodes with tall widget stacks (or user-widened columns) overlap.
  const COL_GAP = 80;
  const ROW_GAP = 40;
  const measure = (n: GraphNode) => {
    const width = Math.max(NODE_WIDTH, n.width || NODE_WIDTH);
    if (n.collapsed) {
      return { width, height: NODE_HEADER_H + 8 };
    }
    const minHeight = calcNodeHeight(n.meta, false, n.params, width);
    const measuredH = n.height && n.height > 0
      ? Math.max(n.height, minHeight)
      : minHeight;
    return { width, height: measuredH };
  };

  // Pre-compute per-layer column width (max measured width) and per-layer
  // node heights so the row offsets can step by each node's own height.
  const layerWidth = new Map<number, number>();
  const layerNodeHeights = new Map<number, number[]>();
  for (const [l, nodesInLayer] of layerMap) {
    let maxW = 0;
    const heights: number[] = [];
    for (const n of nodesInLayer) {
      const { width, height } = measure(n);
      maxW = Math.max(maxW, width);
      heights.push(height);
    }
    layerWidth.set(l, maxW);
    layerNodeHeights.set(l, heights);
  }
  // Cumulative X by layer.
  const layerX = new Map<number, number>();
  let xCursor = 60;
  const sortedLayers = Array.from(layerWidth.keys()).sort((a, b) => a - b);
  for (const l of sortedLayers) {
    layerX.set(l, xCursor);
    xCursor += (layerWidth.get(l) || NODE_WIDTH) + COL_GAP;
  }

  const result: Array<{ id: string; x: number; y: number }> = [];
  for (const n of graphNodes) {
    const l = layer.get(n.id) || 0;
    const nodesInLayer = layerMap.get(l)!;
    const idx = nodesInLayer.findIndex(nn => nn.id === n.id);
    const heights = layerNodeHeights.get(l) || [];
    let y = 60;
    for (let i = 0; i < idx; i++) {
      y += (heights[i] || 80) + ROW_GAP;
    }
    result.push({ id: n.id, x: layerX.get(l) ?? 60, y });
  }
  return result;
}
