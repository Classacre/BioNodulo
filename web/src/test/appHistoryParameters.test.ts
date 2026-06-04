import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';

describe('App inline history workflow parameters', () => {
  it('tracks workflow parameters in snapshots, dedup signatures, and undo/redo restore', () => {
    const appSource = readFileSync(resolve(__dirname, '../App.tsx'), 'utf8');

    expect(appSource).toContain("parameters: Workflow['parameters']");
    expect(appSource).toContain('workflow.parameters ?? []');
    expect(appSource).toContain('parameters: wf.parameters');
    expect(appSource).toContain('activeWorkflow.parameters');
    expect(appSource.match(/parameters: state\.parameters/g)).toHaveLength(2);
  });
});
