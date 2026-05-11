import { useState, useEffect, useRef } from 'react';
import Icon from '../ui/Icon';

interface WorkflowTabsProps {
  tabs: string[];
  active: number;
  onChange: (index: number) => void;
  onClose: (index: number) => void;
  onAdd: () => void;
  onRename?: (index: number, name: string) => void;
  onDuplicate?: (index: number) => void;
  onReorder?: (from: number, to: number) => void;
}

export default function WorkflowTabs({ tabs, active, onChange, onClose, onAdd, onRename, onDuplicate, onReorder }: WorkflowTabsProps) {
  const [menu, setMenu] = useState<{ x: number; y: number; index: number } | null>(null);
  const [renaming, setRenaming] = useState<{ index: number; name: string } | null>(null);
  const [dragIndex, setDragIndex] = useState<number | null>(null);
  const [dragOverIndex, setDragOverIndex] = useState<number | null>(null);
  const renameRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (renaming) renameRef.current?.focus();
  }, [renaming]);

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (!menu) return;
      const target = e.target as HTMLElement;
      if (!target.closest('.tab-context-menu')) setMenu(null);
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [menu]);

  const handleRenameSubmit = () => {
    if (renaming && onRename) {
      const name = renaming.name.trim();
      if (name) onRename(renaming.index, name);
    }
    setRenaming(null);
  };

  const handleDragStart = (e: React.DragEvent, index: number) => {
    setDragIndex(index);
    e.dataTransfer.effectAllowed = 'move';
    // Hide the default ghost image by using a transparent image
    const img = new Image();
    img.src = 'data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7';
    e.dataTransfer.setDragImage(img, 0, 0);
  };

  const handleDragOver = (e: React.DragEvent, index: number) => {
    e.preventDefault();
    if (dragIndex === null || dragIndex === index) return;
    setDragOverIndex(index);
  };

  const handleDrop = (e: React.DragEvent, index: number) => {
    e.preventDefault();
    if (dragIndex === null || dragIndex === index) {
      setDragIndex(null);
      setDragOverIndex(null);
      return;
    }
    if (onReorder) {
      onReorder(dragIndex, index);
    }
    setDragIndex(null);
    setDragOverIndex(null);
  };

  const handleDragEnd = () => {
    setDragIndex(null);
    setDragOverIndex(null);
  };

  return (
    <div className="workflow-tabs">
      {tabs.map((name, i) => (
        <button
          key={i}
          className={`wf-tab ${i === active ? 'active' : ''} ${dragOverIndex === i ? 'drag-over' : ''}`}
          draggable={!!onReorder}
          onDragStart={e => handleDragStart(e, i)}
          onDragOver={e => handleDragOver(e, i)}
          onDrop={e => handleDrop(e, i)}
          onDragEnd={handleDragEnd}
          onClick={() => onChange(i)}
          onMouseDown={e => { if (e.button === 1) { e.preventDefault(); onClose(i); } }}
          onContextMenu={e => { e.preventDefault(); setMenu({ x: e.clientX, y: e.clientY, index: i }); }}
          style={{ opacity: dragIndex === i ? 0.4 : 1 }}
        >
          {renaming?.index === i ? (
            <input
              ref={renameRef}
              className="text-input"
              style={{ width: 120, fontSize: 12, padding: '2px 6px' }}
              value={renaming.name}
              onChange={e => setRenaming({ index: i, name: e.target.value })}
              onBlur={handleRenameSubmit}
              onKeyDown={e => { if (e.key === 'Enter') handleRenameSubmit(); if (e.key === 'Escape') setRenaming(null); }}
              onClick={e => e.stopPropagation()}
            />
          ) : (
            <span onDoubleClick={() => setRenaming({ index: i, name: name || 'Untitled' })}>
              {name || 'Untitled'}
            </span>
          )}
          {tabs.length > 1 && (
            <span className="wf-tab-close" onClick={e => { e.stopPropagation(); onClose(i); }}>
              <Icon name="close" size={12} />
            </span>
          )}
        </button>
      ))}
      <button className="wf-tab" onClick={onAdd} title="New workflow">
        <Icon name="plus" size={14} />
      </button>

      {menu && (
        <div className="tab-context-menu context-menu" style={{ left: menu.x, top: menu.y, position: 'fixed', zIndex: 300 }}>
          <div className="context-menu-body">
            <div className="context-menu-item" onClick={() => { setRenaming({ index: menu.index, name: tabs[menu.index] || 'Untitled' }); setMenu(null); }}>Rename</div>
            {onDuplicate && <div className="context-menu-item" onClick={() => { onDuplicate(menu.index); setMenu(null); }}>Duplicate</div>}
            <div className="context-menu-sep" />
            <div className="context-menu-item" onClick={() => { onClose(menu.index); setMenu(null); }}>Close Tab</div>
            <div className="context-menu-item" onClick={() => { tabs.forEach((_, i) => { if (i < menu.index) onClose(i); }); setMenu(null); }}>Close Tabs to Left</div>
            <div className="context-menu-item" onClick={() => { for (let i = tabs.length - 1; i > menu.index; i--) onClose(i); setMenu(null); }}>Close Tabs to Right</div>
            <div className="context-menu-item" onClick={() => { tabs.forEach((_, i) => { if (i !== menu.index) onClose(i > menu.index ? i - 1 : i); }); setMenu(null); }}>Close Other Tabs</div>
          </div>
        </div>
      )}
    </div>
  );
}
