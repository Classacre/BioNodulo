import * as Y from 'yjs';
import type { Workflow, WorkflowNode, WorkflowEdge, WorkflowGroup } from '../types';

export function createWorkflowDoc(workflowId: string): Y.Doc {
  const ydoc = new Y.Doc();

  // Initialize top-level maps
  const meta = ydoc.getMap('meta');
  meta.set('id', workflowId);
  meta.set('version', 1);
  meta.set('name', 'Untitled');
  meta.set('createdAt', new Date().toISOString());
  meta.set('lastModified', new Date().toISOString());

  ydoc.getMap('nodes');
  ydoc.getMap('edges');
  ydoc.getMap('groups');

  const viewport = ydoc.getMap('viewport');
  viewport.set('x', 0);
  viewport.set('y', 0);
  viewport.set('scale', 1);

  return ydoc;
}

function serializeNode(node: WorkflowNode): Record<string, unknown> {
  // Strip node_info from Yjs storage (reconstructible from type)
  const { node_info, ...rest } = node;
  return rest;
}

function deserializeNode(data: unknown): WorkflowNode {
  if (typeof data !== 'object' || data === null) {
    throw new Error('Invalid node data');
  }
  const d = data as Record<string, unknown>;
  return {
    id: String(d.id || ''),
    type: String(d.type || ''),
    position: Array.isArray(d.position) ? [Number(d.position[0]), Number(d.position[1])] as [number, number] : [0, 0],
    params: (typeof d.params === 'object' && d.params !== null ? d.params : {}) as Record<string, unknown>,
    ui: (typeof d.ui === 'object' && d.ui !== null ? d.ui : undefined) as WorkflowNode['ui'],
  };
}

function serializeEdge(edge: WorkflowEdge): Record<string, unknown> {
  return { ...edge };
}

function deserializeEdge(data: unknown): WorkflowEdge {
  if (typeof data !== 'object' || data === null) {
    throw new Error('Invalid edge data');
  }
  const d = data as Record<string, unknown>;
  return {
    id: String(d.id || ''),
    from: (typeof d.from === 'object' && d.from !== null ? d.from : { node: '', output: '' }) as WorkflowEdge['from'],
    to: (typeof d.to === 'object' && d.to !== null ? d.to : { node: '', input: '' }) as WorkflowEdge['to'],
  };
}

function serializeGroup(group: WorkflowGroup): Record<string, unknown> {
  return { ...group };
}

function deserializeGroup(data: unknown): WorkflowGroup {
  if (typeof data !== 'object' || data === null) {
    throw new Error('Invalid group data');
  }
  const d = data as Record<string, unknown>;
  return {
    id: String(d.id || ''),
    name: String(d.name || ''),
    position: Array.isArray(d.position) ? [Number(d.position[0]), Number(d.position[1])] as [number, number] : [0, 0],
    width: Number(d.width || 0),
    height: Number(d.height || 0),
    color: String(d.color || '#6366f1'),
    collapsed: Boolean(d.collapsed),
    selected: Boolean(d.selected),
  };
}

export function docToWorkflow(doc: Y.Doc): Workflow {
  const meta = doc.getMap('meta');
  const yNodes = doc.getMap('nodes');
  const yEdges = doc.getMap('edges');
  const yGroups = doc.getMap('groups');

  const nodes: WorkflowNode[] = [];
  yNodes.forEach((value) => {
    try {
      nodes.push(deserializeNode(value));
    } catch { /* skip invalid */ }
  });

  const edges: WorkflowEdge[] = [];
  yEdges.forEach((value) => {
    try {
      edges.push(deserializeEdge(value));
    } catch { /* skip invalid */ }
  });

  const groups: WorkflowGroup[] = [];
  yGroups.forEach((value) => {
    try {
      groups.push(deserializeGroup(value));
    } catch { /* skip invalid */ }
  });

  return {
    id: String(meta.get('id') || ''),
    version: String(meta.get('version') || 'Alpha 1.2'),
    app: 'bionodulo',
    name: String(meta.get('name') || 'Untitled'),
    description: '',
    nodes,
    edges,
    groups,
    outputs: {},
  };
}

export function workflowToDoc(workflow: Workflow, doc?: Y.Doc): Y.Doc {
  const ydoc = doc || new Y.Doc();

  ydoc.transact(() => {
    const meta = ydoc.getMap('meta');
    meta.set('id', workflow.id || String(meta.get('id') || workflow.name || 'Untitled'));
    meta.set('version', workflow.version || 'Alpha 1.2');
    meta.set('name', workflow.name || 'Untitled');
    meta.set('lastModified', new Date().toISOString());

    const yNodes = ydoc.getMap('nodes');
    const currentNodeIds = new Set<string>();
    for (const node of workflow.nodes) {
      yNodes.set(node.id, serializeNode(node));
      currentNodeIds.add(node.id);
    }
    // Remove nodes that no longer exist
    yNodes.forEach((_, key) => {
      if (!currentNodeIds.has(key)) yNodes.delete(key);
    });

    const yEdges = ydoc.getMap('edges');
    const currentEdgeIds = new Set<string>();
    for (const edge of workflow.edges) {
      yEdges.set(edge.id, serializeEdge(edge));
      currentEdgeIds.add(edge.id);
    }
    yEdges.forEach((_, key) => {
      if (!currentEdgeIds.has(key)) yEdges.delete(key);
    });

    const yGroups = ydoc.getMap('groups');
    const currentGroupIds = new Set<string>();
    for (const group of workflow.groups) {
      yGroups.set(group.id, serializeGroup(group));
      currentGroupIds.add(group.id);
    }
    yGroups.forEach((_, key) => {
      if (!currentGroupIds.has(key)) yGroups.delete(key);
    });
  }, 'local');

  return ydoc;
}

export { serializeNode, deserializeNode, serializeEdge, deserializeEdge, serializeGroup, deserializeGroup };
