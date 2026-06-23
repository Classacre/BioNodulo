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

test('does not poll host-only endpoints in editor mode', async ({ page }) => {
  const hostCalls: string[] = [];
  page.on('request', req => {
    const p = new URL(req.url()).pathname;
    if (/\/api\/(system_stats|host_status|queue|history)$/.test(p)) hostCalls.push(p);
  });

  const response = await page.goto('/', { waitUntil: 'domcontentloaded' }).catch(() => null);
  if (!response || !response.ok()) {
    test.skip(true, 'dev server unavailable');
    return;
  }
  // Give the boot effects + a couple of overlay poll intervals time to fire.
  await page.waitForTimeout(5000);
  expect(hostCalls, `unexpected host-only polls: ${hostCalls.join(', ')}`).toHaveLength(0);
});
