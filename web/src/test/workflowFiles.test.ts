import { describe, expect, it } from 'vitest';
import { collectLocalFilePaths, baseName } from '../utils/workflowFiles';
import type { Workflow } from '../types';

function wf(nodes: Workflow['nodes']): Workflow {
  return { version: '2.0', app: 'bionodulo', name: 't', description: '', nodes, edges: [], groups: [], outputs: {} };
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
});

describe('baseName', () => {
  it('handles / and \\ separators', () => {
    expect(baseName('a/b/c.txt')).toBe('c.txt');
    expect(baseName('a\\b\\c.txt')).toBe('c.txt');
    expect(baseName('x.txt')).toBe('x.txt');
  });
});
