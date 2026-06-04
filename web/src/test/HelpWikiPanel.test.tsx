import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import HelpWikiPanel from '../components/panels/HelpWikiPanel';
import type { ObjectInfo } from '../types';

const objectInfo: ObjectInfo = {
  diann: {
    id: 'diann',
    display_name: 'DIA-NN',
    category: 'proteomics',
    description: 'Analyze DIA proteomics data with DIA-NN.',
    search_aliases: ['dia-nn', 'data independent acquisition'],
    input_types: {
      required: {
        raw_files: { type: 'FILE', tooltip: 'DIA raw files' },
        library: { type: 'FILE', description: 'Spectral library TSV' },
        fasta: { type: 'FASTA', tooltip: 'Protein FASTA database' },
      },
      optional: {
        threads: { type: 'INT', default: 4 },
      },
    },
    return_types: ['TSV', 'JSON'],
    return_names: ['report', 'stats'],
    requires_external_tools: ['diann'],
    documentation_url: 'https://github.com/vdemichev/DiaNN',
    version: '1.8',
  },
};

describe('HelpWikiPanel node documentation search', () => {
  it('finds node docs by aliases, tools, ports, and output metadata', () => {
    render(<HelpWikiPanel onClose={vi.fn()} objectInfo={objectInfo} />);

    fireEvent.change(screen.getByPlaceholderText('Search help...'), {
      target: { value: 'spectral library' },
    });

    expect(screen.getByText('Nodes')).toBeInTheDocument();
    expect(screen.getByText('DIA-NN')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /DIA-NN/i })).toHaveTextContent('Spectral library TSV');
  });

  it('opens full node documentation from a node search hit', () => {
    render(<HelpWikiPanel onClose={vi.fn()} objectInfo={objectInfo} />);

    fireEvent.change(screen.getByPlaceholderText('Search help...'), {
      target: { value: 'diann' },
    });
    fireEvent.click(screen.getByRole('button', { name: /DIA-NN/i }));

    expect(screen.getByRole('heading', { name: 'DIA-NN' })).toBeInTheDocument();
    expect(screen.getByText('Inputs')).toBeInTheDocument();
    expect(screen.getByText('Outputs')).toBeInTheDocument();
    expect(screen.getByText('raw_files')).toBeInTheDocument();
    expect(screen.getByText('report')).toBeInTheDocument();
    expect(screen.getByText(/Requires:/)).toBeInTheDocument();
  });
});
