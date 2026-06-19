import { expect, test, type Page } from '@playwright/test';

// Full front-end workflow smoke against the production build served by the
// Python backend (FastAPI serving web/dist) on port 8000. Firefox-only.
//
// What it asserts:
//   1. The editor app shell + workflow canvas mount.
//   2. The Run / validate button is present.
//   3. A built-in template can be loaded from the Templates panel, after which
//      nodes appear on the canvas (node-count stat overlay becomes visible).
//   4. The node count after loading a template is > 0.
//
// It does NOT execute any bioinformatics workflow (no bioconda env required).

const NODE_COUNT_RE = /^\d+$/;

async function nodeCount(page: Page): Promise<number> {
  // The stats overlay only renders once the workflow has >= 1 node. The first
  // ".workflow-stats-count" span is the node count.
  const overlay = page.locator('.workflow-stats-overlay');
  if ((await overlay.count()) === 0) return 0;
  const counts = overlay.locator('.workflow-stats-count');
  if ((await counts.count()) === 0) {
    // Collapsed pill form: "<n>n - <e>e ...". Parse the leading integer.
    const pill = page.locator('.workflow-stats-pill');
    if ((await pill.count()) === 0) return 0;
    const text = (await pill.first().innerText()).trim();
    const m = text.match(/^(\d+)/);
    return m ? Number(m[1]) : 0;
  }
  const text = (await counts.first().innerText()).trim();
  return NODE_COUNT_RE.test(text) ? Number(text) : 0;
}

test('editor loads, opens a template, and shows nodes on the canvas', async ({ page }) => {
  await page.goto('/', { waitUntil: 'domcontentloaded' });

  // 1. App shell + canvas mount. The boot loader is replaced by the real app.
  await expect(page).toHaveTitle(/BioNodulo/i);
  const canvasHost = page.locator('.workflow-canvas-host');
  await expect(canvasHost).toBeVisible({ timeout: 45_000 });
  await expect(canvasHost.locator('canvas').first()).toBeVisible();

  // Dismiss the "Getting Started" welcome modal if it is shown — it overlays
  // the left rail and would block clicks.
  const closeWelcome = page.getByRole('button', { name: /^Close$/ });
  if (await closeWelcome.isVisible().catch(() => false)) {
    await closeWelcome.click();
    await expect(closeWelcome).toBeHidden({ timeout: 10_000 });
  }

  // 2. Run / validate control is present (TopBar primary run button). Its
  //    accessible name is "Run workflow (Ctrl+R)".
  const runButton = page.getByRole('button', { name: /Run workflow/i });
  await expect(runButton).toBeVisible();

  // Sanity: a fresh workflow has no nodes yet.
  const before = await nodeCount(page);

  // 3. Open the Templates panel via the left rail. The icon-only rail button's
  //    accessible name is the panel title plus its shortcut, e.g.
  //    "Templates (Ctrl+3)" — match with a regex.
  const templatesRail = page.getByRole('button', { name: /^Templates(\s|$|\()/ });
  await expect(templatesRail).toBeVisible();
  await templatesRail.click();

  // Wait for template cards to load from /api/workflow_templates.
  const firstCard = page.locator('.template-card').first();
  await expect(firstCard).toBeVisible({ timeout: 30_000 });

  // Load the first template (clicking the card applies it to the canvas and
  // closes the panel).
  await firstCard.click();

  // 4. Nodes should now be present on the canvas. The stats overlay appears
  //    only when node count > 0; wait for it then assert the count.
  await expect(page.locator('.workflow-stats-overlay')).toBeVisible({ timeout: 30_000 });
  const after = await nodeCount(page);
  expect(after).toBeGreaterThan(0);
  expect(after).toBeGreaterThan(before);

  // Run button still present after loading the template.
  await expect(runButton).toBeVisible();

  // Dismiss the welcome modal again if it re-appeared (loading a template can
  // open a fresh tab) so the screenshot shows the populated canvas cleanly.
  const closeAgain = page.getByRole('button', { name: /^Close$/ });
  if (await closeAgain.isVisible().catch(() => false)) {
    await closeAgain.click();
    await expect(closeAgain).toBeHidden({ timeout: 10_000 }).catch(() => {});
  }

  await page.screenshot({ path: '/tmp/app-editor.png', fullPage: false });
});
