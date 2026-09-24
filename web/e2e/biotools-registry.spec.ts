import { expect, test } from '@playwright/test';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

const objectInfo = JSON.parse(readFileSync(resolve(process.cwd(), '../bionodulo/nodes/node_metadata.json'), 'utf8'));
const entry = (index: number) => ({
  node_id: `biotools_${index}`,
  accession: `tool-${index}`,
  name: `Tool ${index}`,
  description: `Reference definition for tool ${index}`,
  tool_types: ['Command-line tool'],
  topics: [], operations: [],
  execution_status: 'definition_only',
  blockers: ['No verified execution binding'],
  reference_url: `https://bio.tools/tool-${index}`,
  linked_node_ids: [], runnable_node_ids: [],
});

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
    if (url.pathname.endsWith('/registry/nodes')) {
      const query = url.searchParams.get('q') ?? '';
      const offset = Number(url.searchParams.get('offset') ?? 0);
      const all = Array.from({ length: 85 }, (_, index) => entry(index));
      const matching = all.filter(item => `${item.accession} ${item.name}`.toLowerCase().includes(query.toLowerCase()));
      body = { schema_version: 1, total: 85, matched_count: matching.length, offset, limit: 40,
        snapshot: { records: 85, sha256: 'test-digest', updated_at: '2026-09-24T00:00:00Z' },
        entries: matching.slice(offset, offset + 40) };
    }
    if (url.pathname.startsWith('/api/object_info/biotools_')) {
      const nodeId = url.pathname.split('/').at(-1)!;
      body = { name: nodeId, display_name: `Tool ${nodeId.split('_').at(-1)}`, category: 'bio.tools',
        description: 'Reference only', input: { required: {}, optional: {} }, output: [], output_name: [],
        registry_origin: { accession: `tool-${nodeId.split('_').at(-1)}`, snapshot_sha256: 'test-digest',
          execution_status: 'definition_only', blockers: ['No verified execution binding'] } };
    }
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(body) });
  });
  await page.goto('/', { waitUntil: 'domcontentloaded' });
  await page.locator('nav.left-rail').getByRole('button', { name: /^Nodes/ }).click();
  await page.getByRole('button', { name: /^Browse bio\.tools registry/ }).click();
});

test('paginates all registry definitions and adds a non-executable canvas node', async ({ page }) => {
  const panel = page.locator('.biotools-registry-panel');
  await expect(panel.getByRole('status')).toContainText('85 registry records');
  await expect(panel.getByRole('article')).toHaveCount(40);
  await panel.getByRole('button', { name: 'Next' }).click();
  await expect(panel.getByRole('article').first()).toContainText('Tool 40');
  await panel.getByRole('button', { name: 'Next' }).click();
  await expect(panel.getByRole('article')).toHaveCount(5);
  await panel.getByRole('searchbox').fill('tool-84');
  await expect(panel.getByRole('article')).toHaveCount(1);
  await panel.getByRole('button', { name: 'Add reference node' }).click();
  await expect(page.locator('.bio-node[data-node-id^="biotools_84_"]')).toBeVisible();
  await expect(page.locator('.bio-node[data-node-id^="biotools_84_"]')).toContainText('Reference only');
  await page.waitForTimeout(1200);
  await page.reload({ waitUntil: 'domcontentloaded' });
  await expect(page.locator('.bio-node[data-node-id^="biotools_84_"]')).toBeVisible();
  await expect(page.locator('.bio-node[data-node-id^="biotools_84_"]')).toContainText('Reference only');
});

test('shows search failure and can retry', async ({ page }) => {
  const panel = page.locator('.biotools-registry-panel');
  await page.route('**/api/registry/nodes?**', async route => {
    await route.fulfill({ status: 503, contentType: 'application/json', body: '{"detail":"unavailable"}' });
  });
  await panel.getByRole('searchbox').fill('failure');
  await expect(panel.getByRole('status')).toContainText('unavailable');
  await expect(panel.getByRole('button', { name: 'Retry' })).toBeVisible();
});

test('keeps a failed definition fetch off the canvas', async ({ page }) => {
  const panel = page.locator('.biotools-registry-panel');
  await page.route('**/api/object_info/biotools_84', async route => {
    await route.fulfill({ status: 503, contentType: 'application/json', body: '{"detail":"unavailable"}' });
  });
  await panel.getByRole('searchbox').fill('tool-84');
  await expect(panel.getByRole('article')).toHaveCount(1);
  await panel.getByRole('button', { name: 'Add reference node' }).click();
  await expect(panel.getByRole('alert')).toContainText('Could not add registry node');
  await expect(page.locator('.bio-node[data-node-id^="biotools_84_"]')).toHaveCount(0);
});
