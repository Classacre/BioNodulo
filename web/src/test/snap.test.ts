import { describe, it, expect } from 'vitest';
import { snapToGridValue, dragCoordinate, GRID_SIZE } from '../utils/snap';

describe('snapToGridValue', () => {
  it('rounds to the nearest grid line', () => {
    expect(snapToGridValue(0)).toBe(0);
    expect(snapToGridValue(9)).toBe(0);
    expect(snapToGridValue(10)).toBe(20);
    expect(snapToGridValue(31)).toBe(40);
    expect(GRID_SIZE).toBe(20);
  });
});

describe('dragCoordinate', () => {
  it('returns the raw position when snapping is disabled', () => {
    expect(dragCoordinate(100, 3, false)).toBe(103);
    expect(dragCoordinate(100, 47, false)).toBe(147);
  });

  it('snaps the absolute (start + delta) position, not the per-frame delta', () => {
    // Regression for the "nodes are hard to move with snap on" bug: the old code
    // snapped each tiny per-frame delta added to the already-snapped position, so
    // small movements rounded back to the same grid line and the node never moved.
    // Using start + TOTAL delta, a slow drag accumulates and crosses grid lines.
    const start = 100; // already on a grid line
    expect(dragCoordinate(start, 3, true)).toBe(100); // tiny move: stays
    expect(dragCoordinate(start, 9, true)).toBe(100); // still under half a cell
    expect(dragCoordinate(start, 11, true)).toBe(120); // crosses the halfway point
    expect(dragCoordinate(start, 25, true)).toBe(120);
    expect(dragCoordinate(start, 31, true)).toBe(140);
  });

  it('handles negative deltas symmetrically', () => {
    expect(dragCoordinate(100, -11, true)).toBe(80);
    expect(dragCoordinate(100, -9, true)).toBe(100);
  });

  it('respects a custom grid size (configurable bionodulo.canvas.gridSize)', () => {
    // grid = 50: a 30px move from an on-grid start crosses the halfway point.
    expect(dragCoordinate(100, 30, true, 50)).toBe(150);
    expect(dragCoordinate(100, 20, true, 50)).toBe(100);
    expect(snapToGridValue(173, 50)).toBe(150);
    expect(snapToGridValue(176, 50)).toBe(200);
  });
});
