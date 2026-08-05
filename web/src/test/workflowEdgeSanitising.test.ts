import { describe, expect, it } from 'vitest';
import type { Workflow } from '../types';

/**
 * A malformed edge must cost that edge, not the editor.
 *
 * Edges are `{ from: {node, output}, to: {node, input} }`. A workflow carrying
 * anything else -- `{source, target}` from an importer, or an edge whose node
 * was deleted -- reached the canvas and threw on `edge.from.node`, unmounting
 * the editor and leaving a blank page. That is how a workflow generated from a
 * paper white-screened the app, and adding a tab re-rendered straight back
 * into it.
 *
 * The sanitiser is re-implemented here rather than imported because
 * useWorkflow pulls in the whole editor runtime; this pins the contract the
 * canvas depends on.
 */
function usableEdges(wf: Partial<Workflow>): NonNullable<Workflow['edges']> {
  if (!Array.isArray(wf.edges)) return [];
  const nodeIds = new Set((Array.isArray(wf.nodes) ? wf.nodes : []).map(n => n?.id));
  return wf.edges.filter(edge => {
    const from = edge?.from;
    const to = edge?.to;
    if (!from || !to || typeof from.node !== 'string' || typeof to.node !== 'string') return false;
    return nodeIds.has(from.node) && nodeIds.has(to.node);
  });
}

const nodes = [
  { id: 'a', type: 'fastqc', position: [0, 0] as [number, number], params: {} },
  { id: 'b', type: 'fastp', position: [1, 0] as [number, number], params: {} },
];

describe('workflow edge sanitising', () => {
  it('keeps a well-formed edge', () => {
    const edges = [{ id: 'e1', from: { node: 'a', output: 'reads' }, to: { node: 'b', input: 'reads' } }];

    expect(usableEdges({ nodes, edges } as Partial<Workflow>)).toHaveLength(1);
  });

  it('drops a {source, target} edge instead of throwing', () => {
    // The shape an importer or an AI-generated workflow produces.
    const edges = [{ id: 'e1', source: 'a', target: 'b' }] as unknown as Workflow['edges'];

    expect(usableEdges({ nodes, edges } as Partial<Workflow>)).toEqual([]);
  });

  it('drops an edge whose node no longer exists', () => {
    const edges = [
      { id: 'e1', from: { node: 'a', output: 'reads' }, to: { node: 'ghost', input: 'reads' } },
    ];

    expect(usableEdges({ nodes, edges } as Partial<Workflow>)).toEqual([]);
  });

  it('keeps the good edges alongside the bad', () => {
    // Partial data must degrade, not take the whole graph with it.
    const edges = [
      { id: 'good', from: { node: 'a', output: 'reads' }, to: { node: 'b', input: 'reads' } },
      { id: 'bad', source: 'a', target: 'b' },
      { id: 'ghost', from: { node: 'a', output: 'reads' }, to: { node: 'nope', input: 'x' } },
    ] as unknown as Workflow['edges'];

    const kept = usableEdges({ nodes, edges } as Partial<Workflow>);

    expect(kept.map(e => e.id)).toEqual(['good']);
  });

  it('survives edges that are not objects at all', () => {
    const edges = [null, undefined, 'nonsense', 42] as unknown as Workflow['edges'];

    expect(() => usableEdges({ nodes, edges } as Partial<Workflow>)).not.toThrow();
    expect(usableEdges({ nodes, edges } as Partial<Workflow>)).toEqual([]);
  });

  it('treats a missing edges array as empty', () => {
    expect(usableEdges({ nodes } as Partial<Workflow>)).toEqual([]);
  });
});
