// Collect the LOCAL workspace file paths a workflow references, so Run-on-Cloud
// can upload them before submitting. The canonical local-file node is
// `input_file` (its `params.path`); we also pick up any `path`-style param whose
// value is a plain relative path (not a URL / cloud key). Heuristic but safe:
// non-matching strings are simply not uploaded.
import type { Workflow } from '../types';

const PATH_PARAM_KEYS = new Set(['path', 'file', 'filepath', 'file_path', 'input', 'input_file']);

function looksLocalPath(v: unknown): v is string {
  if (typeof v !== 'string') return false;
  const s = v.trim();
  if (!s || s.length > 4096) return false;
  if (/\n/.test(s)) return false;
  if (/^[a-z]+:\/\//i.test(s)) return false;   // URL (http/s3/gs/...)
  if (/^uploads\//.test(s)) return false;       // already a cloud key
  return /[./\\]/.test(s);                       // has a path-ish separator or dot
}

/** Distinct local file paths referenced by the workflow's node params. */
export function collectLocalFilePaths(workflow: Workflow): string[] {
  const out = new Set<string>();
  for (const node of workflow.nodes || []) {
    const params = node.params || {};
    for (const [key, value] of Object.entries(params)) {
      if (!PATH_PARAM_KEYS.has(key)) continue;
      if (looksLocalPath(value)) out.add(value.trim());
    }
  }
  return [...out];
}

/** Basename for a workspace path (handles both `/` and `\`). */
export function baseName(path: string): string {
  return path.split(/[\\/]/).pop() || path;
}
