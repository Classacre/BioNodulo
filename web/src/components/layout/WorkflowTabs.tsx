import { useState, useEffect, useRef } from 'react';
import { useTranslation } from 'react-i18next';
import Icon from '../ui/Icon';
import { isUntitledWorkflowName } from '../../utils/workflowNaming';

interface WorkflowTabsProps {
  tabs: string[];
  active: number;
  onChange: (index: number) => void;
  onClose: (index: number) => void;
  onAdd: () => void;
  onRename?: (index: number, name: string) => void;
  onDuplicate?: (index: number) => void;
  onReorder?: (from: number, to: number) => void;
  /** Indices whose workflow has unsaved changes; rendered with a small dot. */
  dirtyIndices?: ReadonlySet<number>;
}

export default function WorkflowTabs({ tabs, active, onChange, onClose, onAdd, onRename, onDuplicate, onReorder, dirtyIndices }: WorkflowTabsProps) {
  const { t } = useTranslation();
  const [menu, setMenu] = useState<{ x: number; y: number; index: number } | null>(null);
  const [renaming, setRenaming] = useState<{ index: number; name: string } | null>(null);
  const [dragIndex, setDragIndex] = useState<number | null>(null);
  const [dragOverIndex, setDragOverIndex] = useState<number | null>(null);
  const renameRef = useRef<HTMLInputElement>(null);
  const stripRef = useRef<HTMLDivElement>(null);
  const tabRefs = useRef<Array<HTMLButtonElement | null>>([]);
  const [overflow, setOverflow] = useState<{ left: boolean; right: boolean }>({ left: false, right: false });

  useEffect(() => {
    if (renaming) renameRef.current?.focus();
  }, [renaming]);

  // Track left/right overflow so we know when to show the scroll arrows.
  useEffect(() => {
    const node = stripRef.current;
    if (!node) return;
    const update = () => {
      const left = node.scrollLeft > 2;
      const right = node.scrollWidth - node.clientWidth - node.scrollLeft > 2;
      setOverflow(prev => (prev.left === left && prev.right === right ? prev : { left, right }));
    };
    update();
    node.addEventListener('scroll', update);
    const observer = new ResizeObserver(update);
    observer.observe(node);
    return () => {
      node.removeEventListener('scroll', update);
      observer.disconnect();
    };
  }, [tabs.length]);

  // Bring the active tab into view when the active index changes.
  useEffect(() => {
    const el = tabRefs.current[active];
    if (el?.scrollIntoView) el.scrollIntoView({ block: 'nearest', inline: 'nearest', behavior: 'smooth' });
  }, [active]);

  const scrollBy = (delta: number) => {
    stripRef.current?.scrollBy({ left: delta, behavior: 'smooth' });
  };

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

  const displayName = (name: string) => (isUntitledWorkflowName(name) ? t('common.untitled') : name);

  return (
    <div className="workflow-tabs" ref={stripRef}>
      {overflow.left && (
        <button
          className="wf-tab wf-tab-scroll"
          onClick={() => scrollBy(-160)}
          title={t('workflowTabs.scrollLeft')}
          aria-label={t('workflowTabs.scrollLeft')}
          style={{ position: 'sticky', left: 0, zIndex: 2, padding: '0 6px' }}
        >
          <Icon name="chevronLeft" size={14} />
        </button>
      )}
      {tabs.map((name, i) => (
        <button
          key={i}
          ref={el => { tabRefs.current[i] = el; }}
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
            <span onDoubleClick={() => setRenaming({ index: i, name: displayName(name) })}>
              {dirtyIndices?.has(i) && (
                <span
                  className="wf-tab-dirty"
                  aria-label={t('dialogs.unsavedChangesTitle')}
                  title={t('dialogs.unsavedChangesTitle')}
                />
              )}
              {displayName(name)}
            </span>
          )}
          {tabs.length > 1 && (
            <span className="wf-tab-close" onClick={e => { e.stopPropagation(); onClose(i); }}>
              <Icon name="close" size={12} />
            </span>
          )}
        </button>
      ))}
      <button className="wf-tab" onClick={onAdd} title={t('topbar.newWorkflow')} aria-label={t('workflowTabs.newWorkflowTab')}>
        <Icon name="plus" size={14} />
      </button>
      {overflow.right && (
        <button
          className="wf-tab wf-tab-scroll"
          onClick={() => scrollBy(160)}
          title={t('workflowTabs.scrollRight')}
          aria-label={t('workflowTabs.scrollRight')}
          style={{ position: 'sticky', right: 0, zIndex: 2, padding: '0 6px' }}
        >
          <Icon name="chevronRight" size={14} />
        </button>
      )}

      {menu && (
        <div className="tab-context-menu context-menu" style={{ left: menu.x, top: menu.y, position: 'fixed', zIndex: 300 }}>
          <div className="context-menu-body">
            <div className="context-menu-item" onClick={() => { setRenaming({ index: menu.index, name: displayName(tabs[menu.index] || '') }); setMenu(null); }}>{t('workflowTabs.rename')}</div>
            {onDuplicate && <div className="context-menu-item" onClick={() => { onDuplicate(menu.index); setMenu(null); }}>{t('common.duplicate')}</div>}
            <div className="context-menu-sep" />
            <div className="context-menu-item" onClick={() => { onClose(menu.index); setMenu(null); }}>{t('topbar.closeTab')}</div>
            <div className="context-menu-item" onClick={() => { tabs.forEach((_, i) => { if (i < menu.index) onClose(i); }); setMenu(null); }}>{t('workflowTabs.closeTabsLeft')}</div>
            <div className="context-menu-item" onClick={() => { for (let i = tabs.length - 1; i > menu.index; i--) onClose(i); setMenu(null); }}>{t('workflowTabs.closeTabsRight')}</div>
            <div className="context-menu-item" onClick={() => { tabs.forEach((_, i) => { if (i !== menu.index) onClose(i > menu.index ? i - 1 : i); }); setMenu(null); }}>{t('topbar.closeOtherTabs')}</div>
          </div>
        </div>
      )}
    </div>
  );
}
