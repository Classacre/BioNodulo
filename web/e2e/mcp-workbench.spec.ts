import { test, expect, type Page } from '@playwright/test';
import { readFileSync } from 'node:fs';
import type { CloudWorkflow } from '../src/mcp/draft';

const metadata = JSON.parse(readFileSync(new URL('../../bionodulo/nodes/node_metadata.json', import.meta.url), 'utf8'));
const catalog = Object.fromEntries(['input_file', 'normalize_data', 'extract_columns'].map(id => [id, metadata[id]]));
type Args = Record<string, any>;
async function fixture(page: Page) {
  const calls: { name: string; args: Args }[] = [];
  const transport: string[] = [];
  const network: string[] = [];
  let workflow: CloudWorkflow = {
    id: '11111111-1111-4111-8111-111111111111', name: 'Counts workflow', updatedAt: '2026-10-01T00:00:01.000Z',
    definition: { version: '1.0', app: 'BioNodulo', name: 'Counts workflow', description: '', groups: [], outputs: {}, nodes: [
      { id: 'input', type: 'input_file', position: [20, 50], params: { file: 'uploads/team-fixture/id__counts.tsv', source: 'auto' } },
      { id: 'normalize', type: 'normalize_data', position: [350, 50], params: { method: 'cpm', log_transform: false } },
    ], edges: [{ id: 'e1', from: { node: 'input', output: 'file' }, to: { node: 'normalize', input: 'table' } }] },
  };
  let revision = 1;
  let failSubmit = false;
  page.on('request', request => {
    const url = new URL(request.url());
    if (url.pathname.startsWith('/api/') || /clerk\./.test(url.hostname) || url.pathname === '/src/App.tsx' || url.pathname.startsWith('/assets/App-')) network.push(request.url());
  });
  await page.exposeFunction('fixtureMcpTool', async (name: string, args: Args) => {
    calls.push({ name, args });
    switch (name) {
      case 'get_account_info': return { name: 'Fixture researcher', team: { id: 'team-fixture', name: 'Research team' } };
      case 'get_editor_catalog': return { catalog };
      case 'list_workflows': return { items: [workflow] };
      case 'get_workflow': return workflow;
      case 'update_workflow':
        if (args.expected_updated_at !== workflow.updatedAt) throw new Error('Workflow revision conflict (HTTP 409)');
        workflow = { ...workflow, name: args.name, definition: args.definition, updatedAt: `2026-10-01T00:00:${String(++revision).padStart(2, '0')}.000Z` }; return workflow;
      case 'create_workflow': workflow = { id: '22222222-2222-4222-8222-222222222222', name: args.name, definition: args.definition, updatedAt: '2026-10-01T00:01:00.000Z' }; return workflow;
      case 'validate_workflow': return { valid: true, errors: [], warnings: [] };
      case 'get_credit_balance': return { remaining: 194, plan: 'free' };
      case 'estimate_run_cost': return { allowed: args.compute?.vcpu === 1 && args.compute?.ramGb === 4, vcpu: 1, ramGb: 4, creditPerSecond: 0.00127, creditsPerHour: 5, caps: { maxVcpu: 4, maxRamGb: 16, allowsCustom: true, allowedProfiles: ['gpu'] } };
      case 'submit_run': if (failSubmit) throw new Error('Service temporarily unavailable (HTTP 502)'); return { runId: 'run-fixture', status: 'queued' };
      case 'get_run_status': return { id: 'run-fixture', status: 'completed', creditsUsed: 0.01, logs: 'INFO: Input completed [node:input]\nINFO: Normalize completed [node:normalize]' };
      case 'get_run_events': return { events: args.after_seq ? [] : [{ seq: 1, type: 'run.completed', payload: { status: 'completed' } }] };
      case 'get_run_outputs': return { outputs: [{ key: 'verified/counts.tsv', name: 'counts.tsv', size: 42, sha256: 'a'.repeat(64), url: 'https://outputs.example.org/counts.tsv?temporary=1' }] };
      case 'list_runs': return { items: [{ run: { id: 'run-fixture', status: 'completed' }, workflow: { name: 'Counts workflow' } }] };
      case 'list_files': return { items: [{ key: 'uploads/team-fixture/id__counts.tsv', name: 'counts.tsv', source: 'upload', size: 42 }, { key: 'uploads/team-fixture/pending__unverified.tsv', name: 'unverified.tsv', source: 'upload', size: 40, verificationPending: true }] };
      case 'export_workflow': return { format: args.format, filename: 'workflow.json', content: JSON.stringify(args.workflow), portability: { supported: true } };
      case 'import_workflow': return { workflow: workflow.definition, warnings: ['Review imported command parameters.'] };
      default: throw new Error(`Unexpected tool ${name}`);
    }
  });
  await page.exposeFunction('fixtureTransport', (method: string) => { transport.push(method); });
  const index = await page.request.get('/');
  const resourceHtml = (await index.text()).replace('<html', '<html data-mcp-app="true"');
  await page.route('**/__mcp_resource', route => route.fulfill({ contentType: 'text/html', body: resourceHtml }));
  await page.route('**/__mcp_host', route => route.fulfill({ contentType: 'text/html', body: `<!doctype html><html><body style="margin:0"><iframe title="BioNodulo MCP app" src="/__mcp_resource" style="border:0;width:100%;height:100vh"></iframe><script>
    addEventListener('message', async event => {
      const message = event.data;
      if (!message || message.jsonrpc !== '2.0' || event.source !== document.querySelector('iframe').contentWindow) return;
      const reply = result => event.source.postMessage({jsonrpc:'2.0',id:message.id,result}, '*');
      if (message.method === 'ui/initialize') reply({protocolVersion:message.params.protocolVersion,hostInfo:{name:'Playwright MCP host',version:'1.0'},hostCapabilities:{serverTools:{},message:{text:{}},updateModelContext:{structuredContent:{}},openLinks:{}},hostContext:{theme:'light',availableDisplayModes:['inline','fullscreen']}});
      else if (message.method === 'ui/notifications/initialized') event.source.postMessage({jsonrpc:'2.0',method:'ui/notifications/tool-result',params:{content:[],structuredContent:{workflow_id:'11111111-1111-4111-8111-111111111111',team_id:'team-fixture',capabilities:{}}}}, '*');
      else if (message.method === 'tools/call') {
        try { const value = await window.fixtureMcpTool(message.params.name, message.params.arguments); reply({content:[{type:'text',text:JSON.stringify(value)}],structuredContent:value}); }
        catch(error) { reply({isError:true,content:[{type:'text',text:error.message}]}); }
      } else if (message.id !== undefined) { await window.fixtureTransport(message.method); reply(message.method === 'ui/request-display-mode' ? {mode:message.params.mode} : {}); }
    });
  </script></body></html>` }));
  await page.goto('/__mcp_host');
  const app = page.frameLocator('iframe');
  await expect(app.getByText('Host connected', { exact: true })).toBeVisible();
  await expect(app.getByLabel('Workflow name')).toHaveValue('Counts workflow');
  await expect(app.locator('.react-flow__node')).toHaveCount(2);
  return { app, calls, transport, network, getWorkflow: () => workflow, externalEdit: (name: string) => { workflow = { ...workflow, name, updatedAt: `2026-10-01T00:00:${String(++revision).padStart(2, '0')}.000Z` }; }, failSubmission: () => { failSubmit = true; } };
}

test('real canvas editing uses guarded MCP saves and host assistant without direct account APIs', async ({ page }) => {
  const f = await fixture(page);
  await expect(f.app.locator('.react-flow__edge')).toHaveCount(1);
  await f.app.getByLabel('Search nodes').fill('extract');
  await f.app.getByRole('button', { name: /^Add / }).click();
  await expect(f.app.locator('.react-flow__node')).toHaveCount(3);
  await f.app.getByRole('button', { name: 'Auto layout', exact: true }).click();
  await f.app.getByLabel('Workflow name').fill('Reviewed counts workflow');
  await f.app.getByRole('button', { name: 'Save', exact: true }).click();
  await expect(f.app.getByText('Workflow saved.', { exact: true })).toBeVisible();
  const update = f.calls.find(call => call.name === 'update_workflow')!;
  expect(update.args.expected_updated_at).toBe('2026-10-01T00:00:01.000Z');
  expect(update.args.definition.nodes).toHaveLength(3);
  expect(update.args.team_id).toBe('team-fixture');
  await f.app.getByLabel('Host assistant').fill('Explain the selected workflow and its references');
  await f.app.getByRole('button', { name: 'Send', exact: true }).click();
  await expect.poll(() => f.transport).toContain('ui/message');
  expect(f.transport).toContain('ui/update-model-context');
  await f.app.getByRole('button', { name: 'Fullscreen', exact: true }).click();
  await expect.poll(() => f.transport).toContain('ui/request-display-mode');
  expect(f.network).toEqual([]);
  await page.screenshot({ path: 'test-results/mcp-workbench-desktop.png', fullPage: true });
});

test('external edits refresh clean workflows but preserve a dirty local draft', async ({ page }) => {
  const f = await fixture(page);
  f.externalEdit('AI saved workflow');
  await expect(f.app.getByLabel('Workflow name')).toHaveValue('AI saved workflow', { timeout: 12000 });
  await f.app.getByLabel('Workflow name').fill('My unsaved workflow');
  f.externalEdit('Another AI edit');
  await expect(f.app.getByText('The saved workflow changed while you were editing.', { exact: false })).toBeVisible({ timeout: 12000 });
  await expect(f.app.getByLabel('Workflow name')).toHaveValue('My unsaved workflow');
  await expect(f.app.getByRole('button', { name: 'Save', exact: true })).toBeDisabled();
  await f.app.getByRole('button', { name: 'Save draft as copy' }).click();
  await expect(f.app.getByText('Workflow saved.', { exact: true })).toBeVisible();
  expect(f.calls.find(c => c.name === 'create_workflow')?.args.client_request_id).toMatch(/^[0-9a-f-]{36}$/);
});

test('paid runs require explicit confirmation and show committed output after a fast completion', async ({ page }) => {
  const f = await fixture(page);
  await f.app.getByRole('button', { name: 'Review run', exact: true }).click();
  await expect(f.app.getByRole('dialog', { name: 'Confirm compute credit use' })).toBeVisible();
  await expect(f.app.getByText('194 credits', { exact: true })).toBeVisible();
  expect(f.calls.filter(c => c.name === 'submit_run')).toHaveLength(0);
  await f.app.getByRole('button', { name: 'Confirm and start run' }).click();
  await expect(f.app.getByText('Run · completed', { exact: true })).toBeVisible();
  await expect(f.app.getByRole('button', { name: 'counts.tsv', exact: true })).toBeVisible();
  const submissions = f.calls.filter(c => c.name === 'submit_run');
  expect(submissions).toHaveLength(1);
  expect(submissions[0].args).toMatchObject({ confirm_credit_use: true, compute: { vcpu: 1, ramGb: 4 }, inputs: { artifacts: { 'uploads/team-fixture/id__counts.tsv': { uploadKey: 'uploads/team-fixture/id__counts.tsv', kind: 'file' } } } });
  expect(f.network).toEqual([]);
});

test('uncertain paid submissions are not retried', async ({ page }) => {
  const f = await fixture(page); f.failSubmission();
  await f.app.getByRole('button', { name: 'Review run', exact: true }).click();
  await f.app.getByRole('button', { name: 'Confirm and start run' }).click();
  await expect(f.app.getByRole('alert')).toContainText('Submission was not retried');
  await page.waitForTimeout(1000);
  expect(f.calls.filter(c => c.name === 'submit_run')).toHaveLength(1);
  await expect(f.app.getByRole('button', { name: 'Confirm and start run' })).toHaveCount(0);
});

test('files use verified upload keys, exports use MCP, and narrow layout remains usable', async ({ page }) => {
  const f = await fixture(page);
  await f.app.getByRole('button', { name: 'files', exact: true }).click();
  await expect(f.app.getByRole('button', { name: 'Use as input' })).toHaveCount(1);
  await expect(f.app.getByRole('button', { name: 'Verify upload' })).toHaveCount(1);
  await f.app.getByRole('button', { name: 'Use as input' }).click();
  await expect(f.app.locator('.react-flow__node')).toHaveCount(3);
  await f.app.getByRole('button', { name: 'Export / references' }).click();
  await f.app.getByRole('button', { name: 'Generate', exact: true }).click();
  await expect(f.app.getByLabel('Workflow content')).toContainText('uploads/team-fixture/id__counts.tsv');
  expect(f.calls.filter(c => c.name === 'export_workflow')).toHaveLength(1);
  await page.setViewportSize({ width: 430, height: 850 });
  await f.app.getByRole('dialog').getByRole('button', { name: 'Close', exact: true }).click();
  await f.app.getByRole('button', { name: 'Library', exact: true }).click();
  await expect(f.app.getByLabel('Host assistant')).toBeVisible();
  await expect(f.app.getByLabel('Workflow canvas')).toBeVisible();
  await page.screenshot({ path: 'test-results/mcp-workbench-narrow.png', fullPage: true });
});
