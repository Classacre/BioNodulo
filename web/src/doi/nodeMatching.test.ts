import { describe, expect, it } from 'vitest';
import type { NodeMetadata, ObjectInfo } from '../types';
import {
  matchToolToNodeType,
  parseConnection,
  slugify,
  wireSuggestion,
  type PlacedNode,
} from './nodeMatching';

function meta(partial: Partial<NodeMetadata> & { id: string }): NodeMetadata {
  return {
    display_name: partial.id,
    category: 'Other',
    search_aliases: [],
    input_types: {},
    return_types: [],
    return_names: [],
    ...partial,
  } as NodeMetadata;
}

const objectInfo: ObjectInfo = {
  fastqc: meta({
    id: 'fastqc',
    display_name: 'FastQC',
    search_aliases: ['fastqc', 'quality control'],
    input_types: { required: { reads: { type: 'FASTQ' } } },
    return_types: ['HTML'],
    return_names: ['report'],
  }),
  trim_galore: meta({
    id: 'trim_galore',
    display_name: 'Trim Galore',
    search_aliases: ['trimgalore', 'trim'],
    input_types: { required: { reads: { type: 'FASTQ' } } },
    return_types: ['FASTQ'],
    return_names: ['trimmed'],
  }),
  star_aligner: meta({
    id: 'star_aligner',
    display_name: 'STAR Aligner',
    search_aliases: ['star', 'aligner'],
    input_types: { required: { reads: { type: 'FASTQ' }, reference: { type: 'REFERENCE' } } },
    return_types: ['BAM'],
    return_names: ['bam'],
  }),
  note: meta({
    id: 'note',
    display_name: 'Notes',
    input_types: { required: { text: { type: 'STRING' } } },
  }),
};

describe('matchToolToNodeType', () => {
  it('matches an exact display name', () => {
    expect(matchToolToNodeType('FastQC', undefined, objectInfo).type).toBe('fastqc');
  });

  it('matches normalized spelling of a registered display name', () => {
    expect(matchToolToNodeType('TRIMGALORE', undefined, objectInfo).type).toBe('trim_galore');
  });

  it('matches a registry id', () => {
    expect(matchToolToNodeType('star_aligner', undefined, objectInfo).type).toBe('star_aligner');
  });

  it('matches the exact registered display name', () => {
    expect(matchToolToNodeType('STAR aligner', 'alignment', objectInfo).type).toBe('star_aligner');
  });

  it('matches the registered DESeq2 tool but leaves algorithmic steps as notes', () => {
    const info: ObjectInfo = {
      deseq2: meta({ id: 'deseq2', display_name: 'DESeq2', category: 'differential_expression' }),
      lofreq_filter: meta({
        id: 'lofreq_filter', display_name: 'LoFreq filter', category: 'variant_calling',
        description: 'Filter variants with multiple testing correction',
        search_aliases: ['multiple testing correction'],
      }),
      note: objectInfo.note,
    };
    expect(matchToolToNodeType('DESeq2', 'differential_expression', info).type).toBe('deseq2');
    expect(matchToolToNodeType('MultipleTestingCorrection', 'differential_expression', info).type).toBe('note');
    expect(matchToolToNodeType('SizeFactorEstimation', 'differential_expression', info).type).toBe('note');
  });

  it('does not convert an alias or a close spelling into an executable tool', () => {
    expect(matchToolToNodeType('quality control', 'qc', objectInfo).type).toBe('note');
    expect(matchToolToNodeType('FastQCC', 'qc', objectInfo).type).toBe('note');
  });

  it('uses an explicit registry ID and never falls back when that ID is unknown', () => {
    expect(matchToolToNodeType('Count matrix', 'input', objectInfo, 'fastqc').type).toBe('fastqc');
    expect(matchToolToNodeType('FastQC', 'qc', objectInfo, 'invented_node').type).toBe('note');
    expect(matchToolToNodeType('FastQC', 'qc', objectInfo, '__proto__').type).toBe('note');
    expect(matchToolToNodeType('FastQC', 'qc', objectInfo, null).type).toBe('note');
  });

  it('falls back to note for unknown tools', () => {
    const match = matchToolToNodeType('QuantumFluxinator 9000', undefined, objectInfo);
    expect(match.type).toBe('note');
    expect(match.fellBackToNote).toBe(true);
  });

  it('does not identify a tool from its category alone', () => {
    const info: ObjectInfo = {
      generic: meta({ id: 'generic', display_name: 'FastQC', category: 'alignment' }),
      note: objectInfo.note,
    };
    expect(matchToolToNodeType('Unreported aligner', 'alignment', info).type).toBe('note');
  });
});

describe('parseConnection', () => {
  it('parses ASCII and unicode arrows', () => {
    expect(parseConnection('FastQC -> Trim Galore')).toEqual(['FastQC', 'Trim Galore']);
    expect(parseConnection('A → B')).toEqual(['A', 'B']);
  });

  it('rejects malformed strings', () => {
    expect(parseConnection('no arrow here')).toBeNull();
    expect(parseConnection('A -> ')).toBeNull();
  });
});

describe('wireSuggestion', () => {
  const placed: PlacedNode[] = [
    { node: { id: 'trim-0', type: 'trim_galore', position: [0, 0], params: {} }, label: 'Trim Galore' },
    { node: { id: 'star-1', type: 'star_aligner', position: [0, 0], params: {} }, label: 'STAR Aligner' },
    { node: { id: 'qc-2', type: 'fastqc', position: [0, 0], params: {} }, label: 'FastQC' },
  ];

  it('wires a compatible output→input pair', () => {
    const edges = wireSuggestion(placed, ['Trim Galore -> STAR Aligner'], objectInfo);
    expect(edges).toEqual([
      { id: 'doi-e0', from: { node: 'trim-0', output: 'trimmed' }, to: { node: 'star-1', input: 'reads' } },
    ]);
  });

  it('skips incompatible pairs instead of emitting broken edges', () => {
    // FastQC only outputs HTML; STAR only accepts FASTQ/REFERENCE.
    expect(wireSuggestion(placed, ['FastQC -> STAR Aligner'], objectInfo)).toEqual([]);
  });

  it('does not connect two producers to the same input port', () => {
    const edges = wireSuggestion(placed, ['Trim Galore -> STAR Aligner', 'Trim Galore -> STAR Aligner'], objectInfo);
    expect(edges).toHaveLength(1);
  });

  it('rejects cycles even when every port type matches', () => {
    const chain: PlacedNode[] = ['A', 'B', 'C'].map((label, i) => ({
      node: { id: label, type: 'trim_galore', position: [i, 0], params: {} }, label,
    }));
    const edges = wireSuggestion(chain, ['A -> B', 'B -> C', 'C -> A'], objectInfo);
    expect(edges.map(edge => `${edge.from.node}->${edge.to.node}`)).toEqual(['A->B', 'B->C']);
  });

  it('keeps one producer per input even when producers differ', () => {
    const sources: PlacedNode[] = [
      { node: { id: 'A', type: 'trim_galore', position: [0, 0], params: {} }, label: 'A' },
      { node: { id: 'B', type: 'trim_galore', position: [1, 0], params: {} }, label: 'B' },
      { node: { id: 'C', type: 'trim_galore', position: [2, 0], params: {} }, label: 'C' },
    ];
    const edges = wireSuggestion(sources, ['A -> C', 'B -> C'], objectInfo);
    expect(edges).toHaveLength(1);
    expect(edges[0].from.node).toBe('A');
  });

  it('skips connections that name unknown nodes', () => {
    expect(wireSuggestion(placed, ['Trim Galore -> CellRanger'], objectInfo)).toEqual([]);
  });

  it('rejects malformed connection strings', () => {
    expect(wireSuggestion(placed, ['Trim Galore STAR Aligner'], objectInfo)).toEqual([]);
  });

  it('wires two file instances to distinct DESeq2 inputs only with explicit ports', () => {
    const info: ObjectInfo = {
      input_file: meta({ id: 'input_file', display_name: 'Input File', return_types: ['FILE'], return_names: ['file'] }),
      deseq2: meta({ id: 'deseq2', display_name: 'DESeq2', input_types: { required: {
        count_matrix: { type: 'FILE' }, sample_info: { type: 'FILE' },
      } } }),
    };
    const nodes: PlacedNode[] = [
      { node: { id: 'counts-0', type: 'input_file', position: [0, 0], params: {} }, label: 'Count matrix' },
      { node: { id: 'samples-1', type: 'input_file', position: [0, 0], params: {} }, label: 'Sample information' },
      { node: { id: 'deseq2-2', type: 'deseq2', position: [0, 0], params: {} }, label: 'DESeq2 analysis' },
    ];
    expect(wireSuggestion(nodes, ['Count matrix -> DESeq2 analysis'], info)).toEqual([]);
    const edges = wireSuggestion(nodes, [
      { from: 'Count matrix', to: 'DESeq2 analysis', output: 'file', input: 'count_matrix' },
      { from: 'Sample information', to: 'DESeq2 analysis', output: 'file', input: 'sample_info' },
    ], info);
    expect(edges).toEqual([
      { id: 'doi-e0', from: { node: 'counts-0', output: 'file' }, to: { node: 'deseq2-2', input: 'count_matrix' } },
      { id: 'doi-e1', from: { node: 'samples-1', output: 'file' }, to: { node: 'deseq2-2', input: 'sample_info' } },
    ]);
    expect(wireSuggestion(nodes, [
      { from: 'Count matrix', to: 'DESeq2 analysis', output: 'file', input: 'count_matrix' },
      { from: 'Sample information', to: 'DESeq2 analysis', output: 'file', input: 'count_matrix' },
    ], info)).toHaveLength(1);
  });

  it('rejects explicit ports with wrong names or incompatible types', () => {
    expect(wireSuggestion(placed, [
      { from: 'Trim Galore', to: 'STAR Aligner', output: 'wrong', input: 'reads' },
      { from: 'Trim Galore', to: 'STAR Aligner', output: 'trimmed', input: 'reference' },
    ], objectInfo)).toEqual([]);
  });
});

describe('slugify', () => {
  it('makes stable id fragments', () => {
    expect(slugify('STAR Aligner', 2)).toBe('star-aligner-2');
    expect(slugify('!!!', 0)).toBe('step-0');
  });
});
