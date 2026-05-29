import { describe, it, expect } from 'vitest';
import { renderHook } from '@testing-library/react';
import { useNodeSearch } from '../utils/nodeSearch';
import type { NodeMetadata, ObjectInfo } from '../types';

function meta(id: string, display_name: string, opts: {
  inputs?: Record<string, { type: string }>,
  category?: string,
} = {}): NodeMetadata {
  return {
    id,
    display_name,
    category: opts.category ?? 'Other',
    input_types: opts.inputs ? { required: opts.inputs as never } : undefined,
  } as NodeMetadata;
}

const info: ObjectInfo = {
  fastqc: meta('fastqc', 'FastQC', { inputs: { reads: { type: 'FASTQ' } } }),
  multiqc: meta('multiqc', 'MultiQC', { inputs: { reports: { type: 'FILE' } } }),
  bwa: meta('bwa', 'BWA align', { inputs: { reads: { type: 'FASTQ' }, ref: { type: 'FASTA' } } }),
  trimmomatic: meta('trimmomatic', 'Trimmomatic', { inputs: { reads: { type: 'FASTQ' } } }),
  note: meta('note', 'Notes', { inputs: { text: { type: 'STRING' } } }),
};

describe('useNodeSearch', () => {
  it('returns all nodes when the query is empty and no type filter is set', () => {
    const { result } = renderHook(() => useNodeSearch(info, ''));
    expect(result.current.length).toBe(Object.keys(info).length);
  });

  it('boosts compatible nodes to the top when the query is empty', () => {
    const { result } = renderHook(() => useNodeSearch(info, '', 'FASTQ'));
    const topIds = result.current.slice(0, 3).map((r) => r.meta.id);
    // All FASTQ-consumers should appear in the top 3 results.
    expect(topIds).toEqual(expect.arrayContaining(['fastqc', 'bwa', 'trimmomatic']));
  });

  it('still returns the queried node when the type does not match', () => {
    // "note" is the obvious string match for "note" but it doesn't accept FASTQ.
    const { result } = renderHook(() => useNodeSearch(info, 'note', 'FASTQ'));
    const ids = result.current.map((r) => r.meta.id);
    expect(ids).toContain('note');
  });

  it('ranks a typed match above a weak string match when both are present', () => {
    // "qc" is a substring of fastqc, multiqc — but only fastqc consumes FASTQ.
    const { result } = renderHook(() => useNodeSearch(info, 'qc', 'FASTQ'));
    const first = result.current[0]?.meta.id;
    expect(first).toBe('fastqc');
  });
});
