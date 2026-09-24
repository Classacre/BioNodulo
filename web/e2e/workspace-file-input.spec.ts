import { expect, test } from '@playwright/test';
import { readFileSync } from 'node:fs';

const metadata = JSON.parse(readFileSync(new URL('../../bionodulo/nodes/node_metadata.json', import.meta.url), 'utf8'));

test('workspace drops and clipboard uploads populate the executable Input File field', async ({ context, page }) => {
  await context.addInitScript(() => {
    localStorage.setItem('bionodulo.language', 'en');
    localStorage.setItem('bionodulo.settings', JSON.stringify({
      'bionodulo.getting_started.dismissed': true,
      'bionodulo.getting_started.show_on_startup': false,
    }));
  });
  let submittedNodes: Array<{ type: string; params: Record<string, unknown> }> = [];
  // Every API request is intercepted: this inspects composition/submission and
  // does not upload user data or execute a workflow.
  await page.route(url => url.pathname.startsWith('/api/'), async route => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname;
    let body: unknown = {};
    if (path.endsWith('/object_info')) body = { input_file: metadata.input_file };
    if (path.endsWith('/config')) body = { cloudMode: false, editorMode: false };
    if (path.endsWith('/host_status')) body = { ready: true };
    if (path.endsWith('/workspace/root')) body = { root: 'D:\\workspace' };
    if (path.endsWith('/workspace/files')) body = url.searchParams.get('path') === 'fixtures'
      ? { path: 'fixtures', entries: [{ name: 'counts.tsv', path: 'fixtures\\counts.tsv', type: 'file', size: 40 }] }
      : { path: '.', entries: [{ name: 'fixtures', path: 'fixtures', type: 'directory' }] };
    if (path.endsWith('/workspace/upload')) body = { path: 'uploads/pasted.tsv', original_name: 'pasted.tsv', content_type: 'text/plain' };
    if (path.endsWith('/workflow/validate')) body = { valid: true, errors: [], warnings: [] };
    if (path.endsWith('/manager/resolve')) body = {
      missing_nodes: [], missing_executables: [], missing_packages: [], missing_r_packages: [],
      required_packages: [], env_id: '', env_ready: false, execution_ready: true,
      installable: false, errors: [], has_issues: false, summary: 'Ready.',
    };
    if (path.endsWith('/runs') && request.method() === 'POST') {
      submittedNodes = request.postDataJSON().workflow.nodes;
      body = { run_id: 'intercepted-preview', status: 'dry_run', execution_order: [] };
    }
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(body) });
  });

  await page.goto('/', { waitUntil: 'domcontentloaded' });
  await page.locator('nav.left-rail').getByRole('button', { name: /^Workspace/ }).click();
  await page.getByText('fixtures', { exact: true }).dblclick();
  await page.getByText('counts.tsv', { exact: true }).dragTo(page.locator('.react-flow__pane'));
  await expect(page.locator('.react-flow__node')).toHaveCount(1);
  await page.evaluate(() => {
    const data = new DataTransfer();
    data.items.add(new File(['gene\tcount\na\t10\n'], 'pasted.tsv', { type: 'text/plain' }));
    document.body.dispatchEvent(new ClipboardEvent('paste', { clipboardData: data, bubbles: true }));
  });
  await expect(page.locator('.react-flow__node')).toHaveCount(2);
  await page.getByRole('button', { name: /^Run workflow/ }).click();
  await expect.poll(() => submittedNodes.length).toBe(2);
  expect(submittedNodes.map(node => node.type)).toEqual(['input_file', 'input_file']);
  expect(submittedNodes.map(node => node.params.file)).toEqual(['fixtures/counts.tsv', 'uploads/pasted.tsv']);
  expect(submittedNodes.every(node => !Object.hasOwn(node.params, 'path'))).toBe(true);
});
