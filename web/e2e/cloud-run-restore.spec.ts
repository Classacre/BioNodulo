import { expect, test } from '@playwright/test';

// UI/API contracts only: every request is intercepted, so no compute is started.
const config = {
  editorMode: true, cloudMode: false,
  user: { id: 'u-audit', name: 'Audit', email: 'audit@example.test' },
  team: { id: 'team-audit', name: 'Audit team' },
  accountUrl: null, clerkPublishableKey: null,
};
const workflow = (id: string, name: string, nodeIds: string[]) => ({
  id, name, description: '', updatedAt: '2026-10-14T00:00:00Z',
  definition: { version: '2.0', app: 'bionodulo', nodes: nodeIds.map((nodeId, index) => ({
    id: nodeId, type: 'input_file', position: [index * 280, 0],
    params: { file: 'https://example.test/data.tsv' },
  })), edges: [], groups: [], outputs: {}, parameters: [] },
});
const focused = workflow('wf-focused', 'Focused workflow', ['focused-node']);
const running = workflow('wf-running', 'Running workflow', ['run-first', 'run-second']);

test('reload restores an active cloud run without resubmitting or borrowing the focused graph', async ({ context, page }) => {
  await context.addInitScript(() => {
    localStorage.setItem('bionodulo.language', 'en');
    localStorage.setItem('bionodulo.settings', JSON.stringify({
      'bionodulo.getting_started.dismissed': true, 'bionodulo.getting_started.show_on_startup': false,
    }));
  });
  let submissions = 0;
  let snapshotRequests = 0;
  let runStatus: 'running' | 'failed' = 'running';
  await page.route(url => url.pathname.startsWith('/api/'), async route => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname;
    let body: unknown = {};
    if (path === '/api/config') body = config;
    else if (path === '/api/me') body = { success: true, data: { ...config.user, team: config.team } };
    else if (path === '/api/workflows') body = { success: true, data: [focused] };
    else if (path === '/api/workflows/wf-focused') body = { success: true, data: focused };
    else if (path === '/api/workflows/wf-running') body = { success: true, data: running };
    else if (path === '/api/object_info') body = {
      input_file: { id: 'input_file', display_name: 'Input File', category: 'Input', input_types: { required: { file: { type: 'STRING' } } }, return_types: ['FILE'], return_names: ['file'] },
    };
    else if (path === '/api/runs' && request.method() === 'POST') { submissions += 1; body = { success: false, error: 'Unexpected submission' }; }
    else if (path === '/api/runs' && url.searchParams.get('view') === 'summary') body = { success: true, data: [{
      id: 'restored-run', workflowId: running.id, workflowName: running.name, status: runStatus,
      createdAt: '2026-10-14T00:00:00Z', startedAt: '2026-10-14T00:00:01Z',
      completedAt: runStatus === 'failed' ? '2026-10-14T00:00:05Z' : null, durationMs: null, creditsUsed: null,
    }] };
    else if (path === '/api/runs/restored-run') {
      snapshotRequests += 1;
      body = { id: 'restored-run', workflowId: running.id, status: 'running',
        logs: '[2026-10-14T00:00:02Z] INFO: node input_file completed [node:run-first]\n[2026-10-14T00:00:03Z] INFO: node input_file started [node:run-second]',
        errorMessage: null, creditsUsed: null, durationMs: null, completedAt: null };
    }
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(body) });
  });

  await page.goto('/');
  await expect(page.getByRole('button', { name: 'Queue: 1', exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Queue: 1', exact: true }).click();
  await expect(page.locator('.runs-drawer .queue-run-name')).toHaveText('Running workflow');
  await expect(page.locator('.runs-drawer .queue-run-meta')).toContainText(/1\s*\/\s*2/);
  await expect(page.locator('.bio-node[data-node-id="focused-node"]')).toBeVisible();
  await expect(page.locator('.bio-node[data-node-id="focused-node"]')).not.toHaveAttribute('data-status', 'running');
  await page.reload();
  await expect(page.getByRole('button', { name: 'Queue: 1', exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Queue: 1', exact: true }).click();
  await expect(page.locator('.runs-drawer .queue-run-card')).toHaveCount(1);
  await expect(page.locator('.runs-drawer .queue-run-meta')).toContainText(/1\s*\/\s*2/);
  expect(snapshotRequests).toBeGreaterThanOrEqual(2);
  expect(submissions).toBe(0);
  await expect(page.getByRole('button', { name: 'Compare runs', exact: true })).toHaveCount(0);

  runStatus = 'failed';
  await page.reload();
  await expect(page.getByRole('button', { name: 'Queue: 0', exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Queue: 0', exact: true }).click();
  await page.getByRole('button', { name: 'Open to retry', exact: true }).click();
  await expect(page.locator('.workflow-tabs').getByRole('button', { name: 'Running workflow', exact: true })).toBeVisible();
  await expect(page.locator('.island-peek-title')).toContainText('Workflow opened for review. Check its inputs and compute settings, then select Run to retry.');
  expect(submissions).toBe(0);
  await expect(page.getByRole('button', { name: 'Delete run from history', exact: true })).toHaveCount(0);
});

test('does not request team run summaries before a signed-in team identity exists', async ({ page }) => {
  let summaryRequests = 0;
  await page.route(url => url.pathname.startsWith('/api/'), async route => {
    const url = new URL(route.request().url());
    if (url.pathname === '/api/runs' && url.searchParams.get('view') === 'summary') summaryRequests += 1;
    const body = url.pathname === '/api/config' ? { ...config, user: null, team: null } : {};
    await route.fulfill({ status: url.pathname === '/api/me' ? 401 : 200, contentType: 'application/json', body: JSON.stringify(body) });
  });
  await page.goto('/');
  await expect(page.getByRole('button', { name: /^Run workflow/ })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Queue: 0', exact: true })).toBeVisible();
  expect(summaryRequests).toBe(0);
});
