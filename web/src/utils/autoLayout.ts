/**
 * Pure, dependency-free overlap resolution for rectangular canvas nodes.
 *
 * Used to "push nodes aside" when a node grows (e.g. an inline preview appears
 * below it, increasing its height). Nodes are axis-aligned rectangles in canvas
 * coordinates (top-left origin, y increases downward). Overlaps are eliminated
 * by nudging nodes apart, biased strongly toward pushing the lower node down.
 *
 * No React, no DOM, no app imports.
 */

export interface LayoutRect {
  id: string;
  x: number;
  y: number;
  width: number;
  height: number;
  /** Pinned nodes never move; overlaps are resolved by moving the other node. */
  pinned?: boolean;
}

export interface ResolveOverlapsOptions {
  /** Required separation between nodes, in px. Default 16. */
  gap?: number;
  /** Maximum number of passes before giving up. Default 40. */
  maxIterations?: number;
}

/** Internal mutable working copy of a rect. */
interface WorkRect {
  id: string;
  x: number;
  y: number;
  width: number;
  height: number;
  pinned: boolean;
}

/** Movement smaller than this (px) is treated as "no move". */
const MOVE_EPSILON = 0.5;

/**
 * Compute how much two rectangles overlap once `gap` of required spacing is
 * added around them. Returns the penetration depth on each axis; a value > 0
 * means the rects are closer than `gap` on that axis (and thus violate the
 * required separation when they also violate it on the other axis).
 */
function penetration(
  a: WorkRect,
  b: WorkRect,
  gap: number,
): { px: number; py: number } {
  // Centers.
  const acx = a.x + a.width / 2;
  const acy = a.y + a.height / 2;
  const bcx = b.x + b.width / 2;
  const bcy = b.y + b.height / 2;

  // Required center distance to clear, per axis (half-widths + gap).
  const requiredX = a.width / 2 + b.width / 2 + gap;
  const requiredY = a.height / 2 + b.height / 2 + gap;

  // Penetration = required - actual center distance. >0 means too close.
  const px = requiredX - Math.abs(acx - bcx);
  const py = requiredY - Math.abs(acy - bcy);

  return { px, py };
}

/**
 * Resolve overlaps between rectangular nodes by moving them apart.
 *
 * Returns ONLY the nodes whose position actually changed (by > 0.5px on either
 * axis), as a Map of id -> new {x, y}. If nothing overlaps, returns an empty Map.
 */
export function resolveOverlaps(
  rects: LayoutRect[],
  options?: ResolveOverlapsOptions,
): Map<string, { x: number; y: number }> {
  const gap = options?.gap ?? 16;
  const maxIterations = options?.maxIterations ?? 40;

  // Stable working copies sorted by a deterministic key (y, then x, then id).
  // Sorting ensures the iteration order — and therefore the resolution — is
  // identical for identical input regardless of the caller's array order.
  const work: WorkRect[] = rects
    .map((r) => ({
      id: r.id,
      x: r.x,
      y: r.y,
      width: r.width,
      height: r.height,
      pinned: r.pinned === true,
    }))
    .sort((a, b) => {
      if (a.y !== b.y) return a.y - b.y;
      if (a.x !== b.x) return a.x - b.x;
      return a.id < b.id ? -1 : a.id > b.id ? 1 : 0;
    });

  const n = work.length;

  for (let iter = 0; iter < maxIterations; iter++) {
    let movedThisPass = false;

    for (let i = 0; i < n; i++) {
      for (let j = i + 1; j < n; j++) {
        const a = work[i];
        const b = work[j];

        const { px, py } = penetration(a, b, gap);

        // No overlap on at least one axis => required separation already met.
        if (px <= 0 || py <= 0) continue;

        // Both pinned: cannot resolve, skip (never move a pinned node).
        if (a.pinned && b.pinned) continue;

        // Decide push axis. Bias toward vertical separation: only push
        // horizontally when the nodes are essentially side-by-side, i.e. their
        // vertical center distance is small relative to their horizontal
        // center distance. This makes a growing (taller) node push the nodes
        // below it further down, the natural resolution for downward growth.
        const acx = a.x + a.width / 2;
        const acy = a.y + a.height / 2;
        const bcx = b.x + b.width / 2;
        const bcy = b.y + b.height / 2;

        const dx = bcx - acx;
        const dy = bcy - acy;

        // Side-by-side when horizontal separation dominates AND vertical
        // penetration is the deeper (more costly) axis to push along.
        const sideBySide = Math.abs(dx) > Math.abs(dy) && px <= py;

        if (sideBySide) {
          // Horizontal push: separate along x by `px`.
          // The node further right moves right; the one further left moves left.
          // Direction is deterministic; ties (dx === 0) fall back to id order.
          const aLeft = dx > 0 || (dx === 0 && a.id < b.id);
          applyHorizontal(a, b, px, aLeft);
        } else {
          // Vertical push (the common case). The node with the greater TOP edge
          // (y) is the "lower" one and gets pushed DOWNWARD so its top clears
          // the other's bottom + gap. Using the top edge (rather than the
          // center) means a node that grew TALLER — its top fixed, height
          // expanded downward — is treated as the upper node and stays put,
          // pushing the genuinely-lower nodes further down. Ties fall back to
          // id order for determinism.
          const bIsLower =
            b.y > a.y || (b.y === a.y && a.id < b.id);
          const lower = bIsLower ? b : a;
          const upper = bIsLower ? a : b;
          // Edge-based push distance: move the lower node's top to upper.bottom
          // + gap. This is exact regardless of the height difference.
          const amount = upper.y + upper.height + gap - lower.y;
          if (amount > 0) applyVertical(a, b, amount, bIsLower);
        }

        movedThisPass = true;
      }
    }

    if (!movedThisPass) break;
  }

  // Build result: only nodes that actually moved beyond the epsilon.
  const result = new Map<string, { x: number; y: number }>();
  const originalById = new Map<string, LayoutRect>();
  for (const r of rects) originalById.set(r.id, r);

  for (const w of work) {
    const orig = originalById.get(w.id);
    if (!orig) continue;
    if (
      Math.abs(w.x - orig.x) > MOVE_EPSILON ||
      Math.abs(w.y - orig.y) > MOVE_EPSILON
    ) {
      result.set(w.id, { x: w.x, y: w.y });
    }
  }

  return result;
}

/**
 * Push two rects apart vertically by `amount`. Prefer moving the lower node
 * down. If the node that "should" move is pinned, move the other one instead
 * (in the opposite direction). If neither is pinned, push the lower node down
 * by the full amount (keeping the upper node stationary), which biases toward
 * downward growth resolution and keeps the layout stable.
 */
function applyVertical(
  a: WorkRect,
  b: WorkRect,
  amount: number,
  bIsLower: boolean,
): void {
  const lower = bIsLower ? b : a;
  const upper = bIsLower ? a : b;

  if (!lower.pinned) {
    // Common path: shove the lower node straight down.
    lower.y += amount;
  } else if (!upper.pinned) {
    // Lower is pinned: move the upper node up instead.
    upper.y -= amount;
  }
  // else: both pinned — already filtered out by the caller.
}

/**
 * Push two rects apart horizontally by `amount`. `aLeft` indicates whether `a`
 * is the left node. The left node moves left and the right node moves right,
 * splitting the penetration; pinned nodes hold still and the full push lands on
 * their movable partner.
 */
function applyHorizontal(
  a: WorkRect,
  b: WorkRect,
  amount: number,
  aLeft: boolean,
): void {
  const left = aLeft ? a : b;
  const right = aLeft ? b : a;

  if (!left.pinned && !right.pinned) {
    // Split the push evenly to minimise total movement.
    const half = amount / 2;
    left.x -= half;
    right.x += half;
  } else if (left.pinned && !right.pinned) {
    right.x += amount;
  } else if (!left.pinned && right.pinned) {
    left.x -= amount;
  }
  // else: both pinned — already filtered out by the caller.
}
