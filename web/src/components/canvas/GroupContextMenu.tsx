import { useState, useEffect, useRef } from 'react';
import type { WorkflowGroup, WorkflowNode } from '../../types';
import { promptDialog } from '../ui';

const PRESET_COLORS = [
  '#ef4444', '#f97316', '#f59e0b', '#84cc16', '#22c55e',
  '#10b981', '#14b8a6', '#06b6d4', '#0ea5e9', '#3b82f6',
  '#6366f1', '#8b5cf6', '#a855f7', '#d946ef', '#ec4899',
  '#f43f5e', '#64748b', '#94a3b8',
];

interface GroupContextMenuProps {
  x: number;
  y: number;
  groupId: string;
  groups: WorkflowGroup[];
  nodes: WorkflowNode[];
  onGroupsChange: (groups: WorkflowGroup[]) => void;
  onNodesChange: (nodes: WorkflowNode[]) => void;
  onClose: () => void;
}

function nodesInsideGroup(group: WorkflowGroup, nodes: WorkflowNode[]): WorkflowNode[] {
  const gx1 = group.position[0];
  const gy1 = group.position[1];
  const gx2 = gx1 + group.width;
  const gy2 = gy1 + group.height;
  return nodes.filter(node => (
    node.position[0] >= gx1 && node.position[0] <= gx2
    && node.position[1] >= gy1 && node.position[1] <= gy2
  ));
}

function applyToGroupNodes(
  group: WorkflowGroup | undefined,
  nodes: WorkflowNode[],
  patch: (node: WorkflowNode) => Partial<WorkflowNode['ui']>,
): WorkflowNode[] {
  if (!group) return nodes;
  const insideIds = new Set(nodesInsideGroup(group, nodes).map(n => n.id));
  return nodes.map(node => (
    insideIds.has(node.id)
      ? { ...node, ui: { ...node.ui, ...patch(node) } }
      : node
  ));
}

// Estimate each node's on-screen footprint. We can't know widget-driven node
// heights from this side of the canvas, so we fall back to sensible defaults
// that match the canvas's NODE_HEADER_H / NODE_PIN_H constants. The group
// bounds get a comfortable padding so the title bar still has breathing room.
const NODE_DEFAULT_WIDTH = 220;
const NODE_DEFAULT_HEIGHT = 80;
const GROUP_FIT_PADDING = 20;

function nodeFootprint(node: WorkflowNode): { x: number; y: number; w: number; h: number } {
  const [x, y] = node.position;
  const w = typeof node.ui?.width === 'number' ? node.ui.width : NODE_DEFAULT_WIDTH;
  const h = typeof node.ui?.height === 'number' ? node.ui.height : NODE_DEFAULT_HEIGHT;
  return { x, y, w, h };
}

function fitGroupToNodes(
  group: WorkflowGroup,
  nodes: WorkflowNode[],
): WorkflowGroup {
  const inside = nodesInsideGroup(group, nodes);
  if (inside.length === 0) return group;
  let minX = Infinity;
  let minY = Infinity;
  let maxX = -Infinity;
  let maxY = -Infinity;
  for (const node of inside) {
    const { x, y, w, h } = nodeFootprint(node);
    if (x < minX) minX = x;
    if (y < minY) minY = y;
    if (x + w > maxX) maxX = x + w;
    if (y + h > maxY) maxY = y + h;
  }
  return {
    ...group,
    position: [minX - GROUP_FIT_PADDING, minY - GROUP_FIT_PADDING - 4] as [number, number],
    width: Math.max(120, maxX - minX + GROUP_FIT_PADDING * 2),
    height: Math.max(80, maxY - minY + GROUP_FIT_PADDING * 2 + 4),
  };
}

export default function GroupContextMenu({ x, y, groupId, groups, nodes, onGroupsChange, onNodesChange, onClose }: GroupContextMenuProps) {
  const ref = useRef<HTMLDivElement>(null);
  const [showColors, setShowColors] = useState(false);

  const group = groups.find(gg => gg.id === groupId);

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (!ref.current?.contains(e.target as Node)) onClose();
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [onClose]);

  if (showColors) {
    return (
      <div ref={ref} className="context-menu" style={{ left: x, top: y, zIndex: 200 }}>
        <div className="context-menu-body">
          <div className="context-menu-item" onClick={() => setShowColors(false)}>← Back</div>
          <div className="context-menu-sep" />
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(6, 1fr)', gap: 4, padding: '4px 8px' }}>
            {PRESET_COLORS.map(c => (
              <div
                key={c}
                style={{ width: 20, height: 20, borderRadius: 4, background: c, cursor: 'pointer', border: '1px solid var(--border)' }}
                onClick={() => {
                  onGroupsChange(groups.map(gg => gg.id === groupId ? { ...gg, color: c } : gg));
                  onClose();
                }}
              />
            ))}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div ref={ref} className="context-menu" style={{ left: x, top: y, zIndex: 200 }}>
      <div className="context-menu-body">
        <div className="context-menu-item" onClick={async () => {
          const g = groups.find(gg => gg.id === groupId);
          const name = await promptDialog({
            title: 'Rename group',
            message: 'Choose a group name.',
            inputLabel: 'Group name',
            defaultValue: g?.name || 'Group',
          });
          if (name !== null) {
            onGroupsChange(groups.map(gg => gg.id === groupId ? { ...gg, name } : gg));
          }
          onClose();
        }}>Rename</div>
        <div className="context-menu-item" onClick={() => setShowColors(true)}>Set Color</div>
        <div className="context-menu-item" onClick={() => {
          if (group) {
            const fitted = fitGroupToNodes(group, nodes);
            onGroupsChange(groups.map(gg => gg.id === groupId ? fitted : gg));
          }
          onClose();
        }}>Fit to Nodes</div>
        <div className="context-menu-sep" />
        <div className="context-menu-item" onClick={() => {
          onNodesChange(applyToGroupNodes(group, nodes, () => ({ muted: true })));
          onClose();
        }}>Mute All</div>
        <div className="context-menu-item" onClick={() => {
          onNodesChange(applyToGroupNodes(group, nodes, () => ({ muted: false })));
          onClose();
        }}>Unmute All</div>
        <div className="context-menu-item" onClick={() => {
          onNodesChange(applyToGroupNodes(group, nodes, () => ({ bypassed: true })));
          onClose();
        }}>Bypass All</div>
        <div className="context-menu-item" onClick={() => {
          onNodesChange(applyToGroupNodes(group, nodes, () => ({ bypassed: false })));
          onClose();
        }}>Enable All</div>
        <div className="context-menu-item" onClick={() => {
          onNodesChange(applyToGroupNodes(group, nodes, () => ({ pinned: true })));
          onClose();
        }}>Pin All</div>
        <div className="context-menu-item" onClick={() => {
          onNodesChange(applyToGroupNodes(group, nodes, () => ({ pinned: false })));
          onClose();
        }}>Unpin All</div>
        <div className="context-menu-sep" />
        <div className="context-menu-item" onClick={() => {
          onGroupsChange(groups.filter(gg => gg.id !== groupId));
          onClose();
        }}>Delete Group</div>
      </div>
    </div>
  );
}
