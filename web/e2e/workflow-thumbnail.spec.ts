import { test, expect } from '@playwright/test';

// The SVG→PNG rasteriser (renderWorkflowThumbnailPng) depends on the browser
// decoding an SVG data URL through <img>, which jsdom/vitest cannot do. This
// exercises it in a real browser: render a small workflow to a thumbnail and
// assert we get back a valid PNG data URL (magic bytes), proving the headless
// thumbnail path works without any Canvas2D graph renderer.
test('workflow thumbnail rasterises SVG to a valid PNG in the browser', async ({ page }) => {
  await page.goto('/', { waitUntil: 'domcontentloaded' });
  await expect(page.getByRole('button', { name: /Run workflow/ })).toBeVisible();

  const result = await page.evaluate(async () => {
    const mod = await import('/src/utils/workflowThumbnail.ts');
    const workflow = {
      version: '2.0',
      app: 'BioNodulo',
      name: 'thumb-e2e',
      description: '',
      nodes: [
        { id: 'a', type: 'input_fastq', position: [0, 0], params: {}, ui: { title: 'Input' } },
        { id: 'b', type: 'fastqc', position: [280, 0], params: {}, ui: { title: 'FastQC' } },
      ],
      edges: [{ id: 'e1', from: { node: 'a', output: 'out' }, to: { node: 'b', input: 'in' } }],
      groups: [],
      outputs: {},
    };
    // Sync path returns an inline SVG data URL.
    const svg = mod.renderWorkflowThumbnail(workflow as never);
    // Async path rasterises it to a PNG data URL.
    const png = await mod.renderWorkflowThumbnailPng(workflow as never);
    return { svg: svg.slice(0, 32), png: png.slice(0, 32), pngLen: png.length };
  });

  expect(result.svg).toContain('data:image/svg+xml');
  // PNG data URLs start with the base64 of the PNG magic bytes (\x89PNG) → "iVBORw0".
  expect(result.png.startsWith('data:image/png;base64,iVBORw0')).toBe(true);
  expect(result.pngLen).toBeGreaterThan(256);
});
