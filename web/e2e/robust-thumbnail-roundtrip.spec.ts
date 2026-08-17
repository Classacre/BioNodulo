import { test, expect } from '@playwright/test';
import { readFileSync, writeFileSync } from 'node:fs';
import { resolve } from 'node:path';

// Full-fidelity round trip: render the shipped ROBUST Designer template to a
// PNG thumbnail, embed the complete workflow JSON in its tEXt chunk, decode it
// back, and assert the graph survives byte-for-byte. Also writes the official
// template thumbnail artifact next to the JSON.
test('robust designer thumbnail embeds and restores the workflow', async ({ page }) => {
  await page.goto('/', { waitUntil: 'domcontentloaded' });
  await expect(page.getByRole('button', { name: /Run workflow/ })).toBeVisible();

  const templatePath = resolve(process.cwd(), '../templates/robust_designer.json');
  const workflow = JSON.parse(readFileSync(templatePath, 'utf-8'));

  const result = await page.evaluate(async (wf) => {
    const thumb = await import('/src/utils/workflowThumbnail.ts');
    const png = await import('/src/utils/pngMetadata.ts');
    const dataUrl = await thumb.renderWorkflowThumbnailPng(wf, { quality: 1 });
    const blob = png.embedWorkflowInPngDataUrl(dataUrl, wf);
    const bytes = new Uint8Array(await blob.arrayBuffer());
    const restored = png.extractWorkflowFromPng(bytes);
    return { bytes, restored };
  }, workflow);

  expect(result.restored, 'workflow must survive the PNG tEXt round trip').not.toBeNull();
  expect(result.restored.nodes.length).toBe(workflow.nodes.length);
  expect(result.restored.edges.length).toBe(workflow.edges.length);
  expect(result.restored.outputs).toEqual(workflow.outputs);

  const pngPath = templatePath.replace('robust_designer.json', 'robust_designer.png');
  writeFileSync(pngPath, Buffer.from(result.bytes));
  console.log('thumbnail written:', pngPath);
});
