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

  it('stages template artifacts before the shared-editor Run submission', () => {
    const appSource = readFileSync(resolve(__dirname, '../App.tsx'), 'utf8');
    const stagingStart = appSource.indexOf('const stageCloudRunInputs = useCallback');
    const runStart = appSource.indexOf('const handleRun = useCallback', stagingStart);
    const runEnd = appSource.indexOf('const handleBatchSheetSubmit = useCallback', runStart);

    expect(stagingStart).toBeGreaterThanOrEqual(0);
    expect(runStart).toBeGreaterThan(stagingStart);
    expect(runEnd).toBeGreaterThan(runStart);

    const staging = appSource.slice(stagingStart, runStart);
    const run = appSource.slice(runStart, runEnd);
    expect(staging).toContain('collectLocalInputArtifacts(');
    expect(staging).toContain('uploadWorkspaceFileToCloud(path, baseName(path))');
    expect(run).toContain('editorMode && !dryRunPreview');
    expect(run).toContain('await stageCloudRunInputs(activeWorkflow, parameterOverrides)');
    expect(run).toContain('inputs,');
  });
});
