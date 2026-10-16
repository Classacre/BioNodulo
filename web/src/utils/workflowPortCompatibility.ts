import type { WorkflowEdge, WorkflowNode } from '../types';

interface GraphDefinition {
  nodes: WorkflowNode[];
  edges: WorkflowEdge[];
}

function nodeTypes(nodes: WorkflowNode[]): Map<string, string | undefined> {
  const types = new Map<string, string | undefined>();
  for (const node of nodes) {
    if (!node || typeof node.id !== 'string') continue;
    // A duplicate id makes its target ambiguous; do not guess a migration.
    types.set(node.id, types.has(node.id) ? undefined : node.type);
  }
  return types;
}

/** Only documented historical target aliases; source names stay unchanged. */
function canonicalInput(type: string | undefined, input: string): string {
  return (type === 'samtools_view' && input === 'sam')
    || (type === 'samtools_sort' && input === 'bam') ? 'alignment' : input;
}

/** Copy only changed graph paths. Loading a document never mutates its source. */
export function normalizeWorkflowPortAliases<T extends GraphDefinition>(graph: T, depth = 0): T {
  if (!Array.isArray(graph.nodes) || !Array.isArray(graph.edges) || depth > 100) return graph;
  const targetTypes = nodeTypes(graph.nodes);
  let changed = false;
  const edges = graph.edges.map(edge => {
    if (!edge?.to || typeof edge.to.input !== 'string') return edge;
    const input = canonicalInput(targetTypes.get(edge.to.node), edge.to.input);
    if (input === edge.to.input) return edge;
    changed = true;
    return { ...edge, to: { ...edge.to, input } };
  });
  const nodes = graph.nodes.map(node => {
    if (node?.type !== 'subgraph') return node;
    const inner = node.params?.workflow;
    if (!inner || typeof inner !== 'object' || !Array.isArray((inner as GraphDefinition).nodes)
      || !Array.isArray((inner as GraphDefinition).edges)) return node;
    const nested = inner as GraphDefinition;
    const normalized = normalizeWorkflowPortAliases(nested, depth + 1);
    const innerTypes = nodeTypes(nested.nodes);
    const rawPorts = node.params?.input_ports;
    let portsChanged = false;
    const ports = Array.isArray(rawPorts) ? rawPorts.map(port => {
      if (!port || typeof port !== 'object') return port;
      const entry = port as Record<string, unknown>;
      const innerId = entry.innerNodeId ?? entry.inner_node_id;
      const key = entry.innerSlot !== null && entry.innerSlot !== undefined ? 'innerSlot' : 'inner_slot';
      const slot = entry[key];
      if (typeof innerId !== 'string' || typeof slot !== 'string') return port;
      const canonical = canonicalInput(innerTypes.get(innerId), slot);
      if (canonical === slot) return port;
      portsChanged = true;
      return { ...entry, [key]: canonical };
    }) : rawPorts;
    if (normalized === nested && !portsChanged) return node;
    changed = true;
    return { ...node, params: { ...node.params, workflow: normalized,
      ...(portsChanged ? { input_ports: ports } : {}) } };
  });
  return changed ? { ...graph, nodes, edges } : graph;
}
