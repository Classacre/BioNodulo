// Custom edge built from a native React Flow primitive (<BaseEdge>). Path shape
// follows the canvas "Connection shape" setting (bezier / smoothstep / step /
// straight), read from the edge's data.pathType. Deletion is handled by dragging
// an endpoint onto empty canvas, the edge right-click menu, or the Delete key —
// there is no on-edge ✕ button.
import { memo } from 'react';
import {
  BaseEdge,
  getBezierPath, getSmoothStepPath, getStraightPath,
  type EdgeProps,
} from '@xyflow/react';

function BioEdgeComponent({
  id, sourceX, sourceY, targetX, targetY, sourcePosition, targetPosition, style, markerEnd, data,
}: EdgeProps) {
  const pathType = (data as { pathType?: string } | undefined)?.pathType ?? 'bezier';
  const params = { sourceX, sourceY, sourcePosition, targetX, targetY, targetPosition };
  const [path] =
    pathType === 'straight' ? getStraightPath({ sourceX, sourceY, targetX, targetY })
    : pathType === 'step' ? getSmoothStepPath({ ...params, borderRadius: 0 })
    : pathType === 'smoothstep' ? getSmoothStepPath(params)
    : getBezierPath(params);
  return <BaseEdge id={id} path={path} style={style} markerEnd={markerEnd} />;
}

const BioEdge = memo(BioEdgeComponent);
export default BioEdge;
