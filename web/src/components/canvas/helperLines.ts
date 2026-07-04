// Alignment helper-lines math, adapted from the official React Flow helper-lines
// example. Given the in-flight position change of the dragged node, it finds the
// nearest edge/center alignment with any other node (within `distance` px) and
// returns the guide-line coordinates plus a snapped position.
import type { Node, NodePositionChange } from '@xyflow/react';

export interface HelperLinesResult {
  horizontal?: number;
  vertical?: number;
  snapPosition: { x?: number; y?: number };
}

export function getHelperLines(
  change: NodePositionChange,
  nodes: Node[],
  distance = 5,
): HelperLinesResult {
  const defaultResult: HelperLinesResult = { snapPosition: { x: undefined, y: undefined } };
  const nodeA = nodes.find((n) => n.id === change.id);
  if (!nodeA || !change.position) return defaultResult;

  const aW = nodeA.measured?.width ?? nodeA.width ?? 0;
  const aH = nodeA.measured?.height ?? nodeA.height ?? 0;
  const a = {
    left: change.position.x,
    right: change.position.x + aW,
    top: change.position.y,
    bottom: change.position.y + aH,
    width: aW,
    height: aH,
  };

  let vDist = distance;
  let hDist = distance;

  return nodes
    .filter((n) => n.id !== nodeA.id)
    .reduce<HelperLinesResult>((result, nodeB) => {
      const bW = nodeB.measured?.width ?? nodeB.width ?? 0;
      const bH = nodeB.measured?.height ?? nodeB.height ?? 0;
      const b = {
        left: nodeB.position.x,
        right: nodeB.position.x + bW,
        top: nodeB.position.y,
        bottom: nodeB.position.y + bH,
      };

      // Vertical guides (align on X).
      const leftLeft = Math.abs(a.left - b.left);
      if (leftLeft < vDist) { result.snapPosition.x = b.left; result.vertical = b.left; vDist = leftLeft; }
      const rightRight = Math.abs(a.right - b.right);
      if (rightRight < vDist) { result.snapPosition.x = b.right - a.width; result.vertical = b.right; vDist = rightRight; }
      const leftRight = Math.abs(a.left - b.right);
      if (leftRight < vDist) { result.snapPosition.x = b.right; result.vertical = b.right; vDist = leftRight; }
      const rightLeft = Math.abs(a.right - b.left);
      if (rightLeft < vDist) { result.snapPosition.x = b.left - a.width; result.vertical = b.left; vDist = rightLeft; }

      // Horizontal guides (align on Y).
      const topTop = Math.abs(a.top - b.top);
      if (topTop < hDist) { result.snapPosition.y = b.top; result.horizontal = b.top; hDist = topTop; }
      const bottomTop = Math.abs(a.bottom - b.top);
      if (bottomTop < hDist) { result.snapPosition.y = b.top - a.height; result.horizontal = b.top; hDist = bottomTop; }
      const bottomBottom = Math.abs(a.bottom - b.bottom);
      if (bottomBottom < hDist) { result.snapPosition.y = b.bottom - a.height; result.horizontal = b.bottom; hDist = bottomBottom; }
      const topBottom = Math.abs(a.top - b.bottom);
      if (topBottom < hDist) { result.snapPosition.y = b.bottom; result.horizontal = b.bottom; hDist = topBottom; }

      return result;
    }, defaultResult);
}
