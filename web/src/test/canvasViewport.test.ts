import { afterEach, describe, expect, it } from 'vitest';

import {
  centerOfViewport,
  DEFAULT_POSITION,
  newNodePosition,
  setViewportCenterReader,
} from '../state/canvasViewport';

/**
 * A node added from the library used to land at a fixed point near the flow
 * origin, so once you had panned anywhere it arrived off-screen behind the
 * graph: "i have to move to the centre and bring it to the back". It should
 * arrive where the user is looking.
 */
afterEach(() => setViewportCenterReader(null));

const SIZE = { width: 1000, height: 600 };

describe('viewport centre', () => {
  it('is the middle of the container when unpanned and unzoomed', () => {
    expect(centerOfViewport({ x: 0, y: 0, zoom: 1 }, SIZE)).toEqual([500, 300]);
  });

  it('follows a pan', () => {
    // Panning the canvas right by 200px moves the visible centre left in flow
    // space by the same amount.
    expect(centerOfViewport({ x: 200, y: 0, zoom: 1 }, SIZE)).toEqual([300, 300]);
  });

  it('accounts for zoom', () => {
    // Zoomed 2x, the same pixel span covers half the flow distance.
    expect(centerOfViewport({ x: 0, y: 0, zoom: 2 }, SIZE)).toEqual([250, 150]);
  });

  it('treats zoom 0 as 1 rather than dividing by zero', () => {
    const [x, y] = centerOfViewport({ x: 0, y: 0, zoom: 0 }, SIZE);
    expect(Number.isFinite(x)).toBe(true);
    expect(Number.isFinite(y)).toBe(true);
  });
});

describe('new node position', () => {
  it('uses the canvas centre once the canvas has registered', () => {
    setViewportCenterReader(() => [4000, 2000]);

    const [x, y] = newNodePosition();

    expect(x).toBeGreaterThan(3900);
    expect(x).toBeLessThan(4100);
    expect(y).toBeGreaterThan(1900);
    expect(y).toBeLessThan(2100);
  });

  it('falls back before the canvas mounts', () => {
    const [x, y] = newNodePosition();

    expect(x).toBeCloseTo(DEFAULT_POSITION[0], -2);
    expect(y).toBeCloseTo(DEFAULT_POSITION[1], -2);
  });

  it('falls back when the canvas has no size yet', () => {
    // A container measured before layout reports 0x0; placing a node at the
    // resulting NaN would lose it entirely.
    setViewportCenterReader(() => null);

    const [x, y] = newNodePosition();

    expect(Number.isFinite(x)).toBe(true);
    expect(Number.isFinite(y)).toBe(true);
  });

  it('spreads repeated additions so they do not stack exactly', () => {
    setViewportCenterReader(() => [0, 0]);

    const positions = Array.from({ length: 8 }, () => newNodePosition().join(','));

    expect(new Set(positions).size).toBeGreaterThan(1);
  });
});
