// Lightweight right-click context menu for the canvas (nodes + pane). React Flow
// gives us onNodeContextMenu / onPaneContextMenu with the mouse event; we render
// this menu at the cursor in screen space and close it on outside-click / Escape
// / scroll. Items are plain data so both the node and pane menus reuse it.
// Supports one level of submenu via `item.children` (opens a flyout on hover).
import { useEffect, useRef, useLayoutEffect, useState } from 'react';
import Icon from '../ui/Icon';

export interface MenuItem {
  key: string;
  label?: string;
  /** Name of an SVG glyph in the shared Icon registry (see ui/Icon.tsx). */
  icon?: string;
  onClick?: () => void;
  danger?: boolean;
  checked?: boolean;
  disabled?: boolean;
  separator?: boolean;
  /** Nested items — renders this row as a submenu trigger (flyout on hover). */
  children?: MenuItem[];
}

interface ContextMenuProps {
  x: number;
  y: number;
  items: MenuItem[];
  onClose: () => void;
}

// A single row: plain item, submenu trigger, or separator. Extracted so a
// submenu trigger can own its hover/flyout state without re-rendering siblings.
function MenuRow({ item, onClose }: { item: MenuItem; onClose: () => void }) {
  const rowRef = useRef<HTMLButtonElement>(null);
  const [open, setOpen] = useState(false);
  const [flyout, setFlyout] = useState<{ x: number; y: number }>({ x: 0, y: 0 });

  if (item.separator) return <div className="bio-context-sep" role="separator" />;

  const hasChildren = !!item.children?.length;

  const openFlyout = () => {
    if (!hasChildren || item.disabled) return;
    const r = rowRef.current?.getBoundingClientRect();
    if (r) {
      // Prefer opening to the right; flip left if it would overflow.
      const width = 210;
      const x = r.right + width > window.innerWidth ? r.left - width : r.right;
      setFlyout({ x, y: r.top });
    }
    setOpen(true);
  };

  return (
    <div
      className="bio-context-row"
      onMouseEnter={openFlyout}
      onMouseLeave={() => setOpen(false)}
    >
      <button
        ref={rowRef}
        type="button"
        role="menuitem"
        className={`bio-context-item ${item.danger ? 'danger' : ''} ${hasChildren ? 'has-children' : ''}`}
        disabled={item.disabled}
        aria-haspopup={hasChildren || undefined}
        aria-expanded={hasChildren ? open : undefined}
        onClick={() => {
          if (hasChildren) { openFlyout(); return; }
          item.onClick?.();
          onClose();
        }}
      >
        <span className="bio-context-item-icon" aria-hidden>{item.icon ? <Icon name={item.icon} size={15} /> : null}</span>
        <span className="bio-context-item-label">{item.label}</span>
        {item.checked && <span className="bio-context-item-check" aria-hidden>✓</span>}
        {hasChildren && <span className="bio-context-item-arrow" aria-hidden><Icon name="chevronRight" size={13} /></span>}
      </button>
      {hasChildren && open && (
        <div className="bio-context-menu bio-context-submenu" style={{ left: flyout.x, top: flyout.y }} role="menu">
          {item.children!.map(child => (
            <MenuRow key={child.key} item={child} onClose={onClose} />
          ))}
        </div>
      )}
    </div>
  );
}

export default function ContextMenu({ x, y, items, onClose }: ContextMenuProps) {
  const ref = useRef<HTMLDivElement>(null);
  const [pos, setPos] = useState({ x, y });

  // Keep the menu inside the viewport.
  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;
    const r = el.getBoundingClientRect();
    const nx = x + r.width > window.innerWidth ? Math.max(4, window.innerWidth - r.width - 4) : x;
    const ny = y + r.height > window.innerHeight ? Math.max(4, window.innerHeight - r.height - 4) : y;
    setPos({ x: nx, y: ny });
  }, [x, y]);

  useEffect(() => {
    const onDown = (e: MouseEvent) => { if (ref.current && !ref.current.contains(e.target as Node)) onClose(); };
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('mousedown', onDown, true);
    window.addEventListener('keydown', onKey);
    window.addEventListener('wheel', onClose, { passive: true });
    return () => {
      window.removeEventListener('mousedown', onDown, true);
      window.removeEventListener('keydown', onKey);
      window.removeEventListener('wheel', onClose);
    };
  }, [onClose]);

  return (
    <div ref={ref} className="bio-context-menu" style={{ left: pos.x, top: pos.y }} role="menu">
      {items.map(item => <MenuRow key={item.key} item={item} onClose={onClose} />)}
    </div>
  );
}
