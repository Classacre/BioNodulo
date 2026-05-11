import { useState, useEffect, useRef } from 'react';
import type { WorkflowGroup } from '../../types';

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
  onGroupsChange: (groups: WorkflowGroup[]) => void;
  onClose: () => void;
}

export default function GroupContextMenu({ x, y, groupId, groups, onGroupsChange, onClose }: GroupContextMenuProps) {
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
        <div className="context-menu-item" onClick={() => {
          const g = groups.find(gg => gg.id === groupId);
          const name = window.prompt('Group name:', g?.name || 'Group');
          if (name !== null) {
            onGroupsChange(groups.map(gg => gg.id === groupId ? { ...gg, name } : gg));
          }
          onClose();
        }}>Rename</div>
        <div className="context-menu-item" onClick={() => setShowColors(true)}>Set Color</div>
        <div className="context-menu-sep" />
        <div className="context-menu-item" onClick={() => {
          onGroupsChange(groups.filter(gg => gg.id !== groupId));
          onClose();
        }}>Delete Group</div>
      </div>
    </div>
  );
}
