import { expect, test } from '@playwright/test';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

// Exercise the shipped catalog, not a curated demo list. Only surrounding host
// services are stubbed; this suite does not claim external-tool execution.
const objectInfo = JSON.parse(readFileSync(resolve(process.cwd(), '../bionodulo/nodes/node_metadata.json'), 'utf8'));
const catalogSize = Object.keys(objectInfo).length;
const categoryCount = new Set(Object.values(objectInfo).map((meta: any) => meta.category)).size;
test.beforeEach(async ({ context, page }) => {
  await context.addInitScript(() => {
    localStorage.setItem('bionodulo.language', 'en');
    localStorage.setItem('bionodulo.settings', JSON.stringify({
      'bionodulo.getting_started.dismissed': true,
      'bionodulo.getting_started.show_on_startup': false,
    }));
  });
  await page.route(url => url.pathname.startsWith('/api/'), async route => {
    const url = new URL(route.request().url());
    let body: unknown = {};
    if (url.pathname.endsWith('/object_info')) body = objectInfo;
    if (url.pathname.endsWith('/config')) body = { cloudMode: false, editorMode: false };
    if (url.pathname.endsWith('/host_status')) body = { ready: true };
    if (url.pathname.endsWith('/workflow/validate')) body = { valid: true, errors: [] };
    if (url.pathname.endsWith('/registry/nodes')) body = { schema_version: 1, total: 34248 };
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(body) });
  });
  await page.goto('/', { waitUntil: 'domcontentloaded' });
  await page.locator('nav.left-rail').getByRole('button', { name: /^Nodes/ }).click();
  await page.getByRole('button', { name: 'Open Tool Atlas' }).click();
});

test('explores the complete catalog, explains port matches, and inserts the chosen node', async ({ page }) => {
  const atlas = page.getByRole('dialog', { name: 'Tool Atlas' });
  await expect(atlas.locator('.atlas-counts')).toContainText(catalogSize.toLocaleString());
  await expect(atlas.locator('.atlas-category-grid button')).toHaveCount(categoryCount);
  await page.screenshot({ path: 'test-results/tool-atlas-overview.png', animations: 'disabled' });
  await atlas.getByRole('searchbox').fill('samtools_sort');
  await atlas.locator('.atlas-result').filter({ hasText: 'samtools_sort' }).click();
  await expect(atlas.getByRole('heading', { name: 'Samtools Sort', exact: true })).toBeVisible();
  await expect(atlas.locator('.atlas-graph .react-flow__node').first()).toBeVisible();
  expect(await atlas.locator('.atlas-graph .react-flow__node').count()).toBeLessThanOrEqual(7);
  await expect(atlas.locator('.atlas-note').filter({ hasText: /shared declared port type/i })).toBeVisible();
  await atlas.locator('.atlas-reason').first().click();
  await expect(atlas.locator('.atlas-evidence')).toContainText('→');
  await expect(atlas.locator('.atlas-evidence')).toContainText(/metadata/i);
  await atlas.locator('.atlas-main').evaluate(el => { el.scrollTop = 0; });
  await page.screenshot({ path: 'test-results/tool-atlas-flow.png', animations: 'disabled' });
  const download = page.waitForEvent('download');
  await atlas.getByRole('button', { name: 'Export view' }).click();
  const file = await download;
  const exported = JSON.parse(readFileSync((await file.path())!, 'utf8'));
  expect(exported.focus).toBe('samtools_sort');
  expect(exported.catalog_counts.nodes).toBe(catalogSize);
  expect(exported.relations.length).toBeGreaterThan(0);
  expect(exported.limitations).toContain('no execution or scientific compatibility');
  await atlas.getByRole('button', { name: 'Add to workflow' }).click();
  await expect(atlas).not.toBeVisible();
  await expect(page.locator('.bio-node[data-node-id^="samtools_sort_"]')).toBeVisible();
});

test('shows source-backed relationships and references, with keyboard navigation', async ({ page }) => {
  const atlas = page.getByRole('dialog', { name: 'Tool Atlas' });
  await atlas.getByRole('searchbox').fill('samtools_sort');
  await atlas.locator('.atlas-result').filter({ hasText: 'samtools_sort' }).click();
  await atlas.getByRole('button', { name: 'Related tools', exact: true }).click();
  await atlas.locator('.atlas-lenses select').selectOption('documented_successor');
  await expect(atlas.locator('.atlas-reason')).toHaveCount(1);
  const sourceCard = atlas.locator('.react-flow__node').filter({ hasText: 'Samtools Sort' });
  const targetCard = atlas.locator('.react-flow__node').filter({ hasText: 'Samtools Index' });
  await expect(sourceCard).toBeVisible();
  await expect(targetCard).toBeVisible();
  expect((await targetCard.boundingBox())!.x).toBeGreaterThan((await sourceCard.boundingBox())!.x);
  await atlas.locator('.atlas-reason').click();
  await expect(atlas.locator('.atlas-evidence')).toContainText(/coordinate/i);
  await expect(atlas.locator('.atlas-evidence a')).toHaveAttribute('href', 'https://www.htslib.org/doc/samtools-sort.html');
  await expect(atlas.locator('.atlas-references')).toContainText('10.1093/gigascience/giab008');
  await page.screenshot({ path: 'test-results/tool-atlas-evidence.png', animations: 'disabled' });
  await atlas.locator('.atlas-reasons').getByRole('button', { name: 'Explore' }).click();
  await expect(atlas.getByRole('heading', { name: 'Samtools Index', exact: true })).toBeVisible();
  await atlas.getByRole('button', { name: 'Back', exact: true }).click();
  await expect(atlas.getByRole('heading', { name: 'Samtools Sort', exact: true })).toBeVisible();
  await page.keyboard.press('Escape');
  await expect(atlas).not.toBeVisible();
  await expect(page.getByRole('button', { name: 'Open Tool Atlas' })).toBeFocused();
});

test('uses the selected dark palette for the graph and its controls', async ({ page }) => {
  await page.evaluate(() => localStorage.setItem('bionodulo.palette', 'dark'));
  await page.reload({ waitUntil: 'domcontentloaded' });
  await page.locator('nav.left-rail').getByRole('button', { name: /^Nodes/ }).click();
  await page.getByRole('button', { name: 'Open Tool Atlas' }).click();
  const atlas = page.getByRole('dialog', { name: 'Tool Atlas' });
  await atlas.getByRole('searchbox').fill('samtools_sort');
  await atlas.locator('.atlas-result').filter({ hasText: 'samtools_sort' }).click();
  await atlas.getByRole('button', { name: 'Related tools', exact: true }).click();
  await atlas.locator('.atlas-lenses select').selectOption('documented_successor');
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark');
  const colors = await atlas.locator('.atlas-graph .react-flow').evaluate(el => ({
    background: getComputedStyle(el).backgroundColor,
    surface: getComputedStyle(document.documentElement).getPropertyValue('--surface-2').trim(),
  }));
  expect(colors.background).not.toBe('rgb(255, 255, 255)');
  expect(colors.surface).not.toBe('');
  await page.screenshot({ path: 'test-results/tool-atlas-dark.png', animations: 'disabled' });
});

test('paginates, filters, and keeps the graph usable on a narrow screen', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  const atlas = page.getByRole('dialog', { name: 'Tool Atlas' });
  await atlas.locator('.atlas-library').getByRole('button', { name: 'Next', exact: true }).click();
  await expect(atlas.locator('.atlas-library .atlas-pagination')).toContainText('2 /');
  await atlas.locator('.atlas-library select').selectOption('samtools');
  await expect(atlas.locator('.atlas-list-count')).toContainText(String(Object.values(objectInfo).filter((meta: any) => meta.category === 'samtools').length));
  await atlas.getByRole('searchbox').fill('samtools_sort');
  await atlas.locator('.atlas-result').filter({ hasText: 'samtools_sort' }).click();
  await atlas.locator('.atlas-graph').scrollIntoViewIfNeeded();
  await expect(atlas.locator('.atlas-graph')).toBeVisible();
  const size = await atlas.evaluate(el => ({ width: el.clientWidth, scrollWidth: el.scrollWidth }));
  expect(size.scrollWidth).toBeLessThanOrEqual(size.width + 1);
  await page.screenshot({ path: 'test-results/tool-atlas-mobile.png', animations: 'disabled' });
  await atlas.getByRole('searchbox').fill('no-such-tool-987654321');
  await expect(atlas.locator('.atlas-results')).toContainText('No matching nodes');
});
