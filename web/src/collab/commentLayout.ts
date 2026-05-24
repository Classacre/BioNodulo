export interface OverlayPoint {
  x: number;
  y: number;
}

export interface OverlaySize {
  width: number;
  height: number;
}

export interface OverlayRect extends OverlayPoint, OverlaySize {}

export interface OverlayBounds {
  width: number;
  height: number;
}

const BOUNDS_PADDING = 8;
const NODE_GAP = 12;

export const COMMENT_PIN_HEIGHT = 24;
export const COMMENT_POPOVER_WIDTH = 300;
export const COMMENT_POPOVER_MAX_HEIGHT = 380;

export function getCommentPinSize(commentCount: number): OverlaySize {
  return {
    width: Math.max(24, 20 + String(Math.max(0, commentCount)).length * 7),
    height: COMMENT_PIN_HEIGHT,
  };
}

function clamp(value: number, min: number, max: number): number {
  if (max < min) return min;
  return Math.max(min, Math.min(value, max));
}

function clampToBounds(point: OverlayPoint, size: OverlaySize, bounds: OverlayBounds, padding = BOUNDS_PADDING): OverlayPoint {
  return {
    x: clamp(point.x, padding, bounds.width - size.width - padding),
    y: clamp(point.y, padding, bounds.height - size.height - padding),
  };
}

function intersects(a: OverlayRect, b: OverlayRect): boolean {
  return a.x < b.x + b.width
    && a.x + a.width > b.x
    && a.y < b.y + b.height
    && a.y + a.height > b.y;
}

export function getCommentPinPosition(nodeRect: OverlayRect, bounds: OverlayBounds, commentCount: number): OverlayPoint {
  const size = getCommentPinSize(commentCount);
  const aboveNode = {
    x: nodeRect.x + nodeRect.width - size.width + 2,
    y: nodeRect.y - size.height - 4,
  };
  const point = aboveNode.y >= BOUNDS_PADDING
    ? aboveNode
    : {
      x: nodeRect.x + nodeRect.width - size.width - 4,
      y: nodeRect.y + 6,
    };
  return clampToBounds(point, size, bounds);
}

export function getNodeCommentPopoverPosition(
  nodeRect: OverlayRect,
  bounds: OverlayBounds,
  pinPoint?: OverlayPoint,
  pinSize?: OverlaySize,
): OverlayPoint {
  const popoverSize = { width: COMMENT_POPOVER_WIDTH, height: COMMENT_POPOVER_MAX_HEIGHT };
  const rightSide = {
    x: nodeRect.x + nodeRect.width + NODE_GAP,
    y: nodeRect.y + 8,
  };
  const leftSide = {
    x: nodeRect.x - COMMENT_POPOVER_WIDTH - NODE_GAP,
    y: nodeRect.y + 8,
  };
  const preferred = rightSide.x + COMMENT_POPOVER_WIDTH + BOUNDS_PADDING <= bounds.width
    ? rightSide
    : leftSide;
  let point = clampToBounds(preferred, popoverSize, bounds);

  if (pinPoint && pinSize) {
    const pinRect = { ...pinPoint, ...pinSize };
    const popoverRect = { ...point, ...popoverSize };
    if (intersects(popoverRect, pinRect)) {
      const belowPin = clampToBounds(
        { x: point.x, y: pinPoint.y + pinSize.height + NODE_GAP },
        popoverSize,
        bounds,
      );
      const belowRect = { ...belowPin, ...popoverSize };
      point = intersects(belowRect, pinRect)
        ? clampToBounds({ x: point.x, y: pinPoint.y - COMMENT_POPOVER_MAX_HEIGHT - NODE_GAP }, popoverSize, bounds)
        : belowPin;
    }
  }

  return point;
}
