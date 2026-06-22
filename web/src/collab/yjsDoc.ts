import * as Y from 'yjs';
import type { Workflow, WorkflowNode, WorkflowEdge, WorkflowGroup, WorkflowParameter } from '../types';
import type { Comment } from './types';
import i18n from '../i18n';

function fallbackWorkflowName(): string {
  return i18n.t('common.untitled');
}

export function createWorkflowDoc(workflowId: string): Y.Doc {
  const ydoc = new Y.Doc();

  // Initialize top-level maps
  const meta = ydoc.getMap('meta');
  meta.set('id', workflowId);
  meta.set('version', 1);
  meta.set('name', fallbackWorkflowName());
  meta.set('createdAt', new Date().toISOString());
  meta.set('lastModified', new Date().toISOString());

  ydoc.getMap('nodes');
  ydoc.getMap('edges');
  ydoc.getMap('groups');
  ydoc.getMap('comments');

  const viewport = ydoc.getMap('viewport');
  viewport.set('x', 0);
  viewport.set('y', 0);
  viewport.set('scale', 1);

  return ydoc;
}

/**
 * Make a value safe to store in Yjs: strip `undefined` (and any non-JSON
 * values) via a JSON round-trip. Yjs's writeAny encodes only JSON-compatible
 * values; an `undefined` map KEY or a non-encodable value throws deep in the
 * encoder ("writeString" on undefined), which previously crashed the whole
 * editor when seeding a DB-loaded workflow into the collab doc.
 */
function cleanForYjs<T>(value: T): T {
  return JSON.parse(JSON.stringify(value ?? null));
}

/** A usable Yjs map key: a non-empty string. */
function validId(id: unknown): id is string {
  return typeof id === 'string' && id.length > 0;
}

function serializeNode(node: WorkflowNode): Record<string, unknown> {
  // Strip node_info from Yjs storage (reconstructible from type)
  const { node_info, ...rest } = node;
  return cleanForYjs(rest);
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
  return cleanForYjs({ ...edge });
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
  return cleanForYjs({ ...group });
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

function serializeParameters(parameters: WorkflowParameter[] | undefined): Record<string, unknown>[] {
  return (parameters ?? []).map(parameter => cleanForYjs({ ...parameter }));
}

function serializeComment(comment: Comment): Record<string, unknown> {
  // `replies` is derived for the UI; store only the flat fields.
  const { replies, ...rest } = comment;
  return cleanForYjs(rest);
}

function deserializeComment(data: unknown): Comment {
  if (typeof data !== 'object' || data === null) {
    throw new Error('Invalid comment data');
  }
  const d = data as Record<string, unknown>;
  const created = String(d.created_at || new Date().toISOString());
  return {
    id: String(d.id || ''),
    workflow_id: String(d.workflow_id || ''),
    node_id: typeof d.node_id === 'string' ? d.node_id : null,
    user_id: String(d.user_id || ''),
    user_name: String(d.user_name || ''),
    user_color: String(d.user_color || '#6366f1'),
    content: String(d.content || ''),
    parent_id: typeof d.parent_id === 'string' ? d.parent_id : null,
    resolved: Boolean(d.resolved),
    created_at: created,
    updated_at: String(d.updated_at || created),
    replies: [],
  };
}

function deserializeParameters(data: unknown): WorkflowParameter[] | undefined {
  if (!Array.isArray(data)) return undefined;
  return data
    .filter((parameter): parameter is Record<string, unknown> => (
      Boolean(parameter) && typeof parameter === 'object' && !Array.isArray(parameter)
    ))
    .map(parameter => ({
      name: String(parameter.name || ''),
      type: String(parameter.type || 'STRING'),
      required: typeof parameter.required === 'boolean' ? parameter.required : undefined,
      default: parameter.default,
      value: parameter.value,
      description: typeof parameter.description === 'string' ? parameter.description : undefined,
    }))
    .filter(parameter => parameter.name.trim().length > 0);
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

  const comments: Comment[] = [];
  doc.getMap('comments').forEach((value) => {
    try {
      comments.push(deserializeComment(value));
    } catch { /* skip invalid */ }
  });

  return {
    id: String(meta.get('id') || ''),
    version: String(meta.get('version') || '2.0'),
    app: 'bionodulo',
    name: String(meta.get('name') || fallbackWorkflowName()),
    description: '',
    nodes,
    edges,
    groups,
    outputs: {},
    parameters: deserializeParameters(meta.get('parameters')),
    comments,
  };
}

export function workflowToDoc(workflow: Workflow, doc?: Y.Doc): Y.Doc {
  const ydoc = doc || new Y.Doc();

  ydoc.transact(() => {
    const meta = ydoc.getMap('meta');
    meta.set('id', workflow.id || String(meta.get('id') || workflow.name || 'Untitled'));
    meta.set('version', workflow.version || '2.0');
    meta.set('name', workflow.name || fallbackWorkflowName());
    meta.set('parameters', serializeParameters(workflow.parameters));
    meta.set('lastModified', new Date().toISOString());

    const yNodes = ydoc.getMap('nodes');
    const currentNodeIds = new Set<string>();
    for (const node of workflow.nodes ?? []) {
      if (!validId(node?.id)) continue; // undefined key would crash the Yjs encoder
      yNodes.set(node.id, serializeNode(node));
      currentNodeIds.add(node.id);
    }
    // Remove nodes that no longer exist
    yNodes.forEach((_, key) => {
      if (!currentNodeIds.has(key)) yNodes.delete(key);
    });

    const yEdges = ydoc.getMap('edges');
    const currentEdgeIds = new Set<string>();
    for (const edge of workflow.edges ?? []) {
      if (!validId(edge?.id)) continue;
      yEdges.set(edge.id, serializeEdge(edge));
      currentEdgeIds.add(edge.id);
    }
    yEdges.forEach((_, key) => {
      if (!currentEdgeIds.has(key)) yEdges.delete(key);
    });

    const yGroups = ydoc.getMap('groups');
    const currentGroupIds = new Set<string>();
    for (const group of workflow.groups ?? []) {
      if (!validId(group?.id)) continue;
      yGroups.set(group.id, serializeGroup(group));
      currentGroupIds.add(group.id);
    }
    yGroups.forEach((_, key) => {
      if (!currentGroupIds.has(key)) yGroups.delete(key);
    });

    const yComments = ydoc.getMap('comments');
    const currentCommentIds = new Set<string>();
    for (const comment of workflow.comments ?? []) {
      if (!validId(comment?.id)) continue;
      yComments.set(comment.id, serializeComment(comment));
      currentCommentIds.add(comment.id);
    }
    yComments.forEach((_, key) => {
      if (!currentCommentIds.has(key)) yComments.delete(key);
    });
  }, 'local');

  return ydoc;
}

export { serializeNode, deserializeNode, serializeEdge, deserializeEdge, serializeGroup, deserializeGroup, serializeComment, deserializeComment };
