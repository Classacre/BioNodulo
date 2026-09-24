import { act, renderHook, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { useRegistryNodeHydration } from '../hooks/data/useRegistryNodeHydration';
import { collectRegistryNodeIds, isGeneratedRegistryNodeId } from '../utils/registryNodes';
import type { NodeMetadata, Workflow } from '../types';

const nodeId = `biotools_${'a'.repeat(32)}`;
const secondId = `biotools_${'b'.repeat(32)}`;
const metadata: NodeMetadata = { id: nodeId, display_name: 'Reference', category: 'bio.tools',
  registry_origin: { accession: 'reference', execution_status: 'definition_only', blockers: ['No binding'] } };

function importedWorkflow(): Workflow {
  return {
    id: 'imported', name: 'Imported references', version: '2.0', app: 'bionodulo', edges: [],
    nodes: [{ id: 'outer', type: 'subgraph', position: [0, 0], params: { workflow: {
      nodes: { first: { id: 'first', type: nodeId, position: [0, 0], params: {} },
        second: { id: 'second', type: secondId, position: [100, 0], params: {} } }, edges: [],
    } } }],
  } as Workflow;
}

describe('generated registry metadata restoration', () => {
  it('discovers nested keyed subgraph nodes without embedded node_info', () => {
    expect(collectRegistryNodeIds([importedWorkflow()])).toEqual([nodeId, secondId]);
    expect(isGeneratedRegistryNodeId(nodeId)).toBe(true);
    expect(isGeneratedRegistryNodeId('biotools_not_a_digest')).toBe(false);
  });

  it('restores nested references and recovers from a transient metadata failure', async () => {
    const registerNode = vi.fn(async (id: string) => {
      if (id === nodeId && registerNode.mock.calls.filter(([called]) => called === nodeId).length === 1) {
        throw new Error('temporary outage');
      }
      return { ...metadata, id };
    });
    const { result } = renderHook(() => useRegistryNodeHydration([importedWorkflow()], {}, registerNode, 5));
    await waitFor(() => expect(registerNode).toHaveBeenCalledTimes(3));
    await waitFor(() => expect(result.current.failures).toEqual({}));
    expect(registerNode.mock.calls.map(([id]) => id).sort()).toEqual([nodeId, nodeId, secondId].sort());
  });

  it('stops after bounded failures and exposes a manual retry', async () => {
    const registerNode = vi.fn().mockRejectedValue(new Error('metadata unavailable'));
    const { result } = renderHook(() => useRegistryNodeHydration([{
      ...importedWorkflow(), nodes: [{ id: 'ref', type: nodeId, position: [0, 0], params: {} }],
    }], {}, registerNode, 5));
    await waitFor(() => expect(registerNode).toHaveBeenCalledTimes(3));
    await waitFor(() => expect(result.current.failures[nodeId]).toBe('metadata unavailable'));
    await new Promise(resolve => setTimeout(resolve, 30));
    expect(registerNode).toHaveBeenCalledTimes(3);
    registerNode.mockResolvedValueOnce(metadata);
    act(() => result.current.retry());
    await waitFor(() => expect(registerNode).toHaveBeenCalledTimes(4));
    await waitFor(() => expect(result.current.failures).toEqual({}));
  });

  it('retries an exhausted definition when it is removed and later re-added', async () => {
    const workflow = { ...importedWorkflow(), nodes: [{ id: 'ref', type: nodeId, position: [0, 0], params: {} }] } as Workflow;
    const registerNode = vi.fn().mockRejectedValue(new Error('metadata unavailable'));
    const { result, rerender } = renderHook(
      ({ workflows }) => useRegistryNodeHydration(workflows, {}, registerNode, 5),
      { initialProps: { workflows: [workflow] as Workflow[] } },
    );
    await waitFor(() => expect(registerNode).toHaveBeenCalledTimes(3));
    await waitFor(() => expect(result.current.failures[nodeId]).toBe('metadata unavailable'));

    rerender({ workflows: [] });
    await waitFor(() => expect(result.current.failures).toEqual({}));
    registerNode.mockResolvedValueOnce(metadata);
    rerender({ workflows: [workflow] });
    await waitFor(() => expect(registerNode).toHaveBeenCalledTimes(4));
    await waitFor(() => expect(result.current.failures).toEqual({}));
  });
});
