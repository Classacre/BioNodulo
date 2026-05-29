// Subgraph extraction + write-back helpers.
//
// A "subgraph" in BioNodulo is just a regular node whose type is `subgraph`
// and whose `params.workflow` carries the embedded Workflow JSON. Its visible
// input/output ports are computed from the edges that crossed the selection
// boundary at extraction time, so the parent graph can keep connecting to
// the subgraph the same way it connected to the loose nodes before.

import type { Workflow, WorkflowEdge, WorkflowNode } from '../types';

const PORT_DELIM = '__';

export interface SubgraphPort {
  /** Stable port name on the subgraph node, e.g. "in__qc__reads". */
  name: string;
  /** Data type carried through this port. */
  type: string;
  /** Inner node id that owns the original slot. */
  innerNodeId: string;
  /** Original slot name on the inner node. */
  innerSlot: string;
}

export interface ExtractionResult {
  /** The brand-new subgraph node that replaces the selection. */
  subgraphNode: WorkflowNode;
  /** Updated parent nodes — selection removed, subgraph node inserted. */
  nodes: WorkflowNode[];
  /** Updated parent edges — internal edges removed, external edges retargeted. */
  edges: WorkflowEdge[];
  /** Groups that lived entirely inside the selection (moved into the subgraph). */
  innerGroups: Workflow['groups'];
  /** Groups left in the parent. */
  outerGroups: Workflow['groups'];
}

interface InferredSlot {
  type: string;
}

function findOutputType(node: WorkflowNode | undefined, slotName: string): string {
  if (!node) return '*';
  const outputs = (node.node_info?.return_types ?? []) as unknown as string[];
  const names = (node.node_info?.return_names ?? []) as unknown as string[];
  const idx = names.indexOf(slotName);
  return outputs[idx] ?? '*';
}

function findInputType(node: WorkflowNode | undefined, slotName: string): string {
  if (!node) return '*';
  const required = (node.node_info?.input_types?.required ?? {}) as Record<string, InferredSlot>;
  const optional = (node.node_info?.input_types?.optional ?? {}) as Record<string, InferredSlot>;
  const spec = required[slotName] ?? optional[slotName];
  return (spec && typeof spec === 'object' && 'type' in spec ? String((spec as InferredSlot).type) : '*');
}

function uniquePortName(base: string, used: Set<string>): string {
  if (!used.has(base)) {
    used.add(base);
    return base;
  }
  let n = 2;
  while (used.has(`${base}_${n}`)) n += 1;
  const final = `${base}_${n}`;
  used.add(final);
  return final;
}

/**
 * Extract the nodes identified by `selectedIds` from `parent` into a single
 * subgraph node. External connections become explicit ports on the new node.
 */
export function extractSubgraph(
  parent: Workflow,
  selectedIds: string[],
  subgraphName: string,
  position: [number, number],
): ExtractionResult {
  const selected = new Set(selectedIds);
  const selectedNodes = parent.nodes.filter(n => selected.has(n.id));
  const externalIn: SubgraphPort[] = [];
  const externalOut: SubgraphPort[] = [];
  const portNames = new Set<string>();
  const inEdgeRemap: Record<string, string> = {}; // originalEdgeId -> port name
  const outEdgeRemap: Record<string, string> = {};

  for (const edge of parent.edges) {
    const fromSelected = selected.has(edge.from.node);
    const toSelected = selected.has(edge.to.node);
    if (fromSelected === toSelected) continue;
    if (!fromSelected && toSelected) {
      // External -> internal: create input port
      const innerNode = parent.nodes.find(n => n.id === edge.to.node);
      const portName = uniquePortName(`in_${edge.to.input}`, portNames);
      externalIn.push({
        name: portName,
        type: findInputType(innerNode, edge.to.input),
        innerNodeId: edge.to.node,
        innerSlot: edge.to.input,
      });
      inEdgeRemap[edge.id] = portName;
    } else {
      // Internal -> external: create output port
      const innerNode = parent.nodes.find(n => n.id === edge.from.node);
      const portName = uniquePortName(`out_${edge.from.output}`, portNames);
      externalOut.push({
        name: portName,
        type: findOutputType(innerNode, edge.from.output),
        innerNodeId: edge.from.node,
        innerSlot: edge.from.output,
      });
      outEdgeRemap[edge.id] = portName;
    }
  }

  // Inner edges = edges fully inside the selection. They stay on the subgraph.
  const innerEdges: WorkflowEdge[] = parent.edges.filter(e => selected.has(e.from.node) && selected.has(e.to.node));

  // Group splits: a group is "inner" if every selected node it covers stays
  // inside the selection and at least one selected node is inside its bbox.
  const innerGroups: Workflow['groups'] = [];
  const outerGroups: Workflow['groups'] = [];
  for (const group of parent.groups) {
    const gx1 = group.position[0];
    const gy1 = group.position[1];
    const gx2 = gx1 + group.width;
    const gy2 = gy1 + group.height;
    const nodesInGroup = parent.nodes.filter(n => (
      n.position[0] >= gx1 && n.position[0] <= gx2
      && n.position[1] >= gy1 && n.position[1] <= gy2
    ));
    const allInSelection = nodesInGroup.length > 0 && nodesInGroup.every(n => selected.has(n.id));
    if (allInSelection) innerGroups.push(group);
    else outerGroups.push(group);
  }

  const subgraphId = `subgraph_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`;
  const innerWorkflow: Workflow = {
    version: '2.0',
    app: 'bionodulo',
    name: subgraphName,
    description: '',
    nodes: selectedNodes.map(n => ({ ...n })),
    edges: innerEdges.map(e => ({ ...e })),
    groups: innerGroups.map(g => ({ ...g })),
    outputs: {},
  };

  // Synthetic node_info so the canvas can render the right number of slots.
  const inputTypesRequired: Record<string, [string, Record<string, unknown>]> = {};
  for (const port of externalIn) inputTypesRequired[port.name] = [port.type, { description: `${port.innerNodeId}.${port.innerSlot}` }];

  const subgraphNode: WorkflowNode = {
    id: subgraphId,
    type: 'subgraph',
    position,
    params: {
      workflow: innerWorkflow,
      input_ports: externalIn,
      output_ports: externalOut,
    } as unknown as Record<string, unknown>,
    node_info: {
      id: 'subgraph',
      display_name: subgraphName,
      category: 'Subgraph',
      input_types: { required: inputTypesRequired as never },
      return_types: externalOut.map(p => p.type) as never,
      return_names: externalOut.map(p => p.name) as never,
    } as WorkflowNode['node_info'],
    ui: {
      title: subgraphName,
      color: '#6366f1',
      shape: 'card',
    },
  };

  // Build the new parent nodes/edges.
  const parentNodes = parent.nodes.filter(n => !selected.has(n.id)).concat(subgraphNode);
  const parentEdges = parent.edges.flatMap<WorkflowEdge>(edge => {
    const fromSelected = selected.has(edge.from.node);
    const toSelected = selected.has(edge.to.node);
    if (fromSelected && toSelected) return [];
    if (!fromSelected && toSelected) {
      const portName = inEdgeRemap[edge.id];
      if (!portName) return [edge];
      return [{
        id: `e_${Date.now()}_${edge.id.slice(-6)}_in`,
        from: edge.from,
        to: { node: subgraphId, input: portName },
      }];
    }
    if (fromSelected && !toSelected) {
      const portName = outEdgeRemap[edge.id];
      if (!portName) return [edge];
      return [{
        id: `e_${Date.now()}_${edge.id.slice(-6)}_out`,
        from: { node: subgraphId, output: portName },
        to: edge.to,
      }];
    }
    return [edge];
  });

  return {
    subgraphNode,
    nodes: parentNodes,
    edges: parentEdges,
    innerGroups,
    outerGroups,
  };
}

/**
 * Write an edited inner workflow back into the parent subgraph node. We do
 * NOT touch the port shape on the subgraph node — adding/removing ports
 * requires re-extraction so the parent's edges stay consistent.
 *
 * Promoted widgets, if any, are baked back into the inner workflow before the
 * snapshot is saved so the parent's edits to surfaced widgets actually take
 * effect when the subgraph executes.
 */
export function writeSubgraphBack(
  parent: Workflow,
  subgraphNodeId: string,
  innerWorkflow: Workflow,
): Workflow {
  return {
    ...parent,
    nodes: parent.nodes.map(node => {
      if (node.id !== subgraphNodeId) return node;
      const promoted = (node.params?.promoted_widgets as PromotedWidget[] | undefined) ?? [];
      const reconciledInner = applyPromotedToInner(innerWorkflow, node.params || {}, promoted);
      return {
        ...node,
        params: {
          ...(node.params || {}),
          workflow: reconciledInner,
        },
      };
    }),
  };
}

export interface PromotedWidget {
  /** Key on the subgraph node where the surfaced value lives. */
  parentKey: string;
  /** Inner node that owns the original widget. */
  innerNodeId: string;
  /** Inner parameter key. */
  innerParamKey: string;
  /** Label to show on the subgraph node. */
  label: string;
  /** Original spec (type + min/max/options/default) copied from the inner node. */
  spec: unknown;
}

/**
 * Add a new promoted widget to a subgraph node so its inner control surfaces
 * directly on the parent. The subgraph node's `node_info.input_types.optional`
 * gets the new entry and the parent's `params[parentKey]` is seeded with the
 * current inner value.
 */
export function promoteWidget(
  parent: Workflow,
  subgraphNodeId: string,
  innerNodeId: string,
  innerParamKey: string,
  spec: unknown,
  label?: string,
): Workflow {
  const subgraphNode = parent.nodes.find(n => n.id === subgraphNodeId);
  if (!subgraphNode) return parent;
  const innerWorkflow = subgraphNode.params?.workflow as Workflow | undefined;
  if (!innerWorkflow) return parent;
  const innerNode = innerWorkflow.nodes.find(n => n.id === innerNodeId);
  if (!innerNode) return parent;

  const existing = (subgraphNode.params?.promoted_widgets as PromotedWidget[] | undefined) ?? [];
  const dup = existing.find(p => p.innerNodeId === innerNodeId && p.innerParamKey === innerParamKey);
  if (dup) return parent;

  const parentKey = uniquePortName(`promoted_${innerParamKey}`, new Set(existing.map(p => p.parentKey)));
  const nextPromoted: PromotedWidget[] = [
    ...existing,
    {
      parentKey,
      innerNodeId,
      innerParamKey,
      label: label ?? `${innerNode.ui?.title || innerNode.type}.${innerParamKey}`,
      spec,
    },
  ];
  const seedValue = innerNode.params?.[innerParamKey];

  // Synthesise a new input spec on the subgraph's node_info so the DOM widget
  // overlay renders it. The spec carries the same shape as the inner one.
  const optionalCurrent = (subgraphNode.node_info?.input_types?.optional || {}) as Record<string, unknown>;
  const newOptional: Record<string, unknown> = {
    ...optionalCurrent,
    [parentKey]: spec,
  };

  return {
    ...parent,
    nodes: parent.nodes.map(node => {
      if (node.id !== subgraphNodeId) return node;
      return {
        ...node,
        params: {
          ...(node.params || {}),
          promoted_widgets: nextPromoted,
          [parentKey]: seedValue,
        },
        node_info: {
          ...(node.node_info || {}),
          input_types: {
            ...(node.node_info?.input_types || {}),
            optional: newOptional as never,
          },
        } as WorkflowNode['node_info'],
      };
    }),
  };
}

/**
 * Take the parent subgraph node's promoted values and write them into the
 * embedded inner workflow's inner nodes. Used on exit from a subgraph view so
 * the saved inner workflow reflects parent edits to promoted widgets.
 */
export function applyPromotedToInner(
  innerWorkflow: Workflow,
  subgraphParams: Record<string, unknown>,
  promoted: PromotedWidget[],
): Workflow {
  if (promoted.length === 0) return innerWorkflow;
  return {
    ...innerWorkflow,
    nodes: innerWorkflow.nodes.map(node => {
      const overrides = promoted.filter(p => p.innerNodeId === node.id);
      if (overrides.length === 0) return node;
      const nextParams = { ...(node.params || {}) };
      for (const p of overrides) {
        if (p.parentKey in subgraphParams) {
          nextParams[p.innerParamKey] = subgraphParams[p.parentKey];
        }
      }
      return { ...node, params: nextParams };
    }),
  };
}

export const SUBGRAPH_INPUT_PREFIX = `in${PORT_DELIM}`;
export const SUBGRAPH_OUTPUT_PREFIX = `out${PORT_DELIM}`;
