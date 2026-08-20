import { describe, expect, it } from 'vitest';
import {
  AI_DRAWER_DEFAULT_WIDTH,
  AI_DRAWER_MIN_WIDTH,
  clampDrawerWidth,
  filterSkills,
  type SkillSummary,
} from '../utils/aiAssistant';

const SKILLS: SkillSummary[] = [
  { name: 'alphafold', description: 'Predict protein structures', source: 'bundled' },
  { name: 'rnaseq', description: 'RNA-seq quantification pipeline', source: 'bundled' },
  { name: 'rnaseq-batch', description: 'Batch RNA-seq runs', source: 'user' },
  { name: 'qc-report', description: 'Aggregate QC metrics', source: 'user' },
  { name: 'variants', description: 'Variant calling with RNA-seq support', source: 'workspace' },
];

describe('filterSkills', () => {
  it('returns the first skills (up to the limit) for an empty query', () => {
    const many = Array.from({ length: 12 }, (_, i) => ({ name: `skill-${i}`, description: '' }));
    expect(filterSkills('', many)).toHaveLength(8);
    expect(filterSkills('   ', SKILLS).map(s => s.name)).toEqual(SKILLS.map(s => s.name));
  });

  it('matches name prefixes case-insensitively', () => {
    expect(filterSkills('RNAS', SKILLS).map(s => s.name)).toEqual(['rnaseq', 'rnaseq-batch']);
  });

  it('matches description substrings case-insensitively', () => {
    expect(filterSkills('QUANT', SKILLS).map(s => s.name)).toEqual(['rnaseq']);
  });

  it('ranks name-prefix matches above description-only matches', () => {
    expect(filterSkills('rna', SKILLS).map(s => s.name)).toEqual(['rnaseq', 'rnaseq-batch', 'variants']);
  });

  it('returns an empty list when nothing matches', () => {
    expect(filterSkills('zzz', SKILLS)).toEqual([]);
  });

  it('tolerates missing descriptions', () => {
    expect(filterSkills('x', [{ name: 'xray' }] as SkillSummary[]).map(s => s.name)).toEqual(['xray']);
  });
});

describe('clampDrawerWidth', () => {
  it('keeps widths inside [320, 80vw]', () => {
    expect(clampDrawerWidth(200, 1000)).toBe(AI_DRAWER_MIN_WIDTH);
    expect(clampDrawerWidth(500, 1000)).toBe(500);
    expect(clampDrawerWidth(900, 1000)).toBe(800);
  });

  it('rounds fractional widths', () => {
    expect(clampDrawerWidth(412.6, 2000)).toBe(413);
  });

  it('falls back to the default width for non-finite input', () => {
    expect(clampDrawerWidth(Number.NaN, 1000)).toBe(AI_DRAWER_DEFAULT_WIDTH);
    expect(clampDrawerWidth(Number.POSITIVE_INFINITY, 1000)).toBe(AI_DRAWER_DEFAULT_WIDTH);
  });

  it('lets the minimum win on extremely narrow viewports', () => {
    expect(clampDrawerWidth(500, 300)).toBe(AI_DRAWER_MIN_WIDTH);
  });
});
