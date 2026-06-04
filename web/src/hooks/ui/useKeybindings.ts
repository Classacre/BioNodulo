import { useCallback, useEffect, useMemo, useRef, useSyncExternalStore } from 'react';
import {
  eventToKeybinding,
  findKeybindingConflicts,
  getKeybindingsSnapshot,
  keybindingMatchesEvent,
  resetAllKeybindings,
  resetKeybinding,
  setKeybinding,
  subscribeKeybindings,
  type KeybindingRecord,
} from '../../state/keybindings';
import { hasOpenOverlay } from '../../state/overlays';

function isEditableTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  const tag = target.tagName.toLowerCase();
  return tag === 'input'
    || tag === 'textarea'
    || tag === 'select'
    || target.isContentEditable
    || target.closest('[contenteditable="true"]') !== null;
}

export function useKeybindings() {
  const bindings = useSyncExternalStore(
    subscribeKeybindings,
    getKeybindingsSnapshot,
    getKeybindingsSnapshot,
  );

  const conflicts = useMemo(() => findKeybindingConflicts(bindings), [bindings]);
  const conflictActionIds = useMemo(() => {
    const ids = new Set<string>();
    conflicts.forEach(conflict => conflict.actionIds.forEach(id => ids.add(id)));
    return ids;
  }, [conflicts]);

  const getBinding = useCallback((id: string) => {
    return bindings.find(binding => binding.id === id)?.binding ?? null;
  }, [bindings]);

  const hasConflict = useCallback((id: string) => conflictActionIds.has(id), [conflictActionIds]);

  const getConflictsForAction = useCallback((id: string) => {
    return conflicts.filter(conflict => conflict.actionIds.includes(id));
  }, [conflicts]);

  return {
    bindings,
    conflicts,
    getBinding,
    hasConflict,
    getConflictsForAction,
    setBinding: setKeybinding,
    resetBinding: resetKeybinding,
    resetAll: resetAllKeybindings,
    eventToKeybinding,
    keybindingMatchesEvent,
  };
}

export interface GlobalShortcutOptions {
  enabled?: boolean;
  allowInInputs?: boolean;
  preventDefault?: boolean;
  // When true (default), the handler is suppressed while any modal/dropdown
  // overlay is open. Set to false for shortcuts that must always fire — e.g.
  // a global "close any overlay" Escape.
  respectOverlays?: boolean;
}

export function useGlobalShortcut(
  actionId: string,
  handler: (event: KeyboardEvent, binding: KeybindingRecord | undefined) => void,
  options: GlobalShortcutOptions = {},
) {
  const { bindings } = useKeybindings();
  const handlerRef = useRef(handler);
  const binding = bindings.find(item => item.id === actionId);
  const enabled = options.enabled ?? true;
  const allowInInputs = options.allowInInputs ?? false;
  const preventDefault = options.preventDefault ?? true;
  const respectOverlays = options.respectOverlays ?? true;

  useEffect(() => {
    handlerRef.current = handler;
  }, [handler]);

  useEffect(() => {
    if (!enabled || !binding?.binding) return;

    const onKeyDown = (event: KeyboardEvent) => {
      if (!allowInInputs && isEditableTarget(event.target)) return;
      if (!keybindingMatchesEvent(binding.binding, event)) return;
      // Scope enforcement. Canvas-scoped bindings stay quiet inside overlays
      // (covered by respectOverlays); modal-scoped bindings ONLY fire while
      // an overlay is open. Global is the default and matches today's
      // behavior exactly.
      const scope = binding.scope ?? 'global';
      const overlayOpen = hasOpenOverlay();
      if (scope === 'modal' && !overlayOpen) return;
      if (scope === 'canvas' && overlayOpen) return;
      // If any modal/dropdown is open, defer to its own Escape/Enter handler
      // instead of triggering a global shortcut beneath it.
      if (respectOverlays && overlayOpen && scope !== 'modal') return;
      if (preventDefault) event.preventDefault();
      handlerRef.current(event, binding);
    };

    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [allowInInputs, binding, enabled, preventDefault, respectOverlays]);
}
