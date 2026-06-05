import { describe, expect, it } from 'vitest';
import { docToWorkflow, workflowToDoc } from '../collab/yjsDoc';
import type { Workflow } from '../types';

describe('collaboration workflow document serialization', () => {
  it('preserves workflow parameters across Yjs round trips', () => {
    const workflow: Workflow = {
      id: 'wf-params',
      version: '2.0',
      app: 'bionodulo',
      name: 'Parameterized collaboration',
      description: '',
      nodes: [],
      edges: [],
      groups: [],
      outputs: {},
      parameters: [
        {
          name: 'sample_id',
          type: 'STRING',
          required: true,
          default: 'S1',
          description: 'Sample identifier',
        },
      ],
    };

    const doc = workflowToDoc(workflow);
    const roundTripped = docToWorkflow(doc);

    expect(roundTripped.parameters).toEqual(workflow.parameters);
  });
});
