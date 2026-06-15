// Detect (and optionally fix) node overlaps in workflow templates using the
// REAL frontend node-sizing code, so measurements match the canvas exactly.
// Run from web/: npx vite-node scripts/templateLayout.ts -- [--write]
import { readFileSync, writeFileSync, readdirSync } from 'node:fs';
import { resolve, join } from 'node:path';
import { calcRegularNodeHeight, NODE_HEADER_H } from '../src/utils/nodeLayout';
import type { NodeMetadata } from '../src/types';

const NODE_WIDTH = 220;
const NODE_NOTE_WIDTH = 260;
const WRITE = process.argv.includes('--write');
const TEMPLATES_DIR = resolve(process.cwd(), '..', 'templates');
const OBJECT_INFO_URL = 'http://127.0.0.1:8765/api/object_info';

// --- note height (mirrors WorkflowCanvas.calcNoteHeight) -------------------
function calcNoteHeight(text: string, width: number): number {
  const maxCharsPerLine = Math.floor((width - 20) / 6.5);
  const lines = text.split('\n').reduce((total, line) => total + Math.max(1, Math.ceil(line.length / maxCharsPerLine)), 0);
  return NODE_HEADER_H + Math.max(40, lines * 15 + 20);
}

function nodeSize(node: any, meta: NodeMetadata | null): { w: number; h: number } {
  const type = node.type;
  if (type === 'note') {
    const w = NODE_NOTE_WIDTH;
    return { w, h: calcNoteHeight(String(node.params?.text || ''), w) };
  }
  if (node.collapsed) return { w: NODE_WIDTH, h: NODE_HEADER_H };
  let h = calcRegularNodeHeight(meta, node.params || {});
  if (type === 'image_preview') h += 120;
  if (type === 'html_preview') h += 200;
  return { w: NODE_WIDTH, h };
}

function rectsOverlap(a: any, b: any, pad = 0): boolean {
  return (
    a.x < b.x + b.w + pad &&
    a.x + a.w + pad > b.x &&
    a.y < b.y + b.h + pad &&
    a.y + a.h + pad > b.y
  );
}

async function main() {
  const res = await fetch(OBJECT_INFO_URL);
  const objectInfo = (await res.json()) as Record<string, NodeMetadata>;

  const files = readdirSync(TEMPLATES_DIR).filter(f => f.endsWith('.json'));
  const report: Array<{ file: string; overlaps: number; pairs: string[] }> = [];

  for (const file of files) {
    const path = join(TEMPLATES_DIR, file);
    const raw = JSON.parse(readFileSync(path, 'utf8'));
    const wf = raw.workflow ?? raw;
    const nodes: any[] = wf.nodes ?? [];

    const rects = nodes.map(n => {
      const meta = (objectInfo[n.type] ?? null) as NodeMetadata | null;
      const { w, h } = nodeSize(n, meta);
      const pos = n.position ?? [0, 0];
      return { id: n.id, type: n.type, x: pos[0], y: pos[1], w, h, node: n };
    });

    // Notes are free-floating annotations; ignore them for overlap (they are
    // meant to sit beside the graph and can legitimately overlap empty space).
    const layoutRects = rects.filter(r => r.type !== 'note');

    const pairs: string[] = [];
    for (let i = 0; i < layoutRects.length; i++) {
      for (let j = i + 1; j < layoutRects.length; j++) {
        if (rectsOverlap(layoutRects[i], layoutRects[j])) {
          pairs.push(`${layoutRects[i].id} <> ${layoutRects[j].id}`);
        }
      }
    }
    report.push({ file, overlaps: pairs.length, pairs });

    if (WRITE && pairs.length > 0) {
      relayout(wf, rects, objectInfo);
      writeFileSync(path, JSON.stringify(raw, null, 2) + '\n');
    }
  }

  for (const r of report) {
    const tag = r.overlaps > 0 ? `OVERLAP x${r.overlaps}` : 'ok';
    console.log(`${tag.padEnd(12)} ${r.file}`);
    if (r.overlaps > 0) for (const p of r.pairs.slice(0, 6)) console.log(`             ${p}`);
  }
  const bad = report.filter(r => r.overlaps > 0).length;
  console.log(`\n${bad} of ${report.length} templates have overlaps${WRITE ? ' (rewritten)' : ''}.`);
}

// Minimal, layout-preserving overlap fix. The templates are hand-arranged into
// columns (nodes share an x within a column); all detected overlaps are tall
// preview/report nodes stacked too tightly in the SAME column. So we only
// decompact each column vertically: walk top→down and push a node DOWN just
// enough to clear the previous one. Nothing else moves, columns stay intact.
function relayout(wf: any, rects: any[], _objectInfo: Record<string, NodeMetadata>) {
  const MIN_GAP = 40;
  const layoutNodes = rects.filter(r => r.type !== 'note');
  if (layoutNodes.length === 0) return;

  const columns = new Map<number, any[]>();
  for (const r of layoutNodes) {
    const list = columns.get(r.x) ?? [];
    list.push(r);
    columns.set(r.x, list);
  }

  for (const colNodes of columns.values()) {
    colNodes.sort((a, b) => a.y - b.y);
    for (let i = 1; i < colNodes.length; i++) {
      const prev = colNodes[i - 1];
      const cur = colNodes[i];
      const minY = prev.y + prev.h + MIN_GAP;
      if (cur.y < minY) {
        cur.y = minY;
        cur.node.position = [cur.x, Math.round(minY)];
      }
    }
  }
}

main().catch(err => { console.error(err); process.exit(1); });
