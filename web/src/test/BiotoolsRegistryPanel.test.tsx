import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import BiotoolsRegistryPanel from '../components/panels/BiotoolsRegistryPanel';
import type { ObjectInfo } from '../types';
import '../i18n';

const objectInfo: ObjectInfo = { fastqc: { id: 'fastqc', display_name: 'FastQC', category: 'QC',
  description: 'Read QC', input_types: { required: {} }, return_types: [] } };

function tools() {
  return Array.from({ length: 42 }, (_, index) => ({ id: `tool${index}`, name: `Tool ${index}`,
    description: index === 41 ? 'CRISPR assay discovery' : 'Sequence analysis',
    types: ['Command-line tool'], topics: [], nodes: index === 0 ? ['fastqc'] : [] }));
}

function setup(records = tools(), reported = records.length, catalog = objectInfo) {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => ({
    records: reported, updated_at: '2026-09-19T00:00:00Z', tools: records,
  }) }));
  const onAddNode = vi.fn();
  const onBack = vi.fn();
  render(<BiotoolsRegistryPanel objectInfo={catalog} onAddNode={onAddNode} onBack={onBack} onClose={vi.fn()} />);
  return { onAddNode, onBack };
}

afterEach(() => vi.unstubAllGlobals());

describe('complete bio.tools discovery', () => {
  it('links a generated node by exact accession without a curated snapshot link', async () => {
    const generated = { ...objectInfo.fastqc, id: 'auto_unknown_123', display_name: 'Generated QC',
      declarative_runtime: { kind: 'cwl_reference_command_line_tool', biotools_accession: 'FASTQC', verification: 'unverified' } };
    const { onAddNode } = setup([{ id: 'fastqc', name: 'FastQC', description: 'Read QC', types: [], topics: [], nodes: [] }], 1,
      { auto_unknown_123: generated });
    fireEvent.click(await screen.findByRole('button', { name: 'Add Generated QC' }));
    expect(onAddNode).toHaveBeenCalledWith(generated);
    expect(screen.queryByText('Metadata only · no linked app node')).not.toBeInTheDocument();
  });

  it('searches beyond the first page and never offers metadata as an executable node', async () => {
    setup();
    await screen.findByText(/42 matches/);
    expect(screen.getAllByRole('article')).toHaveLength(40);
    expect(screen.queryByRole('link', { name: 'Tool 41' })).not.toBeInTheDocument();
    fireEvent.change(screen.getByRole('searchbox'), { target: { value: 'CRISPR' } });
    await screen.findByRole('link', { name: 'Tool 41' });
    expect(screen.getAllByRole('article')).toHaveLength(1);
    expect(screen.getByText('Metadata only · no linked app node')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /^Add / })).not.toBeInTheDocument();
  });

  it('paginates and adds only linked definitions already present in the app catalog', async () => {
    const { onAddNode, onBack } = setup();
    fireEvent.click(await screen.findByRole('button', { name: 'Add FastQC' }));
    expect(onAddNode).toHaveBeenCalledWith(objectInfo.fastqc);
    fireEvent.click(screen.getByRole('button', { name: 'Next' }));
    expect(screen.getAllByRole('article')).toHaveLength(2);
    fireEvent.click(screen.getByRole('button', { name: 'Back to nodes' }));
    expect(onBack).toHaveBeenCalledOnce();
  });

  it('rejects an incomplete snapshot instead of presenting partial coverage', async () => {
    setup(tools(), 500);
    await waitFor(() => expect(screen.getByRole('status')).toHaveTextContent('snapshot is unavailable'));
    expect(screen.queryByRole('article')).not.toBeInTheDocument();
  });

  it('ranks an exact registry identity ahead of descriptive matches', async () => {
    setup([
      { id: 'another', name: 'Related tool', description: 'Uses FastQC', types: [], topics: [], nodes: [] },
      { id: 'fastqc', name: 'FastQC', description: 'Read QC', types: [], topics: [], nodes: ['fastqc'] },
    ]);
    await screen.findByText(/2 matches/);
    fireEvent.change(screen.getByRole('searchbox'), { target: { value: 'fastqc' } });
    await waitFor(() => expect(screen.getAllByRole('article')[0]).toHaveTextContent('Add FastQC'));
  });
});
