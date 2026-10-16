import type { NodeMetadata, WorkflowNode } from '../types';
import type { FitViewOptions } from '@xyflow/react';
import { NODE_NOTE_WIDTH, NODE_WIDTH } from '../components/canvas/canvasModel';
import { getInteractiveWidgetEntries, NODE_HEADER_H, NODE_PIN_H } from './nodeLayout';

export interface PlacementRect { x: number; y: number; width: number; height: number }
export interface PlacementSize { width: number; height: number }
export interface SnippetCanvasArea extends PlacementSize { leftInset: number; rightInset: number; bottomInset: number }

const GAP = 40;
const positive = (value: unknown, fallback: number): number =>
  typeof value === 'number' && Number.isFinite(value) && value > 0 ? value : fallback;

/** Pixel padding is asymmetric because drawers and the console overlay Flow. */
export function snippetRevealOptions(area: SnippetCanvasArea, nodeIds: string[]): FitViewOptions {
  const marginX = Math.min(24, (area.width - area.leftInset - area.rightInset) / 4);
  const marginY = Math.min(24, (area.height - area.bottomInset) / 4);
  return { nodes: nodeIds.map(id => ({ id })), padding: {
    left: `${area.leftInset + marginX}px`, right: `${area.rightInset + marginX}px`,
    top: `${marginY}px`, bottom: `${area.bottomInset + marginY}px`,
  }, minZoom: 0, duration: 220 };
}

/** Live unscaled measurements win; unseen library nodes need a conservative size. */
export function snippetNodeSize(node: WorkflowNode, meta?: NodeMetadata, measured?: PlacementSize): PlacementSize {
  if (measured && Number.isFinite(measured.width) && Number.isFinite(measured.height)
    && measured.width > 0 && measured.height > 0) return measured;
  if (node.type === 'reroute') return { width: 20, height: 20 };
  const width = positive(node.ui?.width, node.type === 'note' ? NODE_NOTE_WIDTH : NODE_WIDTH);
  if (node.ui?.collapsed) return { width, height: NODE_HEADER_H };
  if (typeof node.ui?.height === 'number' && Number.isFinite(node.ui.height) && node.ui.height > 0) {
    return { width, height: node.ui.height };
  }
  if (node.type === 'note') {
    const columns = Math.max(1, Math.floor((width - 16) / 7));
    const lines = String(node.params?.text ?? '').split('\n')
      .reduce((count, line) => count + Math.max(1, Math.ceil(line.length / columns)), 0);
    return { width, height: NODE_HEADER_H + 16 + lines * 20 };
  }
  const inputs = { ...meta?.input_types?.required, ...meta?.input_types?.optional };
  const widgets = meta ? getInteractiveWidgetEntries(meta, node.params) : Object.keys(node.params).map(key => ({ key }));
  const widgetKeys = new Set(widgets.map(entry => entry.key));
  const ports = Object.keys(inputs).filter(key => !widgetKeys.has(key)).length + (meta?.return_types?.length ?? 1);
  return { width, height: NODE_HEADER_H + 24 + ports * NODE_PIN_H + widgets.length * 90 };
}

export function placementBounds(rects: PlacementRect[]): PlacementRect {
  if (!rects.length) return { x: 0, y: 0, width: 0, height: 0 };
  const x = Math.min(...rects.map(rect => rect.x));
  const y = Math.min(...rects.map(rect => rect.y));
  return { x, y, width: Math.max(...rects.map(rect => rect.x + rect.width)) - x,
    height: Math.max(...rects.map(rect => rect.y + rect.height)) - y };
}

export function placementOverlaps(a: PlacementRect, b: PlacementRect, gap = GAP): boolean {
  return a.x < b.x + b.width + gap && a.x + a.width + gap > b.x
    && a.y < b.y + b.height + gap && a.y + a.height + gap > b.y;
}

/** Search nearby visible gaps, then fall back outside the graph and reveal it. */
export function findSnippetPlacement(existing: PlacementRect[], snippet: PlacementSize, visible: PlacementRect): {
  x: number; y: number; needsReveal: boolean;
} {
  const marginX = Math.min(24, visible.width / 4);
  const marginY = Math.min(24, visible.height / 4);
  const inner = { x: visible.x + marginX, y: visible.y + marginY,
    width: visible.width - marginX * 2, height: visible.height - marginY * 2 };
  const ideal = { x: visible.x + (visible.width - snippet.width) / 2,
    y: visible.y + (visible.height - snippet.height) / 2 };
  const clampX = (x: number) => snippet.width <= inner.width
    ? Math.max(inner.x, Math.min(inner.x + inner.width - snippet.width, x)) : x;
  const clampY = (y: number) => snippet.height <= inner.height
    ? Math.max(inner.y, Math.min(inner.y + inner.height - snippet.height, y)) : y;
  const distance = (rect: { x: number; y: number }) => (rect.x - ideal.x) ** 2 + (rect.y - ideal.y) ** 2;
  const nearby = [...existing].sort((a, b) => distance(a) - distance(b)).slice(0, 16);
  const xs = new Set([clampX(ideal.x), inner.x, inner.x + inner.width - snippet.width]);
  const ys = new Set([clampY(ideal.y), inner.y, inner.y + inner.height - snippet.height]);
  for (const rect of nearby) {
    xs.add(clampX(rect.x - snippet.width - GAP));
    xs.add(clampX(rect.x + rect.width + GAP));
    ys.add(clampY(rect.y - snippet.height - GAP));
    ys.add(clampY(rect.y + rect.height + GAP));
  }
  const candidates = [...xs].flatMap(x => [...ys].map(y => ({ x: Math.round(x), y: Math.round(y) })));
  if (existing.length) {
    const bounds = placementBounds(existing);
    candidates.push(
      { x: Math.ceil(bounds.x + bounds.width + GAP), y: Math.round(ideal.y) },
      { x: Math.floor(bounds.x - snippet.width - GAP), y: Math.round(ideal.y) },
      { x: Math.round(ideal.x), y: Math.ceil(bounds.y + bounds.height + GAP) },
      { x: Math.round(ideal.x), y: Math.floor(bounds.y - snippet.height - GAP) },
    );
  }
  const fits = (rect: PlacementRect) => rect.x >= inner.x && rect.y >= inner.y
    && rect.x + rect.width <= inner.x + inner.width && rect.y + rect.height <= inner.y + inner.height;
  const at = (position: { x: number; y: number }): PlacementRect => ({ ...position, width: snippet.width, height: snippet.height });
  const free = candidates.filter(candidate => !existing.some(rect => placementOverlaps(at(candidate), rect)));
  free.sort((a, b) => Number(fits(at(b))) - Number(fits(at(a))) || distance(a) - distance(b));
  const position = free[0] ?? ideal;
  return { ...position, needsReveal: !fits(at(position)) };
}
