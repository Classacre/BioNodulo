import { describe, expect, it } from 'vitest';
import type { WorkflowEdge, WorkflowNode } from '../types';
import {
  deriveView,
  writeViewBack,
  wirePort,
  unwirePort,
  resolveLevel,
  viewPrefix,
  boundaryEdgePort,
  IO_INPUTS_TYPE,
  IO_OUTPUTS_TYPE,
  ADD_PORT_HANDLE,
  getSubgraphPorts,
} from '../utils/subgraphView';

function innerNode(id: string, params: Record<string, unknown> = {}): WorkflowNode {
  return { id, type: 'python_code', position: [0, 0], params };
}

function subgraphNode(
  id: string,
  inner: { nodes: WorkflowNode[]; edges: WorkflowEdge[] },
  inputPorts: unknown[] = [],
  outputPorts: unknown[] = [],
): WorkflowNode {
  return {
    id,
    type: 'subgraph',
    position: [100, 100],
    params: {
      workflow: { version: '2.0', app: 'bionodulo', name: id, description: '', nodes: inner.nodes, edges: inner.edges, groups: [], outputs: {} },
      input_ports: inputPorts,
      output_ports: outputPorts,
    },
    ui: { title: id },
  };
}

// Root: inputA -> sub1 -> outputB. sub1 hosts innerX + innerY wired together.
function makeRoot() {
  const inner = {
    nodes: [innerNode('innerX', { code: 'x' }), innerNode('innerY')],
    edges: [
      { id: 'e-xy', from: { node: 'innerX', output: 'result' }, to: { node: 'innerY', input: 'data' } },
    ] as WorkflowEdge[],
  };
  const sub = subgraphNode(
    'sub1',
    inner,
    [{ name: 'in__innerX__data', type: 'ANY', innerNodeId: 'innerX', innerSlot: 'data' }],
    [{ name: 'out__innerY__result', type: 'ANY', innerNodeId: 'innerY', innerSlot: 'result' }],
  );
  const nodes: WorkflowNode[] = [innerNode('inputA'), sub, innerNode('outputB')];
  const edges: WorkflowEdge[] = [
    { id: 'e1', from: { node: 'inputA', output: 'out' }, to: { node: 'sub1', input: 'in__innerX__data' } },
    { id: 'e2', from: { node: 'sub1', output: 'out__innerY__result' }, to: { node: 'outputB', input: 'in' } },
  ];
  return { nodes, edges };
}

describe('deriveView', () => {
  it('returns the root graph unchanged at the root path', () => {
    const { nodes, edges } = makeRoot();
    const view = deriveView(nodes, edges, [])!;
    expect(view.nodes).toBe(nodes);
    expect(view.edges).toBe(edges);
  });

  it('namespaces inner ids and derives boundary edges from the port entries', () => {
    const { nodes, edges } = makeRoot();
    const view = deriveView(nodes, edges, ['sub1'])!;
    const prefix = viewPrefix(['sub1']);
    const ids = view.nodes.map(n => n.id);
    expect(ids).toContain(`${prefix}innerX`);
    expect(ids).toContain(`${prefix}innerY`);
    expect(ids).toContain(`${prefix}${IO_INPUTS_TYPE}`);
    expect(ids).toContain(`${prefix}${IO_OUTPUTS_TYPE}`);

    // One derived boundary edge per port entry.
    const boundaryIn = view.edges.find(e => e.from.node === `${prefix}${IO_INPUTS_TYPE}`);
    expect(boundaryIn).toBeDefined();
    expect(boundaryIn!.from.output).toBe('in__innerX__data');
    expect(boundaryIn!.to).toEqual({ node: `${prefix}innerX`, input: 'data' });
    const boundaryOut = view.edges.find(e => e.to.node === `${prefix}${IO_OUTPUTS_TYPE}`);
    expect(boundaryOut!.from).toEqual({ node: `${prefix}innerY`, output: 'result' });
    expect(boundaryOut!.to.input).toBe('out__innerY__result');

    // The stored inner edge is namespaced but its endpoints are untouched.
    const inner = view.edges.find(e => e.id === `${prefix}e-xy`);
    expect(inner!.from.node).toBe(`${prefix}innerX`);
    expect(inner!.to.node).toBe(`${prefix}innerY`);

    expect(boundaryEdgePort(boundaryIn!.id, prefix)).toEqual({ direction: 'input', portName: 'in__innerX__data' });
  });

  it('resolves nested paths through multiple subgraph levels', () => {
    // sub2 lives inside sub1 and hosts innerZ.
    const sub2 = subgraphNode(
      'sub2',
      { nodes: [innerNode('innerZ')], edges: [] },
      [{ name: 'in__innerZ__data', type: 'ANY', inner_node_id: 'innerZ', inner_slot: 'data' }],
      [],
    );
    const sub1 = subgraphNode('sub1', { nodes: [sub2], edges: [] });
    const level = resolveLevel([sub1], [], ['sub1', 'sub2']);
    expect(level).not.toBeNull();
    expect(level!.nodes.map(n => n.id)).toEqual(['innerZ']);
    // snake_case port entries normalize too (engine accepts both spellings).
    expect(level!.inputPorts[0]).toMatchObject({ name: 'in__innerZ__data', innerNodeId: 'innerZ', innerSlot: 'data' });

    const view = deriveView([sub1], [], ['sub1', 'sub2'])!;
    expect(view.nodes.some(n => n.id === 'sub1.sub2.innerZ')).toBe(true);
  });

  it('returns null when the path references a missing or non-subgraph node', () => {
    const { nodes, edges } = makeRoot();
    expect(deriveView(nodes, edges, ['nope'])).toBeNull();
    expect(deriveView(nodes, edges, ['inputA'])).toBeNull();
  });
});

describe('writeViewBack', () => {
  it('round-trips: edits to an inner node param land in the root document', () => {
    const { nodes, edges } = makeRoot();
    const path = ['sub1'];
    const view = deriveView(nodes, edges, path)!;
    const prefix = viewPrefix(path);
    // Simulate a widget edit on innerX inside the subgraph view.
    const editedViewNodes = view.nodes.map(n =>
      n.id === `${prefix}innerX` ? { ...n, params: { ...n.params, code: 'edited' } } : n);
    const out = writeViewBack(nodes, edges, path, editedViewNodes, view.edges);

    // Root node ids untouched; the inner node inside sub1 got the new param.
    expect(out.nodes.map(n => n.id)).toEqual(['inputA', 'sub1', 'outputB']);
    const sub = out.nodes.find(n => n.id === 'sub1')!;
    const inner = (sub.params.workflow as { nodes: WorkflowNode[] }).nodes;
    expect(inner.find(n => n.id === 'innerX')!.params.code).toBe('edited');
    // The stored inner ids were never rewritten with the namespaced form.
    expect(inner.some(n => n.id.includes('.'))).toBe(false);
    // Root edges unchanged.
    expect(out.edges).toEqual(edges);
  });

  it('strips IO panels and boundary edges so they never reach the document', () => {
    const { nodes, edges } = makeRoot();
    const path = ['sub1'];
    const view = deriveView(nodes, edges, path)!;
    const out = writeViewBack(nodes, edges, path, view.nodes, view.edges);
    const sub = out.nodes.find(n => n.id === 'sub1')!;
    const workflow = sub.params.workflow as { nodes: WorkflowNode[]; edges: WorkflowEdge[] };
    expect(workflow.nodes.every(n => n.type !== IO_INPUTS_TYPE && n.type !== IO_OUTPUTS_TYPE)).toBe(true);
    expect(workflow.edges).toHaveLength(1);
    expect(workflow.edges[0].id).toBe('e-xy');
  });

  it('sanitizes ports whose inner node was deleted and prunes the parent wires', () => {
    const { nodes, edges } = makeRoot();
    const path = ['sub1'];
    const view = deriveView(nodes, edges, path)!;
    const prefix = viewPrefix(path);
    // Delete innerX inside the subgraph: its input port must go, and the root
    // edge feeding that port must go with it.
    const nextViewNodes = view.nodes.filter(n => n.id !== `${prefix}innerX`);
    const out = writeViewBack(nodes, edges, path, nextViewNodes, view.edges);
    const sub = out.nodes.find(n => n.id === 'sub1')!;
    expect(getSubgraphPorts(sub, 'input_ports')).toEqual([]);
    expect(getSubgraphPorts(sub, 'output_ports')).toHaveLength(1);
    expect(out.edges.some(e => e.to.node === 'sub1' && e.to.input === 'in__innerX__data')).toBe(false);
    expect(out.edges.some(e => e.id === 'e2')).toBe(true);
  });
});

describe('boundary wiring (wirePort / unwirePort)', () => {
  it('creates a new input port from the + handle with an in__N__S name', () => {
    const { nodes, edges } = makeRoot();
    const out = wirePort(nodes, edges, ['sub1'], 'input', null, 'innerY', 'extra', 'STRING');
    const sub = out.nodes.find(n => n.id === 'sub1')!;
    const ports = getSubgraphPorts(sub, 'input_ports');
    expect(ports).toHaveLength(2);
    expect(ports[1]).toEqual({ name: 'in__innerY__extra', type: 'STRING', innerNodeId: 'innerY', innerSlot: 'extra' });
  });

  it('remaps an existing port to a new inner slot but keeps its name (parent wires survive)', () => {
    const { nodes, edges } = makeRoot();
    const out = wirePort(nodes, edges, ['sub1'], 'input', 'in__innerX__data', 'innerY', 'data');
    const sub = out.nodes.find(n => n.id === 'sub1')!;
    const ports = getSubgraphPorts(sub, 'input_ports');
    expect(ports).toHaveLength(1);
    expect(ports[0]).toMatchObject({ name: 'in__innerX__data', innerNodeId: 'innerY', innerSlot: 'data' });
    // The root edge into the port is untouched.
    expect(out.edges.some(e => e.to.node === 'sub1' && e.to.input === 'in__innerX__data')).toBe(true);
  });

  it('claiming an inner input slot drops the real inner edge feeding it', () => {
    const { nodes, edges } = makeRoot();
    // Wire a new input port onto innerY.data, which e-xy currently feeds.
    const out = wirePort(nodes, edges, ['sub1'], 'input', null, 'innerY', 'data');
    const sub = out.nodes.find(n => n.id === 'sub1')!;
    const innerEdges = (sub.params.workflow as { edges: WorkflowEdge[] }).edges;
    expect(innerEdges.some(e => e.to.node === 'innerY' && e.to.input === 'data')).toBe(false);
    expect(getSubgraphPorts(sub, 'input_ports').some(p => p.innerNodeId === 'innerY' && p.innerSlot === 'data')).toBe(true);
  });

  it('creates output ports from the outputs panel + handle', () => {
    const { nodes, edges } = makeRoot();
    const out = wirePort(nodes, edges, ['sub1'], 'output', null, 'innerX', 'result', 'ANY');
    const sub = out.nodes.find(n => n.id === 'sub1')!;
    expect(getSubgraphPorts(sub, 'output_ports').map(p => p.name)).toContain('out__innerX__result');
  });

  it('unwirePort removes the port AND the parent edge referencing it', () => {
    const { nodes, edges } = makeRoot();
    const out = unwirePort(nodes, edges, ['sub1'], 'input', 'in__innerX__data');
    const sub = out.nodes.find(n => n.id === 'sub1')!;
    expect(getSubgraphPorts(sub, 'input_ports')).toEqual([]);
    expect(out.edges.some(e => e.id === 'e1')).toBe(false);
    // Unrelated edges stay.
    expect(out.edges.some(e => e.id === 'e2')).toBe(true);
  });

  it('nested write-back: editing two levels down lands in the root document', () => {
    const sub2 = subgraphNode(
      'sub2',
      { nodes: [innerNode('innerZ', { v: 1 })], edges: [] },
      [],
      [{ name: 'out__innerZ__result', type: 'ANY', innerNodeId: 'innerZ', innerSlot: 'result' }],
    );
    const sub1 = subgraphNode('sub1', { nodes: [sub2], edges: [] });
    const roots = { nodes: [sub1] as WorkflowNode[], edges: [] as WorkflowEdge[] };

    const path = ['sub1', 'sub2'];
    const view = deriveView(roots.nodes, roots.edges, path)!;
    const edited = view.nodes.map(n =>
      n.id === 'sub1.sub2.innerZ' ? { ...n, params: { v: 42 } } : n);
    const out = writeViewBack(roots.nodes, roots.edges, path, edited, view.edges);
    const l1 = (out.nodes[0].params.workflow as { nodes: WorkflowNode[] }).nodes[0];
    const l2 = (l1.params.workflow as { nodes: WorkflowNode[] }).nodes[0];
    expect(l2.id).toBe('innerZ');
    expect(l2.params.v).toBe(42);
  });
});

describe('panel handles', () => {
  it('exposes a stable + handle id for port creation', () => {
    expect(ADD_PORT_HANDLE).toBe('__add__');
  });
});
