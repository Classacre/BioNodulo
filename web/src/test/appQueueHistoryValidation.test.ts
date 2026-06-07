import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';

describe('App queue and history API validation', () => {
  it('validates startup queue and history payloads before mapping run records', () => {
    const appSource = readFileSync(resolve(__dirname, '../App.tsx'), 'utf8');

    expect(appSource).toContain("import { safeValidateHostStatus, safeValidateRunsList } from './api/validators';");
    expect(appSource).toContain('const validatedQueue = queueData ? safeValidateRunsList(queueData) : null;');
    expect(appSource).toContain('const validatedHistory = historyData ? safeValidateRunsList(historyData) : null;');
    expect(appSource).toContain('const queueRuns = validatedQueue?.ok ? validatedQueue.value : [];');
    expect(appSource).toContain('const historyRuns = validatedHistory?.ok ? validatedHistory.value : [];');
  });
});
