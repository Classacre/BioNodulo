// Custom edge built from native React Flow primitives (<BaseEdge> +
// <EdgeLabelRenderer>). Path shape follows the canvas "Connection shape" setting
// (bezier / smoothstep / step / straight), read from the edge's data.pathType.
// Adds a small ✕ delete button at the midpoint when the edge is selected.
import { memo, useContext } from 'react';
import {
  BaseEdge, EdgeLabelRenderer,
  getBezierPath, getSmoothStepPath, getStraightPath,
  type EdgeProps,
} from '@xyflow/react';
import { useTranslation } from 'react-i18next';
import { BioEdgeActionsContext } from './bioEdgeActions';

function BioEdgeComponent({
  id, sourceX, sourceY, targetX, targetY, sourcePosition, targetPosition, style, markerEnd, selected, data,
}: EdgeProps) {
  const { t } = useTranslation();
  const actions = useContext(BioEdgeActionsContext);
  const pathType = (data as { pathType?: string } | undefined)?.pathType ?? 'bezier';
  const params = { sourceX, sourceY, sourcePosition, targetX, targetY, targetPosition };
  const [path, labelX, labelY] =
    pathType === 'straight' ? getStraightPath({ sourceX, sourceY, targetX, targetY })
    : pathType === 'step' ? getSmoothStepPath({ ...params, borderRadius: 0 })
    : pathType === 'smoothstep' ? getSmoothStepPath(params)
    : getBezierPath(params);
  return (
    <>
      <BaseEdge id={id} path={path} style={style} markerEnd={markerEnd} />
      {selected && (
        <EdgeLabelRenderer>
          <button
            type="button"
            className="bio-edge-delete nodrag nopan"
            style={{ transform: `translate(-50%, -50%) translate(${labelX}px, ${labelY}px)` }}
            onClick={(e) => { e.stopPropagation(); actions?.removeEdge(id); }}
            title={t('canvas.edge.delete')}
            aria-label={t('canvas.edge.delete')}
          >
            <span aria-hidden>✕</span>
          </button>
        </EdgeLabelRenderer>
      )}
    </>
  );
}

const BioEdge = memo(BioEdgeComponent);
export default BioEdge;
