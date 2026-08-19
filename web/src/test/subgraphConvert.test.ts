import { describe, expect, it } from 'vitest';
import type { WorkflowEdge, WorkflowNode } from '../types';
import { convertSelectionToSubgraph, unpackSubgraph } from '../utils/subgraph';

function node(id: string, x = 0, y = 0): WorkflowNode {
  return { id, type: 'python_code', position: [x, y], params: {} };
}

// source -> [a -> b] -> sink, with a second wire source2 -> b so the input
// boundary has two distinct outside sources.
function makeLevel() {
  const nodes = [node('source'), node('source2'), node('a', 100, 0), node('b', 300, 0), node('sink')];
  const edges: WorkflowEdge[] = [
    { id: 'e-sa', from: { node: 'source', output: 'out' }, to: { node: 'a', input: 'in' } },
    { id: 'e-s2b', from: { node: 'source2', output: 'out' }, to: { node: 'b', input: 'in' } },
    { id: 'e-ab', from: { node: 'a', output: 'result' }, to: { node: 'b', input: 'data' } },
    { id: 'e-bs', from: { node: 'b', output: 'result' }, to: { node: 'sink', input: 'in' } },
  ];
  return { nodes, edges };
}

describe('convertSelectionToSubgraph', () => {
  it('requires at least two selected nodes', () => {
    const { nodes, edges } = makeLevel();
    expect(convertSelectionToSubgraph(nodes, edges, ['a'], 'Sub')).toBeNull();
    expect(convertSelectionToSubgraph(nodes, edges, [], 'Sub')).toBeNull();
  });

  it('replaces the selection with a subgraph node at the selection centroid', () => {
    const { nodes, edges } = makeLevel();
    const result = convertSelectionToSubgraph(nodes, edges, ['a', 'b'], 'Sub')!;
    const sub = result.nodes.find(n => n.type === 'subgraph')!;
    expect(sub.position).toEqual([200, 0]);
    expect(result.nodes.map(n => n.id).sort()).toEqual(['sink', 'source', 'source2', sub.id].sort());
    expect(result.nodes.some(n => n.id === 'a')).toBe(false);
    expect(result.nodes.some(n => n.id === 'b')).toBe(false);
  });

  it('synthesizes one port per unique outside source -> inside slot pair, named in__N__S / out__N__S', () => {
    const { nodes, edges } = makeLevel();
    const result = convertSelectionToSubgraph(nodes, edges, ['a', 'b'], 'Sub')!;
    const sub = result.nodes.find(n => n.type === 'subgraph')!;
    const inputPorts = sub.params.input_ports as { name: string; innerNodeId: string; innerSlot: string }[];
    const outputPorts = sub.params.output_ports as { name: string; innerNodeId: string; innerSlot: string }[];

    expect(inputPorts.map(p => p.name).sort()).toEqual(['in__a__in', 'in__b__in']);
    expect(inputPorts.find(p => p.name === 'in__a__in')).toMatchObject({ innerNodeId: 'a', innerSlot: 'in' });
    expect(outputPorts.map(p => p.name)).toEqual(['out__b__result']);
    expect(outputPorts[0]).toMatchObject({ innerNodeId: 'b', innerSlot: 'result' });
  });

  it('moves internal edges into the embedded workflow and retargets boundary edges', () => {
    const { nodes, edges } = makeLevel();
    const result = convertSelectionToSubgraph(nodes, edges, ['a', 'b'], 'Sub')!;
    const sub = result.nodes.find(n => n.type === 'subgraph')!;
    const inner = sub.params.workflow as { nodes: WorkflowNode[]; edges: WorkflowEdge[] };

    expect(inner.nodes.map(n => n.id).sort()).toEqual(['a', 'b']);
    expect(inner.edges.map(e => e.id)).toEqual(['e-ab']);

    const sa = result.edges.find(e => e.id === 'e-sa')!;
    expect(sa.to).toEqual({ node: sub.id, input: 'in__a__in' });
    const bs = result.edges.find(e => e.id === 'e-bs')!;
    expect(bs.from).toEqual({ node: sub.id, output: 'out__b__result' });
    // Internal edge is gone from the parent level.
    expect(result.edges.some(e => e.id === 'e-ab')).toBe(false);
  });

  it('synthesizes node_info so the parent canvas renders the port handles', () => {
    const { nodes, edges } = makeLevel();
    const result = convertSelectionToSubgraph(nodes, edges, ['a', 'b'], 'Sub')!;
    const sub = result.nodes.find(n => n.type === 'subgraph')!;
    expect(sub.node_info?.return_names).toEqual(['out__b__result']);
    expect(Object.keys(sub.node_info?.input_types?.required ?? {}).sort()).toEqual(['in__a__in', 'in__b__in']);
  });
});

describe('unpackSubgraph', () => {
  it('is the inverse of convert: nodes, edges and boundary wiring are restored', () => {
    const { nodes, edges } = makeLevel();
    const converted = convertSelectionToSubgraph(nodes, edges, ['a', 'b'], 'Sub')!;
    const subId = converted.nodes.find(n => n.type === 'subgraph')!.id;
    const restored = unpackSubgraph(converted.nodes, converted.edges, subId)!;

    expect(restored.nodes.map(n => n.id).sort()).toEqual(['a', 'b', 'sink', 'source', 'source2']);
    const byId = new Map(restored.edges.map(e => [e.id, e]));
    expect(byId.get('e-sa')!.to).toEqual({ node: 'a', input: 'in' });
    expect(byId.get('e-s2b')!.to).toEqual({ node: 'b', input: 'in' });
    expect(byId.get('e-ab')).toBeDefined();
    expect(byId.get('e-bs')!.from).toEqual({ node: 'b', output: 'result' });
  });

  it('returns null for non-subgraph nodes or a missing embedded workflow', () => {
    const { nodes, edges } = makeLevel();
    expect(unpackSubgraph(nodes, edges, 'a')).toBeNull();
    const hollow: WorkflowNode = { id: 'hollow', type: 'subgraph', position: [0, 0], params: {} };
    expect(unpackSubgraph([hollow], [], 'hollow')).toBeNull();
  });

  it('drops parent edges that reference ports without a mapping', () => {
    const { nodes, edges } = makeLevel();
    const converted = convertSelectionToSubgraph(nodes, edges, ['a', 'b'], 'Sub')!;
    const sub = converted.nodes.find(n => n.type === 'subgraph')!;
    // Add a dangling edge into a port that does not exist.
    const withDangling = {
      nodes: converted.nodes,
      edges: [...converted.edges, { id: 'e-bad', from: { node: 'source', output: 'out' }, to: { node: sub.id, input: 'in__nope__nope' } }],
    };
    const restored = unpackSubgraph(withDangling.nodes, withDangling.edges, sub.id)!;
    expect(restored.edges.some(e => e.id === 'e-bad')).toBe(false);
  });
});
