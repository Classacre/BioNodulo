/**
 * Where a newly added node should land.
 *
 * Nodes used to be placed at a fixed point near the flow origin, so after
 * panning anywhere the node appeared off-screen behind whatever you were
 * looking at: "it adds it to the centre of the whole tool window so i have to
 * move to the centre and bring it to the back". A node should arrive where the
 * user is looking.
 *
 * The viewport belongs to React Flow, which lives inside the canvas, while the
 * add handlers live in App. Rather than thread an instance through several
 * component layers, the canvas registers a reader here and callers ask for a
 * position. There is exactly one canvas, so a module-level slot is honest about
 * the cardinality.
 */

/** Reads the visible centre in flow coordinates. Registered by the canvas. */
export type ViewportCenterReader = () => [number, number] | null;

let reader: ViewportCenterReader | null = null;

/** Called by the canvas on mount; pass null on unmount. */
export function setViewportCenterReader(next: ViewportCenterReader | null): void {
  reader = next;
}

/** Fallback used before the canvas mounts, or in tests. */
export const DEFAULT_POSITION: [number, number] = [200, 200];

/** Nodes dropped at the same point would stack exactly; nudge each one. */
const SPREAD = 40;

/**
 * A position for a new node: the centre of the visible canvas, jittered so
 * several additions in a row do not land on top of each other.
 */
export function newNodePosition(): [number, number] {
  const centre = reader?.() ?? null;
  const [x, y] = centre ?? DEFAULT_POSITION;
  return [x + (Math.random() - 0.5) * SPREAD, y + (Math.random() - 0.5) * SPREAD];
}

/**
 * Centre of a viewport, in flow coordinates.
 *
 * React Flow's transform maps flow -> screen as `screen = flow * zoom + pan`,
 * so the inverse of the container's midpoint is `(mid - pan) / zoom`.
 */
export function centerOfViewport(
  viewport: { x: number; y: number; zoom: number },
  size: { width: number; height: number },
): [number, number] {
  const zoom = viewport.zoom || 1;
  return [
    (size.width / 2 - viewport.x) / zoom,
    (size.height / 2 - viewport.y) / zoom,
  ];
}
