// Custom edge built from native React Flow primitives (<BaseEdge> +
// <EdgeLabelRenderer> + getBezierPath). Renders the same bezier link as the
// default edge, plus a small ✕ delete button at its midpoint — shown only when
// the edge is selected, so clicking a link gives you a one-tap delete.
import { memo, useContext } from 'react';
import { BaseEdge, EdgeLabelRenderer, getBezierPath, type EdgeProps } from '@xyflow/react';
import { BioEdgeActionsContext } from './bioEdgeActions';

function BioEdgeComponent({
  id, sourceX, sourceY, targetX, targetY, sourcePosition, targetPosition, style, markerEnd, selected,
}: EdgeProps) {
  const actions = useContext(BioEdgeActionsContext);
  const [path, labelX, labelY] = getBezierPath({
    sourceX, sourceY, sourcePosition, targetX, targetY, targetPosition,
  });
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
            title="Delete link"
            aria-label="Delete link"
          >
            ✕
          </button>
        </EdgeLabelRenderer>
      )}
    </>
  );
}

const BioEdge = memo(BioEdgeComponent);
export default BioEdge;
