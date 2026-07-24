import { describe, expect, it } from 'vitest';
import { collectLocalFilePaths, collectLocalInputArtifacts, baseName } from '../utils/workflowFiles';
import type { NodeMetadata, ObjectInfo, Workflow } from '../types';

function wf(nodes: Workflow['nodes']): Workflow {
  return { version: '2.0', app: 'bionodulo', name: 't', description: '', nodes, edges: [], groups: [], outputs: {} };
}

function meta(
  id: string,
  category: string,
  required: Record<string, { type: string }>,
): NodeMetadata {
  return {
    id,
    display_name: id,
    category,
    input_types: { required },
  };
}

describe('collectLocalFilePaths', () => {
  it('collects input_file paths and dedupes', () => {
    const w = wf([
      { id: 'a', type: 'input_file', position: [0, 0], params: { path: 'data/reads.fastq' } },
      { id: 'b', type: 'input_file', position: [0, 0], params: { path: 'data/reads.fastq' } },
      { id: 'c', type: 'input_file', position: [0, 0], params: { file: 'genome/ref.fa' } },
    ]);
    expect(collectLocalFilePaths(w).sort()).toEqual(['data/reads.fastq', 'genome/ref.fa']);
  });

  it('ignores urls, cloud keys, empty and non-path params', () => {
    const w = wf([
      { id: 'a', type: 'input_file', position: [0, 0], params: { path: 'https://example.com/x.fq' } },
      { id: 'b', type: 'input_file', position: [0, 0], params: { path: 'uploads/team/abc__x.fq' } },
      { id: 'c', type: 'input_file', position: [0, 0], params: { path: '' } },
      { id: 'd', type: 'foo', position: [0, 0], params: { threads: 4, name: 'plain' } },
    ]);
    expect(collectLocalFilePaths(w)).toEqual([]);
  });

  it('collects typed runtime file parameters, including lists', () => {
    const w = {
      ...wf([]),
      parameters: [
        { name: 'alignment', type: 'SAM', required: true },
        { name: 'reads', type: 'FASTQ_LIST', required: true },
        { name: 'sample_id', type: 'STRING', required: true },
      ],
    };

    expect(collectLocalFilePaths(w, {
      alignment: '/workspace/tiny.sam',
      reads: ['data/R1.fastq.gz', 'data/R2.fastq.gz'],
      sample_id: 'cohort/sample.1',
    }).sort()).toEqual([
      '/workspace/tiny.sam',
      'data/R1.fastq.gz',
      'data/R2.fastq.gz',
    ]);
  });

  it('uses node input metadata for canonical files and ignores output destinations', () => {
    const objectInfo: ObjectInfo = {
      input_fasta: meta('input_fasta', 'input', { reference: { type: 'FASTA' } }),
      input_fastq: meta('input_fastq', 'input', { reads: { type: 'FASTQ_LIST' } }),
      input_gff: meta('input_gff', 'input', { annotation: { type: 'GFF_GTF' } }),
      input_sample_sheet: meta('input_sample_sheet', 'input', { sample_sheet: { type: 'STRING' } }),
      write_file: meta('write_file', 'utils', {
        content: { type: 'STRING' },
        file_path: { type: 'STRING' },
      }),
    };
    const w = wf([
      {
        id: 'ref', type: 'input_fasta', position: [0, 0],
        params: { reference: 'data/reference.fa' },
        node_info: objectInfo.input_fasta,
      },
      {
        id: 'reads', type: 'input_fastq', position: [0, 0],
        params: { reads: ['data/R1.fastq.gz', 'data/R2.fastq.gz'] },
      },
      {
        id: 'annotation', type: 'input_gff', position: [0, 0],
        params: { annotation: 'data/genes.gff3' },
      },
      {
        id: 'sheet', type: 'input_sample_sheet', position: [0, 0],
        params: { sample_sheet: 'data/samples.csv' },
      },
      {
        id: 'writer', type: 'write_file', position: [0, 0],
        params: { content: 'result', file_path: 'results/future.txt' },
      },
    ]);

    expect(collectLocalFilePaths(w, {}, objectInfo).sort()).toEqual([
      'data/R1.fastq.gz',
      'data/R2.fastq.gz',
      'data/genes.gff3',
      'data/reference.fa',
      'data/samples.csv',
    ]);
  });

  it('collects typed directory inputs for cloud archive staging', () => {
    const objectInfo: ObjectInfo = {
      input_directory: meta('input_directory', 'input', { directory: { type: 'DIRECTORY' } }),
    };
    const w = wf([{
      id: 'directory',
      type: 'input_directory',
      position: [0, 0],
      params: { directory: 'data/reference-index' },
    }]);

    expect(collectLocalInputArtifacts(w, {}, objectInfo)).toEqual([
      { path: 'data/reference-index', kind: 'directory' },
    ]);
  });

  it('does not stage workflow placeholders or hidden file/control slots', () => {
    const placeholderMeta = meta('caller', 'variant', { reference: { type: 'FASTA' } });
    const hiddenMeta = meta('hidden-control', 'utils', {});
    hiddenMeta.input_types = {
      ...hiddenMeta.input_types,
      hidden: { output: { type: 'FILE' } },
    };
    const w = wf([
      {
        id: 'caller', type: 'caller', position: [0, 0],
        params: { reference: '{{ tiny_sam }}' }, node_info: placeholderMeta,
      },
      {
        id: 'control', type: 'hidden-control', position: [0, 0],
        params: { output: 'results/internal.txt' }, node_info: hiddenMeta,
      },
    ]);

    expect(collectLocalFilePaths(w)).toEqual([]);
  });
});

describe('baseName', () => {
  it('handles / and \\ separators', () => {
    expect(baseName('a/b/c.txt')).toBe('c.txt');
    expect(baseName('a\\b\\c.txt')).toBe('c.txt');
    expect(baseName('x.txt')).toBe('x.txt');
  });
});
