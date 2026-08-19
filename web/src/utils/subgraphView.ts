// Subgraph drill-down view model.
//
// The canvas always edits ONE level of the workflow at a time. At the root
// that is the workflow itself; inside a subgraph it is the embedded inner
// workflow of the 'subgraph' node at the current navigation path. This module
// is the pure mapping layer between the two:
//
//   deriveView()      root document -> the namespaced graph the canvas shows
//   writeViewBack()   edited view   -> updated root document
//   wirePort()/unwirePort()         boundary-edge edits -> params.input_ports /
//                                     params.output_ports updates on the host
//
// Engine contract (see bionodulo/execution/executor.py): boundary wiring lives
// ONLY in params.input_ports / params.output_ports entries of shape
// { name, innerNodeId, innerSlot } — the inner workflow's edges must reference
// real inner nodes only (validation rejects anything else), so the boundary
// edges the canvas shows are DERIVED from the port entries, never stored.

import type { WorkflowEdge, WorkflowNode } from '../types';

export interface SubgraphPortView {
  name: string;
  type: string;
  innerNodeId: string;
  innerSlot: string;
}

export interface LevelGraph {
  nodes: WorkflowNode[];
  edges: WorkflowEdge[];
  /** The subgraph node hosting this level (null at the root). */
  host: WorkflowNode | null;
  inputPorts: SubgraphPortView[];
  outputPorts: SubgraphPortView[];
}

export interface DerivedView {
  nodes: WorkflowNode[];
  edges: WorkflowEdge[];
  level: LevelGraph;
}

export const IO_INPUTS_TYPE = '__subgraph_io_inputs__';
export const IO_OUTPUTS_TYPE = '__subgraph_io_outputs__';
/** Handle id of the '+' row on each IO panel — wiring from/to it creates a port. */
export const ADD_PORT_HANDLE = '__add__';

const BOUNDARY_IN_MARK = '__bnd_in__';
const BOUNDARY_OUT_MARK = '__bnd_out__';

/** Deepest-possible nav depth guard (matches nothing on the engine; pure UI). */
export const MAX_NAV_DEPTH = 100;

/** Canvas id prefix for a nav path: ['sub1'] -> 'sub1.'. Root -> ''. */
export function viewPrefix(path: string[]): string {
  return path.length ? `${path.join('.')}.` : '';
}

export function isIOPanelNode(node: WorkflowNode): boolean {
  return node.type === IO_INPUTS_TYPE || node.type === IO_OUTPUTS_TYPE;
}

/** True when a (namespaced) canvas id belongs to one of the IO panel nodes. */
export function isIOPanelNodeId(id: string, prefix: string): boolean {
  return id === `${prefix}${IO_INPUTS_TYPE}` || id === `${prefix}${IO_OUTPUTS_TYPE}`;
}

export function isBoundaryEdgeId(edgeId: string, prefix: string): boolean {
  return (
    edgeId.startsWith(`${prefix}${BOUNDARY_IN_MARK}`)
    || edgeId.startsWith(`${prefix}${BOUNDARY_OUT_MARK}`)
  );
}

/** Port name carried by a derived boundary edge id, or null when not one. */
export function boundaryEdgePort(edgeId: string, prefix: string): { direction: 'input' | 'output'; portName: string } | null {
  if (edgeId.startsWith(`${prefix}${BOUNDARY_IN_MARK}`)) {
    return { direction: 'input', portName: edgeId.slice(prefix.length + BOUNDARY_IN_MARK.length) };
  }
  if (edgeId.startsWith(`${prefix}${BOUNDARY_OUT_MARK}`)) {
    return { direction: 'output', portName: edgeId.slice(prefix.length + BOUNDARY_OUT_MARK.length) };
  }
  return null;
}

/** Normalize one params.input_ports / output_ports entry (snake or camel case). */
export function normalizePort(raw: unknown): SubgraphPortView | null {
  if (!raw || typeof raw !== 'object') return null;
  const entry = raw as Record<string, unknown>;
  const name = typeof entry.name === 'string' ? entry.name : '';
  if (!name) return null;
  const innerNodeId = String(entry.innerNodeId ?? entry.inner_node_id ?? '') || '';
  const innerSlot = String(entry.innerSlot ?? entry.inner_slot ?? '') || '';
  const type = typeof entry.type === 'string' && entry.type ? entry.type : '*';
  return { name, type, innerNodeId, innerSlot };
}

export function getSubgraphPorts(node: WorkflowNode, key: 'input_ports' | 'output_ports'): SubgraphPortView[] {
  const raw = node.params?.[key];
  if (!Array.isArray(raw)) return [];
  const out: SubgraphPortView[] = [];
  for (const entry of raw) {
    const port = normalizePort(entry);
    if (port) out.push(port);
  }
  return out;
}

/** The embedded inner workflow of a subgraph node, or null when missing. */
export function getInnerWorkflow(node: WorkflowNode): { nodes: WorkflowNode[]; edges: WorkflowEdge[] } | null {
  const raw = node.params?.workflow as { nodes?: WorkflowNode[]; edges?: WorkflowEdge[] } | undefined;
  if (!raw || !Array.isArray(raw.nodes)) return null;
  return { nodes: raw.nodes, edges: Array.isArray(raw.edges) ? raw.edges : [] };
}

/** Walk the nav path from the root and resolve the level the canvas should show. */
export function resolveLevel(rootNodes: WorkflowNode[], rootEdges: WorkflowEdge[], path: string[]): LevelGraph | null {
  let nodes = rootNodes;
  let edges = rootEdges;
  let host: WorkflowNode | null = null;
  let inputPorts: SubgraphPortView[] = [];
  let outputPorts: SubgraphPortView[] = [];
  for (const id of path) {
    const node = nodes.find(n => n.id === id);
    if (!node || node.type !== 'subgraph') return null;
    const inner = getInnerWorkflow(node);
    if (!inner) return null;
    host = node;
    inputPorts = getSubgraphPorts(node, 'input_ports');
    outputPorts = getSubgraphPorts(node, 'output_ports');
    nodes = inner.nodes;
    edges = inner.edges;
  }
  return { nodes, edges, host, inputPorts, outputPorts };
}

export interface PanelPositions {
  inputs?: [number, number];
  outputs?: [number, number];
}

/** Default IO-panel anchors: just outside the inner graph's bounding box. */
export function defaultPanelPositions(level: LevelGraph): Required<PanelPositions> {
  if (level.nodes.length === 0) return { inputs: [0, 0], outputs: [520, 0] };
  let minX = Infinity;
  let minY = Infinity;
  let maxX = -Infinity;
  for (const n of level.nodes) {
    minX = Math.min(minX, n.position[0]);
    minY = Math.min(minY, n.position[1]);
    maxX = Math.max(maxX, n.position[0]);
  }
  return { inputs: [Math.round(minX - 340), Math.round(minY)], outputs: [Math.round(maxX + 300), Math.round(minY)] };
}

function makePanelNode(
  type: string,
  id: string,
  title: string,
  ports: SubgraphPortView[],
  connectedPorts: Set<string>,
  position: [number, number],
): WorkflowNode {
  return {
    id,
    type,
    position,
    params: {
      title,
      ports: ports.map(p => ({ name: p.name, type: p.type, connected: connectedPorts.has(p.name) })),
    },
    ui: { pinned: true },
  };
}

/**
 * Build the graph the canvas shows for `path`: inner nodes/edges namespaced by
 * the path (so React Flow ids stay unique across levels — stored inner ids are
 * never rewritten), the two IO panel nodes, and boundary edges derived from
 * the host's port entries.
 */
export function deriveView(
  rootNodes: WorkflowNode[],
  rootEdges: WorkflowEdge[],
  path: string[],
  panelPositions?: PanelPositions,
): DerivedView | null {
  const level = resolveLevel(rootNodes, rootEdges, path);
  if (!level) return null;
  if (path.length === 0) return { nodes: rootNodes, edges: rootEdges, level };

  const prefix = viewPrefix(path);
  const hostId = path[path.length - 1];
  // Edges of the level CONTAINING the host subgraph node — used to mark which
  // panel ports are wired from the outside.
  const containingEdges = path.length === 1
    ? rootEdges
    : (resolveLevel(rootNodes, rootEdges, path.slice(0, -1))?.edges ?? []);
  const connectedInputs = new Set(
    containingEdges.filter(e => e.to.node === hostId).map(e => e.to.input),
  );
  const connectedOutputs = new Set(
    containingEdges.filter(e => e.from.node === hostId).map(e => e.from.output),
  );

  const innerNodeIds = new Set(level.nodes.map(n => n.id));
  const nodes: WorkflowNode[] = level.nodes.map(n => ({ ...n, id: `${prefix}${n.id}` }));
  const edges: WorkflowEdge[] = level.edges.map(e => ({
    ...e,
    id: `${prefix}${e.id}`,
    from: { node: `${prefix}${e.from.node}`, output: e.from.output },
    to: { node: `${prefix}${e.to.node}`, input: e.to.input },
  }));

  const inputsId = `${prefix}${IO_INPUTS_TYPE}`;
  const outputsId = `${prefix}${IO_OUTPUTS_TYPE}`;
  for (const port of level.inputPorts) {
    if (!port.innerNodeId || !port.innerSlot || !innerNodeIds.has(port.innerNodeId)) continue;
    edges.push({
      id: `${prefix}${BOUNDARY_IN_MARK}${port.name}`,
      from: { node: inputsId, output: port.name },
      to: { node: `${prefix}${port.innerNodeId}`, input: port.innerSlot },
    });
  }
  for (const port of level.outputPorts) {
    if (!port.innerNodeId || !port.innerSlot || !innerNodeIds.has(port.innerNodeId)) continue;
    edges.push({
      id: `${prefix}${BOUNDARY_OUT_MARK}${port.name}`,
      from: { node: `${prefix}${port.innerNodeId}`, output: port.innerSlot },
      to: { node: outputsId, input: port.name },
    });
  }

  const defaults = defaultPanelPositions(level);
  const panels: WorkflowNode[] = [
    makePanelNode(IO_INPUTS_TYPE, inputsId, 'inputs', level.inputPorts, connectedInputs, panelPositions?.inputs ?? defaults.inputs),
    makePanelNode(IO_OUTPUTS_TYPE, outputsId, 'outputs', level.outputPorts, connectedOutputs, panelPositions?.outputs ?? defaults.outputs),
  ];
  return { nodes: [...panels, ...nodes], edges, level };
}

/**
 * Replace the level graph at `path` with `levelNodes`/`levelEdges` (raw,
 * un-namespaced ids) and return the updated ROOT nodes/edges. Sanitizes the
 * host's port entries against the surviving inner nodes and prunes any
 * containing-level edges left pointing at removed ports.
 */
export function writeLevelBack(
  rootNodes: WorkflowNode[],
  rootEdges: WorkflowEdge[],
  path: string[],
  levelNodes: WorkflowNode[],
  levelEdges: WorkflowEdge[],
): { nodes: WorkflowNode[]; edges: WorkflowEdge[] } {
  if (path.length === 0) return { nodes: levelNodes, edges: levelEdges };

  const innerNodeIds = new Set(levelNodes.map(n => n.id));

  function replaceIn(
    nodes: WorkflowNode[],
    edges: WorkflowEdge[],
    rest: string[],
  ): { nodes: WorkflowNode[]; edges: WorkflowEdge[] } {
    const head = rest[0];
    const isHost = rest.length === 1;
    let droppedInputs = new Set<string>();
    let droppedOutputs = new Set<string>();
    const nextNodes = nodes.map(n => {
      if (n.id !== head) return n;
      if (isHost) {
        const params = { ...(n.params || {}) };
        const workflowRaw = (params.workflow && typeof params.workflow === 'object')
          ? params.workflow as Record<string, unknown>
          : {};
        const keptInputs = getSubgraphPorts(n, 'input_ports').filter(p => innerNodeIds.has(p.innerNodeId));
        const keptOutputs = getSubgraphPorts(n, 'output_ports').filter(p => innerNodeIds.has(p.innerNodeId));
        droppedInputs = new Set(
          getSubgraphPorts(n, 'input_ports').filter(p => !innerNodeIds.has(p.innerNodeId)).map(p => p.name),
        );
        droppedOutputs = new Set(
          getSubgraphPorts(n, 'output_ports').filter(p => !innerNodeIds.has(p.innerNodeId)).map(p => p.name),
        );
        return {
          ...n,
          params: {
            ...params,
            workflow: { ...workflowRaw, nodes: levelNodes, edges: levelEdges },
            input_ports: keptInputs,
            output_ports: keptOutputs,
          },
        };
      }
      const inner = getInnerWorkflow(n);
      if (!inner) return n;
      const replaced = replaceIn(inner.nodes, inner.edges, rest.slice(1));
      const workflowRaw = (n.params?.workflow && typeof n.params.workflow === 'object')
        ? n.params.workflow as Record<string, unknown>
        : {};
      return {
        ...n,
        params: {
          ...(n.params || {}),
          workflow: { ...workflowRaw, nodes: replaced.nodes, edges: replaced.edges },
        },
      };
    });
    // Prune this level's edges that reference ports dropped from the host.
    const nextEdges = (droppedInputs.size === 0 && droppedOutputs.size === 0)
      ? edges
      : edges.filter(e => !(
        (e.to.node === head && droppedInputs.has(e.to.input))
        || (e.from.node === head && droppedOutputs.has(e.from.output))
      ));
    return { nodes: nextNodes, edges: nextEdges };
  }

  return replaceIn(rootNodes, rootEdges, path);
}

/**
 * Inverse of deriveView: take the canvas's (namespaced, panel-carrying) view
 * graph and fold it back into the root document. Boundary edges and panel
 * nodes are stripped — they are derived state, never stored.
 */
export function writeViewBack(
  rootNodes: WorkflowNode[],
  rootEdges: WorkflowEdge[],
  path: string[],
  viewNodes: WorkflowNode[],
  viewEdges: WorkflowEdge[],
): { nodes: WorkflowNode[]; edges: WorkflowEdge[] } {
  if (path.length === 0) return { nodes: viewNodes, edges: viewEdges };
  const prefix = viewPrefix(path);
  const levelNodes = viewNodes
    .filter(n => !isIOPanelNode(n))
    .map(n => ({ ...n, id: n.id.slice(prefix.length) }));
  const levelEdges = viewEdges
    .filter(e => !isBoundaryEdgeId(e.id, prefix))
    .map(e => ({
      ...e,
      id: e.id.slice(prefix.length),
      from: { ...e.from, node: e.from.node.slice(prefix.length) },
      to: { ...e.to, node: e.to.node.slice(prefix.length) },
    }));
  return writeLevelBack(rootNodes, rootEdges, path, levelNodes, levelEdges);
}

function uniquePortName(base: string, used: Set<string>): string {
  if (!used.has(base)) return base;
  let n = 2;
  while (used.has(`${base}_${n}`)) n += 1;
  return `${base}_${n}`;
}

function updateHostPorts(
  rootNodes: WorkflowNode[],
  rootEdges: WorkflowEdge[],
  path: string[],
  updater: (host: WorkflowNode) => { node: WorkflowNode; extraInnerEdgesFilter?: (edges: WorkflowEdge[]) => WorkflowEdge[] },
): { nodes: WorkflowNode[]; edges: WorkflowEdge[] } {
  const hostId = path[path.length - 1];
  const level = resolveLevel(rootNodes, rootEdges, path.slice(0, -1));
  if (!level) return { nodes: rootNodes, edges: rootEdges };
  const host = level.nodes.find(n => n.id === hostId);
  if (!host) return { nodes: rootNodes, edges: rootEdges };
  const { node: nextHost, extraInnerEdgesFilter } = updater(host);
  let nextLevelNodes = level.nodes.map(n => (n.id === hostId ? nextHost : n));
  // The inner-edge cleanup (dropping a real inner edge feeding a slot a
  // boundary wire just claimed) happens inside the host's embedded workflow.
  if (extraInnerEdgesFilter) {
    nextLevelNodes = nextLevelNodes.map(n => {
      if (n.id !== hostId) return n;
      const inner = getInnerWorkflow(n);
      if (!inner) return n;
      const workflowRaw = n.params?.workflow as Record<string, unknown>;
      return {
        ...n,
        params: {
          ...(n.params || {}),
          workflow: { ...workflowRaw, edges: extraInnerEdgesFilter(inner.edges) },
        },
      };
    });
  }
  return writeLevelBack(rootNodes, rootEdges, path.slice(0, -1), nextLevelNodes, level.edges);
}

/**
 * Wire a boundary connection: Inputs panel port -> inner node slot (input), or
 * inner node output -> Outputs panel port (output). `portName` null means the
 * panel's '+' handle was used, so a new port is created (named in__N__S /
 * out__N__S, uniquified); otherwise the existing port keeps its name (parent
 * edges stay valid) and is re-pointed at the new inner slot.
 */
export function wirePort(
  rootNodes: WorkflowNode[],
  rootEdges: WorkflowEdge[],
  path: string[],
  direction: 'input' | 'output',
  portName: string | null,
  innerNodeId: string,
  innerSlot: string,
  type = '*',
): { nodes: WorkflowNode[]; edges: WorkflowEdge[] } {
  const key = direction === 'input' ? 'input_ports' : 'output_ports';
  return updateHostPorts(rootNodes, rootEdges, path, (host) => {
    const ports = getSubgraphPorts(host, key);
    let nextPorts: SubgraphPortView[];
    if (portName === null) {
      const prefixTag = direction === 'input' ? 'in' : 'out';
      const name = uniquePortName(`${prefixTag}__${innerNodeId}__${innerSlot}`, new Set(ports.map(p => p.name)));
      nextPorts = [...ports, { name, type, innerNodeId, innerSlot }];
    } else {
      nextPorts = ports.map(p => (p.name === portName ? { ...p, innerNodeId, innerSlot } : p));
    }
    const node: WorkflowNode = {
      ...host,
      params: { ...(host.params || {}), [key]: nextPorts },
    };
    // A boundary wire claims the inner input slot: drop any real inner edge
    // still feeding it (outputs fan out, so only inputs need this).
    const extraInnerEdgesFilter = direction === 'input'
      ? (edges: WorkflowEdge[]) => edges.filter(e => !(e.to.node === innerNodeId && e.to.input === innerSlot))
      : undefined;
    return { node, extraInnerEdgesFilter };
  });
}

/**
 * Remove one boundary edge: drops the port entry entirely (one edge per port
 * in this UI) and prunes containing-level edges that referenced the port on
 * the host subgraph node — so the parent handle and its wires vanish together.
 */
export function unwirePort(
  rootNodes: WorkflowNode[],
  rootEdges: WorkflowEdge[],
  path: string[],
  direction: 'input' | 'output',
  portName: string,
): { nodes: WorkflowNode[]; edges: WorkflowEdge[] } {
  const key = direction === 'input' ? 'input_ports' : 'output_ports';
  const hostId = path[path.length - 1];
  const level = resolveLevel(rootNodes, rootEdges, path.slice(0, -1));
  if (!level) return { nodes: rootNodes, edges: rootEdges };
  const host = level.nodes.find(n => n.id === hostId);
  if (!host) return { nodes: rootNodes, edges: rootEdges };
  const ports = getSubgraphPorts(host, key);
  const nextHost: WorkflowNode = {
    ...host,
    params: { ...(host.params || {}), [key]: ports.filter(p => p.name !== portName) },
  };
  const nextLevelNodes = level.nodes.map(n => (n.id === hostId ? nextHost : n));
  // Prune the containing level's edges to the now-missing port, so the parent
  // handle and its wires vanish together.
  const nextLevelEdges = level.edges.filter(e => !(
    (direction === 'input' && e.to.node === hostId && e.to.input === portName)
    || (direction === 'output' && e.from.node === hostId && e.from.output === portName)
  ));
  return writeLevelBack(rootNodes, rootEdges, path.slice(0, -1), nextLevelNodes, nextLevelEdges);
}
