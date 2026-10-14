import { describe, expect, it } from 'vitest';
import { isCuratedTemplateInputArtifact } from '../localTemplates';

describe('curated template worker inputs', () => {
  it.each([
    'templates/data/smoke/coding_sequences.fasta',
    'templates/data/deseq2_gene_sets.json',
    'examples/data/deseq2/counts.csv',
    'examples/data/deseq2/sample_info.csv',
    'examples/data/metabolomics/sample.mzML',
    'examples/data/proteomics/target_decoy.fasta',
  ])('recognizes the exact shipped file %s', path => {
    expect(isCuratedTemplateInputArtifact({ path, kind: 'file' })).toBe(true);
    expect(isCuratedTemplateInputArtifact({ path, kind: 'directory' })).toBe(false);
  });

  it.each([
    'examples/data/spatial_transcriptomics/visium_outs',
    'examples/data/epigenomics/bismark_genome',
  ])('recognizes the exact shipped directory %s', path => {
    expect(isCuratedTemplateInputArtifact({ path, kind: 'directory' })).toBe(true);
    expect(isCuratedTemplateInputArtifact({ path, kind: 'file' })).toBe(false);
  });

  it.each([
    'templates/data/../../private.csv',
    'templates/data/not-curated.csv',
    'examples/data/deseq2/not-curated.csv',
    'examples/data/deseq2/../deseq2/counts.csv',
    'examples\\data\\deseq2\\counts.csv',
    '/examples/data/deseq2/counts.csv',
    'uploads/team-id/counts.csv',
  ])('does not trust a caller-controlled namespace or alias: %s', path => {
    expect(isCuratedTemplateInputArtifact({ path, kind: 'file' })).toBe(false);
  });
});
