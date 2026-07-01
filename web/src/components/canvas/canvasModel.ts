// Pure (JSX-free, i18n-free) canvas model helpers shared by the React Flow
// WorkflowCanvas and its sub-components. Extracted from the legacy Canvas2D
// implementation so the node geometry / colour / layout logic stays a single
// source of truth during and after the React Flow migration.
import type { WorkflowEdge, WorkflowGroup, NodeMetadata, NodeStatus } from '../../types';
import { NODE_HEADER_H, NODE_PIN_H, calcRegularNodeHeight } from '../../utils/nodeLayout';

export const NODE_WIDTH = 220;
export const NODE_NOTE_WIDTH = 260;

// Inline preview body on terminal-visual tool nodes: a small toggle bar plus a
// collapsible figure/report band, so the result renders on the producing node
// instead of a separate preview sink.
export const INLINE_PREVIEW_TOGGLE_H = 20;
export const INLINE_PREVIEW_BAND_H = 150;

export const PREVIEW_SINK_TYPES = new Set(['image_preview', 'html_preview', 'table_preview', 'text_preview']);

export interface NodeCommentSummary {
  count: number;
  unresolved: boolean;
}

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
  createSubgraphFromSelection: () => void;
  /** Topological auto-layout: lays out the selection (or all nodes if none
   *  selected) in horizontal columns based on dependency depth. */
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
  previewCollapsed = false,
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
  void previewCollapsed;
  return base;
}

export function getNodesInGroup(group: WorkflowGroup, graphNodes: GraphNode[]): string[] {
  const gx1 = group.position[0];
  const gy1 = group.position[1];
  const gx2 = gx1 + group.width;
  const gy2 = gy1 + group.height;
  return graphNodes
    .filter(n => {
      const ncx = n.x + n.width / 2;
      const ncy = n.y + n.height / 2;
      return ncx >= gx1 && ncx <= gx2 && ncy >= gy1 && ncy <= gy2;
    })
    .map(n => n.id);
}

// Topmost group whose body contains the point, or null. Used by reroute
// insertion so a reroute dropped inside a group inherits that group as its
// parentId (so future select/move-by-group also picks up the reroute).
export function groupContainingPoint(groups: WorkflowGroup[], x: number, y: number): WorkflowGroup | null {
  for (let i = groups.length - 1; i >= 0; i -= 1) {
    const g = groups[i];
    if (!g) continue;
    if (x >= g.position[0] && x <= g.position[0] + g.width
      && y >= g.position[1] && y <= g.position[1] + g.height) {
      return g;
    }
  }
  return null;
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
  const layer = new Map<string, number>();
  for (const id of topo) {
    let maxLayer = 0;
    for (const e of edges) {
      if (e.to.node === id) {
        maxLayer = Math.max(maxLayer, (layer.get(e.from.node) || 0) + 1);
      }
    }
    layer.set(id, maxLayer);
  }
  const layerMap = new Map<number, GraphNode[]>();
  for (const n of graphNodes) {
    const l = layer.get(n.id) || 0;
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

function roundRect(ctx: CanvasRenderingContext2D, x: number, y: number, w: number, h: number, r: number | Record<string, number>) {
  if (typeof r === 'number') r = { tl: r, tr: r, br: r, bl: r };
  const rad = r as Record<string, number>;
  ctx.beginPath();
  ctx.moveTo(x + rad.tl, y);
  ctx.lineTo(x + w - rad.tr, y);
  ctx.quadraticCurveTo(x + w, y, x + w, y + rad.tr);
  ctx.lineTo(x + w, y + h - rad.br);
  ctx.quadraticCurveTo(x + w, y + h, x + w - rad.br, y + h);
  ctx.lineTo(x + rad.bl, y + h);
  ctx.quadraticCurveTo(x, y + h, x, y + h - rad.bl);
  ctx.lineTo(x, y + rad.tl);
  ctx.quadraticCurveTo(x, y, x + rad.tl, y);
  ctx.closePath();
}

// Rasterises the current graph into a 480x360 PNG data URL for thumbnails and
// the export-thumbnail canvas menu action. Uses an offscreen 2D context; this
// is not part of the interactive render path.
export function exportThumbnailDataURL(graphNodes: GraphNode[], edges: WorkflowEdge[], groups: WorkflowGroup[]): string {
  const c = document.createElement('canvas');
  c.width = 480;
  c.height = 360;
  const ctx = c.getContext('2d')!;
  ctx.fillStyle = '#0f172a';
  ctx.fillRect(0, 0, c.width, c.height);

  let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
  for (const n of graphNodes) {
    minX = Math.min(minX, n.x);
    minY = Math.min(minY, n.y);
    maxX = Math.max(maxX, n.x + n.width);
    maxY = Math.max(maxY, n.y + n.height);
  }
  for (const g of groups) {
    minX = Math.min(minX, g.position[0]);
    minY = Math.min(minY, g.position[1]);
    maxX = Math.max(maxX, g.position[0] + g.width);
    maxY = Math.max(maxY, g.position[1] + g.height);
  }
  if (!isFinite(minX)) { minX = 0; minY = 0; maxX = c.width; maxY = c.height; }

  const pad = 30;
  const bw = maxX - minX + pad * 2;
  const bh = maxY - minY + pad * 2;
  const s = Math.min(c.width / bw, c.height / bh);
  const ox = (c.width - bw * s) / 2 + pad * s - minX * s;
  const oy = (c.height - bh * s) / 2 + pad * s - minY * s;
  ctx.setTransform(s, 0, 0, s, ox, oy);

  for (const g of groups) {
    ctx.fillStyle = g.color + '18';
    ctx.fillRect(g.position[0], g.position[1], g.width, g.height);
    ctx.strokeStyle = g.color + '40';
    ctx.lineWidth = 1 / s;
    ctx.strokeRect(g.position[0], g.position[1], g.width, g.height);
  }

  for (const edge of edges) {
    const fromNode = graphNodes.find(n => n.id === edge.from.node);
    const toNode = graphNodes.find(n => n.id === edge.to.node);
    if (!fromNode || !toNode) continue;
    const fromOutIndex = fromNode.outputs.findIndex(o => o.name === edge.from.output);
    const toInIndex = toNode.inputs.findIndex(i => i.name === edge.to.input);
    const fy = fromNode.y + NODE_HEADER_H + NODE_PIN_H / 2 + (fromOutIndex >= 0 ? fromOutIndex : 0) * NODE_PIN_H;
    const ty = toNode.y + NODE_HEADER_H + NODE_PIN_H / 2 + (toInIndex >= 0 ? toInIndex : 0) * NODE_PIN_H;
    const fx = fromNode.x + fromNode.width;
    const tx = toNode.x;
    const dist = Math.hypot(tx - fx, ty - fy);
    const cd = Math.max(30, dist * 0.25);
    ctx.strokeStyle = '#94a3b8';
    ctx.lineWidth = 1.5 / s;
    ctx.beginPath();
    ctx.moveTo(fx, fy);
    ctx.bezierCurveTo(fx + cd, fy, tx - cd, ty, tx, ty);
    ctx.stroke();
  }

  for (const node of graphNodes) {
    ctx.fillStyle = node.color;
    roundRect(ctx, node.x, node.y, node.width, node.height, 8);
    ctx.fill();
    ctx.fillStyle = 'rgba(0,0,0,0.35)';
    ctx.fillRect(node.x, node.y, node.width, NODE_HEADER_H);
    ctx.fillStyle = '#ffffff';
    ctx.font = `${11 / s}px Inter, sans-serif`;
    ctx.textAlign = 'left';
    ctx.fillText(node.display_name, node.x + 10, node.y + 21);
  }

  ctx.setTransform(1, 0, 0, 1, 0, 0);
  return c.toDataURL('image/png');
}

export function createGroupFromNodes(nodes: GraphNode[], fallbackName: string): WorkflowGroup {
  const minX = Math.min(...nodes.map(n => n.x));
  const minY = Math.min(...nodes.map(n => n.y));
  const maxX = Math.max(...nodes.map(n => n.x + n.width));
  const maxY = Math.max(...nodes.map(n => n.y + n.height));
  const padding = 20;
  return {
    id: typeof crypto !== 'undefined' && crypto.randomUUID ? crypto.randomUUID() : `group_${Date.now()}`,
    name: fallbackName,
    position: [minX - padding, minY - padding] as [number, number],
    width: maxX - minX + padding * 2,
    height: maxY - minY + padding * 2,
    color: '#6366f1',
    collapsed: false,
  };
}
