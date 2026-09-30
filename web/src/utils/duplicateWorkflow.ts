import type { Workflow } from '../types';

/** Copy an editor tab while keeping graph-local IDs and their edge references aligned. */
export function duplicateWorkflow(wf: Workflow, id: string, name: string): Workflow {
  return {
    ...wf,
    id,
    name,
    cloudPending: false,
    cloudRequestId: undefined,
    nodes: wf.nodes.map(node => ({ ...node })),
    edges: wf.edges.map(edge => ({ ...edge, from: { ...edge.from }, to: { ...edge.to } })),
    groups: wf.groups?.map(group => ({ ...group })),
  };
}
