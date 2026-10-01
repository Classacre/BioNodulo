import { test, expect, type Page } from '@playwright/test';
import { readFileSync } from 'node:fs';
import type { CloudWorkflow } from '../src/mcp/draft';

const metadata = JSON.parse(readFileSync(new URL('../../bionodulo/nodes/node_metadata.json', import.meta.url), 'utf8'));
const catalog = Object.fromEntries(['input_file', 'normalize_data', 'extract_columns', 'string_primitive', 'write_file'].map(id => [id, metadata[id]]));
type Args = Record<string, any>;
async function fixture(page: Page, options: { assetOrigin?: string; awaitReady?: boolean; workflow?: CloudWorkflow; allowForms?: boolean } = {}) {
  const calls: { name: string; args: Args }[] = [];
  const transport: string[] = [];
  const protocol: { method: string; params: Args }[] = [];
  const network: string[] = [];
  let workflow: CloudWorkflow = {
    id: '11111111-1111-4111-8111-111111111111', name: 'Counts workflow', updatedAt: '2026-10-01T00:00:01.000Z',
    definition: { version: '1.0', app: 'BioNodulo', name: 'Counts workflow', description: '', groups: [], outputs: {}, nodes: [
      { id: 'input', type: 'input_file', position: [20, 50], params: { file: 'uploads/team-fixture/id__counts.tsv', source: 'auto' } },
      { id: 'normalize', type: 'normalize_data', position: [350, 50], params: { method: 'cpm', log_transform: false } },
    ], edges: [{ id: 'e1', from: { node: 'input', output: 'file' }, to: { node: 'normalize', input: 'table' } }] },
  };
  if (options.workflow) workflow = structuredClone(options.workflow);
  let revision = 1;
  let failSubmit = false;
  page.on('request', request => {
    const url = new URL(request.url());
    if (url.pathname.startsWith('/api/') || /clerk\./.test(url.hostname) || url.pathname === '/src/App.tsx' || /\/(?:build\/)?assets\/App-/.test(url.pathname)) network.push(request.url());
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
  await page.exposeFunction('fixtureTransport', (method: string, params: Args) => { transport.push(method); protocol.push({ method, params }); });
  const index = await page.request.get('/');
  let resourceHtml = (await index.text()).replace('<html', '<html data-mcp-app="true"');
  if (options.assetOrigin) {
    // Match the website resource's HTML-only rewriting. In particular, do NOT
    // inject <base> or rewrite compiled JS: either would mask an absolute Vite
    // preload base resolving dynamic CSS against the resource's host origin.
    resourceHtml = resourceHtml
      .replace(/((?:src|href)=")\/build\//g, `$1${options.assetOrigin}/build/`)
      .replace(/((?:src|href)=")\.\/assets\//g, `$1${options.assetOrigin}/build/assets/`);
  }
  await page.route('**/__mcp_resource', route => route.fulfill({ contentType: 'text/html', body: resourceHtml }));
  await page.route('**/__mcp_host', route => route.fulfill({ contentType: 'text/html', body: `<!doctype html><html><body style="margin:0"><iframe title="BioNodulo MCP app" sandbox="allow-scripts allow-same-origin allow-downloads${options.allowForms ? ' allow-forms' : ''}" src="/__mcp_resource" style="border:0;width:100%;height:100vh"></iframe><script>
    addEventListener('message', async event => {
      const message = event.data;
      if (!message || message.jsonrpc !== '2.0' || event.source !== document.querySelector('iframe').contentWindow) return;
      const reply = result => event.source.postMessage({jsonrpc:'2.0',id:message.id,result}, '*');
      if (message.method === 'ui/initialize') reply({protocolVersion:message.params.protocolVersion,hostInfo:{name:'Playwright MCP host',version:'1.0'},hostCapabilities:{serverTools:{},message:{text:{}},updateModelContext:{structuredContent:{}},openLinks:{}},hostContext:{theme:'light',availableDisplayModes:['inline','fullscreen']}});
      else if (message.method === 'ui/notifications/initialized') event.source.postMessage({jsonrpc:'2.0',method:'ui/notifications/tool-result',params:{content:[],structuredContent:{workflow_id:'11111111-1111-4111-8111-111111111111',team_id:'team-fixture',capabilities:{}}}}, '*');
      else if (message.method === 'tools/call') {
        try { const value = await window.fixtureMcpTool(message.params.name, message.params.arguments); reply({content:[{type:'text',text:JSON.stringify(value)}],structuredContent:value}); }
        catch(error) { reply({isError:true,content:[{type:'text',text:error.message}]}); }
      } else if (message.id !== undefined) { await window.fixtureTransport(message.method, message.params); reply(message.method === 'ui/request-display-mode' ? {mode:message.params.mode} : {}); }
    });
  </script></body></html>` }));
  await page.goto('/__mcp_host');
  const app = page.frameLocator('iframe');
  if (options.awaitReady !== false) {
    await expect(app.getByText('Host connected', { exact: true })).toBeVisible();
    await expect(app.getByLabel('Workflow name')).toHaveValue(workflow.name);
    await expect(app.locator('.react-flow__node')).toHaveCount(2);
  }
  return { app, calls, transport, protocol, network, resourceHtml, getWorkflow: () => workflow, externalEdit: (name: string, definition = workflow.definition) => { workflow = { ...workflow, name, definition, updatedAt: `2026-10-01T00:00:${String(++revision).padStart(2, '0')}.000Z` }; }, failSubmission: () => { failSubmit = true; } };
}

for (const allowForms of [false, true]) {
  test(`host assistant sends context and messages ${allowForms ? 'with' : 'without'} sandbox form permission`, async ({ page }) => {
    const formErrors: string[] = [];
    page.on('console', message => { if (message.type() === 'error') formErrors.push(message.text()); });
    const f = await fixture(page, { allowForms });
    expect((await page.locator('iframe').getAttribute('sandbox'))?.includes('allow-forms')).toBe(allowForms);
    const prompt = f.app.getByLabel('Host assistant');
    const send = f.app.getByRole('button', { name: 'Send', exact: true });
    const expectedMessages: Args[] = [];
    for (const action of ['input-enter', 'button-enter', 'button-click']) {
      const text = `Explain this workflow via ${action}`;
      await prompt.fill(`  ${text}  `);
      await expect(send).toBeEnabled();
      if (action === 'input-enter') await prompt.press('Enter');
      else if (action === 'button-enter') { await send.focus(); await page.keyboard.press('Enter'); }
      else await send.click();
      expectedMessages.push({ role: 'user', content: [{ type: 'text', text }] });
      await expect.poll(() => ({
        messages: f.protocol.filter(item => item.method === 'ui/message').map(item => item.params),
        formErrors,
      })).toEqual({ messages: expectedMessages, formErrors: [] });
      await expect(prompt).toHaveValue('');
      await expect(f.app.getByText('Sent to your host assistant.', { exact: false })).toBeVisible();
      const index = f.protocol.findLastIndex(item => item.method === 'ui/message');
      expect(f.protocol[index - 1]).toMatchObject({
        method: 'ui/update-model-context',
        params: { structuredContent: { workflow_id: '11111111-1111-4111-8111-111111111111', team_id: 'team-fixture' } },
      });
    }
    expect(f.network).toEqual([]);
  });
}

test('connected scalar inputs render real edges without stored UI promotion flags', async ({ page }) => {
  test.setTimeout(45_000);
  const definition = {
    version: '1.0', app: 'BioNodulo', name: 'Text output', description: '', groups: [], outputs: {},
    nodes: [
      { id: 'text', type: 'string_primitive', position: [20, 50], params: { value: 'MCP canvas regression' } },
      { id: 'output', type: 'write_file', position: [350, 50], params: { file_path: 'result.txt', format: 'text', encoding: 'utf-8' } },
    ],
    edges: [{ id: 'text-to-content', from: { node: 'text', output: 'value' }, to: { node: 'output', input: 'content' } }],
  };
  const f = await fixture(page, { workflow: {
    id: '11111111-1111-4111-8111-111111111111', name: 'Text output',
    updatedAt: '2026-10-01T00:00:01.000Z', definition,
  } });
  const target = f.app.locator('.react-flow__node[data-id="output"] .react-flow__handle.target[data-handleid="content"]');
  const assertConnected = async () => {
    await expect(target).toHaveCount(1);
    await expect(target).toBeVisible();
    await expect(target).toHaveClass(/connected/);
    const edge = f.app.locator('.react-flow__edge[data-id="text-to-content"] .react-flow__edge-path');
    await expect(edge).toBeVisible();
    // Counting an edge wrapper is insufficient: verify the SVG curve exists
    // and its endpoints really meet the canonical value/content handle pair.
    await expect.poll(() => edge.evaluate(element => {
      const path = element as SVGPathElement;
      const matrix = path.getScreenCTM()!;
      const length = path.getTotalLength();
      const endpoint = (distance: number) => {
        const point = path.getPointAtLength(distance);
        return new DOMPoint(point.x, point.y).matrixTransform(matrix);
      };
      const near = (point: DOMPoint, selector: string) => {
        const rect = element.ownerDocument.querySelector(selector)!.getBoundingClientRect();
        return Math.hypot(point.x - rect.x - rect.width / 2, point.y - rect.y - rect.height / 2) < 12;
      };
      const style = getComputedStyle(path);
      return length > 40 && style.stroke !== 'none' && Number.parseFloat(style.strokeWidth) > 0
        && near(endpoint(0), '.react-flow__node[data-id="text"] .react-flow__handle.source[data-handleid="value"]')
        && near(endpoint(length), '.react-flow__node[data-id="output"] .react-flow__handle.target[data-handleid="content"]');
    })).toBe(true);
  };
  await assertConnected();
  // External edits can add a handle without changing node dimensions. React
  // Flow must remeasure that handle when the edge returns after a remote poll.
  f.externalEdit('Text output disconnected', { ...definition, edges: [] });
  await expect(f.app.getByLabel('Workflow name')).toHaveValue('Text output disconnected', { timeout: 12000 });
  await expect(target).toHaveCount(0);
  await page.reload();
  await expect(f.app.getByLabel('Workflow name')).toHaveValue('Text output disconnected');
  await expect(target).toHaveCount(0);
  f.externalEdit('Text output reconnected', definition);
  await expect(f.app.getByLabel('Workflow name')).toHaveValue('Text output reconnected', { timeout: 12000 });
  await assertConnected();
  await f.app.getByRole('button', { name: 'Save', exact: true }).click();
  await expect(f.app.getByText('Workflow saved.', { exact: true })).toBeVisible();
  const saved = f.calls.find(call => call.name === 'update_workflow')!.args.definition;
  expect(saved.nodes).toEqual(definition.nodes);
  expect(saved.edges).toEqual(definition.edges);
  expect(f.network).toEqual([]);
  await page.screenshot({ path: 'test-results/mcp-workbench-scalar-edge.png', fullPage: true });
});

test('production MCP resource loads dynamic canvas assets from a separate origin', async ({ page }, testInfo) => {
  test.skip(testInfo.config.metadata.productionMcp !== true, 'Requires the dedicated production build/config and remote asset server.');
  const assetOrigin = 'http://127.0.0.1:5176';
  const hostOrigin = new URL(testInfo.project.use.baseURL!).origin;
  // Fulfilled host HTML has no network address-space classification. Permit
  // this fixture to reach its loopback asset server; normal CORS still applies.
  await page.context().grantPermissions(['local-network-access'], { origin: hostOrigin });
  const hostAssets: string[] = [];
  const loadedStyles: string[] = [];
  const assetFailures: string[] = [];
  const pageErrors: string[] = [];
  const consoleErrors: string[] = [];
  const isAsset = (url: URL) => /\/(?:build\/)?assets\//.test(url.pathname);
  page.on('pageerror', error => pageErrors.push(error.message));
  page.on('console', message => { if (message.type() === 'error') consoleErrors.push(message.text()); });
  page.on('request', request => {
    const url = new URL(request.url());
    if (url.origin === hostOrigin && isAsset(url)) hostAssets.push(url.href);
  });
  page.on('requestfailed', request => {
    if (isAsset(new URL(request.url()))) assetFailures.push(`${request.url()}: ${request.failure()?.errorText}`);
  });
  page.on('response', response => {
    const url = new URL(response.url());
    if (isAsset(url) && !response.ok()) assetFailures.push(`${url.href}: HTTP ${response.status()}`);
    if (isAsset(url) && url.pathname.endsWith('.css') && response.ok()) loadedStyles.push(url.href);
  });
  // The host has no copies of editor assets. A wrong-origin preload must fail,
  // even if the local Vite preview would otherwise serve that path by accident.
  await page.route(url => url.origin === hostOrigin && isAsset(url), route => route.fulfill({ status: 404, body: 'MCP host does not serve BioNodulo assets' }));
  // Shared fonts are optional; keep this regression entirely on local servers.
  await page.route('https://fonts.googleapis.com/**', route => route.fulfill({ contentType: 'text/css', body: '' }));
  const f = await fixture(page, { assetOrigin, awaitReady: false });
  expect(f.resourceHtml).not.toMatch(/<base\b/i);
  expect(f.resourceHtml).toContain(`${assetOrigin}/build/assets/`);
  await expect(async () => {
    expect({ pageErrors, hostAssets, assetFailures, consoleErrors }, 'All production preloads must load from the remote asset origin without errors').toEqual({ pageErrors: [], hostAssets: [], assetFailures: [], consoleErrors: [] });
    await expect(f.app.locator('.react-flow__node')).toHaveCount(2, { timeout: 500 });
  }).toPass({ timeout: 12_000 });
  await expect(f.app.locator('.react-flow__edge')).toHaveCount(1);
  await expect(f.app.getByText('Host connected', { exact: true })).toBeVisible();
  // This rule comes from the dynamically imported native React Flow CSS.
  await expect(f.app.locator('.react-flow__pane')).toHaveCSS('position', 'absolute');
  const initialStyles = [...f.resourceHtml.matchAll(/href="([^"]+\.css)"/g)].map(match => match[1]);
  expect(loadedStyles.filter(url => !initialStyles.includes(url)), 'Canvas CSS must actually load after the HTML stylesheet set').not.toEqual([]);
  expect(loadedStyles.every(url => new URL(url).origin === assetOrigin)).toBe(true);
  expect(assetFailures).toEqual([]);
  expect(pageErrors).toEqual([]);
  expect(consoleErrors).toEqual([]);
  expect(hostAssets).toEqual([]);
  expect(f.network).toEqual([]);
});

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
