// Canvas grid + snap helpers. Node drags compute an ABSOLUTE position
// (start + total delta) and snap that, rather than snapping an accumulated
// per-frame delta — otherwise snap-to-grid rounds away each small frame delta
// and nodes become almost impossible to move on slow drags.

export const GRID_SIZE = 20;

/** Round a single coordinate to the nearest grid line. */
export function snapToGridValue(value: number, grid: number = GRID_SIZE): number {
  return Math.round(value / grid) * grid;
}

/**
 * Absolute drag coordinate: `start + delta`, snapped to the grid when enabled.
 *
 * `start` must be the position at the moment the drag began (not the node's
 * current, possibly already-snapped position) and `delta` the total movement
 * since then, so slow drags accumulate and cross grid lines as expected.
 */
export function dragCoordinate(
  start: number,
  delta: number,
  snap: boolean,
  grid: number = GRID_SIZE,
): number {
  const next = start + delta;
  return snap ? snapToGridValue(next, grid) : next;
}
