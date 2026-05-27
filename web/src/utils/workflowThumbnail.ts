// Render a workflow JSON to a PNG dataURL with no dependency on the live
// canvas component, so the export modal can produce a thumbnail without
// the LiteGraphCanvas being mounted on a particular tab.

import type { Workflow, WorkflowNode } from '../types';

const NODE_WIDTH = 220;
const NODE_HEADER_H = 32;
const NODE_PIN_H = 18;
const WIDGET_ROW_H = 24;
const WIDGET_BLOCK_PAD = 8;

const CATEGORY_COLORS: Array<[string, string]> = [
  ['input', '#22c55e'],
  ['qc', '#eab308'],
  ['fastqc', '#eab308'],
  ['trim', '#f97316'],
  ['cutadapt', '#f97316'],
  ['fastp', '#f97316'],
  ['align', '#0ea5e9'],
  ['bwa', '#0ea5e9'],
  ['bowtie', '#0ea5e9'],
  ['hisat', '#0ea5e9'],
  ['star', '#0ea5e9'],
  ['minimap', '#0ea5e9'],
  ['count', '#a855f7'],
  ['featurecounts', '#a855f7'],
  ['kallisto', '#a855f7'],
  ['salmon', '#a855f7'],
  ['variant', '#ef4444'],
  ['gatk', '#ef4444'],
  ['freebayes', '#ef4444'],
  ['bcftools', '#ef4444'],
  ['assembly', '#14b8a6'],
  ['spades', '#14b8a6'],
  ['flye', '#14b8a6'],
  ['canu', '#14b8a6'],
  ['phylo', '#6366f1'],
  ['mafft', '#6366f1'],
  ['iqtree', '#6366f1'],
  ['viz', '#ec4899'],
  ['plot', '#ec4899'],
  ['heatmap', '#ec4899'],
  ['kraken', '#10b981'],
  ['metag', '#10b981'],
];

function colorForType(nodeType: string): string {
  const lower = (nodeType || '').toLowerCase();
  for (const [key, color] of CATEGORY_COLORS) {
    if (lower.includes(key)) return color;
  }
  return '#2dd4bf';
}

function isNote(node: WorkflowNode): boolean { return node.type === 'note'; }
function isReroute(node: WorkflowNode): boolean { return node.type === 'reroute'; }

function estimateHeight(node: WorkflowNode): number {
  if (isReroute(node)) return 20;
  if (isNote(node)) {
    const text = String(node.params?.text || '');
    const lines = Math.max(1, text.split('\n').length + Math.floor(text.length / 60));
    return NODE_HEADER_H + Math.max(40, lines * 15 + 20);
  }
  const params = node.params || {};
  let interactive = 0;
  for (const value of Object.values(params)) {
    if (value !== '' && value !== undefined && value !== null && typeof value !== 'object') interactive += 1;
  }
  interactive = Math.min(interactive, 8);
  const io = 3 * NODE_PIN_H;
  const widgetBlock = interactive ? interactive * WIDGET_ROW_H + WIDGET_BLOCK_PAD : 0;
  return NODE_HEADER_H + io + widgetBlock + 24;
}

function roundRect(ctx: CanvasRenderingContext2D, x: number, y: number, w: number, h: number, r: number) {
  const radius = Math.max(0, Math.min(r, w / 2, h / 2));
  ctx.beginPath();
  ctx.moveTo(x + radius, y);
  ctx.lineTo(x + w - radius, y);
  ctx.quadraticCurveTo(x + w, y, x + w, y + radius);
  ctx.lineTo(x + w, y + h - radius);
  ctx.quadraticCurveTo(x + w, y + h, x + w - radius, y + h);
  ctx.lineTo(x + radius, y + h);
  ctx.quadraticCurveTo(x, y + h, x, y + h - radius);
  ctx.lineTo(x, y + radius);
  ctx.quadraticCurveTo(x, y, x + radius, y);
  ctx.closePath();
}

export interface RenderOptions {
  width?: number;
  height?: number;
  background?: string;
  /** Output encoding for the dataURL. JPEG is ~10x smaller — good for localStorage. */
  format?: 'png' | 'jpeg';
  /**
   * For JPEG: encoder quality (0-1, default 0.85).
   * For PNG: rendering scale (PNG is lossless, so we drive output resolution
   * instead). 1.0 keeps the requested width/height; 0.5 halves them, etc.
   */
  quality?: number;
  /**
   * When `true`, the background fill is skipped and the canvas remains
   * transparent. Useful for embedding the thumbnail in slide decks / docs.
   */
  transparent?: boolean;
}

// Smaller, JPEG-encoded variant used to stamp recents in localStorage. Keeps
// the per-entry payload to ~3-6 KB so we stay well under the 5 MB origin quota
// even with the full 12-entry MAX_ENTRIES recents list.
export function renderRecentThumbnail(workflow: Workflow): string {
  try {
    return renderWorkflowThumbnail(workflow, {
      width: 240,
      height: 150,
      format: 'jpeg',
      quality: 0.72,
    });
  } catch {
    return '';
  }
}

export function renderWorkflowThumbnail(workflow: Workflow, options: RenderOptions = {}): string {
  const baseWidth = options.width ?? 640;
  const baseHeight = options.height ?? 400;
  const format = options.format ?? 'png';
  const quality = options.quality ?? (format === 'jpeg' ? 0.85 : 1);
  const transparent = options.transparent === true;
  const background = transparent ? null : (options.background ?? '#0f172a');
  // PNG uses `quality` as a resolution multiplier (it's lossless). Clamp so
  // we never produce an absurdly large or near-empty canvas.
  const pngScale = format === 'png' ? Math.max(0.25, Math.min(1, quality)) : 1;
  const width = Math.max(64, Math.round(baseWidth * pngScale));
  const height = Math.max(64, Math.round(baseHeight * pngScale));

  const canvas = document.createElement('canvas');
  canvas.width = width;
  canvas.height = height;
  const ctx = canvas.getContext('2d');
  if (!ctx) throw new Error('Canvas 2D context unavailable');
  if (background) {
    ctx.fillStyle = background;
    ctx.fillRect(0, 0, width, height);
  } else {
    ctx.clearRect(0, 0, width, height);
  }

  const nodes = workflow.nodes || [];
  if (nodes.length === 0) {
    ctx.fillStyle = '#94a3b8';
    ctx.font = '14px Inter, sans-serif';
    ctx.fillText('(empty workflow)', 16, 24);
    return format === 'jpeg'
      ? canvas.toDataURL('image/jpeg', quality)
      : canvas.toDataURL('image/png');
  }

  let minX = Infinity;
  let minY = Infinity;
  let maxX = -Infinity;
  let maxY = -Infinity;
  for (const node of nodes) {
    const w = isReroute(node) ? 40 : NODE_WIDTH;
    const h = estimateHeight(node);
    minX = Math.min(minX, node.position[0]);
    minY = Math.min(minY, node.position[1]);
    maxX = Math.max(maxX, node.position[0] + w);
    maxY = Math.max(maxY, node.position[1] + h);
  }
  const pad = 24;
  const bw = maxX - minX + pad * 2;
  const bh = maxY - minY + pad * 2;
  const scale = Math.min(width / bw, height / bh);
  const offX = (width - bw * scale) / 2 + (pad - minX) * scale;
  const offY = (height - bh * scale) / 2 + (pad - minY) * scale;

  const toScreen = (x: number, y: number): [number, number] => [x * scale + offX, y * scale + offY];

  ctx.strokeStyle = '#94a3b8';
  ctx.lineWidth = 1.4;
  const byId = new Map(nodes.map(node => [node.id, node]));
  for (const edge of workflow.edges || []) {
    const a = byId.get(edge.from.node);
    const b = byId.get(edge.to.node);
    if (!a || !b) continue;
    const aW = isReroute(a) ? 40 : NODE_WIDTH;
    const aH = estimateHeight(a);
    const bH = estimateHeight(b);
    const [x1, y1] = toScreen(a.position[0] + aW, a.position[1] + aH / 2);
    const [x2, y2] = toScreen(b.position[0], b.position[1] + bH / 2);
    const cd = Math.max(20, Math.hypot(x2 - x1, y2 - y1) * 0.25);
    ctx.beginPath();
    ctx.moveTo(x1, y1);
    ctx.bezierCurveTo(x1 + cd, y1, x2 - cd, y2, x2, y2);
    ctx.stroke();
  }

  for (const node of nodes) {
    const ui = node.ui || {};
    const color = ui.color || colorForType(node.type);
    if (isReroute(node)) {
      const [cx, cy] = toScreen(node.position[0] + 20, node.position[1] + 10);
      const r = Math.max(3, 6 * scale);
      ctx.fillStyle = color;
      ctx.beginPath();
      ctx.arc(cx, cy, r, 0, Math.PI * 2);
      ctx.fill();
      continue;
    }
    const nw = NODE_WIDTH;
    const nh = estimateHeight(node);
    const [x0, y0] = toScreen(node.position[0], node.position[1]);
    const w = nw * scale;
    const h = nh * scale;
    const radius = Math.max(2, 8 * scale);
    if (isNote(node)) {
      ctx.fillStyle = 'rgba(245,158,11,0.18)';
      roundRect(ctx, x0, y0, w, h, radius);
      ctx.fill();
      ctx.strokeStyle = '#f59e0b';
      ctx.lineWidth = 1;
      ctx.stroke();
    } else {
      ctx.fillStyle = 'rgba(30,41,59,0.9)';
      roundRect(ctx, x0, y0, w, h, radius);
      ctx.fill();
      ctx.strokeStyle = color;
      ctx.lineWidth = 1.2;
      ctx.stroke();
      ctx.fillStyle = color;
      roundRect(ctx, x0, y0, w, Math.max(6, NODE_HEADER_H * scale), radius);
      ctx.fill();
    }
    ctx.fillStyle = '#ffffff';
    ctx.font = `600 ${Math.max(9, 11 * scale)}px Inter, sans-serif`;
    const label = ui.title || node.type || 'node';
    const maxChars = Math.max(6, Math.floor((nw - 12) * scale / 6));
    const text = label.length > maxChars ? label.slice(0, maxChars - 1) + '…' : label;
    ctx.fillText(text, x0 + 6, y0 + Math.max(10, NODE_HEADER_H * scale * 0.65));
  }

  ctx.strokeStyle = 'rgba(45,212,191,0.35)';
  ctx.lineWidth = 1;
  roundRect(ctx, 0.5, 0.5, width - 1, height - 1, 8);
  ctx.stroke();

  return format === 'jpeg'
    ? canvas.toDataURL('image/jpeg', quality)
    : canvas.toDataURL('image/png');
}
