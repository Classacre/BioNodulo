import { existsSync, readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';

const workflowHooks = ['useAutoSave.ts', 'useQueueMode.ts', 'useWorkflowMessages.ts'];

describe('hooks organization', () => {
  it('keeps App-owned workflow hooks in the workflow hooks category', () => {
    const appSource = readFileSync(resolve(process.cwd(), 'src/App.tsx'), 'utf8');

    for (const hookFile of workflowHooks) {
      expect(existsSync(resolve(process.cwd(), 'src/hooks/workflow', hookFile)), hookFile).toBe(true);
      expect(existsSync(resolve(process.cwd(), 'src/hooks', hookFile)), hookFile).toBe(false);
    }
    expect(appSource).toContain("from './hooks/workflow'");
    expect(appSource).not.toContain("from './hooks/useAutoSave'");
    expect(appSource).not.toContain("from './hooks/useQueueMode'");
    expect(appSource).not.toContain("from './hooks/useWorkflowMessages'");
  });
});
