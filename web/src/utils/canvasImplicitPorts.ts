import type { NodeMetadata, WorkflowNode } from '../types';

export interface CanvasImplicitPort {
  name: string;
  type: string;
  connected: boolean;
}

/** Engine-only ports already wired in saved graphs need handles, not body rows. */
export function connectedImplicitPorts(
  node: WorkflowNode,
  connectedInputs: ReadonlySet<string>,
  connectedOutputs: ReadonlySet<string>,
  meta?: NodeMetadata | null,
): { inputs: CanvasImplicitPort[]; outputs: CanvasImplicitPort[] } {
  const input = node.type === 'while_loop' ? '_body_result' : node.type === 'foreach' ? 'body_result' : null;
  return {
    inputs: input && connectedInputs.has(`${node.id}:${input}`)
      ? [{ name: input, type: meta?.input_types?.hidden?.[input]?.type || 'ANY', connected: true }] : [],
    outputs: node.type === 'subgraph' && connectedOutputs.has(`${node.id}:subgraph_dir`)
      ? [{ name: 'subgraph_dir', type: 'DIRECTORY', connected: true }] : [],
  };
}
