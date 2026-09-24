import { expect, test } from '@playwright/test';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

const snapshot = JSON.parse(readFileSync(resolve(process.cwd(), 'public/biotools-registry/index.json'), 'utf8'));
const objectInfo = JSON.parse(readFileSync(resolve(process.cwd(), '../bionodulo/nodes/node_metadata.json'), 'utf8'));

test('complete registry discovery remains separate from executable app nodes', async ({ context, page }, testInfo) => {
  await context.addInitScript(() => {
    localStorage.setItem('bionodulo.language', 'en');
    localStorage.setItem('bionodulo.settings', JSON.stringify({
      'bionodulo.getting_started.dismissed': true,
      'bionodulo.getting_started.show_on_startup': false,
    }));
  });
  await page.route(url => url.pathname.startsWith('/api/'), async route => {
    const path = new URL(route.request().url()).pathname;
    let body: unknown = {};
    if (path.endsWith('/object_info')) body = objectInfo;
    if (path.endsWith('/config')) body = { cloudMode: false, editorMode: false };
    if (path.endsWith('/host_status')) body = { ready: true };
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(body) });
  });
  await page.goto('/', { waitUntil: 'domcontentloaded' });
  await page.locator('nav.left-rail').getByRole('button', { name: /^Nodes/ }).click();
  await page.getByRole('button', { name: 'Browse bio.tools registry' }).click();
  const panel = page.locator('.biotools-registry-panel');
  await expect(panel.getByRole('status')).toContainText(`${snapshot.records.toLocaleString()} registry records`);
  expect(new Set(snapshot.tools.map((tool: { id: string }) => tool.id.toLowerCase())).size).toBe(snapshot.records);
  await expect(panel.getByRole('article')).toHaveCount(40);
  const last = snapshot.tools.at(-1);
  await panel.getByRole('searchbox').fill(last.id);
  await expect(panel.getByRole('link', { name: last.name, exact: true })).toBeVisible();
  await expect(panel.getByRole('button', { name: /^Add / })).toHaveCount(0);
  await panel.getByRole('searchbox').fill('fastqc');
  await expect(panel.getByRole('button', { name: 'Add FastQC', exact: true })).toBeVisible();
  await expect(panel.getByRole('article').first().getByRole('link')).toHaveText('FastQC');
  await page.screenshot({ path: testInfo.outputPath('biotools-desktop.png') });
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(panel.getByRole('searchbox')).toBeVisible();
  await page.screenshot({ path: testInfo.outputPath('biotools-narrow.png') });
});
