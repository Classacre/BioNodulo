import { describe, expect, it } from 'vitest';

import {
  type LayoutRect,
  resolveOverlaps,
} from '../utils/autoLayout';

/** True if two rects are separated by at least `gap` px on some axis. */
function clears(a: LayoutRect, b: LayoutRect, gap: number): boolean {
  const horizontal =
    a.x + a.width + gap <= b.x || b.x + b.width + gap <= a.x;
  const vertical =
    a.y + a.height + gap <= b.y || b.y + b.height + gap <= a.y;
  return horizontal || vertical;
}

/** Apply a resolution Map onto a copy of the input rects. */
function applyMoves(
  rects: LayoutRect[],
  moves: Map<string, { x: number; y: number }>,
): LayoutRect[] {
  return rects.map((r) => {
    const m = moves.get(r.id);
    return m ? { ...r, x: m.x, y: m.y } : { ...r };
  });
}

describe('resolveOverlaps', () => {
  it('returns an empty map when nothing overlaps', () => {
    const rects: LayoutRect[] = [
      { id: 'a', x: 0, y: 0, width: 100, height: 50 },
      { id: 'b', x: 0, y: 200, width: 100, height: 50 },
      { id: 'c', x: 300, y: 0, width: 100, height: 50 },
    ];
    const moves = resolveOverlaps(rects);
    expect(moves.size).toBe(0);
  });

  it('pushes the lower of two vertically-overlapping rects downward', () => {
    const gap = 16;
    const rects: LayoutRect[] = [
      { id: 'top', x: 0, y: 0, width: 100, height: 100 },
      // overlaps "top" heavily; sits below it.
      { id: 'bottom', x: 0, y: 40, width: 100, height: 100 },
    ];

    const moves = resolveOverlaps(rects, { gap });

    // Only the lower node moves.
    expect(moves.has('top')).toBe(false);
    expect(moves.has('bottom')).toBe(true);

    const moved = applyMoves(rects, moves);
    const top = moved.find((r) => r.id === 'top')!;
    const bottom = moved.find((r) => r.id === 'bottom')!;

    // Upper node unchanged.
    expect(top.x).toBe(0);
    expect(top.y).toBe(0);

    // Lower node pushed strictly down and now clears the gap.
    expect(bottom.x).toBe(0);
    expect(bottom.y).toBeGreaterThan(40);
    expect(bottom.y).toBeGreaterThanOrEqual(top.y + top.height + gap);
    expect(clears(top, bottom, gap)).toBe(true);
  });

  it('never moves a pinned node; its neighbor moves instead', () => {
    const gap = 16;
    const rects: LayoutRect[] = [
      { id: 'pinned', x: 0, y: 100, width: 100, height: 100, pinned: true },
      // overlaps the pinned node; it sits above (smaller y center).
      { id: 'mover', x: 0, y: 40, width: 100, height: 100 },
    ];

    const moves = resolveOverlaps(rects, { gap });

    expect(moves.has('pinned')).toBe(false);
    expect(moves.has('mover')).toBe(true);

    const moved = applyMoves(rects, moves);
    const pinned = moved.find((r) => r.id === 'pinned')!;
    const mover = moved.find((r) => r.id === 'mover')!;

    // Pinned node truly unchanged.
    expect(pinned.x).toBe(0);
    expect(pinned.y).toBe(100);

    // Overlap resolved by moving the other node.
    expect(clears(pinned, mover, gap)).toBe(true);
  });

  it('is idempotent: re-running on the resolved layout yields no moves', () => {
    const gap = 16;
    const rects: LayoutRect[] = [
      { id: 'a', x: 0, y: 0, width: 120, height: 80 },
      { id: 'b', x: 10, y: 30, width: 120, height: 80 },
      { id: 'c', x: 20, y: 60, width: 120, height: 80 },
    ];

    const firstMoves = resolveOverlaps(rects, { gap });
    expect(firstMoves.size).toBeGreaterThan(0);

    const resolved = applyMoves(rects, firstMoves);
    const secondMoves = resolveOverlaps(resolved, { gap });

    expect(secondMoves.size).toBe(0);
  });

  it('is deterministic: same input yields identical output', () => {
    const rects: LayoutRect[] = [
      { id: 'a', x: 0, y: 0, width: 100, height: 100 },
      { id: 'b', x: 0, y: 50, width: 100, height: 100 },
      { id: 'c', x: 0, y: 90, width: 100, height: 100 },
    ];

    const a = resolveOverlaps(rects);
    const b = resolveOverlaps(rects);

    expect([...a.entries()].sort()).toEqual([...b.entries()].sort());
  });

  it('a node growing taller pushes all the lower nodes down without overlaps', () => {
    const gap = 16;
    // "grown" is a tall node that now overlaps three stacked nodes below it.
    const rects: LayoutRect[] = [
      { id: 'grown', x: 0, y: 0, width: 100, height: 260 },
      { id: 'n1', x: 0, y: 80, width: 100, height: 60 },
      { id: 'n2', x: 0, y: 160, width: 100, height: 60 },
      { id: 'n3', x: 0, y: 240, width: 100, height: 60 },
    ];

    const moves = resolveOverlaps(rects, { gap });

    // The tall node should stay put (it is the upper node in every pair).
    expect(moves.has('grown')).toBe(false);

    const moved = applyMoves(rects, moves);

    // No remaining overlaps among any pair.
    for (let i = 0; i < moved.length; i++) {
      for (let j = i + 1; j < moved.length; j++) {
        expect(
          clears(moved[i], moved[j], gap),
          `${moved[i].id} vs ${moved[j].id}`,
        ).toBe(true);
      }
    }

    // All three lower nodes ended up below the grown node.
    const grown = moved.find((r) => r.id === 'grown')!;
    for (const id of ['n1', 'n2', 'n3']) {
      const node = moved.find((r) => r.id === id)!;
      expect(node.y).toBeGreaterThanOrEqual(grown.y + grown.height + gap - 0.001);
    }
  });
});
