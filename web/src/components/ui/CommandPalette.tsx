import type { KeyboardEvent as ReactKeyboardEvent, ReactNode } from 'react';
import { useDeferredValue, useEffect, useMemo, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { useTranslation } from 'react-i18next';
import '../../i18n';
import Icon from './Icon';
import { useFoundationStyles } from './FoundationStyles';
import {
  setCommandPaletteOpen,
  useCommandPaletteStore,
  type CommandItem,
} from '../../state/commandPalette';

export interface CommandPaletteProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  items: CommandItem[];
  title?: string;
  placeholder?: string;
  emptyLabel?: string;
  footer?: ReactNode;
}

function itemSearchText(item: CommandItem) {
  return [
    item.label,
    item.description,
    item.group,
    ...(item.keywords ?? []),
  ].filter(Boolean).join(' ').toLowerCase();
}

function Shortcut({ value }: { value: string }) {
  return (
    <span className="bn-ui-kbd-list" aria-label={value}>
      {value.split('+').map(part => <kbd key={part}>{part}</kbd>)}
    </span>
  );
}

export function CommandPalette({
  open,
  onOpenChange,
  items,
  title,
  placeholder,
  emptyLabel,
  footer,
}: CommandPaletteProps) {
  useFoundationStyles();
  const { t } = useTranslation();
  const inputRef = useRef<HTMLInputElement | null>(null);
  const listRef = useRef<HTMLDivElement | null>(null);
  const [query, setQuery] = useState('');
  const deferredQuery = useDeferredValue(query.trim().toLowerCase());
  const [activeIndex, setActiveIndex] = useState(0);

  const filteredItems = useMemo(() => {
    const normalized = deferredQuery;
    if (!normalized) return items;
    return items.filter(item => itemSearchText(item).includes(normalized));
  }, [deferredQuery, items]);

  const groupedItems = useMemo(() => {
    const groups = new Map<string, CommandItem[]>();
    filteredItems.forEach(item => {
      const group = item.group || t('commandPalette.defaultGroup');
      groups.set(group, [...(groups.get(group) ?? []), item]);
    });
    return Array.from(groups.entries());
  }, [filteredItems, t]);
  const visibleItems = useMemo(() => groupedItems.flatMap(([, groupItems]) => groupItems), [groupedItems]);

  useEffect(() => {
    if (!open) return;
    setQuery('');
    setActiveIndex(0);
    window.setTimeout(() => inputRef.current?.focus(), 0);
  }, [open]);

  useEffect(() => {
    setActiveIndex(index => Math.min(index, Math.max(0, visibleItems.length - 1)));
  }, [visibleItems.length]);

  useEffect(() => {
    if (!open) return;
    const active = listRef.current?.querySelector<HTMLElement>('[data-active="true"]');
    active?.scrollIntoView({ block: 'nearest' });
  }, [activeIndex, open]);

  if (typeof document === 'undefined' || !open) return null;

  const moveActive = (direction: 1 | -1) => {
    if (!visibleItems.length) return;
    let next = activeIndex;
    for (let step = 0; step < visibleItems.length; step += 1) {
      next = (next + direction + visibleItems.length) % visibleItems.length;
      if (!visibleItems[next]?.disabled) break;
    }
    setActiveIndex(next);
  };

  const selectItem = (item: CommandItem | undefined) => {
    if (!item || item.disabled) return;
    item.onSelect?.();
    if (item.closeOnSelect !== false) onOpenChange(false);
  };

  const onKeyDown = (event: ReactKeyboardEvent) => {
    if (event.key === 'Escape') {
      event.preventDefault();
      onOpenChange(false);
    } else if (event.key === 'ArrowDown') {
      event.preventDefault();
      moveActive(1);
    } else if (event.key === 'ArrowUp') {
      event.preventDefault();
      moveActive(-1);
    } else if (event.key === 'Enter') {
      event.preventDefault();
      selectItem(visibleItems[activeIndex]);
    }
  };

  let itemIndex = 0;

  return createPortal(
    <div className="bn-ui-overlay" role="presentation" onMouseDown={() => onOpenChange(false)}>
      <section
        aria-label={title ?? t('commandPalette.title')}
        aria-modal="true"
        className="bn-ui-command"
        onKeyDown={onKeyDown}
        onMouseDown={event => event.stopPropagation()}
        role="dialog"
      >
        <div className="bn-ui-command-input-wrap">
          <Icon name="search" size={16} />
          <input
            aria-label={t('commandPalette.searchLabel')}
            className="bn-ui-command-input"
            onChange={event => setQuery(event.target.value)}
            placeholder={placeholder ?? t('commandPalette.placeholder')}
            ref={inputRef}
            value={query}
          />
          <kbd>Esc</kbd>
        </div>
        <div className="bn-ui-command-list" ref={listRef} role="listbox">
          {filteredItems.length ? groupedItems.map(([group, groupItems]) => (
            <div key={group}>
              <div className="bn-ui-command-group">{group}</div>
              {groupItems.map(item => {
                const currentIndex = itemIndex;
                itemIndex += 1;
                return (
                  <button
                    aria-selected={activeIndex === currentIndex}
                    className="bn-ui-command-item"
                    data-active={activeIndex === currentIndex}
                    disabled={item.disabled}
                    key={`${group}-${item.id}`}
                    onClick={() => selectItem(item)}
                    onMouseEnter={() => setActiveIndex(currentIndex)}
                    role="option"
                    type="button"
                  >
                    <span aria-hidden="true">{item.icon ?? <Icon name="chevronRight" size={15} />}</span>
                    <span>
                      <span className="bn-ui-command-label">{item.label}</span>
                      {item.description ? <span className="bn-ui-command-description">{item.description}</span> : null}
                    </span>
                    {item.shortcut ? <Shortcut value={item.shortcut} /> : null}
                  </button>
                );
              })}
            </div>
          )) : (
            <div className="bn-ui-empty">{emptyLabel ?? t('commandPalette.empty')}</div>
          )}
        </div>
        {footer ? <footer className="bn-ui-dialog-footer">{footer}</footer> : null}
      </section>
    </div>,
    document.body,
  );
}

export interface CommandPaletteHostProps extends Omit<CommandPaletteProps, 'open' | 'onOpenChange' | 'items'> {
  items?: CommandItem[];
}

export function CommandPaletteHost({ items = [], ...props }: CommandPaletteHostProps) {
  const state = useCommandPaletteStore();
  const allItems = useMemo(() => [...items, ...state.items], [items, state.items]);

  return (
    <CommandPalette
      {...props}
      items={allItems}
      onOpenChange={setCommandPaletteOpen}
      open={state.open}
    />
  );
}

export default CommandPalette;
