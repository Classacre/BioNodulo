import { expect, test } from '@playwright/test';

const checkpointManifest = {
  exists: true,
  manifest_path: '/workspace/checkpoints/checkpoint_manifest.json',
  manifest: {
    checkpoints: {
      '/workspace/checkpoints/after_qc.json': {
        checkpoint_name: 'after_qc',
        checkpoint_path: '/workspace/checkpoints/after_qc.json',
        node_id: 'qc-node',
        run_id: 'run-42',
      },
    },
  },
};

const pauseRequests = {
  pause_requests_dir: '/workspace/pause_requests',
  count: 1,
  review_decision_supported: true,
  engine_pause_supported: true,
  pause_note: 'Review request decisions and executor-level blocking pause/resume are supported.',
  errors: [],
  pause_requests: [
    {
      pause_file: '/workspace/pause_requests/manual-review.json',
      node_id: 'manual-review',
      message: 'Review QC metrics',
      status: 'waiting',
      engine_pause_supported: true,
    },
  ],
};

const workflowTriggers = {
  trigger_dir: '/workspace/workflow_triggers',
  count: 1,
  errors: [],
  triggers: [
    {
      trigger_file: '/workspace/workflow_triggers/nightly.json',
      trigger_type: 'schedule',
      target_workflow: 'Nightly QC workflow',
      status: 'active',
    },
  ],
};

test.beforeEach(async ({ context, page }) => {
  await context.addInitScript(() => {
    window.localStorage.setItem('bionodulo.language', 'en');
    window.localStorage.setItem('bionodulo.settings', JSON.stringify({
      'bionodulo.getting_started.dismissed': true,
      'bionodulo.getting_started.show_on_startup': false,
    }));
  });

  await page.route(url => url.pathname.startsWith('/api/'), async route => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname;
    let payload: unknown = {};

    if (path.endsWith('/api/checkpoints/manifest')) {
      payload = checkpointManifest;
    } else if (path.endsWith('/api/pause_requests') && request.method() === 'GET') {
      payload = pauseRequests;
    } else if (path.endsWith('/api/workflow_triggers') && request.method() === 'GET') {
      payload = workflowTriggers;
    } else if (path.endsWith('/api/checkpoints/resolve')) {
      payload = {
        found: true,
        manifest_path: checkpointManifest.manifest_path,
        checkpoint: checkpointManifest.manifest.checkpoints['/workspace/checkpoints/after_qc.json'],
      };
    } else if (path.endsWith('/api/workflow_triggers/evaluate')) {
      payload = {
        trigger_dir: workflowTriggers.trigger_dir,
        due_schedule_triggers: workflowTriggers.triggers,
        due_schedule_count: 1,
        due_file_watch_triggers: [],
        due_file_watch_count: 0,
        // Required: the validator calls requireArray on submitted_runs, so
        // omitting it threw ApiValidationError, the evaluation state was never
        // set, and the counts silently never rendered.
        submitted_runs: [],
        errors: [],
        scheduler_runner_contract_supported: true,
        file_watch_runner_contract_supported: true,
        run_submission_supported: false,
      };
    } else if (path.endsWith('/api/pause_requests/resolve')) {
      payload = {
        pause_request: {
          ...pauseRequests.pause_requests[0],
          status: 'approved',
          approved: true,
        },
      };
    } else if (path.endsWith('/api/object_info') || path.endsWith('/api/settings')) {
      payload = {};
    }

    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(payload),
    });
  });
});

test('runtime artifacts panel exposes checkpoints, pause requests, and workflow triggers', async ({ page }) => {
  const resolvedPauseRequests: unknown[] = [];
  let checkpointResolveUrl = '';
  let triggerEvaluationRequested = false;

  page.on('request', request => {
    const url = request.url();
    if (url.includes('/api/checkpoints/resolve')) checkpointResolveUrl = url;
    if (url.includes('/api/workflow_triggers/evaluate')) triggerEvaluationRequested = true;
    if (url.includes('/api/pause_requests/resolve')) {
      resolvedPauseRequests.push(request.postDataJSON());
    }
  });

  await page.goto('/', { waitUntil: 'domcontentloaded' });
  await page.getByRole('button', { name: 'Runtime artifacts' }).click();

  await expect(page.getByRole('heading', { name: 'Checkpoints' })).toBeVisible();
  await expect(page.getByText('1 checkpoint')).toBeVisible();
  await expect(page.getByText('after_qc')).toBeVisible();
  await expect(page.getByText('qc-node')).toBeVisible();

  await expect(page.getByRole('heading', { name: 'Pause requests' })).toBeVisible();
  await expect(page.getByText('Review QC metrics')).toBeVisible();
  await expect(page.getByText('manual-review · waiting')).toBeVisible();
  await expect(page.getByText('Blocking pause available')).toBeVisible();

  await expect(page.getByRole('heading', { name: 'Workflow triggers' })).toBeVisible();
  await expect(page.getByText('Nightly QC workflow')).toBeVisible();
  await expect(page.getByText('schedule · active')).toBeVisible();

  await page.getByRole('button', { name: 'Resolve after_qc' }).click();
  await expect(page.getByText('Resolved checkpoint')).toBeVisible();
  await expect(page.getByText('/workspace/checkpoints/after_qc.json')).toBeVisible();
  expect(checkpointResolveUrl).toContain('checkpoint_name=after_qc');

  await page.getByRole('button', { name: 'Evaluate triggers' }).click();
  await expect(page.getByText('1 schedule trigger due')).toBeVisible();
  await expect(page.getByText('0 file-watch triggers due')).toBeVisible();
  expect(triggerEvaluationRequested).toBe(true);

  await page.getByRole('button', { name: 'Approve manual-review' }).click();
  await expect.poll(() => resolvedPauseRequests.length).toBe(1);
  expect(resolvedPauseRequests[0]).toMatchObject({
    action: 'approve',
    node_id: 'manual-review',
    pause_file: '/workspace/pause_requests/manual-review.json',
  });
});
