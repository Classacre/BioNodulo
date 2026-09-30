import { expect, test } from '@playwright/test';
import { execFileSync } from 'node:child_process';
import { existsSync, readFileSync } from 'node:fs';
import { resolve } from 'node:path';

const repoRoot = resolve(process.cwd(), '..');
const venvPython = resolve(repoRoot, process.platform === 'win32' ? '.venv/Scripts/python.exe' : '.venv/bin/python');
const python = process.env.BIONODULO_PYTHON || (existsSync(venvPython) ? venvPython : 'python');

// The browser still makes the real export/import requests and creates a real
// download. Only the server boundary is routed through the checked-in Python
// converters, so no local daemon or cloud account is required for this test.
const converterBridge = String.raw`
import json, sys, tempfile
from pathlib import Path
from bionodulo.workflow.export import export_workflow
from bionodulo.converter import import_from_snakemake, import_from_nextflow, import_from_cwl, import_from_galaxy
data = json.load(sys.stdin)
fmt = data['format']
try:
    if data['action'] == 'export':
        result = {'content': export_workflow(data['workflow'], fmt)}
    elif fmt == 'cwl':
        files = json.loads(data['content'])
        if not isinstance(files, dict) or 'workflow.cwl' not in files:
            raise ValueError('CWL bundle requires workflow.cwl')
        with tempfile.TemporaryDirectory(prefix='bionodulo-playwright-cwl-') as directory:
            root = Path(directory)
            for name, content in files.items():
                if not isinstance(name, str) or not isinstance(content, str):
                    raise ValueError('CWL bundle requires text content keyed by relative file paths')
                path = Path(name)
                if (path.is_absolute() or '..' in path.parts or '\\' in name or ':' in name
                    or (name not in {'workflow.cwl', 'bionodulo-roundtrip.json'}
                        and not (name.startswith('tools/') and len(path.parts) == 2))):
                    raise ValueError(f'Unsafe or unsupported CWL bundle path: {name}')
                target = root / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(content, encoding='utf-8')
            result = {'workflow': import_from_cwl(root / 'workflow.cwl')}
    else:
        importer = {'snakemake': import_from_snakemake, 'nextflow': import_from_nextflow, 'galaxy': import_from_galaxy}[fmt]
        result = {'workflow': importer(data['content'])}
except ValueError as error:
    result = {'error': str(error)}
print(json.dumps(result))
`;

function convert(payload: unknown): { content?: string; workflow?: unknown; error?: string } {
  return JSON.parse(execFileSync(python, ['-c', converterBridge], {
    cwd: repoRoot,
    input: JSON.stringify(payload),
    encoding: 'utf8',
    timeout: 20_000,
  })) as { content?: string; workflow?: unknown; error?: string };
}

const qcWorkflow = {
  id: 'original-workflow', version: '2.0', app: 'bionodulo', name: 'Portable QC', description: 'Round-trip fixture',
  nodes: [
    {
      id: 'qc', type: 'fastqc', position: [140, 180], params: { reads: 'sample.fastq', threads: 1 },
      node_info: { id: 'fastqc', display_name: 'FastQC', category: 'quality_control',
        input_types: { required: { reads: { type: 'FILE' } } }, return_names: ['report_dir'], return_types: ['FILE'],
        citation_urls: ['https://www.bioinformatics.babraham.ac.uk/projects/fastqc/'] },
    },
    {
      id: 'summary', type: 'multiqc', position: [440, 180], params: { filename: 'qc_report', title: 'Example QC', force: true },
      node_info: { id: 'multiqc', display_name: 'MultiQC', category: 'quality_control',
        input_types: { required: { reports: { type: 'FILE' } } }, return_names: ['report', 'data_dir'], return_types: ['FILE', 'FILE'],
        citation_dois: ['10.1093/bioinformatics/btw354'] },
    },
  ],
  edges: [{ id: 'qc-summary', from: { node: 'qc', output: 'report_dir' }, to: { node: 'summary', input: 'reports' } }],
  groups: [{ id: 'qc-group', name: 'QC', position: [100, 100], width: 500, height: 250, color: '#abcdef', collapsed: false }],
  outputs: {}, parameters: [{ name: 'sample', type: 'FILE', value: 'sample.fastq' }],
  provenance: { source: 'playwright-roundtrip' }, references: ['10.1093/bioinformatics/btw354'],
};

const cwlWorkflow = {
  ...qcWorkflow, name: 'Portable transform',
  nodes: [{
    id: 'filter', type: 'filter_rows', position: [150, 210], params: { column: 'quality', operator: '>', value: '20' },
    node_info: { id: 'filter_rows', display_name: 'Filter Rows', category: 'data_transform',
      input_types: { required: { table: { type: 'FILE' } } }, return_names: ['filtered_table'], return_types: ['FILE'],
    },
  }],
  edges: [],
};

test.beforeEach(async ({ context, page }, testInfo) => {
  await context.addInitScript(workflow => {
    localStorage.setItem('bionodulo.language', 'en');
    localStorage.setItem('bionodulo.settings', JSON.stringify({
      'bionodulo.getting_started.dismissed': true,
      'bionodulo.getting_started.show_on_startup': false,
    }));
    localStorage.setItem('bionodulo.local.workflows', JSON.stringify({ workflows: [workflow], activeIndex: 0 }));
  }, testInfo.title.includes('unchanged cwl export') ? cwlWorkflow : qcWorkflow);
  await page.route(url => url.pathname.startsWith('/api/'), async route => {
    const path = new URL(route.request().url()).pathname;
    if (path.endsWith('/workflow/export') || path.endsWith('/workflow/import')) {
      const request = route.request().postDataJSON();
      const result = convert({
        action: path.endsWith('/workflow/export') ? 'export' : 'import',
        format: request.format || request.source,
        workflow: request.workflow,
        content: request.content,
      });
      await route.fulfill({ status: result.error ? 400 : 200, contentType: 'application/json',
        body: JSON.stringify(result.error ? { detail: result.error } : result) });
      return;
    }
    const body = path.endsWith('/config') ? { cloudMode: false, editorMode: false }
      : path.endsWith('/host_status') ? { ready: true }
      : path.endsWith('/workflow/validate') ? { valid: true, errors: [] }
      : path.endsWith('/object_info') ? {} : {};
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(body) });
  });
  await page.goto('/', { waitUntil: 'domcontentloaded' });
});

for (const [label, extension, format] of [
  ['Snakemake', '.smk', 'snakemake'],
  ['Nextflow', '.nf', 'nextflow'],
  ['CWL bundle (.json)', '.cwl-bundle.json', 'cwl'],
  ['Galaxy (.ga)', '.ga', 'galaxy'],
] as const) {
  test(`downloads and reimports an unchanged ${format} export`, async ({ page }) => {
    test.setTimeout(60_000);
    await page.getByRole('button', { name: /Export workflow/ }).click();
    const exportDialog = page.getByRole('dialog', { name: 'Export workflow' });
    await expect(exportDialog).toBeVisible();
    await exportDialog.getByRole('button', { name: label, exact: true }).click();
    await exportDialog.getByRole('button', { name: 'Generate' }).click();
    await expect(exportDialog.getByRole('textbox')).toBeVisible();
    expect(await exportDialog.getByRole('textbox').inputValue({ timeout: 5000 })).not.toBe('');
    const downloadPromise = page.waitForEvent('download');
    await exportDialog.getByRole('button', { name: 'Download' }).click();
    const download = await downloadPromise;
    expect(download.suggestedFilename()).toBe(`${format === 'cwl' ? 'Portable transform' : 'Portable QC'}${extension}`);
    const content = readFileSync((await download.path())!, 'utf8');
    expect(content.length).toBeGreaterThan(100);
    if (format === 'cwl') {
      const files = JSON.parse(content) as Record<string, string>;
      expect(Object.keys(files)).toEqual(expect.arrayContaining(['workflow.cwl', 'tools/filter.cwl', 'bionodulo-roundtrip.json']));
    } else if (format === 'galaxy') {
      expect(JSON.parse(content)).toHaveProperty('bionodulo_roundtrip');
    } else {
      expect(content).toContain('BIONODULO_ROUNDTRIP_V1');
    }
    await exportDialog.getByRole('button', { name: 'Close' }).click();
    await page.keyboard.press('Control+i');
    const importDialog = page.getByRole('dialog', { name: 'Import workflow' });
    await expect(importDialog).toBeVisible();
    await importDialog.locator('input[type=file]').setInputFiles({ name: download.suggestedFilename(), mimeType: 'text/plain', buffer: Buffer.from(content) });
    await expect(importDialog.getByRole('textbox', { name: 'Workflow source' })).toHaveValue(content);
    await importDialog.getByRole('button', { name: 'Import', exact: true }).click();
    await expect(importDialog).not.toBeVisible();
    await page.getByRole('button', { name: /Export workflow/ }).click();
    const restoredDialog = page.getByRole('dialog', { name: 'Export workflow' });
    await restoredDialog.getByLabel('JSON only (skip PNG wrapper)').check();
    const restored = JSON.parse(await restoredDialog.getByRole('textbox').inputValue());
    const original = format === 'cwl' ? cwlWorkflow : qcWorkflow;
    expect(restored.name).toBe(original.name);
    expect(restored.nodes).toEqual(original.nodes);
    expect(restored.edges).toEqual(original.edges);
    expect(restored.groups).toEqual(original.groups);
    expect(restored.parameters).toEqual(original.parameters);
    expect(restored.provenance).toEqual(original.provenance);
    expect(restored.references).toEqual(original.references);
    await restoredDialog.getByRole('button', { name: 'Close' }).click();
  });
}

test('shows a converter rejection and offers no mislabeled CWL download', async ({ page }) => {
  await page.getByRole('button', { name: /Export workflow/ }).click();
  const dialog = page.getByRole('dialog', { name: 'Export workflow' });
  await dialog.getByRole('button', { name: 'CWL bundle (.json)' }).click();
  await dialog.getByRole('button', { name: 'Generate' }).click();
  await expect(dialog).toContainText("Cannot export unsupported node type 'fastqc' to CWL");
  await expect(dialog.getByRole('button', { name: 'Download' })).toHaveCount(0);
});

test('rejects a changed marked export with the converter detail visible', async ({ page }) => {
  const source = convert({ action: 'export', format: 'snakemake', workflow: qcWorkflow }).content!;
  const changed = source.replace('sample.fastq', 'changed.fastq');
  expect(changed).not.toBe(source);
  await page.keyboard.press('Control+i');
  const importDialog = page.getByRole('dialog', { name: 'Import workflow' });
  await importDialog.locator('input[type=file]').setInputFiles({
    name: 'changed.smk', mimeType: 'text/plain', buffer: Buffer.from(changed),
  });
  await importDialog.getByRole('button', { name: 'Import', exact: true }).click();
  const alert = page.getByRole('dialog', { name: 'Notice' });
  await expect(alert).toContainText('Exported source or BioNodulo round-trip metadata changed');
  await expect(alert.getByRole('button', { name: 'OK' })).toBeFocused();
  await page.keyboard.press('Tab');
  await expect(alert.getByRole('button', { name: 'OK' })).toBeFocused();
  await page.keyboard.press('Shift+Tab');
  await expect(alert.getByRole('button', { name: 'OK' })).toBeFocused();
  await page.keyboard.press('Escape');
  await expect(alert).not.toBeVisible();
  await expect(importDialog).toBeVisible();
  await expect.poll(() => importDialog.evaluate(element => element.contains(document.activeElement))).toBe(true);
  await importDialog.getByRole('button', { name: 'Import', exact: true }).click();
  await expect(alert).toContainText('Exported source or BioNodulo round-trip metadata changed');
  await alert.getByRole('button', { name: 'OK' }).click();
  await expect(importDialog).toBeVisible();
  await expect.poll(() => importDialog.evaluate(element => element.contains(document.activeElement))).toBe(true);
});

test('keeps header actions and Run options visible after closing Export at narrow and desktop widths', async ({ page }) => {
  for (const width of [508, 1280]) {
    await page.setViewportSize({ width, height: 590 });
    const exportButton = page.getByRole('button', { name: /Export workflow/ });
    await exportButton.click();
    await page.getByRole('dialog', { name: 'Export workflow' }).getByRole('button', { name: 'Close' }).click();
    await expect(exportButton).toBeFocused();
    const bounds = await page.evaluate(() => {
      const shell = document.querySelector('.app-shell')!;
      const header = document.querySelector('.topbar')!;
      const rail = document.querySelector('.left-rail')!;
      const canvas = document.querySelector('.main-canvas')!;
      return {
        scrollLeft: shell.scrollLeft,
        header: header.getBoundingClientRect().toJSON(),
        rail: rail.getBoundingClientRect().toJSON(),
        canvas: canvas.getBoundingClientRect().toJSON(),
      };
    });
    expect(bounds.scrollLeft).toBe(0);
    expect(bounds.header.x).toBeGreaterThanOrEqual(0);
    expect(bounds.header.right).toBeLessThanOrEqual(width);
    expect(bounds.rail.x).toBeGreaterThanOrEqual(0);
    expect(bounds.canvas.x).toBeGreaterThanOrEqual(bounds.rail.right);
    const options = page.getByRole('button', { name: 'Run options' });
    await options.click();
    const menu = page.getByRole('menu');
    await expect(menu).toBeVisible();
    const menuBounds = await menu.boundingBox();
    expect(menuBounds!.x).toBeGreaterThanOrEqual(0);
    expect(menuBounds!.x + menuBounds!.width).toBeLessThanOrEqual(width);
    await options.click();
  }
});
