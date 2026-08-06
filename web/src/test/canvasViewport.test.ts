import { afterEach, describe, expect, it } from 'vitest';

import {
  DEFAULT_POSITION,
  newNodePosition,
  setViewportCenterReader,
} from '../state/canvasViewport';

/**
 * A node added from the library used to land at a fixed point near the flow
 * origin, so once you had panned anywhere it arrived off-screen behind the
 * graph: "i have to move to the centre and bring it to the back". It should
 * arrive where the user is looking.
 *
 * The screen-to-flow conversion itself is React Flow's `screenToFlowPosition`,
 * so what is left to test here is the fallback behaviour and the spread.
 */
afterEach(() => setViewportCenterReader(null));

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
