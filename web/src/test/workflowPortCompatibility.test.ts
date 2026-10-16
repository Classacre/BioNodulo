import { describe, expect, it } from 'vitest';
import type { WorkflowEdge, WorkflowNode } from '../types';
import { normalizeWorkflowPortAliases } from '../utils/workflowPortCompatibility';

const node = (id: string, type: string): WorkflowNode => ({ id, type, position: [0, 0], params: {} });
const edge = (id: string, target: string, input: string): WorkflowEdge => ({
  id, from: { node: 'source', output: 'bam' }, to: { node: target, input },
});

describe('known saved-workflow input port compatibility', () => {
  it('canonicalizes only the exact samtools target aliases, preserving every edge and source', () => {
    const graph = { nodes: [node('source', 'samtools_view'), node('view', 'samtools_view'),
      node('sort', 'samtools_sort'), node('other', 'custom')],
    edges: [edge('view-old', 'view', 'sam'), edge('sort-old', 'sort', 'bam'),
      edge('canonical', 'sort', 'alignment'), edge('other', 'other', 'bam'),
      edge('unknown', 'view', 'bam'), edge('missing', 'absent', 'sam')] };
    const before = JSON.stringify(graph);
    const result = normalizeWorkflowPortAliases(graph);
    expect(result.edges.map(e => [e.id, e.to.input])).toEqual([
      ['view-old', 'alignment'], ['sort-old', 'alignment'], ['canonical', 'alignment'],
      ['other', 'bam'], ['unknown', 'bam'], ['missing', 'sam'],
    ]);
    expect(result.edges).toHaveLength(graph.edges.length);
    expect(result.edges[0].from).toBe(graph.edges[0].from);
    expect(result.edges[2]).toBe(graph.edges[2]);
    expect(JSON.stringify(graph)).toBe(before);
    expect(normalizeWorkflowPortAliases(result)).toBe(result);
  });

  it('normalizes nested edges and boundary target slots without renaming external ports or outputs', () => {
    const inner = { nodes: [node('source', 'input_file'), node('sort', 'samtools_sort')],
      edges: [edge('inner-edge', 'sort', 'bam')] };
    const child: WorkflowNode = { ...node('sub', 'subgraph'), params: {
      workflow: inner,
      input_ports: [{ name: 'public_bam', inner_node_id: 'sort', inner_slot: 'bam', type: 'BAM' }],
      output_ports: [{ name: 'public_result', innerNodeId: 'source', innerSlot: 'bam', type: 'BAM' }],
    } };
    const graph = { nodes: [node('source', 'input_file'), { ...node('outer', 'subgraph'),
      params: { workflow: { nodes: [child], edges: [] } } }], edges: [] };
    const before = JSON.stringify(graph);
    const result = normalizeWorkflowPortAliases(graph);
    const nested = (result.nodes[1].params.workflow as { nodes: WorkflowNode[] }).nodes[0];
    expect((nested.params.workflow as typeof inner).edges[0].to.input).toBe('alignment');
    expect(nested.params.input_ports).toEqual([
      { name: 'public_bam', inner_node_id: 'sort', inner_slot: 'alignment', type: 'BAM' },
    ]);
    expect(nested.params.output_ports).toBe(child.params.output_ports);
    expect(JSON.stringify(graph)).toBe(before);
  });

  it('retains all engine feedback and subgraph directory edges unchanged', () => {
    const graph = { nodes: [node('source', 'subgraph'), node('loop', 'while_loop'), node('each', 'foreach')],
      edges: [{ ...edge('dir', 'loop', 'value'), from: { node: 'source', output: 'subgraph_dir' } },
        edge('while', 'loop', '_body_result'), edge('foreach', 'each', 'body_result')] };
    expect(normalizeWorkflowPortAliases(graph)).toBe(graph);
  });

  it('does not guess an alias for an ambiguous duplicate target id', () => {
    const graph = { nodes: [node('source', 'input_file'), node('duplicate', 'samtools_sort'),
      node('duplicate', 'custom')], edges: [edge('ambiguous', 'duplicate', 'bam')] };
    expect(normalizeWorkflowPortAliases(graph)).toBe(graph);
  });
});
