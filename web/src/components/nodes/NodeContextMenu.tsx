import { useState, useEffect, useRef } from 'react';

const PRESET_COLORS = [
  '#ef4444', '#f97316', '#f59e0b', '#84cc16', '#22c55e',
  '#10b981', '#14b8a6', '#06b6d4', '#0ea5e9', '#3b82f6',
  '#6366f1', '#8b5cf6', '#a855f7', '#d946ef', '#ec4899',
  '#f43f5e', '#64748b', '#94a3b8',
];

interface NodeContextMenuProps {
  x: number;
  y: number;
  nodeId: string | null;
  onAction: (action: string, nodeId: string, extra?: string) => void;
  onClose: () => void;
}

export default function NodeContextMenu({ x, y, nodeId, onAction, onClose }: NodeContextMenuProps) {
  const ref = useRef<HTMLDivElement>(null);
  const [showColors, setShowColors] = useState(false);

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (!ref.current?.contains(e.target as Node)) onClose();
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [onClose]);

  if (showColors) {
    return (
      <div ref={ref} className="context-menu" style={{ left: x, top: y }}>
        <div className="context-menu-body">
          <div className="context-menu-item" onClick={() => setShowColors(false)}>← Back</div>
          <div className="context-menu-sep" />
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(6, 1fr)', gap: 4, padding: '4px 8px' }}>
            {PRESET_COLORS.map(c => (
              <div
                key={c}
                style={{ width: 20, height: 20, borderRadius: 4, background: c, cursor: 'pointer', border: '1px solid var(--border)' }}
                onClick={() => { onAction('color', nodeId || '', c); setShowColors(false); }}
              />
            ))}
          </div>
        </div>
      </div>
    );
  }

  const items = nodeId ? [
    { label: 'Edit Properties', action: 'edit' },
    { label: 'Rename', action: 'rename' },
    { label: 'Node Info', action: 'info' },
    { label: 'Add Comment', action: 'comment' },
    { label: 'Duplicate', action: 'duplicate' },
    null,
    { label: 'Mute Node', action: 'mute' },
    { label: 'Bypass Node', action: 'bypass' },
    { label: 'Pin / Lock Node', action: 'pin' },
    { label: 'Collapse/Expand', action: 'collapse' },
    null,
    { label: 'Set as Output', action: 'output' },
    { label: 'Set Color', action: 'color', handler: () => setShowColors(true) },
    { label: 'Round Shape', action: 'shape:round' },
    { label: 'Box Shape', action: 'shape:box' },
    { label: 'Card Shape', action: 'shape:card' },
    null,
    { label: 'Group Selected', action: 'group' },
    { label: 'Create Subgraph', action: 'subgraph' },
    { label: 'Save Subgraph to Library', action: 'saveSubgraphBlueprint' },
    { label: 'Promote Widgets to Parent', action: 'promoteWidgets' },
    { label: 'Save Params as Preset…', action: 'savePreset' },
    { label: 'Apply Preset…', action: 'applyPreset' },
    { label: 'Execute Selected', action: 'executeSelected' },
    null,
    { label: 'Delete', action: 'delete' },
  ] : [
    { label: 'Add Node', action: 'add' },
    { label: 'Add Group', action: 'addGroup' },
    null,
    { label: 'Select All', action: 'selectAll' },
    null,
    { label: 'Paste', action: 'paste' },
  ];

  return (
    <div ref={ref} className="context-menu" style={{ left: x, top: y }}>
      <div className="context-menu-body">
        {items.map((item, i) => (
          item === null
            ? <div key={i} className="context-menu-sep" />
            : (
              <div key={i} className="context-menu-item" onClick={() => {
                if ('handler' in item && item.handler) {
                  item.handler();
                } else {
                  if (nodeId && item.action.startsWith('shape:')) onAction('shape', nodeId, item.action.split(':')[1]);
                  else if (nodeId) onAction(item.action, nodeId);
                  else onAction(item.action, '');
                }
              }}>
                {item.label}
              </div>
            )
        ))}
      </div>
    </div>
  );
}
