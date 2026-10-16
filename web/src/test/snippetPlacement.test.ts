import { describe, expect, it, vi } from 'vitest';
import { fitViewport, getViewportForBounds, type Viewport } from '@xyflow/system';
import { findSnippetPlacement, placementBounds, placementOverlaps, snippetNodeSize, snippetRevealOptions, type PlacementRect } from '../utils/snippetPlacement';
import type { NodeMetadata, WorkflowNode } from '../types';

const visible = { x: -600, y: -300, width: 1500, height: 1000 };
const existing = [
  { x: -390, y: 0, width: 260, height: 120 },
  { x: 0, y: 0, width: 220, height: 280 },
  { x: 440, y: 0, width: 220, height: 280 },
];
const size = { width: 1050, height: 280 };
const at = (position: { x: number; y: number }, dimensions = size): PlacementRect => ({ ...position, width: dimensions.width, height: dimensions.height });

describe('collision-aware snippet placement', () => {
  it('centers the entire snippet in an empty panned/zoomed viewport', () => {
    const position = findSnippetPlacement([], size, visible);
    expect(position).toEqual({ x: -375, y: 60, needsReveal: false });
    expect(position.x + size.width / 2).toBe(visible.x + visible.width / 2);
  });

  it('finds a visible gap for the actual three-node audit layout without moving existing nodes', () => {
    const before = structuredClone(existing);
    const position = findSnippetPlacement(existing, size, visible);
    expect(existing.some(rect => placementOverlaps(at(position), rect))).toBe(false);
    expect(position.needsReveal).toBe(false);
    expect(position.x).toBeGreaterThanOrEqual(visible.x + 24);
    expect(position.x + size.width).toBeLessThanOrEqual(visible.x + visible.width - 24);
    expect(position.y).toBeGreaterThanOrEqual(visible.y + 24);
    expect(position.y + size.height).toBeLessThanOrEqual(visible.y + visible.height - 24);
    expect(findSnippetPlacement(existing, size, visible)).toEqual(position);
    expect(existing).toEqual(before);
  });

  it('treats earlier insertions as obstacles and keeps the same internal bounding box', () => {
    const first = findSnippetPlacement(existing, size, visible);
    const second = findSnippetPlacement([...existing, at(first)], size, visible);
    expect(placementOverlaps(at(first), at(second))).toBe(false);
    expect(existing.some(rect => placementOverlaps(at(second), rect))).toBe(false);
  });

  it('uses a collision-free fallback and requests reveal when the group cannot fit', () => {
    const crowded = { x: -100, y: -100, width: 200, height: 150 };
    const position = findSnippetPlacement(existing, size, crowded);
    expect(position.needsReveal).toBe(true);
    expect(existing.some(rect => placementOverlaps(at(position), rect))).toBe(false);
    expect(Number.isFinite(position.x) && Number.isFinite(position.y)).toBe(true);
  });

  it('checks all obstacles even when the nearest-candidate search is bounded', () => {
    const many = Array.from({ length: 40 }, (_, index) => ({ x: index * 300, y: index * 120,
      width: 260, height: 300 }));
    const position = findSnippetPlacement(many, size, visible);
    expect(many.some(rect => placementOverlaps(at(position), rect))).toBe(false);
  });

  it('does not confuse an original negative bounding-box origin with the desired placement', () => {
    const bounds = placementBounds(existing);
    expect(bounds).toEqual({ x: -390, y: 0, width: 1050, height: 280 });
    const position = findSnippetPlacement(existing, bounds, visible);
    expect(existing.some(rect => placementOverlaps(at(position, bounds), rect))).toBe(false);
    expect(placementBounds([])).toEqual({ x: 0, y: 0, width: 0, height: 0 });
  });
});

describe('installed XYFlow overlay-aware insertion reveal', () => {
  it('fits only inserted IDs into side/console padding even below the normal minimum zoom', async () => {
    const bounds = { x: 1000, y: 800, width: 20000, height: 5000 };
    const area = { width: 1200, height: 900, leftInset: 400, rightInset: 200, bottomInset: 450 };
    const options = snippetRevealOptions(area, ['new']);
    const node = (id: string, rect: PlacementRect) => {
      const userNode = { id, position: { x: rect.x, y: rect.y }, data: {} };
      return { ...userNode, measured: { width: rect.width, height: rect.height },
        internals: { positionAbsolute: userNode.position, z: 0, userNode } };
    };
    const nodes = new Map([['new', node('new', bounds)], ['existing', node('existing', {
      x: -1000000, y: -1000000, width: 220, height: 300,
    })]]);
    const setViewport = vi.fn(async (view: Viewport) => ({ x: view.x, y: view.y, k: view.zoom }));
    type PanZoom = Parameters<typeof fitViewport>[0]['panZoom'];
    await fitViewport({ nodes, width: area.width, height: area.height, minZoom: 0.1, maxZoom: 2,
      panZoom: { setViewport } as unknown as PanZoom }, options);
    expect(setViewport).toHaveBeenCalledOnce();
    const view = setViewport.mock.calls[0][0];
    expect(view).toEqual(getViewportForBounds(bounds, area.width, area.height, options.minZoom!, 2, options.padding!));
    expect(view.zoom).toBeGreaterThan(0);
    expect(view.zoom).toBeLessThan(0.1);
    expect(bounds.x * view.zoom + view.x).toBeGreaterThanOrEqual(424 - 0.0001);
    expect((bounds.x + bounds.width) * view.zoom + view.x).toBeLessThanOrEqual(976 + 0.0001);
    expect(bounds.y * view.zoom + view.y).toBeGreaterThanOrEqual(24 - 0.0001);
    expect((bounds.y + bounds.height) * view.zoom + view.y).toBeLessThanOrEqual(426 + 0.0001);
  });

  it('keeps a one-pixel drawable region finite with at most native subpixel quantization', () => {
    const area = { width: 390, height: 644, leftInset: 389, rightInset: 0, bottomInset: 643 };
    const bounds = { x: -390, y: -700, width: 20000, height: 5000 };
    const options = snippetRevealOptions(area, ['new']);
    const view = getViewportForBounds(bounds, area.width, area.height, options.minZoom!, 2, options.padding!);
    expect(Object.values(view).every(Number.isFinite)).toBe(true);
    expect(view.zoom).toBeGreaterThan(0);
    // Installed getViewportForBounds floors requested pixel padding and the
    // applied bounds in calculateAppliedPaddings. With only one pixel free,
    // asymmetric correction can shift a fractional pixel (currently 0.5px).
    // This is a finite-fit guard, not a readability/strict visibility claim.
    // The normal live-layout case below retains strict containment bounds.
    expect(bounds.x * view.zoom + view.x).toBeGreaterThanOrEqual(389 - 1);
    expect((bounds.x + bounds.width) * view.zoom + view.x).toBeLessThanOrEqual(390 + 1);
    expect(bounds.y * view.zoom + view.y).toBeGreaterThanOrEqual(-1);
    expect((bounds.y + bounds.height) * view.zoom + view.y).toBeLessThanOrEqual(1 + 1);
  });

  it('contains the audit group within the exact live Workspace and Console geometry', () => {
    const area = { width: 1224, height: 644, leftInset: 372, rightInset: 0, bottomInset: 280 };
    const bounds = { x: 700, y: 40, width: 1050, height: 400 };
    const options = snippetRevealOptions(area, ['new']);
    const view = getViewportForBounds(bounds, area.width, area.height, options.minZoom!, 2, options.padding!);
    expect(bounds.x * view.zoom + view.x).toBeGreaterThanOrEqual(396 - 0.0001);
    expect((bounds.x + bounds.width) * view.zoom + view.x).toBeLessThanOrEqual(1200 + 0.0001);
    expect(bounds.y * view.zoom + view.y).toBeGreaterThanOrEqual(24 - 0.0001);
    expect((bounds.y + bounds.height) * view.zoom + view.y).toBeLessThanOrEqual(340 + 0.0001);
  });
});

describe('snippet node bounds', () => {
  const node: WorkflowNode = { id: 'note', type: 'note', position: [0, 0], params: { text: 'A'.repeat(600) } };

  it('uses unscaled live DOM size instead of zoomed or estimated dimensions', () => {
    expect(snippetNodeSize(node, undefined, { width: 400, height: 700 })).toEqual({ width: 400, height: 700 });
  });

  it('honors user size, collapse, reroutes and long metadata-free notes', () => {
    expect(snippetNodeSize({ ...node, ui: { width: 300, height: 900 } })).toEqual({ width: 300, height: 900 });
    expect(snippetNodeSize({ ...node, ui: { width: 300, height: 900, collapsed: true } })).toEqual({ width: 300, height: 32 });
    expect(snippetNodeSize({ ...node, type: 'reroute' })).toEqual({ width: 20, height: 20 });
    expect(snippetNodeSize(node).height).toBeGreaterThan(350);
    expect(snippetNodeSize(node, undefined, { width: Infinity, height: NaN }).height).toBeGreaterThan(350);
  });

  it('includes visible widgets and ports for unseen ordinary nodes', () => {
    const meta = { id: 'example', input_types: { required: {
      table: { type: 'TABLE', forceInput: true }, text: { type: 'STRING' }, options: { type: 'JSON' },
    } }, return_types: ['STRING'] } as NodeMetadata;
    expect(snippetNodeSize({ ...node, type: 'example', params: { text: 'Hello', options: '{}' } }, meta).height)
      .toBeGreaterThanOrEqual(32 + 2 * 22 + 2 * 90);
  });
});
