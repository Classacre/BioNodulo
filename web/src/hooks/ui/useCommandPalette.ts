import { useEffect } from 'react';
import {
  closeCommandPalette,
  openCommandPalette,
  registerCommandItems,
  setCommandPaletteOpen,
  toggleCommandPalette,
  useCommandPaletteStore,
  type CommandItem,
} from '../../state/commandPalette';
import { useGlobalShortcut } from './useKeybindings';

export function useCommandPalette() {
  const state = useCommandPaletteStore();

  useGlobalShortcut('commandPalette.open', () => {
    toggleCommandPalette();
  });

  return {
    ...state,
    open: openCommandPalette,
    close: closeCommandPalette,
    toggle: toggleCommandPalette,
    setOpen: setCommandPaletteOpen,
  };
}

export function useRegisteredCommands(sourceId: string, items: CommandItem[]) {
  useEffect(() => registerCommandItems(sourceId, items), [items, sourceId]);
}
