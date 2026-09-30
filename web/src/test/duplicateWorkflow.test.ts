import { describe, expect, it } from 'vitest';
import type { Workflow } from '../types';
import { duplicateWorkflow } from '../utils/duplicateWorkflow';

describe('duplicateWorkflow', () => {
  it('keeps copied edges connected while giving the cloud copy its own row identity', () => {
    const source: Workflow = {
      id: 'server-original', version: '2.0', app: 'bionodulo',
      name: 'Original', description: '', outputs: {}, groups: [],
      cloudRequestId: 'old-request', cloudPending: true,
      nodes: [
        { id: 'input', type: 'input', position: [0, 0], params: {} },
        { id: 'output', type: 'output', position: [100, 0], params: {} },
      ],
      edges: [{ id: 'edge', from: { node: 'input', output: 'data' }, to: { node: 'output', input: 'data' } }],
    };
    const copy = duplicateWorkflow(source, 'local-copy', 'Original copy');
    expect(copy).toMatchObject({ id: 'local-copy', name: 'Original copy', cloudPending: false });
    expect(copy.cloudRequestId).toBeUndefined();
    expect(copy.edges[0].from.node).toBe(copy.nodes[0].id);
    expect(copy.edges[0].to.node).toBe(copy.nodes[1].id);
    copy.edges[0].from.node = 'changed';
    expect(source.edges[0].from.node).toBe('input');
  });
});
