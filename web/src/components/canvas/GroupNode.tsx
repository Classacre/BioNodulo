// Native React Flow group node (sub-flow container). Uses the built-in `group`
// node type semantics — no handles; child nodes reference it via parentId and
// move with it. Adds a resizer, a title label, and a toolbar (rename / ungroup /
// delete). The tinted body sits behind its children (React Flow renders parents
// under their children).
import { memo, useContext, useState } from 'react';
import { NodeResizer, NodeToolbar, Position, type NodeProps } from '@xyflow/react';
import { useTranslation } from 'react-i18next';
import { BioNodeActionsContext, MultiSelectContext } from './bioNodeActions';

export interface GroupNodeData extends Record<string, unknown> {
  title: string;
  color: string;
}

function GroupNodeComponent({ id, data, selected }: NodeProps) {
  const { t } = useTranslation();
  const actions = useContext(BioNodeActionsContext);
  const multiSelected = useContext(MultiSelectContext);
  const [hovered, setHovered] = useState(false);
  const { title, color } = data as GroupNodeData;

  return (
    <div
      className={`bio-group-node ${selected ? 'selected' : ''}`}
      style={{ ['--bio-group-color' as string]: color }}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
    >
      <NodeResizer
        isVisible={selected}
        minWidth={140}
        minHeight={90}
        onResizeEnd={(_e, params) => actions?.resize(id, Math.round(params.width), Math.round(params.height))}
      />
      <NodeToolbar isVisible={(selected || hovered) && !multiSelected} position={Position.Top} className="bio-node-toolbar">
        <button type="button" title={t('canvas.menu.rename')} onClick={() => actions?.rename(id)}>A</button>
        <button type="button" title={t('canvas.group.ungroup')} onClick={() => actions?.ungroup(id)}>⤢</button>
        <button type="button" className="danger" title={t('canvas.group.delete')} onClick={() => actions?.deleteGroup(id)}>✕</button>
      </NodeToolbar>
      <div className="bio-group-node-label" title={title}>{title}</div>
    </div>
  );
}

const GroupNode = memo(GroupNodeComponent);
export default GroupNode;
