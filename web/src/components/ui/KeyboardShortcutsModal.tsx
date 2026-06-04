import { useEffect, useMemo, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { useTranslation } from 'react-i18next';
import '../../i18n';
import { useFocusTrap, useKeybindings } from '../../hooks/ui';
import { eventToKeybinding, type KeybindingCategory, type KeybindingRecord } from '../../state/keybindings';
import Icon from './Icon';
import { useFoundationStyles } from './FoundationStyles';

export interface KeyboardShortcutsModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title?: string;
}

const CATEGORY_ORDER: KeybindingCategory[] = ['global', 'workflow', 'canvas', 'panels'];

function ShortcutKeys({ binding }: { binding: string }) {
  if (!binding) return <span>-</span>;
  return (
    <span className="bn-ui-kbd-list" aria-label={binding}>
      {binding.split('+').map(part => <kbd key={part}>{part}</kbd>)}
    </span>
  );
}

function categoryLabel(category: KeybindingCategory, t: (key: string) => string) {
  return t(`shortcuts.categories.${category}`);
}

export function KeyboardShortcutsModal({ open, onOpenChange, title }: KeyboardShortcutsModalProps) {
  useFoundationStyles();
  const { t } = useTranslation();
  const {
    bindings,
    conflicts,
    getConflictsForAction,
    hasConflict,
    resetAll,
    resetBinding,
    setBinding,
  } = useKeybindings();
  const [query, setQuery] = useState('');
  const [recordingId, setRecordingId] = useState<string | null>(null);

  const filteredBindings = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    if (!normalized) return bindings;
    return bindings.filter(binding => [
      binding.label,
      binding.description,
      binding.category,
      binding.binding,
    ].filter(Boolean).join(' ').toLowerCase().includes(normalized));
  }, [bindings, query]);

  const groupedBindings = useMemo(() => {
    const byCategory = new Map<KeybindingCategory, KeybindingRecord[]>();
    filteredBindings.forEach(binding => {
      byCategory.set(binding.category, [...(byCategory.get(binding.category) ?? []), binding]);
    });
    return CATEGORY_ORDER
      .map(category => [category, byCategory.get(category) ?? []] as const)
      .filter(([, items]) => items.length > 0);
  }, [filteredBindings]);

  useEffect(() => {
    if (!open) {
      setRecordingId(null);
      setQuery('');
    }
  }, [open]);

  useEffect(() => {
    if (!recordingId) return;

    const onKeyDown = (event: KeyboardEvent) => {
      event.preventDefault();
      event.stopPropagation();

      if (event.key === 'Escape') {
        setRecordingId(null);
        return;
      }

      if (event.key === 'Backspace' || event.key === 'Delete') {
        setBinding(recordingId, '');
        setRecordingId(null);
        return;
      }

      const binding = eventToKeybinding(event);
      if (!binding) return;
      setBinding(recordingId, binding);
      setRecordingId(null);
    };

    window.addEventListener('keydown', onKeyDown, true);
    return () => window.removeEventListener('keydown', onKeyDown, true);
  }, [recordingId, setBinding]);

  useEffect(() => {
    if (!open || recordingId) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onOpenChange(false);
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [onOpenChange, open, recordingId]);

  const dialogRef = useRef<HTMLElement>(null);
  useFocusTrap(dialogRef, open, () => onOpenChange(false));

  if (typeof document === 'undefined' || !open) return null;

  return createPortal(
    <div className="bn-ui-overlay" role="presentation" onMouseDown={() => onOpenChange(false)}>
      <section
        ref={dialogRef}
        aria-label={title ?? t('shortcuts.title')}
        aria-modal="true"
        className="bn-ui-shortcuts"
        onMouseDown={event => event.stopPropagation()}
        role="dialog"
      >
        <header className="bn-ui-shortcuts-header">
          <div className="bn-ui-shortcuts-title">{title ?? t('shortcuts.title')}</div>
          <button
            aria-label={t('common.close')}
            className="bn-ui-icon-button"
            onClick={() => onOpenChange(false)}
            type="button"
          >
            <Icon name="close" size={15} />
          </button>
        </header>
        <div className="bn-ui-shortcuts-body">
          <div className="bn-ui-shortcuts-tools">
            <input
              aria-label={t('shortcuts.searchLabel')}
              className="bn-ui-shortcuts-search"
              onChange={event => setQuery(event.target.value)}
              placeholder={t('shortcuts.searchPlaceholder')}
              value={query}
            />
            <button className="bn-ui-button" onClick={resetAll} type="button">
              {t('shortcuts.resetAll')}
            </button>
          </div>
          {conflicts.length ? (
            <div className="bn-ui-shortcut-conflict" style={{ marginBottom: 10 }}>
              {t('shortcuts.conflictSummary', { count: conflicts.length })}
            </div>
          ) : null}
          {groupedBindings.length ? groupedBindings.map(([category, items]) => (
            <section className="bn-ui-shortcut-section" key={category}>
              <div className="bn-ui-shortcut-section-title">{categoryLabel(category, t)}</div>
              {items.map(binding => {
                const bindingConflicts = getConflictsForAction(binding.id);
                return (
                  <div className="bn-ui-shortcut-row" key={binding.id}>
                    <div>
                      <div className="bn-ui-shortcut-label">{binding.label}</div>
                      {binding.description ? <div className="bn-ui-shortcut-desc">{binding.description}</div> : null}
                    </div>
                    <button
                      className="bn-ui-shortcut-input"
                      data-recording={recordingId === binding.id}
                      disabled={binding.editable === false}
                      onClick={() => setRecordingId(binding.id)}
                      type="button"
                    >
                      {recordingId === binding.id
                        ? t('shortcuts.recording')
                        : <ShortcutKeys binding={binding.binding} />}
                    </button>
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: 8 }}>
                      {hasConflict(binding.id) ? (
                        <span className="bn-ui-shortcut-conflict" title={bindingConflicts.map(conflict => conflict.binding).join(', ')}>
                          {t('shortcuts.conflict')}
                        </span>
                      ) : null}
                      <button className="bn-ui-button bn-ui-button-ghost" onClick={() => resetBinding(binding.id)} type="button">
                        {t('shortcuts.reset')}
                      </button>
                    </div>
                  </div>
                );
              })}
            </section>
          )) : (
            <div className="bn-ui-empty">{t('shortcuts.empty')}</div>
          )}
        </div>
        <footer className="bn-ui-shortcuts-footer">
          <button className="bn-ui-button bn-ui-button-primary" onClick={() => onOpenChange(false)} type="button">
            {t('common.done')}
          </button>
        </footer>
      </section>
    </div>,
    document.body,
  );
}

export default KeyboardShortcutsModal;
