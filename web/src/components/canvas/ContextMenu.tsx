// Lightweight right-click context menu for the canvas (nodes + pane). React Flow
// gives us onNodeContextMenu / onPaneContextMenu with the mouse event; we render
// this menu at the cursor in screen space and close it on outside-click / Escape
// / scroll. Items are plain data so both the node and pane menus reuse it.
import { useEffect, useRef, useLayoutEffect, useState } from 'react';

export interface MenuItem {
  key: string;
  label?: string;
  icon?: string;
  onClick?: () => void;
  danger?: boolean;
  checked?: boolean;
  disabled?: boolean;
  separator?: boolean;
}

interface ContextMenuProps {
  x: number;
  y: number;
  items: MenuItem[];
  onClose: () => void;
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
      {items.map(item => item.separator ? (
        <div key={item.key} className="bio-context-sep" role="separator" />
      ) : (
        <button
          key={item.key}
          type="button"
          role="menuitem"
          className={`bio-context-item ${item.danger ? 'danger' : ''}`}
          disabled={item.disabled}
          onClick={() => { item.onClick?.(); onClose(); }}
        >
          <span className="bio-context-item-icon" aria-hidden>{item.icon ?? ''}</span>
          <span className="bio-context-item-label">{item.label}</span>
          {item.checked && <span className="bio-context-item-check" aria-hidden>✓</span>}
        </button>
      ))}
    </div>
  );
}
