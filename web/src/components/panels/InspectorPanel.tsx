// Persistent right-rail wrapper around `NodeEditor`. The floating modal
// editor (double-click on a node) keeps working; this panel always shows the
// currently selected node so users can keep params visible while editing the
// graph.
//
// We synthesise a minimal `GraphNode`-shaped object from the workflow node +
// metadata. NodeEditor only reads `id`, `title`, `color`, `meta`, `params` —
// the rest is filled with sensible defaults.

import type { ReactNode } from 'react';
import type { ObjectInfo, WorkflowNode } from '../../types';
import type { GraphNode } from '../canvas/WorkflowCanvas';
import NodeEditor from '../nodes/NodeEditor';
import Icon from '../ui/Icon';

interface InspectorPanelProps {
  selectedNode: WorkflowNode | null;
  objectInfo: ObjectInfo;
  onParamChange: (nodeId: string, key: string, value: unknown) => void;
  onClose: () => void;
}

function emptyState(message: string, hint?: ReactNode): ReactNode {
  return (
    <div className="rail-panel-empty" style={{ padding: 16, fontSize: 12, color: 'var(--muted)' }}>
      <div style={{ fontWeight: 600, marginBottom: 6 }}>{message}</div>
      {hint && <div style={{ fontSize: 11, lineHeight: 1.5 }}>{hint}</div>}
    </div>
  );
}

export default function InspectorPanel({ selectedNode, objectInfo, onParamChange, onClose }: InspectorPanelProps) {
  return (
    <div className="rail-panel inspector-panel">
      <div className="rail-panel-header">
        <span>Inspector</span>
        <button className="btn btn-icon btn-sm" onClick={onClose} title="Close inspector">
          <Icon name="close" size={14} />
        </button>
      </div>
      <div className="rail-panel-body" style={{ overflow: 'auto' }}>
        {!selectedNode
          ? emptyState(
            'No node selected',
            'Click any node on the canvas to edit its parameters here. Double-click also opens a floating editor.',
          )
          : (() => {
            const meta = objectInfo[selectedNode.type] ?? selectedNode.node_info ?? null;
            const synthetic: GraphNode = {
              id: selectedNode.id,
              type: selectedNode.type,
              display_name: meta?.display_name || selectedNode.type,
              category: meta?.category || '',
              x: selectedNode.position?.[0] ?? 0,
              y: selectedNode.position?.[1] ?? 0,
              width: 240,
              height: 80,
              inputs: [],
              outputs: [],
              params: selectedNode.params || {},
              meta,
              color: selectedNode.ui?.color || 'var(--accent)',
              muted: false,
              bypassed: false,
              selected: true,
              collapsed: false,
              pinned: false,
              shape: 'card',
              title: selectedNode.ui?.title || meta?.display_name || selectedNode.type,
              visualOnly: false,
            };
            return (
              <NodeEditor
                node={synthetic}
                onParamChange={onParamChange}
                onClose={onClose}
              />
            );
          })()}
      </div>
    </div>
  );
}
