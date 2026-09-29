import { expect, test } from '@playwright/test';
import { readFileSync, readdirSync } from 'node:fs';
import { resolve } from 'node:path';

// Exercise actual shipped metadata, not simplified hand-written demo nodes.
// Host APIs are stubbed: these tests prove editor presentation, not execution.
const nodeRoot = resolve(process.cwd(), '../bionodulo/nodes');
const info = JSON.parse(readFileSync(resolve(nodeRoot, 'node_metadata.json'), 'utf8'));
const index: Record<string, string> = JSON.parse(readFileSync(resolve(nodeRoot, 'node_index.json'), 'utf8'));
const generated = readdirSync(resolve(nodeRoot, 'generated'))
  .filter(name => name.endsWith('_node_ids.json'))
  .flatMap(name => JSON.parse(readFileSync(resolve(nodeRoot, 'generated', name), 'utf8')).node_ids as string[]);
const newFamilies = ['csvtk_family', 'emboss_family', 'htslib_tabix_family', 'seqfu_family', 'unikmer_family', 'vcflib_family'];
const additions = [...new Set([...generated, ...Object.keys(index).filter(id =>
  newFamilies.some(family => index[id].startsWith(`bionodulo.nodes.builtin.${family}.`)),
)])].sort();
const families = [...new Set(additions.map(id => index[id].split('.')[3]))];

// Allow a cold Vite start before the census begins on Windows test hosts.
test.describe.configure({ timeout: 120_000 });

test.beforeEach(async ({ context, page }) => {
  // Keep the intentionally offline host stub from opening backend sockets.
  await page.routeWebSocket(url => url.pathname.startsWith('/ws'), () => {});
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
    if (path.endsWith('/object_info')) body = info;
    if (path.endsWith('/config')) body = { cloudMode: false, editorMode: false };
    if (path.endsWith('/host_status')) body = { ready: true };
    if (path.endsWith('/workflow/validate')) body = { valid: true, errors: [] };
    if (path.endsWith('/registry/nodes')) body = { schema_version: 1, total: 34248 };
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(body) });
  });
  await page.goto('/', { waitUntil: 'domcontentloaded' });
  await page.locator('nav.left-rail').getByRole('button', { name: /^Nodes/ }).click();
});

for (const family of families) {
  test(`${family}: every added node is searchable, inserts, and exposes its metadata`, async ({ page }) => {
    const errors: string[] = [];
    page.on('pageerror', error => errors.push(error.message));
    const ids = additions.filter(id => index[id].split('.')[3] === family);
    // The family census grows; allow bounded time per editor interaction cycle.
    test.setTimeout(120_000 + ids.length * 5_000);
    for (const id of ids) {
      await test.step(id, async () => {
        await page.locator('.node-search-input').fill(id);
        const result = page.locator(`#node-library-result-${id}`);
        await expect(result.locator('.node-search-result-title')).toContainText(info[id].display_name);
        await result.click();
        const node = page.locator(`.bio-node[data-node-id^="${id}_"]`);
        await expect(node.locator('.bio-node-title')).toHaveText(info[id].display_name);
        await expect(node).not.toContainText('[object Object]');
        await node.locator('.bio-node-header').click({ button: 'right' });
        await page.getByRole('menuitem', { name: 'Node info', exact: true }).click();
        const dialog = page.locator('.bio-props-dialog');
        expect(info[id].description.trim(), `${id} needs a useful description`).not.toBe('');
        await expect(dialog.locator('.bio-props-meta')).toContainText(id);
        await expect(dialog.locator('.bio-props-meta')).toContainText(info[id].category);
        await expect(dialog.locator('.bio-props-desc').first()).toHaveText(info[id].description);
        await expect(dialog).not.toContainText('[object Object]');
        for (const key of Object.keys(info[id].input?.required || {})) {
          await expect(dialog).toContainText(key);
        }
        if (id === ids[0] || id === 'emboss_water' || id === 'seqkit_pair') {
          await page.screenshot({ path: `test-results/expanded-node-${id}.png`, animations: 'disabled' });
        }
        await dialog.getByRole('button', { name: 'Done', exact: true }).click();
        if (id === ids[0] || id === 'emboss_water' || id === 'seqkit_pair') {
          await node.screenshot({ path: `test-results/expanded-canvas-${id}.png`, animations: 'disabled' });
        }
        await node.locator('.bio-node-header').click({ button: 'right' });
        await page.getByRole('menuitem', { name: 'Delete', exact: true }).click();
        await expect(node).toHaveCount(0);
      });
    }
    expect(errors).toEqual([]);
  });
}
