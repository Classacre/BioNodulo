import { useEffect, useMemo, useRef, useState } from 'react';
import type { GraphNode } from './LiteGraphCanvas';
import type { WorkflowGroup } from '../../types';

interface SelectionToolboxProps {
  graphNodes: GraphNode[];
  groups: WorkflowGroup[];
  offset: { x: number; y: number };
  scale: number;
  isDragging: boolean;
  onAction: (action: string, extra?: string) => void;
  hostRef: React.RefObject<HTMLDivElement | null>;
}

const PRESET_COLORS = [
  '#ef4444', '#f97316', '#f59e0b', '#84cc16', '#22c55e',
  '#10b981', '#14b8a6', '#06b6d4', '#0ea5e9', '#3b82f6',
  '#6366f1', '#8b5cf6', '#a855f7', '#d946ef', '#ec4899',
  '#f43f5e', '#64748b', '#94a3b8',
];

export default function SelectionToolbox({ graphNodes, groups, offset, scale, isDragging, onAction, hostRef }: SelectionToolboxProps) {
  const [showColorPicker, setShowColorPicker] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (!ref.current?.contains(e.target as Node)) setShowColorPicker(false);
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  const selectedNodes = graphNodes.filter(n => n.selected);
  const selectedGroups = groups.filter(g => g.selected);
  const hasSelection = selectedNodes.length > 0 || selectedGroups.length > 0;

  const position = useMemo(() => {
    if (!hasSelection) return null;
    let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
    for (const n of selectedNodes) {
      minX = Math.min(minX, n.x);
      minY = Math.min(minY, n.y);
      maxX = Math.max(maxX, n.x + n.width);
      maxY = Math.max(maxY, n.y + n.height);
    }
    for (const g of selectedGroups) {
      minX = Math.min(minX, g.position[0]);
      minY = Math.min(minY, g.position[1]);
      maxX = Math.max(maxX, g.position[0] + g.width);
      maxY = Math.max(maxY, g.position[1] + g.height);
    }
    const centerX = (minX + maxX) / 2;
    const topY = minY;
    const screenX = centerX * scale + offset.x;
    const screenY = topY * scale + offset.y;
    // Add the canvas host's viewport offset so position:fixed lands correctly
    const hostRect = hostRef.current?.getBoundingClientRect();
    const hostOffsetX = hostRect ? hostRect.left : 0;
    const hostOffsetY = hostRect ? hostRect.top : 0;
    return { x: screenX + hostOffsetX, y: screenY + hostOffsetY };
  }, [selectedNodes, selectedGroups, offset, scale, hasSelection, hostRef]);

  if (!hasSelection || isDragging || !position) return null;

  const singleNode = selectedNodes.length === 1 && selectedGroups.length === 0 ? selectedNodes[0] : null;
  const canCollapse = singleNode && singleNode.type !== 'note' && singleNode.type !== 'reroute';

  return (
    <div
      ref={ref}
      style={{
        position: 'fixed',
        left: position.x,
        top: position.y,
        transform: 'translate(-50%, -115%)',
        zIndex: 40,
        display: 'flex',
        alignItems: 'center',
        gap: 2,
        padding: '4px 6px',
        borderRadius: 8,
        background: 'var(--surface, #1e293b)',
        border: '1px solid var(--border, #334155)',
        boxShadow: 'var(--shadow, 0 4px 12px rgba(0,0,0,0.3))',
        pointerEvents: 'auto',
      }}
    >
      <ToolboxButton title="Delete" onClick={() => onAction('delete')}>
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="3 6 5 6 21 6" /><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" /><line x1="10" y1="11" x2="10" y2="17" /><line x1="14" y1="11" x2="14" y2="17" /></svg>
      </ToolboxButton>
      <ToolboxButton title="Duplicate" onClick={() => onAction('duplicate')}>
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="9" y="9" width="13" height="13" rx="2" ry="2" /><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" /></svg>
      </ToolboxButton>
      {singleNode && (
        <>
          <div style={{ width: 1, height: 16, background: 'var(--border)', margin: '0 2px' }} />
          <ToolboxButton title="Mute" onClick={() => onAction('mute')}>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5" /><line x1="23" y1="9" x2="17" y2="15" /><line x1="17" y1="9" x2="23" y2="15" /></svg>
          </ToolboxButton>
          <ToolboxButton title="Bypass" onClick={() => onAction('bypass')}>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M17 1l4 4-4 4" /><path d="M3 11V9a4 4 0 0 1 4-4h14" /><path d="M7 23l-4-4 4-4" /><path d="M21 13v2a4 4 0 0 1-4 4H3" /></svg>
          </ToolboxButton>
          {canCollapse && (
            <ToolboxButton title="Collapse/Expand" onClick={() => onAction('collapse')}>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="4 14 10 14 10 20" /><polyline points="20 10 14 10 14 4" /><line x1="14" y1="10" x2="21" y2="3" /><line x1="3" y1="21" x2="10" y2="14" /></svg>
            </ToolboxButton>
          )}
        </>
      )}
      <div style={{ width: 1, height: 16, background: 'var(--border)', margin: '0 2px' }} />
      <div style={{ position: 'relative' }}>
        <ToolboxButton title="Color" onClick={() => setShowColorPicker(v => !v)}>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="13.5" cy="6.5" r="2.5" /><path d="M13.5 9c-2.5 0-3.5 1.5-3.5 3.5 0 2.5 3.5 4.5 3.5 9" /><path d="M9 18c-1.5 0-3-1-3-3.5s2.5-5 5-7.5" /><path d="M18 18c1.5 0 3-1 3-3.5s-2.5-5-5-7.5" /></svg>
        </ToolboxButton>
        {showColorPicker && (
          <div style={{
            position: 'absolute',
            bottom: 'calc(100% + 4px)',
            left: '50%',
            transform: 'translateX(-50%)',
            display: 'grid',
            gridTemplateColumns: 'repeat(6, 1fr)',
            gap: 4,
            padding: 6,
            borderRadius: 6,
            background: 'var(--surface, #1e293b)',
            border: '1px solid var(--border, #334155)',
            boxShadow: 'var(--shadow, 0 4px 12px rgba(0,0,0,0.3))',
            zIndex: 50,
          }}>
            {PRESET_COLORS.map(c => (
              <div
                key={c}
                style={{ width: 18, height: 18, borderRadius: 4, background: c, cursor: 'pointer', border: '1px solid var(--border)' }}
                onClick={() => { onAction('color', c); setShowColorPicker(false); }}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function ToolboxButton({ title, onClick, children }: { title: string; onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      title={title}
      onClick={onClick}
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        width: 26,
        height: 26,
        borderRadius: 6,
        border: 'none',
        background: 'transparent',
        color: 'var(--muted, #94a3b8)',
        cursor: 'pointer',
        padding: 0,
      }}
      onMouseEnter={e => { (e.currentTarget as HTMLButtonElement).style.background = 'var(--hover-bg, rgba(255,255,255,0.08))'; (e.currentTarget as HTMLButtonElement).style.color = 'var(--text, #e2e8f0)'; }}
      onMouseLeave={e => { (e.currentTarget as HTMLButtonElement).style.background = 'transparent'; (e.currentTarget as HTMLButtonElement).style.color = 'var(--muted, #94a3b8)'; }}
    >
      {children}
    </button>
  );
}
