import { expect, test } from '@playwright/test';

// Browser-to-API contract only. Every API request is intercepted; no job is run.
const scenarios: Array<{
  name: string; envReady: boolean; executionReady?: boolean; submit: boolean; resolveFails?: boolean;
}> = [
  { name: 'backend permits host execution without an isolated environment', envReady: false, executionReady: true, submit: true },
  { name: 'backend blocks execution even when an environment exists', envReady: true, executionReady: false, submit: false },
  { name: 'legacy ready environment remains supported', envReady: true, executionReady: undefined, submit: true },
  { name: 'legacy unready environment remains blocked', envReady: false, executionReady: undefined, submit: false },
  { name: 'failed dependency check cannot submit a run', envReady: false, submit: false, resolveFails: true },
];
for (const scenario of scenarios) {
  test(scenario.name, async ({ context, page }) => {
    await context.addInitScript(() => {
      localStorage.setItem('bionodulo.language', 'en');
      localStorage.setItem('bionodulo.settings', JSON.stringify({
        'bionodulo.getting_started.dismissed': true,
        'bionodulo.getting_started.show_on_startup': false,
      }));
    });
    let submissions = 0;
    const reason = scenario.resolveFails
      ? 'Could not check workflow dependencies. Try again before running.'
      : 'Install the required workflow environment before running.';
    await page.route(url => url.pathname.startsWith('/api/'), async route => {
      const request = route.request();
      const path = new URL(request.url()).pathname;
      let body: unknown = {};
      if (path.endsWith('/config')) body = { cloudMode: false, editorMode: false };
      if (path.endsWith('/host_status')) body = { ready: true };
      if (path.endsWith('/workflow/validate')) body = { valid: true, errors: [], warnings: [] };
      if (path.endsWith('/manager/resolve')) body = {
        missing_nodes: [], missing_executables: [], missing_packages: [], missing_r_packages: [],
        required_packages: [], env_id: 'fixture-env', env_ready: scenario.envReady,
        execution_ready: scenario.executionReady, installable: true, errors: [],
        has_issues: !scenario.submit, summary: scenario.submit ? 'Ready.' : reason,
      };
      if (path.endsWith('/runs') && request.method() === 'POST') {
        submissions += 1;
        body = { run_id: 'intercepted-preview', status: 'dry_run', execution_order: [] };
      }
      await route.fulfill({
        status: path.endsWith('/manager/resolve') && scenario.resolveFails ? 503 : 200,
        contentType: 'application/json', body: JSON.stringify(body),
      });
    });
    await page.goto('/', { waitUntil: 'domcontentloaded' });
    await page.getByRole('button', { name: /^Run workflow/ }).click();
    if (scenario.submit) {
      await expect.poll(() => submissions).toBe(1);
    } else {
      await expect(page.getByText(reason, { exact: true }).first()).toBeVisible();
      expect(submissions).toBe(0);
    }
  });
}
