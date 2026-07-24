import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';

describe('App template loading', () => {
  it('replaces the active workflow so stale parameters cannot survive a template load', () => {
    const appSource = readFileSync(resolve(__dirname, '../App.tsx'), 'utf8');
    const start = appSource.indexOf('const handleLoadTemplate = useCallback');
    const end = appSource.indexOf('const handleImport = useCallback', start);
    expect(start).toBeGreaterThanOrEqual(0);
    expect(end).toBeGreaterThan(start);

    const handler = appSource.slice(start, end);
    expect(handler).toContain('setWorkflow(activeIndex, () => sharedWorkflow);');
    expect(handler).not.toContain('updateWorkflow(activeIndex, sharedWorkflow);');
    expect(handler).toContain('setWorkflow, t]);');
  });
});
