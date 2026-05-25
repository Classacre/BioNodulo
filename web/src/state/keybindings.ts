import type { KeyboardEvent as ReactKeyboardEvent } from 'react';

export type KeybindingCategory = 'global' | 'canvas' | 'workflow' | 'panels';

export interface KeybindingDefinition {
  id: string;
  category: KeybindingCategory;
  label: string;
  description?: string;
  defaultBinding: string;
  editable?: boolean;
}

export interface KeybindingRecord extends KeybindingDefinition {
  binding: string;
}

export interface KeybindingConflict {
  binding: string;
  actionIds: string[];
}

const STORAGE_KEY = 'bionodulo.keybindings.v1';
const listeners = new Set<() => void>();

export const DEFAULT_KEYBINDINGS: KeybindingDefinition[] = [
  { id: 'commandPalette.open', category: 'global', label: 'Open command palette', defaultBinding: 'Ctrl+K' },
  { id: 'shortcuts.open', category: 'global', label: 'Open keyboard shortcuts', defaultBinding: 'Ctrl+Shift+/' },
  { id: 'nodes.search', category: 'panels', label: 'Open node search', defaultBinding: 'Ctrl+F' },
  { id: 'workflow.run', category: 'workflow', label: 'Run workflow', defaultBinding: 'Ctrl+R' },
  { id: 'workflow.export', category: 'workflow', label: 'Export workflow', defaultBinding: 'Ctrl+E' },
  { id: 'workflow.import', category: 'workflow', label: 'Import workflow', defaultBinding: 'Ctrl+I' },
  { id: 'settings.toggle', category: 'panels', label: 'Toggle settings', defaultBinding: 'Ctrl+,' },
  { id: 'console.toggle', category: 'panels', label: 'Toggle console', defaultBinding: 'Ctrl+`' },
  { id: 'ai.open', category: 'global', label: 'Open AI assistant', defaultBinding: 'Ctrl+Shift+A' },
  { id: 'rail.workspace', category: 'panels', label: 'Open workspace panel', defaultBinding: 'Ctrl+1' },
  { id: 'rail.nodes', category: 'panels', label: 'Open nodes panel', defaultBinding: 'Ctrl+2' },
  { id: 'rail.templates', category: 'panels', label: 'Open templates panel', defaultBinding: 'Ctrl+3' },
  { id: 'rail.environment', category: 'panels', label: 'Open environment panel', defaultBinding: 'Ctrl+4' },
  { id: 'rail.hpc', category: 'panels', label: 'Open HPC panel', defaultBinding: 'Ctrl+5' },
  { id: 'rail.help', category: 'panels', label: 'Open help panel', defaultBinding: 'Ctrl+6' },
  { id: 'rail.console', category: 'panels', label: 'Open console panel', defaultBinding: 'Ctrl+7' },
  { id: 'canvas.selectAll', category: 'canvas', label: 'Select all nodes', defaultBinding: 'Ctrl+A' },
  { id: 'canvas.copy', category: 'canvas', label: 'Copy selection', defaultBinding: 'Ctrl+C' },
  { id: 'canvas.paste', category: 'canvas', label: 'Paste selection', defaultBinding: 'Ctrl+V' },
  { id: 'canvas.cut', category: 'canvas', label: 'Cut selection', defaultBinding: 'Ctrl+X' },
  { id: 'canvas.undo', category: 'canvas', label: 'Undo', defaultBinding: 'Ctrl+Z' },
  { id: 'canvas.redo', category: 'canvas', label: 'Redo', defaultBinding: 'Ctrl+Y' },
  { id: 'canvas.redoAlternate', category: 'canvas', label: 'Redo alternate', defaultBinding: 'Ctrl+Shift+Z' },
  { id: 'canvas.group', category: 'canvas', label: 'Group selected nodes', defaultBinding: 'Ctrl+G' },
  { id: 'canvas.collapse', category: 'canvas', label: 'Collapse selected nodes', defaultBinding: 'Alt+C' },
  { id: 'canvas.delete', category: 'canvas', label: 'Delete selected nodes', defaultBinding: 'Delete' },
];

let overrides = loadOverrides();
let snapshot = buildSnapshot();

function loadOverrides(): Record<string, string> {
  if (typeof localStorage === 'undefined') return {};
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) as Record<string, string> : {};
  } catch {
    return {};
  }
}

function saveOverrides() {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(overrides));
  } catch {
    /* ignore */
  }
}

function buildSnapshot(): KeybindingRecord[] {
  return DEFAULT_KEYBINDINGS.map(definition => ({
    ...definition,
    editable: definition.editable ?? true,
    binding: overrides[definition.id] ?? normalizeKeybinding(definition.defaultBinding) ?? definition.defaultBinding,
  }));
}

function emit() {
  snapshot = buildSnapshot();
  listeners.forEach(listener => listener());
}

function normalizeKeyName(key: string): string {
  const aliases: Record<string, string> = {
    esc: 'Escape',
    escape: 'Escape',
    del: 'Delete',
    delete: 'Delete',
    backspace: 'Backspace',
    enter: 'Enter',
    return: 'Enter',
    space: 'Space',
    ' ': 'Space',
    tab: 'Tab',
    up: 'ArrowUp',
    down: 'ArrowDown',
    left: 'ArrowLeft',
    right: 'ArrowRight',
    comma: ',',
    period: '.',
    slash: '/',
    backslash: '\\',
    grave: '`',
  };
  const trimmed = key.trim();
  const alias = aliases[trimmed.toLowerCase()];
  if (alias) return alias;
  if (/^arrow(up|down|left|right)$/i.test(trimmed)) {
    return `Arrow${trimmed.slice(5, 6).toUpperCase()}${trimmed.slice(6).toLowerCase()}`;
  }
  if (trimmed.length === 1) return trimmed.toUpperCase();
  return trimmed.slice(0, 1).toUpperCase() + trimmed.slice(1);
}

export function normalizeKeybinding(binding: string | null | undefined): string | null {
  if (!binding) return null;
  const rawParts = binding.split('+').map(part => part.trim()).filter(Boolean);
  if (!rawParts.length) return null;

  const modifiers = new Set<string>();
  let key = '';
  rawParts.forEach(part => {
    const normalized = part.toLowerCase();
    if (normalized === 'ctrl' || normalized === 'control' || normalized === 'mod') modifiers.add('Ctrl');
    else if (normalized === 'cmd' || normalized === 'command' || normalized === 'meta') modifiers.add('Meta');
    else if (normalized === 'alt' || normalized === 'option') modifiers.add('Alt');
    else if (normalized === 'shift') modifiers.add('Shift');
    else key = normalizeKeyName(part);
  });

  if (!key) return null;
  const ordered = ['Ctrl', 'Meta', 'Alt', 'Shift'].filter(modifier => modifiers.has(modifier));
  return [...ordered, key].join('+');
}

export function eventToKeybinding(event: KeyboardEvent | ReactKeyboardEvent): string | null {
  const key = event.key;
  if (key === 'Control' || key === 'Shift' || key === 'Alt' || key === 'Meta') return null;

  const parts: string[] = [];
  if (event.ctrlKey) parts.push('Ctrl');
  if (event.metaKey) parts.push('Meta');
  if (event.altKey) parts.push('Alt');
  if (event.shiftKey) parts.push('Shift');
  parts.push(normalizeKeyName(key));
  return parts.join('+');
}

export function keybindingMatchesEvent(binding: string | null | undefined, event: KeyboardEvent | ReactKeyboardEvent): boolean {
  const normalized = normalizeKeybinding(binding);
  if (!normalized) return false;
  return normalized === eventToKeybinding(event);
}

export function getKeybindingsSnapshot(): KeybindingRecord[] {
  return snapshot;
}

export function subscribeKeybindings(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function setKeybinding(id: string, binding: string): void {
  const normalized = normalizeKeybinding(binding);
  if (normalized) overrides = { ...overrides, [id]: normalized };
  else overrides = { ...overrides, [id]: '' };
  saveOverrides();
  emit();
}

export function resetKeybinding(id: string): void {
  const next = { ...overrides };
  delete next[id];
  overrides = next;
  saveOverrides();
  emit();
}

export function resetAllKeybindings(): void {
  overrides = {};
  saveOverrides();
  emit();
}

export function findKeybindingConflicts(bindings: KeybindingRecord[]): KeybindingConflict[] {
  const byBinding = new Map<string, string[]>();
  bindings.forEach(binding => {
    const normalized = normalizeKeybinding(binding.binding);
    if (!normalized) return;
    const ids = byBinding.get(normalized) ?? [];
    ids.push(binding.id);
    byBinding.set(normalized, ids);
  });

  return Array.from(byBinding.entries())
    .filter(([, actionIds]) => actionIds.length > 1)
    .map(([binding, actionIds]) => ({ binding, actionIds }));
}
