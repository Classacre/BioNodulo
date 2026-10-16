import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it, vi } from 'vitest';
import ts from 'typescript';

function appCallback(name: string, bindings: Record<string, unknown>): (run: unknown) => Promise<void> {
  const source = readFileSync(resolve(__dirname, '../App.tsx'), 'utf8');
  const app = ts.createSourceFile('App.tsx', source, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
  let callback: ts.Expression | undefined;
  function visit(node: ts.Node) {
    if (ts.isVariableDeclaration(node) && ts.isIdentifier(node.name) && node.name.text === name
      && node.initializer && ts.isCallExpression(node.initializer)) callback = node.initializer.arguments[0];
    ts.forEachChild(node, visit);
  }
  visit(app);
  if (!callback) throw new Error(`Missing production callback ${name}`);
  const script = ts.transpileModule(`const callback = ${callback.getText(app)};`, {
    compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.None },
  }).outputText;
  return new Function(...Object.keys(bindings), `${script}\nreturn callback;`)(...Object.values(bindings));
}

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

    const websiteImports = appSource.match(/import\s+\{([^}]+)\}\s+from\s+['"]\.\/api\/website['"]/)?.[1]
      .split(',').map(value => value.trim().replace(/^type\s+/, ''));
    expect(websiteImports).toEqual(expect.arrayContaining([
      'cancelCloudRun', 'getCloudRun', 'getCloudCredits', 'CloudRunInputs',
    ]));
    expect(appSource).toContain('if (run.options?.cloud === true)');
    expect(appSource).toContain('await cancelCloudRun(run.run_id);');
    expect(appSource).toContain(
      'await apiPost(`/api/queue/${encodeURIComponent(run.run_id)}/cancel`);',
    );
  });

  it.each(['handleLoadRunWorkflow', 'handleRetryRun'])('%s does not claim success or adopt a run after a failed/stale opener', async name => {
    const openCloudWorkflow = vi.fn().mockResolvedValue(false);
    const pollCloudRun = vi.fn();
    const toast = { success: vi.fn(), info: vi.fn(), error: vi.fn() };
    const logError = vi.fn();
    const apiPost = vi.fn();
    const callback = appCallback(name, { openCloudWorkflow, pollCloudRun, toast, logError, apiPost,
      consoleActionCopy: { error: { noRunWorkflowSnapshot: 'No workflow', couldNotLoadWorkflow: 'Could not load', couldNotRetryRun: 'Could not retry' } },
      t: (key: string) => key,
    });
    await callback({ run_id: 'run', workflow_id: 'saved', workflow_name: 'Synthetic draft', options: { cloud: true } });
    expect(openCloudWorkflow).toHaveBeenCalledExactlyOnceWith('saved');
    expect(pollCloudRun).not.toHaveBeenCalled();
    expect(toast.success).not.toHaveBeenCalled();
    expect(toast.info).not.toHaveBeenCalled();
    expect(toast.error).toHaveBeenCalledOnce();
    expect(logError).toHaveBeenCalledOnce();
    expect(apiPost).not.toHaveBeenCalled();
  });

  it.each(['handleLoadRunWorkflow', 'handleRetryRun'])('%s preserves read-only monitoring and feedback after an actual open', async name => {
    const openCloudWorkflow = vi.fn().mockResolvedValue(true);
    const pollCloudRun = vi.fn();
    const toast = { success: vi.fn(), info: vi.fn(), error: vi.fn() };
    const logError = vi.fn();
    const apiPost = vi.fn();
    const callback = appCallback(name, { openCloudWorkflow, pollCloudRun, toast, logError, apiPost,
      consoleActionCopy: { error: {}, toast: { workflowLoadedFromRun: 'Loaded' } },
      t: (key: string) => key,
    });
    await callback({ run_id: 'run', workflow_id: 'saved', workflow_name: 'Synthetic draft', options: { cloud: true } });
    expect(openCloudWorkflow).toHaveBeenCalledExactlyOnceWith('saved');
    expect(pollCloudRun).toHaveBeenCalledOnce();
    expect(name === 'handleLoadRunWorkflow' ? toast.success : toast.info).toHaveBeenCalledOnce();
    expect(toast.error).not.toHaveBeenCalled();
    expect(logError).not.toHaveBeenCalled();
    expect(apiPost).not.toHaveBeenCalled();
  });
});
