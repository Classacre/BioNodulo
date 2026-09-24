import type { Workflow } from '../types';

const GENERATED_NODE_ID = /^biotools_[a-f0-9]{32}$/;

export function isGeneratedRegistryNodeId(value: unknown): value is string {
  return typeof value === 'string' && GENERATED_NODE_ID.test(value);
}

export function collectRegistryNodeIds(workflows: readonly Workflow[]): string[] {
  const ids = new Set<string>();
  const visited = new WeakSet<object>();
  const scan = (value: unknown) => {
    if (!value || typeof value !== 'object' || visited.has(value)) return;
    visited.add(value);
    const workflow = value as Record<string, unknown>;
    const rawNodes = workflow.nodes;
    const nodes = Array.isArray(rawNodes) ? rawNodes
      : rawNodes && typeof rawNodes === 'object' ? Object.values(rawNodes) : [];
    for (const rawNode of nodes) {
      if (!rawNode || typeof rawNode !== 'object') continue;
      const node = rawNode as Record<string, unknown>;
      if (isGeneratedRegistryNodeId(node.type)) ids.add(node.type);
      if (node.type === 'subgraph' && node.params && typeof node.params === 'object') {
        scan((node.params as Record<string, unknown>).workflow);
      }
    }
  };
  workflows.forEach(scan);
  return [...ids];
}
