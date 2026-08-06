import { describe, expect, it } from 'vitest';

import { connectionTypeWarning } from '../components/canvas/WorkflowCanvas';

/**
 * Connections used to be refused silently: React Flow greyed the port out and
 * said nothing, so a user reasonably concluded the editor was broken —
 * "don't know why i can't connect fastqc to multiqc".
 *
 * Types are now advisory. The link is made, and a mismatch is explained so the
 * user can judge it; the tool gives the authoritative answer when it runs.
 */
describe('connection type warning', () => {
  const labels = { source: 'report_dir', target: 'reports' };

  it('says nothing when the types agree', () => {
    expect(connectionTypeWarning('BAM', 'BAM', labels)).toBeNull();
  });

  it('says nothing when the input accepts a union containing the output', () => {
    // This is the fastqc -> multiqc case, once MultiQC declares that it takes
    // report directories as well as file lists.
    expect(
      connectionTypeWarning('QC_REPORT_DIR', 'FILE_LIST|QC_REPORT_DIR|DIRECTORY', labels)
    ).toBeNull();
  });

  it('says nothing when either side is untyped', () => {
    // An unknown type is not evidence of a problem, and guessing would train
    // users to ignore the warning.
    expect(connectionTypeWarning('', 'BAM', labels)).toBeNull();
    expect(connectionTypeWarning('BAM', '', labels)).toBeNull();
  });

  it('says nothing for a generic port', () => {
    expect(connectionTypeWarning('ANY', 'BAM', labels)).toBeNull();
    expect(connectionTypeWarning('BAM', '*', labels)).toBeNull();
  });

  it('allows a link within a type family', () => {
    expect(connectionTypeWarning('FASTQ_PAIRED', 'FASTQ', labels)).toBeNull();
  });

  it('names both types when they genuinely disagree', () => {
    // The bwa-mem2 index -> freebayes reference case: a real mismatch, where
    // the user needs to be told what was expected rather than just blocked.
    const warning = connectionTypeWarning('BWA_MEM2_INDEX', 'FASTA', {
      source: 'index',
      target: 'reference',
    });

    expect(warning).toContain('BWA_MEM2_INDEX');
    expect(warning).toContain('FASTA');
    expect(warning).toContain('index');
    expect(warning).toContain('reference');
  });

  it('tells the user the link was still made', () => {
    const warning = connectionTypeWarning('FASTQ', 'VCF', labels);

    expect(warning).toMatch(/anyway/i);
  });
});
