import type { ReactNode } from 'react';
import { useSyncExternalStore } from 'react';

export interface CommandItem {
  id: string;
  label: string;
  description?: string;
  group?: string;
  keywords?: string[];
  shortcut?: string;
  icon?: ReactNode;
  disabled?: boolean;
  closeOnSelect?: boolean;
  onSelect?: () => void;
}

export interface RegisteredCommandItem extends CommandItem {
  sourceId: string;
}

export interface CommandPaletteSnapshot {
  open: boolean;
  items: RegisteredCommandItem[];
}

const listeners = new Set<() => void>();
const commands = new Map<string, RegisteredCommandItem>();
let snapshot: CommandPaletteSnapshot = { open: false, items: [] };

function commandKey(sourceId: string, id: string) {
  return `${sourceId}:${id}`;
}

function emit() {
  snapshot = {
    open: snapshot.open,
    items: Array.from(commands.values()),
  };
  listeners.forEach(listener => listener());
}

export function setCommandPaletteOpen(open: boolean): void {
  if (snapshot.open === open) return;
  snapshot = { ...snapshot, open };
  listeners.forEach(listener => listener());
}

export function openCommandPalette(): void {
  setCommandPaletteOpen(true);
}

export function closeCommandPalette(): void {
  setCommandPaletteOpen(false);
}

export function toggleCommandPalette(): void {
  setCommandPaletteOpen(!snapshot.open);
}

export function registerCommandItems(sourceId: string, items: CommandItem[]): () => void {
  Array.from(commands.keys())
    .filter(key => key.startsWith(`${sourceId}:`))
    .forEach(key => commands.delete(key));

  items.forEach(item => {
    commands.set(commandKey(sourceId, item.id), { ...item, sourceId });
  });
  emit();

  return () => {
    Array.from(commands.keys())
      .filter(key => key.startsWith(`${sourceId}:`))
      .forEach(key => commands.delete(key));
    emit();
  };
}

export function registerCommandItem(sourceId: string, item: CommandItem): () => void {
  return registerCommandItems(sourceId, [item]);
}

export function subscribeCommandPalette(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function getCommandPaletteSnapshot(): CommandPaletteSnapshot {
  return snapshot;
}

export function useCommandPaletteStore(): CommandPaletteSnapshot {
  return useSyncExternalStore(
    subscribeCommandPalette,
    getCommandPaletteSnapshot,
    getCommandPaletteSnapshot,
  );
}
