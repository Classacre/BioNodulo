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

  it('matches a search alias case-insensitively', () => {
    expect(matchToolToNodeType('TRIMGALORE', undefined, objectInfo).type).toBe('trim_galore');
  });

  it('matches a registry id', () => {
    expect(matchToolToNodeType('star_aligner', undefined, objectInfo).type).toBe('star_aligner');
  });

  it('fuzzy-matches a close name', () => {
    expect(matchToolToNodeType('STAR aligner', 'alignment', objectInfo).type).toBe('star_aligner');
  });

  it('falls back to note for unknown tools', () => {
    const match = matchToolToNodeType('QuantumFluxinator 9000', undefined, objectInfo);
    expect(match.type).toBe('note');
    expect(match.fellBackToNote).toBe(true);
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

  it('skips connections that name unknown nodes', () => {
    expect(wireSuggestion(placed, ['Trim Galore -> CellRanger'], objectInfo)).toEqual([]);
  });

  it('rejects malformed connection strings', () => {
    expect(wireSuggestion(placed, ['Trim Galore STAR Aligner'], objectInfo)).toEqual([]);
  });
});

describe('slugify', () => {
  it('makes stable id fragments', () => {
    expect(slugify('STAR Aligner', 2)).toBe('star-aligner-2');
    expect(slugify('!!!', 0)).toBe('step-0');
  });
});
