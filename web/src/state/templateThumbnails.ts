// Tiny LRU cache for template thumbnail PNG data URLs. Templates can have a
// server-rendered `thumbnail_url`, but for local templates (and for templates
// without a backing PNG on disk) we render the workflow JSON client-side via
// `renderWorkflowThumbnailPng` and embed the JSON via `embedWorkflowInPngDataUrl`,
// so dragging a card off the panel onto the canvas reuses the same
// PNG-with-embedded-workflow import path used by the export flow.
//
// LRU is bounded at 50 entries; rendering is cheap but we don't want to keep
// every template card's data URL alive forever.

import type { Workflow } from '../types';
import { renderWorkflowThumbnailPng } from '../utils/workflowThumbnail';
import { embedWorkflowInPngDataUrl } from '../utils/pngMetadata';

const MAX_ENTRIES = 50;

interface CachedThumb {
  /** PNG data URL with the workflow JSON embedded as a tEXt chunk. */
  dataUrl: string;
  /** Stand-alone Blob URL for `<img>` consumption — created on first read. */
  objectUrl?: string;
}

const cache = new Map<string, CachedThumb>();
// Tracks in-flight renders so concurrent callers for the same templateId (e.g.
// React effect double-invocation) await one render instead of each creating a
// separate Blob URL — which would leak the untracked one past LRU/clear.
const inflight = new Map<string, Promise<{ dataUrl: string; objectUrl: string } | null>>();

function touch(key: string, value: CachedThumb): void {
  cache.delete(key);
  cache.set(key, value);
  while (cache.size > MAX_ENTRIES) {
    const firstKey = cache.keys().next().value;
    if (firstKey === undefined) break;
    const evicted = cache.get(firstKey);
    if (evicted?.objectUrl) URL.revokeObjectURL(evicted.objectUrl);
    cache.delete(firstKey);
  }
}

/** Render + embed once per (templateId, workflow) pair; subsequent calls hit
 *  the LRU. Returns `null` if rendering fails. */
export async function getOrRenderTemplateThumbnail(
  templateId: string,
  workflow: Workflow,
): Promise<{ dataUrl: string; objectUrl: string } | null> {
  const cached = cache.get(templateId);
  if (cached) {
    cache.delete(templateId);
    cache.set(templateId, cached);
    if (!cached.objectUrl) {
      try {
        const blob = embedWorkflowInPngDataUrl(cached.dataUrl, workflow);
        cached.objectUrl = URL.createObjectURL(blob);
      } catch {
        return { dataUrl: cached.dataUrl, objectUrl: cached.dataUrl };
      }
    }
    return { dataUrl: cached.dataUrl, objectUrl: cached.objectUrl };
  }

  // Cache miss: de-dupe concurrent renders for the same templateId so racing
  // callers share one render + one Blob URL (see `inflight` above).
  const existing = inflight.get(templateId);
  if (existing) return existing;

  const pending = (async () => {
    let dataUrl: string;
    try {
      dataUrl = await renderWorkflowThumbnailPng(workflow);
    } catch {
      return null;
    }
    let objectUrl = dataUrl;
    try {
      const blob = embedWorkflowInPngDataUrl(dataUrl, workflow);
      objectUrl = URL.createObjectURL(blob);
    } catch {
      // Embedding failed; the rendered PNG without metadata is still usable as
      // a visual thumbnail.
    }
    touch(templateId, { dataUrl, objectUrl });
    return { dataUrl, objectUrl };
  })().finally(() => {
    inflight.delete(templateId);
  });

  inflight.set(templateId, pending);
  return pending;
}

/** Clear the cache (used by tests). */
export function clearTemplateThumbnailCache(): void {
  cache.forEach(entry => { if (entry.objectUrl) URL.revokeObjectURL(entry.objectUrl); });
  cache.clear();
}
