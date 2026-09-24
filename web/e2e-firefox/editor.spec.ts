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

async function nodeCount(page: Page): Promise<number> {
  // React Flow renders nodes as DOM elements, not a raster canvas.
  return page.locator('.react-flow__node').count();
}

test('editor loads, opens a template, and shows nodes on the canvas', async ({ page }, testInfo) => {
  // Welcome hydration can finish after the canvas mounts. Dismiss it whenever
  // it blocks an action instead of racing a one-time isVisible() check.
  await page.addLocatorHandler(page.getByRole('dialog', { name: 'Getting Started' }), async dialog => {
    await dialog.getByRole('button', { name: 'Close', exact: true }).click();
  });
  await page.goto('/', { waitUntil: 'domcontentloaded' });

  // 1. App shell + canvas mount. The boot loader is replaced by the real app.
  await expect(page).toHaveTitle(/BioNodulo/i);
  const canvasHost = page.locator('.workflow-canvas-host');
  await expect(canvasHost).toBeVisible({ timeout: 45_000 });
  await expect(canvasHost.locator('.react-flow__pane')).toBeVisible();

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

  // 4. Wait for template nodes to be rendered by React Flow.
  await expect(page.locator('.react-flow__node').first()).toBeVisible({ timeout: 30_000 });
  const after = await nodeCount(page);
  expect(after).toBeGreaterThan(0);
  expect(after).toBeGreaterThan(before);

  // Run button still present after loading the template.
  await expect(runButton).toBeVisible();

  await page.screenshot({ path: testInfo.outputPath('app-editor.png'), fullPage: false });
});
