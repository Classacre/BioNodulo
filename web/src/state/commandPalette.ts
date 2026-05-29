import type { ReactNode } from 'react';
import { useSyncExternalStore } from 'react';

// Canonical command-palette groups, in display order. New groups should be
// added here rather than free-form strings so the palette UI can render them
// in a stable order with consistent labels. Strings remain accepted for
// backwards compatibility with extensions / experimental registrations.
export const COMMAND_GROUPS = {
  Workflow: 'Workflow',
  Edit: 'Edit',
  View: 'View',
  Panels: 'Panels',
  Tools: 'Tools',
  Appearance: 'Appearance',
  Collaboration: 'Collaboration',
  Help: 'Help',
} as const;

export type CommandGroup = (typeof COMMAND_GROUPS)[keyof typeof COMMAND_GROUPS];

export const COMMAND_GROUP_ORDER: readonly CommandGroup[] = [
  COMMAND_GROUPS.Workflow,
  COMMAND_GROUPS.Edit,
  COMMAND_GROUPS.View,
  COMMAND_GROUPS.Panels,
  COMMAND_GROUPS.Tools,
  COMMAND_GROUPS.Appearance,
  COMMAND_GROUPS.Collaboration,
  COMMAND_GROUPS.Help,
];

/**
 * Sort comparator that puts known groups in canonical order and pushes any
 * unknown / extension group to the end (alphabetically among themselves).
 */
export function compareCommandGroups(a: string | undefined, b: string | undefined): number {
  const ai = a ? COMMAND_GROUP_ORDER.indexOf(a as CommandGroup) : -1;
  const bi = b ? COMMAND_GROUP_ORDER.indexOf(b as CommandGroup) : -1;
  if (ai === -1 && bi === -1) return (a || '').localeCompare(b || '');
  if (ai === -1) return 1;
  if (bi === -1) return -1;
  return ai - bi;
}

export interface CommandItem {
  id: string;
  label: string;
  description?: string;
  /** Accepts CommandGroup for typed registration; free-form strings still work. */
  group?: CommandGroup | string;
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
