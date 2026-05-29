// URL-hash workflow sharing. Encodes a workflow as a base64-url JSON blob
// stuffed into `#wf=...` so a teammate can paste a single link and open the
// same graph without any server round-trip.
//
// We deliberately don't compress with LZ-string or pako here — the median
// workflow JSON is ~5-30 KB which base64-encoded fits well within the
// 32 KB practical URL limit most browsers handle. If users start hitting
// the cap we can swap in a compressor without changing the surface.
//
// Caveats:
//   - Long workflows may exceed mail-client / chat-tool URL parsing limits.
//     The caller can fall back to /api/workflow/export when this happens.
//   - The hash is decoded once on first load; subsequent navigation doesn't
//     re-trigger so editing the URL during a session is a no-op.

import type { Workflow } from '../types';

const HASH_PREFIX = '#wf=';

function utf8ToBase64Url(input: string): string {
  // btoa needs Latin-1 — use TextEncoder + manual chunking so unicode workflow
  // names survive the round-trip.
  const bytes = new TextEncoder().encode(input);
  let binary = '';
  const CHUNK = 0x8000;
  for (let i = 0; i < bytes.length; i += CHUNK) {
    binary += String.fromCharCode(...bytes.subarray(i, i + CHUNK));
  }
  return btoa(binary)
    .replace(/\+/g, '-')
    .replace(/\//g, '_')
    .replace(/=+$/, '');
}

function base64UrlToUtf8(input: string): string {
  const padded = input.replace(/-/g, '+').replace(/_/g, '/') + '==='.slice((input.length + 3) % 4);
  const binary = atob(padded);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i += 1) bytes[i] = binary.charCodeAt(i);
  return new TextDecoder().decode(bytes);
}

/**
 * Build a shareable absolute URL that encodes the workflow into the hash.
 * Returns null when serialization fails.
 */
export function buildShareUrl(workflow: Workflow, baseUrl: string = window.location.origin + window.location.pathname): string | null {
  try {
    const payload = JSON.stringify(workflow);
    const encoded = utf8ToBase64Url(payload);
    return `${baseUrl}${HASH_PREFIX}${encoded}`;
  } catch {
    return null;
  }
}

/**
 * Try to decode a workflow from `window.location.hash`. Returns null when no
 * hash is present or the payload is malformed.
 */
export function readWorkflowFromHash(hash: string = window.location.hash): Workflow | null {
  if (!hash.startsWith(HASH_PREFIX)) return null;
  try {
    const encoded = hash.slice(HASH_PREFIX.length);
    if (!encoded) return null;
    const json = base64UrlToUtf8(encoded);
    const parsed = JSON.parse(json) as Workflow;
    if (parsed && Array.isArray(parsed.nodes)) return parsed;
  } catch {
    /* corrupted hash — caller can show a toast */
  }
  return null;
}

/**
 * Strip the workflow hash from the URL without reloading. Call after the
 * payload has been imported so a refresh doesn't re-import the same graph.
 */
export function clearShareHash(): void {
  if (typeof window === 'undefined') return;
  if (!window.location.hash.startsWith(HASH_PREFIX)) return;
  history.replaceState(null, '', window.location.pathname + window.location.search);
}
