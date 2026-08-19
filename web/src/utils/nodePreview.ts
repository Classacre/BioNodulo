// Inline node output previews — pure helpers.
//
// After a run completes, RunRecord.previews maps nodeId -> file path for nodes
// that produced a previewable artifact. The canvas renders that preview inside
// the node body: images render inline, delimited tables render as a mini-table,
// everything else shows a chip that opens the existing HTML preview modal.

import type { RunRecord } from '../types';

export type NodePreviewKind = 'image' | 'table' | 'other';

const IMAGE_EXTENSIONS = new Set(['png', 'jpg', 'jpeg', 'gif', 'svg', 'webp']);
const TABLE_EXTENSIONS = new Set(['tsv', 'csv', 'tab']);

export function previewKindForPath(path: string): NodePreviewKind {
  const clean = path.split(/[?#]/)[0];
  const dot = clean.lastIndexOf('.');
  if (dot < 0) return 'other';
  const ext = clean.slice(dot + 1).toLowerCase();
  if (IMAGE_EXTENSIONS.has(ext)) return 'image';
  if (TABLE_EXTENSIONS.has(ext)) return 'table';
  return 'other';
}

export interface NodePreviewRef {
  runId: string;
  nodeId: string;
  path: string;
}

function runTime(run: RunRecord): number {
  const stamp = run.end_time || run.start_time || '';
  const parsed = Date.parse(stamp);
  return Number.isNaN(parsed) ? 0 : parsed;
}

/**
 * The preview to show for each node: the one from the LATEST run (by end/start
 * time) that has a preview for that node id. Runs still executing carry no
 * previews, so they never displace a completed run's entry.
 */
export function deriveLatestPreviews(runs: RunRecord[]): Record<string, NodePreviewRef> {
  const sorted = [...runs].sort((a, b) => runTime(b) - runTime(a));
  const out: Record<string, NodePreviewRef> = {};
  for (const run of sorted) {
    const previews = run.previews || {};
    for (const [nodeId, path] of Object.entries(previews)) {
      if (!out[nodeId]) out[nodeId] = { runId: run.run_id, nodeId, path };
    }
  }
  return out;
}

export interface TablePreviewData {
  header: string[];
  rows: string[][];
  /** Total data rows in the file (excluding the header). */
  totalRows: number;
  truncated: boolean;
}

/**
 * Parse the first `maxRows` data rows of a tsv/csv file. Delimiter is inferred
 * from the header line (tab wins over comma). Intentionally simple — no quoted
 * field support; run artifacts are engine-written and flat.
 */
export function parseDelimitedPreview(text: string, maxRows = 5): TablePreviewData {
  const lines = text.split(/\r?\n/).filter(line => line.trim().length > 0);
  if (lines.length === 0) return { header: [], rows: [], totalRows: 0, truncated: false };
  const delimiter = lines[0].includes('\t') ? '\t' : ',';
  const header = lines[0].split(delimiter).map(cell => cell.trim());
  const dataLines = lines.slice(1);
  const rows = dataLines.slice(0, maxRows).map(line => line.split(delimiter).map(cell => cell.trim()));
  return {
    header,
    rows,
    totalRows: dataLines.length,
    truncated: dataLines.length > rows.length,
  };
}
