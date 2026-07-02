// Render a workflow JSON to a thumbnail with no dependency on the live canvas
// component, so recents, template cards, and the export modal can produce a
// preview without the React Flow canvas being mounted.
//
// The graph is drawn declaratively as an SVG string (matching the React Flow
// DOM aesthetic) — there is NO Canvas2D node renderer here. For the paths that
// need real PNG bytes (the export download + template drag-drop, which embed
// the workflow JSON as a PNG tEXt chunk for the Python `workflow_embed.py`
// interop), `rasterizeSvgToPng` converts the SVG to a PNG using an <img> +
// one-shot canvas purely for image encoding.

import type { Workflow, WorkflowNode } from '../types';
import i18n from '../i18n';

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

// Escape text for inclusion in SVG element bodies / attribute values.
function esc(text: string): string {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

export interface RenderOptions {
  width?: number;
  height?: number;
  background?: string;
  /**
   * PNG resolution multiplier (SVG is vector, so this only affects the
   * rasterised PNG output via `renderWorkflowThumbnailPng`). 1.0 keeps the
   * requested width/height; 0.5 halves them, etc. Clamped to [0.25, 1].
   */
  quality?: number;
  /**
   * When `true`, the background fill is skipped and the SVG stays transparent.
   * Useful for embedding the thumbnail in slide decks / docs.
   */
  transparent?: boolean;
}

// Compact SVG thumbnail used to stamp recents in localStorage. SVG is plain
// text, so a small graph serialises to a few KB — well under the origin quota
// even across the full recents list.
export function renderRecentThumbnail(workflow: Workflow): string {
  try {
    return renderWorkflowThumbnail(workflow, { width: 240, height: 150 });
  } catch {
    return '';
  }
}

/**
 * Render the workflow to an inline SVG data URL. Synchronous and safe to use
 * directly as an `<img src>`; call `rasterizeSvgToPng` on the result when real
 * PNG bytes are required (e.g. the workflow-embedded export download).
 */
export function renderWorkflowThumbnail(workflow: Workflow, options: RenderOptions = {}): string {
  const width = Math.max(64, options.width ?? 640);
  const height = Math.max(64, options.height ?? 400);
  const transparent = options.transparent === true;
  const background = transparent ? null : (options.background ?? '#0f172a');

  const body: string[] = [];
  if (background) {
    body.push(`<rect width="${width}" height="${height}" fill="${esc(background)}"/>`);
  }

  const nodes = workflow.nodes || [];
  if (nodes.length === 0) {
    body.push(
      `<text x="16" y="24" font-family="Inter, sans-serif" font-size="14" fill="#94a3b8">` +
      `${esc(i18n.t('workflowThumbnail.emptyWorkflow'))}</text>`,
    );
    return svgDataUrl(width, height, body.join(''));
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

  // Edges (behind nodes).
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
    body.push(
      `<path d="M${x1.toFixed(1)},${y1.toFixed(1)} C${(x1 + cd).toFixed(1)},${y1.toFixed(1)} ` +
      `${(x2 - cd).toFixed(1)},${y2.toFixed(1)} ${x2.toFixed(1)},${y2.toFixed(1)}" ` +
      `fill="none" stroke="#94a3b8" stroke-width="1.4"/>`,
    );
  }

  // Nodes.
  for (const node of nodes) {
    const ui = node.ui || {};
    const color = ui.color || colorForType(node.type);
    if (isReroute(node)) {
      const [cx, cy] = toScreen(node.position[0] + 20, node.position[1] + 10);
      const r = Math.max(3, 6 * scale);
      body.push(`<circle cx="${cx.toFixed(1)}" cy="${cy.toFixed(1)}" r="${r.toFixed(1)}" fill="${esc(color)}"/>`);
      continue;
    }
    const nh = estimateHeight(node);
    const [x0, y0] = toScreen(node.position[0], node.position[1]);
    const w = NODE_WIDTH * scale;
    const h = nh * scale;
    const radius = Math.max(2, 8 * scale);
    if (isNote(node)) {
      body.push(
        `<rect x="${x0.toFixed(1)}" y="${y0.toFixed(1)}" width="${w.toFixed(1)}" height="${h.toFixed(1)}" ` +
        `rx="${radius.toFixed(1)}" fill="rgba(245,158,11,0.18)" stroke="#f59e0b" stroke-width="1"/>`,
      );
    } else {
      const headerH = Math.max(6, NODE_HEADER_H * scale);
      body.push(
        `<rect x="${x0.toFixed(1)}" y="${y0.toFixed(1)}" width="${w.toFixed(1)}" height="${h.toFixed(1)}" ` +
        `rx="${radius.toFixed(1)}" fill="rgba(30,41,59,0.9)" stroke="${esc(color)}" stroke-width="1.2"/>`,
        `<path d="M${x0.toFixed(1)},${(y0 + radius).toFixed(1)} q0,${(-radius).toFixed(1)} ${radius.toFixed(1)},${(-radius).toFixed(1)} ` +
        `h${(w - 2 * radius).toFixed(1)} q${radius.toFixed(1)},0 ${radius.toFixed(1)},${radius.toFixed(1)} ` +
        `v${(headerH - radius).toFixed(1)} h${(-w).toFixed(1)} Z" fill="${esc(color)}"/>`,
      );
    }
    const label = ui.title || node.type || i18n.t('workflowThumbnail.nodeFallback');
    const maxChars = Math.max(6, Math.floor((NODE_WIDTH - 12) * scale / 6));
    const text = label.length > maxChars ? label.slice(0, maxChars - 1) + '…' : label;
    const fontSize = Math.max(9, 11 * scale);
    body.push(
      `<text x="${(x0 + 6).toFixed(1)}" y="${(y0 + Math.max(10, NODE_HEADER_H * scale * 0.65)).toFixed(1)}" ` +
      `font-family="Inter, sans-serif" font-weight="600" font-size="${fontSize.toFixed(1)}" fill="#ffffff">` +
      `${esc(text)}</text>`,
    );
  }

  // Subtle border.
  body.push(
    `<rect x="0.5" y="0.5" width="${width - 1}" height="${height - 1}" rx="8" ` +
    `fill="none" stroke="rgba(45,212,191,0.35)" stroke-width="1"/>`,
  );

  return svgDataUrl(width, height, body.join(''));
}

function svgDataUrl(width: number, height: number, inner: string): string {
  const svg =
    `<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}" ` +
    `viewBox="0 0 ${width} ${height}">${inner}</svg>`;
  return `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}`;
}

/**
 * Rasterise an SVG data URL to a PNG data URL. The canvas here is used purely
 * as an image encoder (it draws a fully-formed SVG image), not as a graph
 * renderer. Needed by the paths that embed the workflow JSON into PNG metadata.
 */
export function rasterizeSvgToPng(
  svgDataUrl: string,
  options: { width?: number; height?: number; background?: string } = {},
): Promise<string> {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => {
      const width = options.width ?? img.width ?? 640;
      const height = options.height ?? img.height ?? 400;
      const canvas = document.createElement('canvas');
      canvas.width = width;
      canvas.height = height;
      const ctx = canvas.getContext('2d');
      if (!ctx) { reject(new Error('Canvas 2D context unavailable')); return; }
      if (options.background) {
        ctx.fillStyle = options.background;
        ctx.fillRect(0, 0, width, height);
      }
      ctx.drawImage(img, 0, 0, width, height);
      resolve(canvas.toDataURL('image/png'));
    };
    img.onerror = () => reject(new Error('Failed to rasterise SVG thumbnail'));
    img.src = svgDataUrl;
  });
}

/**
 * Convenience: render the workflow and rasterise it to a PNG data URL in one
 * step, for callers that need real PNG bytes (export download, template embed).
 */
export async function renderWorkflowThumbnailPng(workflow: Workflow, options: RenderOptions = {}): Promise<string> {
  const svg = renderWorkflowThumbnail(workflow, options);
  const scale = Math.max(0.25, Math.min(1, options.quality ?? 1));
  return rasterizeSvgToPng(svg, {
    width: Math.round((options.width ?? 640) * scale),
    height: Math.round((options.height ?? 400) * scale),
    background: options.transparent ? undefined : (options.background ?? '#0f172a'),
  });
}
