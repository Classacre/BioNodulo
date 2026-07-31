import { test, expect } from '@playwright/test';

// Cloud-editor gating: when /api/config reports editorMode, host-only features
// that the stateless Lambda can't serve must be hidden, and the host-only boot
// polls (queue/history/system_stats/host_status/ws) must not fire. This exercises
// the runtime gating wired through cloudConfigAtom (LeftRail, overlay, console).

const editorConfig = {
  cloudMode: false,
  editorMode: true,
  user: { id: 'u1', name: 'Cloud User', email: 'cloud@example.com' },
  team: { id: 't1', name: 'Team' },
  plan: 'free',
  credits: { remaining: 100, total: 500 },
  accountUrl: null,
  clerkPublishableKey: null,
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
    const path = new URL(route.request().url()).pathname;
    let payload: unknown = {};
    if (path.endsWith('/api/config')) payload = editorConfig;
    else if (path.endsWith('/api/me')) {
      payload = { id: 'u1', name: 'Cloud User', email: 'cloud@example.com', team: { id: 't1', name: 'Team' } };
    }
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(payload) });
  });
});

test('hides host-only rail panels in editor mode', async ({ page }) => {
  const response = await page.goto('/', { waitUntil: 'domcontentloaded' }).catch(() => null);
  if (!response || !response.ok()) {
    // Never skip in CI. A silent skip meant a green suite could prove nothing
    // at all -- which is how three canvas regressions reached main unnoticed.
    if (process.env.CI) throw new Error('dev server unavailable (refusing to skip in CI)');
    test.skip(true, 'dev server unavailable');
    return;
  }
  // Nodes + Templates stay; Workspace/Environment/Runtime artifacts/HPC go.
  // Rail buttons carry a shortcut suffix in their accessible name, so match by
  // prefix rather than exact text.
  await expect(page.getByRole('button', { name: /^Nodes/ })).toBeVisible();
  await expect(page.getByRole('button', { name: /^Workspace/ })).toHaveCount(0);
  await expect(page.getByRole('button', { name: /^Environment/ })).toHaveCount(0);
  await expect(page.getByRole('button', { name: /^Runtime artifacts/ })).toHaveCount(0);
  await expect(page.getByRole('button', { name: /^HPC/ })).toHaveCount(0);
});

test('shows User + Cloud-compute rail menus above settings when signed in', async ({ page }) => {
  const response = await page.goto('/', { waitUntil: 'domcontentloaded' }).catch(() => null);
  if (!response || !response.ok()) {
    // Never skip in CI. A silent skip meant a green suite could prove nothing
    // at all -- which is how three canvas regressions reached main unnoticed.
    if (process.env.CI) throw new Error('dev server unavailable (refusing to skip in CI)');
    test.skip(true, 'dev server unavailable');
    return;
  }
  const rail = page.locator('nav.left-rail');
  await expect(rail.getByRole('button', { name: /^Cloud compute/ })).toBeVisible();
  await expect(rail.getByRole('button', { name: /^Account/ })).toBeVisible();

  // Both must sit above the settings cog (later in DOM order = lower in the rail).
  const labels = await rail.locator('button').evaluateAll(els =>
    els.map(e => e.getAttribute('aria-label') || ''));
  const idxCompute = labels.findIndex(l => l.startsWith('Cloud compute'));
  const idxAccount = labels.findIndex(l => l.startsWith('Account'));
  const idxSettings = labels.findIndex(l => l.startsWith('Settings'));
  expect(idxCompute).toBeGreaterThan(-1);
  expect(idxAccount).toBeGreaterThan(-1);
  expect(idxSettings).toBeGreaterThan(idxCompute);
  expect(idxSettings).toBeGreaterThan(idxAccount);
});

test('Compute panel shows a live credits/hr quote', async ({ page }) => {
  const response = await page.goto('/', { waitUntil: 'domcontentloaded' }).catch(() => null);
  if (!response || !response.ok()) {
    // Never skip in CI. A silent skip meant a green suite could prove nothing
    // at all -- which is how three canvas regressions reached main unnoticed.
    if (process.env.CI) throw new Error('dev server unavailable (refusing to skip in CI)');
    test.skip(true, 'dev server unavailable');
    return;
  }
  await page.locator('nav.left-rail').getByRole('button', { name: /^Cloud compute/ }).click();
  // The panel legitimately shows the rate twice -- once as the headline quote
  // and once in the custom-compute row -- so any bare text match trips strict
  // mode. Scope to the panel body and take the headline, and assert the number
  // separately so the test fails if the quote renders as an empty label.
  const computeBody = page.locator('.rail-panel-body');
  await expect(computeBody.getByText('credits / hr', { exact: true }).first()).toBeVisible();
  await expect(computeBody.getByText(/^[\d,]+$/).first()).toBeVisible();
  // Presets render. QUICK_SIZES is labelled XS/S/M/L/XL/XXL -- the test used to
  // look for "Small", which no longer exists anywhere in the panel.
  await expect(page.getByRole('button', { name: 'S', exact: true })).toBeVisible();
});

test('does not poll host-only endpoints in editor mode', async ({ page }) => {
  const hostCalls: string[] = [];
  page.on('request', req => {
    const p = new URL(req.url()).pathname;
    if (/\/api\/(system_stats|host_status|queue|history)$/.test(p)) hostCalls.push(p);
  });

  const response = await page.goto('/', { waitUntil: 'domcontentloaded' }).catch(() => null);
  if (!response || !response.ok()) {
    // Never skip in CI. A silent skip meant a green suite could prove nothing
    // at all -- which is how three canvas regressions reached main unnoticed.
    if (process.env.CI) throw new Error('dev server unavailable (refusing to skip in CI)');
    test.skip(true, 'dev server unavailable');
    return;
  }
  // Give the boot effects + a couple of overlay poll intervals time to fire.
  await page.waitForTimeout(5000);
  expect(hostCalls, `unexpected host-only polls: ${hostCalls.join(', ')}`).toHaveLength(0);
});
