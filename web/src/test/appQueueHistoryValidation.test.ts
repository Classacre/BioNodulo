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

  it('logs user-triggered queue and history action failures with stable scopes', () => {
    const appSource = readFileSync(resolve(__dirname, '../App.tsx'), 'utf8');

    const expectedScopes = [
      'app.queue.cancel',
      'app.run.loadWorkflow',
      'app.run.retry',
      'app.queue.reorder',
      'app.queue.clear',
      'app.history.clear',
      'app.history.delete',
      'app.template.save',
    ];

    for (const scope of expectedScopes) {
      expect(appSource).toContain(`logError('${scope}', err);`);
    }
  });

  it('cancels cloud runs through the website while preserving local queue cancellation', () => {
    const appSource = readFileSync(resolve(__dirname, '../App.tsx'), 'utf8');

    expect(appSource).toContain(
      "import { cancelCloudRun, getCloudRun, getCloudCredits, type CloudRunInputs } from './api/website';",
    );
    expect(appSource).toContain('if (run.options?.cloud === true)');
    expect(appSource).toContain('await cancelCloudRun(run.run_id);');
    expect(appSource).toContain(
      'await apiPost(`/api/queue/${encodeURIComponent(run.run_id)}/cancel`);',
    );
  });
});
