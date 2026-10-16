import { describe, expect, it } from 'vitest';
import type { WorkflowNode } from '../types';
import { connectedImplicitPorts } from '../utils/canvasImplicitPorts';

const node = (id: string, type: string): WorkflowNode => ({ id, type, position: [0, 0], params: {} });

describe('connected engine-only canvas handles', () => {
  it('recognizes only the supported node/port combinations, including namespaced inner ids', () => {
    expect(connectedImplicitPorts(node('sub.loop', 'while_loop'), new Set(['sub.loop:_body_result']), new Set()).inputs)
      .toEqual([{ name: '_body_result', type: 'ANY', connected: true }]);
    expect(connectedImplicitPorts(node('each', 'foreach'), new Set(['each:body_result']), new Set()).inputs)
      .toEqual([{ name: 'body_result', type: 'ANY', connected: true }]);
    expect(connectedImplicitPorts(node('sub', 'subgraph'), new Set(), new Set(['sub:subgraph_dir'])).outputs)
      .toEqual([{ name: 'subgraph_dir', type: 'DIRECTORY', connected: true }]);
    expect(connectedImplicitPorts(node('other', 'custom'), new Set(['other:body_result']), new Set(['other:subgraph_dir'])))
      .toEqual({ inputs: [], outputs: [] });
  });

  it('does not create new implicit pins when no corresponding edge exists', () => {
    for (const type of ['while_loop', 'foreach', 'subgraph']) {
      expect(connectedImplicitPorts(node('node', type), new Set(), new Set())).toEqual({ inputs: [], outputs: [] });
    }
  });
});
