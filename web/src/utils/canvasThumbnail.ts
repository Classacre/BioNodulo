// Capture the live React Flow canvas to a PNG data URL using html-to-image.
// This replaces the old Canvas2D `exportThumbnailDataURL` graph rasteriser:
// instead of re-drawing nodes/edges imperatively, we snapshot the actual
// rendered React Flow DOM (the same pixels the user sees), so the export always
// matches the current node system with zero duplicate render logic.

import { toPng } from 'html-to-image';

// React Flow renders the transformed graph inside `.react-flow__viewport`,
// wrapped by the `.react-flow` pane. We snapshot the viewport so the capture
// covers the whole graph regardless of the current pan/zoom, then rely on the
// caller having framed it (fitView) beforehand.
const VIEWPORT_SELECTOR = '.react-flow__viewport';
const PANE_SELECTOR = '.react-flow';

export interface CaptureOptions {
  /** Output background. Pass `null`/omit for a dark canvas fill. */
  background?: string | null;
  /** Device pixel ratio for the raster (default 1; 2 = retina-crisp). */
  pixelRatio?: number;
}

/**
 * Snapshot the React Flow graph within `host` to a PNG data URL. Returns an
 * empty string if the React Flow DOM is not present (e.g. canvas not mounted).
 */
export async function captureCanvasThumbnail(
  host: HTMLElement | null,
  options: CaptureOptions = {},
): Promise<string> {
  if (!host) return '';
  const viewport = host.querySelector<HTMLElement>(VIEWPORT_SELECTOR);
  const pane = host.querySelector<HTMLElement>(PANE_SELECTOR);
  const target = viewport ?? pane;
  if (!target) return '';

  // Both `null` and omitted mean "dark canvas fill" (per CaptureOptions docs);
  // only an explicit color string overrides it.
  const background = options.background == null ? '#0f172a' : options.background;
  return toPng(target, {
    backgroundColor: background,
    pixelRatio: options.pixelRatio ?? 1,
    // The viewport is CSS-transformed (translate+scale); html-to-image honours
    // it, but we cap the filter so foreign/overlay-only nodes don't error out.
    filter: (node) => !(node instanceof HTMLElement && node.dataset.thumbnailExclude === 'true'),
  });
}
