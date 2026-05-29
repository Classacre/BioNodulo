import type { ReactNode } from 'react';
import { useSyncExternalStore } from 'react';

export type PanelGroup = 'workspace' | 'compute' | 'support' | 'system';

export interface PanelDescriptor {
  id: string;
  title: string;
  icon: string;
  shortcutTitle?: string;
  group: PanelGroup;
  order: number;
  render: () => ReactNode;
}

export interface RegisteredPanel extends PanelDescriptor {
  sourceId: string;
}

const listeners = new Set<() => void>();
const panels = new Map<string, RegisteredPanel>();
let snapshot: RegisteredPanel[] = [];

function panelKey(sourceId: string, id: string) {
  return `${sourceId}:${id}`;
}

function rebuildSnapshot() {
  snapshot = Array.from(panels.values()).sort((a, b) => {
    if (a.group !== b.group) {
      const groupOrder: Record<PanelGroup, number> = { workspace: 0, compute: 1, support: 2, system: 3 };
      return groupOrder[a.group] - groupOrder[b.group];
    }
    return a.order - b.order;
  });
}

function emit() {
  rebuildSnapshot();
  listeners.forEach(listener => listener());
}

export function registerPanels(sourceId: string, descriptors: PanelDescriptor[]): () => void {
  for (const descriptor of descriptors) {
    panels.set(panelKey(sourceId, descriptor.id), { ...descriptor, sourceId });
  }
  emit();
  return () => {
    let changed = false;
    for (const descriptor of descriptors) {
      changed = panels.delete(panelKey(sourceId, descriptor.id)) || changed;
    }
    if (changed) emit();
  };
}

export function registerPanel(sourceId: string, descriptor: PanelDescriptor): () => void {
  return registerPanels(sourceId, [descriptor]);
}

export function subscribePanels(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function getPanelsSnapshot(): RegisteredPanel[] {
  return snapshot;
}

export function usePanelRegistry(): RegisteredPanel[] {
  return useSyncExternalStore(subscribePanels, getPanelsSnapshot, getPanelsSnapshot);
}
