import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import BiotoolsRegistryPanel from '../components/panels/BiotoolsRegistryPanel';
import type { ObjectInfo } from '../types';
import '../i18n';

const objectInfo: ObjectInfo = { fastqc: { id: 'fastqc', display_name: 'FastQC', category: 'QC',
  description: 'Read QC', input_types: { required: {} }, return_types: [] } };

function entries() {
  return Array.from({ length: 42 }, (_, index) => ({
    node_id: `biotools_${index}`, accession: `tool${index}`, name: `Tool ${index}`,
    description: index === 41 ? 'CRISPR assay discovery' : 'Sequence analysis',
    tool_types: ['Command-line tool'], topics: [], operations: [],
    execution_status: 'definition_only', blockers: ['No verified execution binding'],
    reference_url: `https://bio.tools/tool${index}`,
    linked_node_ids: index === 0 ? ['fastqc'] : [], runnable_node_ids: [],
  }));
}

function setup(records = entries(), catalog = objectInfo) {
  const requests: URL[] = [];
  const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
    const url = new URL(String(input), 'http://localhost');
    requests.push(url);
    const query = (url.searchParams.get('q') ?? '').toLowerCase();
    const offset = Number(url.searchParams.get('offset') ?? 0);
    const limit = Number(url.searchParams.get('limit') ?? 40);
    const matching = records.filter(record =>
      `${record.accession} ${record.name} ${record.description}`.toLowerCase().includes(query));
    return { ok: true, json: async () => ({
      schema_version: 1, total: records.length, matched_count: matching.length, offset, limit,
      snapshot: { records: records.length, sha256: 'test-digest', updated_at: '2026-09-24T00:00:00Z' },
      entries: matching.slice(offset, offset + limit),
    }) };
  });
  vi.stubGlobal('fetch', fetchMock);
  const onAddNode = vi.fn();
  const onAddGeneratedNode = vi.fn(async () => {});
  const onBack = vi.fn();
  render(<BiotoolsRegistryPanel objectInfo={catalog} onAddNode={onAddNode}
    onAddGeneratedNode={onAddGeneratedNode} onBack={onBack} onClose={vi.fn()} />);
  return { onAddNode, onAddGeneratedNode, onBack, requests, fetchMock };
}

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

describe('bio.tools generated toolbox definitions', () => {
  it('adds every registry record through its stable generated node ID without claiming execution', async () => {
    const { onAddNode, onAddGeneratedNode } = setup();
    await screen.findByText(/42 matches/);
    expect(screen.getAllByRole('article')).toHaveLength(40);
    expect(screen.getAllByText('Execution unavailable for this generated definition')).toHaveLength(40);
    fireEvent.click(screen.getAllByRole('button', { name: 'Add reference node' })[1]);
    await waitFor(() => expect(onAddGeneratedNode).toHaveBeenCalledWith('biotools_1'));
    expect(onAddNode).not.toHaveBeenCalled();
  });

  it('offers exact linked app nodes separately from reference definitions', async () => {
    const { onAddNode, onAddGeneratedNode } = setup();
    fireEvent.click(await screen.findByRole('button', { name: 'Add FastQC' }));
    expect(onAddNode).toHaveBeenCalledWith(objectInfo.fastqc);
    expect(onAddGeneratedNode).not.toHaveBeenCalled();
    expect(screen.getAllByRole('button', { name: 'Add reference node' })).toHaveLength(40);
  });

  it('searches the full catalog on the server and paginates without loading all metadata', async () => {
    const { requests, onBack } = setup();
    await screen.findByText(/42 matches/);
    fireEvent.click(screen.getByRole('button', { name: 'Next' }));
    await waitFor(() => expect(screen.getAllByRole('article')).toHaveLength(2));
    expect(requests.at(-1)?.searchParams.get('offset')).toBe('40');
    fireEvent.change(screen.getByRole('searchbox'), { target: { value: 'CRISPR' } });
    await screen.findByRole('link', { name: 'Tool 41' });
    expect(screen.getAllByRole('article')).toHaveLength(1);
    expect(requests.at(-1)?.searchParams.get('q')).toBe('CRISPR');
    expect(requests.at(-1)?.searchParams.get('offset')).toBe('0');
    fireEvent.click(screen.getByRole('button', { name: 'Back to nodes' }));
    expect(onBack).toHaveBeenCalledOnce();
  });

  it('reports API and add failures while keeping the reference action available', async () => {
    const { fetchMock, onAddGeneratedNode } = setup();
    await screen.findByText(/42 matches/);
    onAddGeneratedNode.mockRejectedValueOnce(new Error('metadata unavailable'));
    fireEvent.click(screen.getAllByRole('button', { name: 'Add reference node' })[0]);
    await screen.findByRole('alert');
    expect(screen.getByRole('alert')).toHaveTextContent('metadata unavailable');
    fetchMock.mockRejectedValueOnce(new Error('registry offline'));
    fireEvent.click(screen.getByRole('button', { name: 'Next' }));
    await waitFor(() => expect(screen.getByRole('status')).toHaveTextContent('Registry nodes are unavailable'));
    expect(screen.queryByRole('article')).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Retry' }));
    await waitFor(() => expect(screen.getAllByRole('article')).toHaveLength(2));
  });
});
