import { describe, expect, it } from 'vitest';
import type { RunRecord } from '../types';
import { deriveLatestPreviews, parseDelimitedPreview, previewKindForPath } from '../utils/nodePreview';

describe('previewKindForPath', () => {
  it('detects images', () => {
    for (const path of ['a/b/plot.png', 'x.jpg', 'x.jpeg', 'x.gif', 'x.svg', 'x.webp', 'UPPER.PNG']) {
      expect(previewKindForPath(path)).toBe('image');
    }
  });

  it('detects tables', () => {
    expect(previewKindForPath('out/results.tsv')).toBe('table');
    expect(previewKindForPath('out/results.csv')).toBe('table');
    expect(previewKindForPath('out/results.tab')).toBe('table');
  });

  it('treats html/json/txt and extensionless paths as other (chip)', () => {
    expect(previewKindForPath('report.html')).toBe('other');
    expect(previewKindForPath('data.json')).toBe('other');
    expect(previewKindForPath('notes.txt')).toBe('other');
    expect(previewKindForPath('no_extension')).toBe('other');
  });
});

describe('parseDelimitedPreview', () => {
  it('parses tsv with a header and caps the rows', () => {
    const text = ['a\tb\tc', '1\t2\t3', '4\t5\t6', '7\t8\t9', '10\t11\t12', '13\t14\t15', '16\t17\t18'].join('\n');
    const table = parseDelimitedPreview(text, 5);
    expect(table.header).toEqual(['a', 'b', 'c']);
    expect(table.rows).toHaveLength(5);
    expect(table.totalRows).toBe(6);
    expect(table.truncated).toBe(true);
  });

  it('parses csv and reports untruncated totals', () => {
    const table = parseDelimitedPreview('x,y\n1,2\n3,4', 5);
    expect(table.header).toEqual(['x', 'y']);
    expect(table.rows).toEqual([['1', '2'], ['3', '4']]);
    expect(table.totalRows).toBe(2);
    expect(table.truncated).toBe(false);
  });

  it('handles empty input', () => {
    expect(parseDelimitedPreview('').header).toEqual([]);
    expect(parseDelimitedPreview('\n\n').rows).toEqual([]);
  });
});

function run(runId: string, previews: Record<string, string>, endTime?: string): RunRecord {
  return {
    run_id: runId,
    status: 'completed',
    workflow_name: '',
    node_statuses: [],
    node_outputs: {},
    execution_plan: [],
    previews,
    artifacts: {},
    end_time: endTime,
  };
}

describe('deriveLatestPreviews', () => {
  it('keeps only the latest run with a preview per node', () => {
    const runs = [
      run('old', { n1: 'old.png' }, '2026-01-01T00:00:00Z'),
      run('new', { n1: 'new.png', n2: 't.tsv' }, '2026-02-01T00:00:00Z'),
    ];
    const out = deriveLatestPreviews(runs);
    expect(out.n1).toMatchObject({ runId: 'new', path: 'new.png' });
    expect(out.n2).toMatchObject({ runId: 'new', path: 't.tsv' });
  });

  it('suppresses an older preview while a newer run of that node is active', () => {
    const runs = [
      run('running', {}, '2026-03-01T00:00:00Z'),
      run('done', { n1: 'a.png' }, '2026-01-01T00:00:00Z'),
    ];
    runs[0].status = 'running';
    runs[0].execution_plan = ['n1'];
    runs[0].node_statuses = [{ node_id: 'n1', status: 'running' }];
    expect(deriveLatestPreviews(runs).n1).toBeUndefined();
  });

  it('does not present a successful preview as output of a newer failed attempt', () => {
    const failed = run('failed', {}, '2026-03-01T00:00:00Z');
    failed.status = 'error';
    failed.execution_plan = ['input', 'validate'];
    failed.node_statuses = [
      { node_id: 'input', status: 'completed' },
      { node_id: 'validate', status: 'error', error: 'coordinate contradiction' },
    ];
    const out = deriveLatestPreviews([
      failed,
      run('successful', { validate: 'head_preview.html' }, '2026-02-01T00:00:00Z'),
    ]);
    expect(out.validate).toBeUndefined();
  });

  it('returns an empty map when nothing has previews', () => {
    expect(deriveLatestPreviews([run('x', {})])).toEqual({});
  });
});
