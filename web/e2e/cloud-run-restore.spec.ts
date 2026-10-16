import { expect, test, type Page } from '@playwright/test';

async function waitForEditor(page: Page) {
  // Cold Vite imports can outlast a business assertion's normal five seconds.
  await expect(page.getByRole('button', { name: /^Run workflow/ })).toBeVisible({ timeout: 20_000 });
}

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
// Reused node IDs are common across templates; identity cannot be inferred from them.
const focused = workflow('wf-focused', 'Focused workflow', ['run-second']);
// The saved graph was edited after submission. It cannot describe the old run.
const running = workflow('wf-running', 'Current saved graph', ['run-second']);
running.definition.nodes[0].params.file = 'https://example.test/edited-data.tsv';

test('reload restores an active cloud run without resubmitting or borrowing the focused graph', async ({ context, page }) => {
  test.setTimeout(60_000); // Three full editor reloads, including cold Vite imports.
  await context.addInitScript(() => {
    localStorage.setItem('bionodulo.language', 'en');
    localStorage.setItem('bionodulo.settings', JSON.stringify({
      'bionodulo.getting_started.dismissed': true, 'bionodulo.getting_started.show_on_startup': false,
    }));
  });
  let submissions = 0;
  let snapshotRequests = 0;
  let savedGraphFetches = 0;
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
    else if (path === '/api/workflows/wf-running') { savedGraphFetches += 1; body = { success: true, data: running }; }
    else if (path === '/api/object_info') body = {
      input_file: { id: 'input_file', display_name: 'Input File', category: 'Input', input_types: { required: { file: { type: 'STRING' } } }, return_types: ['FILE'], return_names: ['file'] },
    };
    else if (path === '/api/runs' && request.method() === 'POST') { submissions += 1; body = { success: false, error: 'Unexpected submission' }; }
    else if (path === '/api/runs' && url.searchParams.get('view') === 'summary') body = { success: true, data: [{
      id: 'restored-run', workflowId: running.id, workflowName: 'Submitted workflow', status: runStatus,
      createdAt: '2026-10-14T00:00:00Z', startedAt: '2026-10-14T00:00:01Z',
      completedAt: runStatus === 'failed' ? '2026-10-14T00:00:05Z' : null, durationMs: null, creditsUsed: null,
    }, {
      id: 'older-run', workflowId: focused.id, workflowName: 'Older completed workflow', status: 'completed',
      createdAt: '2026-07-30T00:00:00Z', startedAt: '2026-07-30T00:00:01Z',
      completedAt: '2026-07-30T00:00:05Z', durationMs: 4000, creditsUsed: 1,
    }] };
    else if (path === '/api/runs/restored-run') {
      snapshotRequests += 1;
      body = { id: 'restored-run', workflowId: running.id, status: runStatus,
        workflowContext: { schemaVersion: 1, workflowName: 'Submitted workflow', executionNodeIds: ['run-first', 'run-second'] },
        logs: '[2026-10-14T00:00:02Z] INFO: node input_file completed [node:run-first]\n[2026-10-14T00:00:03Z] INFO: node input_file started [node:run-second]'
          + (runStatus === 'failed' ? '\n[2026-10-14T00:00:04Z] ERROR: Prior input failed [node:run-second]' : ''),
        errorMessage: runStatus === 'failed' ? 'Prior input failed' : null,
        creditsUsed: null, durationMs: null, completedAt: null };
    }
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(body) });
  });

  await page.goto('/');
  await waitForEditor(page);
  await expect(page.getByRole('button', { name: 'Queue: 1', exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Queue: 1', exact: true }).click();
  await expect(page.locator('.runs-drawer .queue-run-name').first()).toHaveText('Submitted workflow');
  await expect(page.locator('.runs-drawer .queue-run-meta').first()).toContainText(/1\s*\/\s*2/);
  await expect(page.locator('.bio-node[data-node-id="run-second"]')).toBeVisible();
  await expect(page.locator('.bio-node[data-node-id="run-second"]')).not.toHaveAttribute('data-status', 'running');
  await page.reload();
  await waitForEditor(page);
  await expect(page.getByRole('button', { name: 'Queue: 1', exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Queue: 1', exact: true }).click();
  await expect(page.locator('.runs-drawer .queue-run-card')).toHaveCount(2);
  await expect(page.locator('.runs-drawer .queue-run-meta').first()).toContainText(/1\s*\/\s*2/);
  expect(snapshotRequests).toBeGreaterThanOrEqual(2);
  expect(submissions).toBe(0);
  expect(savedGraphFetches).toBe(0);
  await expect(page.getByRole('button', { name: 'Compare runs', exact: true })).toHaveCount(0);

  runStatus = 'failed';
  await page.reload();
  await waitForEditor(page);
  await expect(page.getByRole('button', { name: 'Queue: 0', exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Queue: 0', exact: true }).click();
  await expect(page.locator('.runs-drawer .history-run-card .queue-run-name')).toHaveText([
    'Submitted workflow', 'Older completed workflow',
  ]);
  await page.locator('.history-run-card').filter({ hasText: 'Submitted workflow' })
    .getByRole('button', { name: 'Open workflow', exact: true }).click();
  await expect(page.locator('.workflow-tabs').getByRole('button', { name: 'Current saved graph', exact: true })).toBeVisible();
  await expect(page.locator('.bio-node[data-node-id="run-second"]')).toBeVisible();
  await expect(page.locator('.bio-node[data-node-id="run-second"]')).not.toHaveAttribute('data-status', 'error');
  await expect(page.locator('.bio-node[data-node-id="run-second"]')).not.toContainText('Prior input failed');
  await expect(page.locator('.island-peek-title')).toContainText('Current saved workflow opened');
  await expect(page.locator('.island-peek-line')).toContainText('The graph may have changed since this run.');
  await expect(page.locator('.history-run-card .queue-run-name').first()).toHaveText('Submitted workflow');
  expect(savedGraphFetches).toBe(1); // Only the explicit Open action fetches it.
  expect(submissions).toBe(0);
  await expect(page.getByRole('button', { name: 'Delete run from history', exact: true })).toHaveCount(0);
});

test('legacy cloud progress uses observed IDs without loading the current saved graph', async ({ context, page }) => {
  await context.addInitScript(() => localStorage.setItem('bionodulo.settings', JSON.stringify({
    'bionodulo.getting_started.dismissed': true, 'bionodulo.getting_started.show_on_startup': false,
  })));
  let savedGraphFetches = 0;
  await page.route(url => url.pathname.startsWith('/api/'), async route => {
    const path = new URL(route.request().url()).pathname;
    let body: unknown = {};
    if (path === '/api/config') body = config;
    else if (path === '/api/me') body = { success: true, data: { ...config.user, team: config.team } };
    else if (path === '/api/workflows') body = { success: true, data: [focused] };
    else if (path === '/api/workflows/wf-focused') body = { success: true, data: focused };
    else if (path === '/api/workflows/wf-running') { savedGraphFetches += 1; body = { success: true, data: running }; }
    else if (path === '/api/runs') body = { success: true, data: [{
      id: 'legacy-run', workflowId: running.id, workflowName: null, status: 'running',
      createdAt: '2026-10-14T00:00:00Z', startedAt: null, completedAt: null, durationMs: null, creditsUsed: null,
    }] };
    else if (path === '/api/runs/legacy-run') body = {
      id: 'legacy-run', workflowId: running.id, status: 'running', workflowContext: null,
      logs: '[2026-10-14T00:00:02Z] INFO: node input_file started [node:observed-only]',
      errorMessage: null, creditsUsed: null, durationMs: null, completedAt: null,
    };
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(body) });
  });
  await page.goto('/');
  await waitForEditor(page);
  await expect(page.getByRole('button', { name: 'Queue: 1', exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Queue: 1', exact: true }).click();
  await expect(page.locator('.runs-drawer .queue-run-meta')).toContainText('0/1 observed nodes');
  await expect(page.locator('.runs-drawer .queue-run-name')).toHaveText('Cloud run legacy-run');
  expect(savedGraphFetches).toBe(0);
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
  await waitForEditor(page);
  await expect(page.getByRole('button', { name: /^Run workflow/ })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Queue: 0', exact: true })).toBeVisible();
  expect(summaryRequests).toBe(0);
});

test('timed-out admission reconciles the server run and never submits twice when its response arrives late', async ({ context, page }) => {
  test.setTimeout(60_000);
  await context.addInitScript(() => {
    localStorage.setItem('bionodulo.language', 'en');
    localStorage.setItem('bionodulo.settings', JSON.stringify({
      'bionodulo.getting_started.dismissed': true, 'bionodulo.getting_started.show_on_startup': false,
    }));
  });
  await page.clock.install();
  let submissions = 0;
  let summaryRequests = 0;
  let finishResponse: (() => void) | undefined;
  await page.route(url => url.pathname.startsWith('/api/'), async route => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    let body: unknown = {};
    if (path === '/api/config') body = config;
    else if (path === '/api/me') body = { success: true, data: { ...config.user, team: config.team } };
    else if (path === '/api/workflows') body = { success: true, data: [focused] };
    else if (path === '/api/workflows/wf-focused') body = { success: true, data: focused };
    else if (path === '/api/object_info') body = {
      input_file: { id: 'input_file', display_name: 'Input File', category: 'Input', input_types: { required: { file: { type: 'STRING' } } }, return_types: ['FILE'], return_names: ['file'] },
    };
    else if (path === '/api/workflow/validate') body = { valid: true, errors: [] };
    else if (path === '/api/runs' && request.method() === 'POST') {
      submissions += 1;
      await new Promise<void>(resolve => { finishResponse = resolve; });
      await route.fulfill({ status: 202, contentType: 'application/json', body: JSON.stringify({ success: true, data: { runId: 'admitted-run' } }) }).catch(() => {});
      return;
    } else if (path === '/api/runs') {
      summaryRequests += 1;
      body = { success: true, data: submissions ? [{
        id: 'admitted-run', workflowId: focused.id, workflowName: 'Actual submitted name', status: 'queued',
        createdAt: '2026-10-16T00:00:00Z', startedAt: null, completedAt: null, durationMs: null, creditsUsed: null,
      }] : [] };
    } else if (path === '/api/runs/admitted-run') body = {
      id: 'admitted-run', workflowId: focused.id, status: 'queued', logs: '',
      workflowContext: { schemaVersion: 1, workflowName: 'Actual submitted name', executionNodeIds: ['run-second'] },
      errorMessage: 'Worker scheduling failed; cleanup is pending', creditsUsed: null, durationMs: null, completedAt: null,
    };
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(body) });
  });
  await page.goto('/');
  await waitForEditor(page);
  await expect.poll(() => summaryRequests).toBe(1);
  await page.getByRole('button', { name: /^Run workflow/ }).click();
  await expect.poll(() => submissions).toBe(1);
  await page.clock.fastForward(180_001);
  await expect(page.getByRole('button', { name: /^Run workflow/ })).toBeEnabled();
  await expect(page.locator('.island-peek-title')).toContainText('Run submission outcome unknown');
  await expect(page.locator('.island-peek-line')).toContainText('Check run history before submitting again.');
  await expect(page.getByRole('button', { name: 'Queue: 1', exact: true })).toBeVisible();
  await expect(page.locator('.runs-drawer .queue-run-name')).toHaveText('Actual submitted name');
  expect(summaryRequests).toBeGreaterThanOrEqual(2);
  finishResponse?.(); // Original request settles after the client has timed out.
  await page.clock.fastForward(120_001);
  await expect(page.locator('.runs-drawer .queue-run-card')).toHaveCount(1);
  expect(submissions).toBe(1);
});
