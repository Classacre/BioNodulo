import { test, expect, type Page } from '@playwright/test';
import { readFileSync } from 'node:fs';

// The MCP iframe uses the production host protocol. Only this in-memory
// fixture handles account/editor traffic; a direct browser API request fails.
const metadata = JSON.parse(readFileSync(new URL('../../bionodulo/nodes/node_metadata.json', import.meta.url), 'utf8'));
const catalog = Object.fromEntries(
  ['input_file', 'normalize_data', 'extract_columns', 'string_primitive', 'write_file']
    .map(id => [id, metadata[id]]),
);
const workflowId = '11111111-1111-4111-8111-111111111111';
const teamId = '22222222-2222-4222-8222-222222222222';
const userId = '33333333-3333-4333-8333-333333333333';
const account = { id: userId, name: 'Fixture researcher', email: 'researcher@example.org', team: { id: teamId, name: 'Research team' } };
type Json = Record<string, any>;
type CloudCall = { surface: string; path: string; method: string; body?: any; team_id?: string };

function initialRow() {
  return {
    id: workflowId, name: 'Counts workflow', description: '', updatedAt: '2026-10-01T00:00:01.000Z',
    definition: {
      version: '2.0', app: 'bionodulo', name: 'Counts workflow', description: '', groups: [], outputs: {},
      nodes: [
        { id: 'input', type: 'input_file', position: [20, 50], params: { file: 'uploads/team-fixture/id__counts.tsv', source: 'auto' } },
        { id: 'normalize', type: 'normalize_data', position: [350, 50], params: { method: 'cpm', log_transform: false } },
      ],
      edges: [{ id: 'e1', from: { node: 'input', output: 'file' }, to: { node: 'normalize', input: 'table' } }],
    },
  };
}

async function fixture(page: Page, options: { assetOrigin?: string; awaitReady?: boolean; allowForms?: boolean; initialRunId?: string } = {}) {
  const calls: { name: string; args: Json }[] = [];
  const requests: CloudCall[] = [];
  const unknown: string[] = [];
  const browserApi: string[] = [];
  const browserSockets: string[] = [];
  const protocol: { method: string; params: Json }[] = [];
  let row = initialRow();
  const priorRows = new Map<string, ReturnType<typeof initialRow>>();
  let revision = 1;
  let rejectNextSave = false;
  let rejectNextSubmit = false;
  let runReads = 0;
  const cloudFiles = [{ key: 'uploads/team-fixture/id__counts.tsv', name: 'counts.tsv', size: 42, updatedAt: '2026-10-01T00:00:00Z', url: 'https://outputs.example.org/counts.tsv' }];

  await page.context().addInitScript(() => {
    localStorage.setItem('bionodulo.language', 'en');
    localStorage.setItem('bionodulo.settings', JSON.stringify({
      'bionodulo.getting_started.dismissed': true,
      'bionodulo.getting_started.show_on_startup': false,
    }));
  });
  page.on('websocket', socket => browserSockets.push(socket.url()));
  await page.route(url => url.pathname.startsWith('/api/') || /clerk\./.test(url.hostname), route => {
    browserApi.push(route.request().url());
    return route.fulfill({ status: 599, body: 'Direct API traffic is forbidden inside MCP' });
  });
  await page.route('https://upload.example.org/**', route => route.fulfill({ status: 200, headers: { 'access-control-allow-origin': '*', 'access-control-allow-methods': 'PUT, OPTIONS', 'access-control-allow-headers': 'content-type' }, body: '' }));

  const json = (body: unknown, status = 200) => ({ status, body, content_type: 'application/json' });
  const envelope = (data: unknown, status = 200) => json({ success: status < 400, data }, status);
  const handle = (request: CloudCall) => {
    requests.push(request);
    const { surface, method } = request;
    const url = new URL(request.path, 'https://bionodulo.example');
    const path = url.pathname;
    const body = request.body ?? {};
    if (surface === 'editor') {
      if (method === 'GET' && path === '/api/config') return json({ cloudMode: true, editorMode: true, user: account, team: account.team, plan: 'free', credits: { remaining: 194 }, accountUrl: null, clerkPublishableKey: null, oauth: null });
      if (method === 'GET' && path === '/api/object_info') return json(catalog);
      if (method === 'GET' && path === '/api/settings') return json({});
      if (method === 'GET' && path === '/api/registry/nodes') return json(catalog);
      if (method === 'POST' && path === '/api/manager/resolve') return json({ nodes: [], errors: [], warnings: [] });
      if (method === 'POST' && path === '/api/workflow/validate') return json({ valid: true, errors: [], warnings: [] });
      if (method === 'POST' && path === '/api/workflow/export') return json({ format: body.format, filename: 'workflow.json', content: JSON.stringify(body.workflow), portability: { supported: true } });
      if (method === 'POST' && path === '/api/workflow/import') return json({ workflow: row.definition, warnings: ['Review imported parameters.'] });
    }
    if (surface === 'website') {
      if (method === 'GET' && path === '/api/me') return envelope(account);
      if (method === 'GET' && path === '/api/workflows') return envelope([...priorRows.values(), row].map(item => ({ id: item.id, name: item.name, description: item.description, updatedAt: item.updatedAt })));
      if (method === 'GET' && path.startsWith('/api/workflows/')) {
        const requestedId = path.slice('/api/workflows/'.length);
        if (requestedId === row.id) return envelope(row);
        if (priorRows.has(requestedId)) return envelope(priorRows.get(requestedId));
      }
      if (method === 'PUT' && path === `/api/workflows/${row.id}`) {
        if (rejectNextSave) { rejectNextSave = false; return json({ success: false, error: 'Workflow revision conflict' }, 409); }
        if (body.expectedUpdatedAt && body.expectedUpdatedAt !== row.updatedAt) return json({ success: false, error: 'Workflow revision conflict' }, 409);
        row = { ...row, name: body.name ?? row.name, description: body.description ?? row.description, definition: body.definition ?? row.definition, updatedAt: `2026-10-01T00:00:${String(++revision).padStart(2, '0')}.000Z` };
        return envelope(row);
      }
      if (method === 'POST' && path === '/api/workflows') {
        priorRows.set(row.id, row);
        row = { ...row, id: '44444444-4444-4444-8444-444444444444', name: body.name, definition: body.definition ?? row.definition, updatedAt: '2026-10-01T00:01:00.000Z' };
        return envelope(row, 201);
      }
      if (method === 'GET' && path === '/api/billing/credits') return json({ remaining: 194, monthlyCredits: 200, usedCredits: 6, plan: 'free' });
      if (method === 'POST' && path === '/api/billing/estimate') return json({ allowed: true, vcpu: 1, ramGb: 4, creditPerSecond: 0.00127, creditsPerHour: 4.572, caps: { maxVcpu: 4, maxRamGb: 16, allowsCustom: true } });
      if (method === 'GET' && path === '/api/files') return envelope(cloudFiles);
      if (method === 'POST' && path === '/api/runs') {
        if (rejectNextSubmit) { rejectNextSubmit = false; return json({ success: false, error: 'Submission outcome unknown' }, 502); }
        return envelope({ runId: '55555555-5555-4555-8555-555555555555', dashboardUrl: 'https://bionodulo.example/runs/55555555-5555-4555-8555-555555555555' }, 202);
      }
      if (method === 'GET' && path === '/api/runs/55555555-5555-4555-8555-555555555555') {
        runReads += 1;
        return json({ id: '55555555-5555-4555-8555-555555555555', status: runReads < 2 ? 'running' : 'completed', logs: 'INFO: Input completed\nINFO: Normalize completed', errorMessage: null, outputLocation: null, durationMs: 1000, creditsUsed: 0.01, createdAt: '2026-10-01T00:00:00Z', completedAt: runReads < 2 ? null : '2026-10-01T00:00:01Z' });
      }
      if (method === 'GET' && path === '/api/runs/55555555-5555-4555-8555-555555555555/outputs') return envelope({ outputs: [{ key: 'outputs/55555555-5555-4555-8555-555555555555/result.tsv', name: 'result.tsv', size: 23, url: 'https://outputs.example.org/result.tsv' }] });
    }
    unknown.push(`${surface} ${method} ${path}`);
    return json({ success: false, error: `Unmocked ${surface} route: ${method} ${path}` }, 404);
  };

  await page.exposeFunction('fixtureMcpTool', async (name: string, args: Json) => {
    calls.push({ name, args });
    if (name === 'get_account_info') return account;
    if (name === 'get_credit_balance') return { remaining: 194, monthlyCredits: 200, usedCredits: 6, plan: 'free' };
    if (name === 'get_upload_url') return { url: 'https://upload.example.org/staged.tsv', key: 'uploads/team-fixture/id__staged.tsv' };
    if (name === 'complete_upload') {
      cloudFiles.push({ key: args.key, name: 'staged.tsv', size: 13, updatedAt: '2026-10-01T00:00:03Z', url: 'https://outputs.example.org/staged.tsv' });
      return { key: args.key, status: 'ready' };
    }
    if (name === 'cloud_editor_request') return handle(args as CloudCall);
    if (name === 'get_workflow') return args.workflow_id === row.id ? row : priorRows.get(args.workflow_id) ?? row;
    throw new Error(`Unexpected MCP tool ${name}`);
  });
  await page.exposeFunction('fixtureTransport', (method: string, params: Json) => protocol.push({ method, params }));

  const index = await page.request.get('/');
  await page.context().grantPermissions(['local-network-access'], { origin: new URL(index.url()).origin });
  let resourceHtml = (await index.text()).replace('<html', '<html data-mcp-app="true"').replace('</head>', '<meta name="bionodulo-upload-origins" content="https://upload.example.org"></head>');
  if (options.assetOrigin) {
    // Match the production resource's HTML-only rewrite, without a <base> tag.
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
      else if (message.method === 'ui/notifications/initialized') event.source.postMessage({jsonrpc:'2.0',method:'ui/notifications/tool-result',params:{content:[],structuredContent:{workflow_id:'${workflowId}',team_id:'${teamId}',${options.initialRunId ? `run_id:'${options.initialRunId}',` : ''}capabilities:{}}}}, '*');
      else if (message.method === 'tools/call') {
        try { const value = await window.fixtureMcpTool(message.params.name, message.params.arguments); reply({content:[{type:'text',text:JSON.stringify(value)}],structuredContent:value}); }
        catch(error) { reply({isError:true,content:[{type:'text',text:error.message}]}); }
      } else if (message.id !== undefined) { await window.fixtureTransport(message.method, message.params); reply(message.method === 'ui/request-display-mode' ? {mode:message.params.mode} : {}); }
    });
  </script></body></html>` }));
  await page.goto('/__mcp_host');
  const app = page.frameLocator('iframe');
  if (options.awaitReady !== false) {
    await expect(app.locator('.app-shell')).toBeVisible();
    await expect(app.locator('.workflow-tabs')).toContainText('Counts workflow');
    await expect(app.locator('.react-flow__node')).toHaveCount(2);
  }
  return {
    app, calls, requests, unknown, browserApi, browserSockets, protocol, resourceHtml,
    row: () => row,
    externalEdit: (name: string) => { row = { ...row, name, updatedAt: `2026-10-01T00:00:${String(++revision).padStart(2, '0')}.000Z` }; },
    conflictNextSave: () => { rejectNextSave = true; },
    failNextSubmission: () => { rejectNextSubmit = true; },
  };
}

test('MCP loads the full App shell through the host bridge without direct APIs or sockets', async ({ page }, testInfo) => {
  const f = await fixture(page);
  await expect(f.app.locator('.topbar')).toBeVisible();
  await expect(f.app.locator('nav.left-rail')).toBeVisible();
  await expect(f.app.locator('.workflow-tabs')).toBeVisible();
  await f.app.locator('nav.left-rail').getByRole('button', { name: /^Console/ }).click();
  await expect(f.app.locator('.bottom-console')).toBeVisible();
  await expect(f.app.locator('.mcp-workbench')).toHaveCount(0);
  expect(f.calls[0]?.name).toBe('get_account_info');
  expect(f.calls).toContainEqual({ name: 'get_credit_balance', args: { team_id: teamId } });
  expect(f.requests).toContainEqual(expect.objectContaining({ surface: 'editor', path: '/api/object_info', method: 'GET' }));
  expect(f.requests).toContainEqual(expect.objectContaining({ surface: 'website', path: '/api/workflows', method: 'GET' }));
  expect(f.browserApi).toEqual([]);
  expect(f.browserSockets).toEqual([]);
  expect(f.unknown).toEqual([]);
  await expect(f.app.locator('#bn-boot')).toHaveCount(0);
  await page.screenshot({ path: testInfo.outputPath('desktop-full-app.png') });
});

test('full App remains usable in a narrow host panel', async ({ page }, testInfo) => {
  await page.setViewportSize({ width: 430, height: 844 });
  const f = await fixture(page);
  await expect(f.app.locator('.topbar')).toBeVisible();
  await expect(f.app.locator('.react-flow__node')).toHaveCount(2);
  await expect(f.app.locator('#bn-boot')).toHaveCount(0);
  await page.screenshot({ path: testInfo.outputPath('narrow-full-app.png') });
  expect(f.browserApi).toEqual([]);
  expect(f.unknown).toEqual([]);
});

test('canvas changes use cloud autosave and preserve the full library', async ({ page }) => {
  const f = await fixture(page);
  await f.app.locator('nav.left-rail').getByRole('button', { name: /^Nodes/ }).click();
  await f.app.getByRole('combobox', { name: 'Search nodes' }).fill('normalize');
  await expect(f.app.locator('.rail-panel-body')).toContainText(/normalize/i);
  await f.app.locator('.workflow-tabs .wf-tab.active').dblclick();
  const name = f.app.locator('.workflow-tabs .wf-tab.active input');
  await name.fill('Reviewed counts workflow');
  await name.press('Enter');
  await expect.poll(() => f.requests.filter(r => r.surface === 'website' && r.method === 'PUT' && r.path === `/api/workflows/${workflowId}`).length, { timeout: 12_000 }).toBeGreaterThan(0);
  const save = f.requests.find(r => r.surface === 'website' && r.method === 'PUT' && r.path === `/api/workflows/${workflowId}`)!;
  expect(save.body).toMatchObject({ expectedUpdatedAt: '2026-10-01T00:00:01.000Z', expectedUserId: userId, expectedTeamId: teamId });
  expect(f.row().name).toBe('Reviewed counts workflow');
  expect(f.browserApi).toEqual([]);
  expect(f.unknown).toEqual([]);
});

test('remote revision conflict preserves the other editor\'s saved workflow', async ({ page }) => {
  const f = await fixture(page);
  f.externalEdit('Remote collaborator version');
  await f.app.locator('.workflow-tabs .wf-tab.active').dblclick();
  const name = f.app.locator('.workflow-tabs .wf-tab.active input');
  await name.fill('My conflicting edit');
  await name.press('Enter');
  await expect.poll(() => f.requests.filter(r => r.surface === 'website' && r.method === 'PUT' && r.path === `/api/workflows/${workflowId}`).length, { timeout: 12_000 }).toBeGreaterThan(0);
  expect(f.row().name).toBe('Remote collaborator version');
  await expect(f.app.locator('.app-shell')).toContainText(/conflict|failed|retry|save/i);
  expect(f.browserApi).toEqual([]);
  expect(f.unknown).toEqual([]);
});

test('a clean tab adopts a newer host workflow revision', async ({ page }) => {
  const f = await fixture(page);
  f.externalEdit('Host revised counts');
  await expect(f.app.locator('.workflow-tabs')).toContainText('Host revised counts', { timeout: 13_000 });
  expect(f.requests.filter(request => request.method === 'PUT' && request.path === `/api/workflows/${workflowId}`)).toEqual([]);
  expect(f.browserApi).toEqual([]);
  expect(f.unknown).toEqual([]);
});

test('a dirty tab offers Load latest after host revision changes', async ({ page }) => {
  const f = await fixture(page);
  const initialReads = f.calls.filter(call => call.name === 'get_workflow').length;
  await f.app.locator('.workflow-tabs .wf-tab.active').dblclick();
  const name = f.app.locator('.workflow-tabs .wf-tab.active input');
  await name.fill('Local draft');
  await name.press('Enter');
  f.externalEdit('Remote saved version');
  await expect.poll(() => f.calls.filter(call => call.name === 'get_workflow').length, { timeout: 13_000 }).toBeGreaterThan(initialReads);
  await expect(f.app.locator('.workflow-tabs')).toContainText('Local draft');
  await f.app.locator('.island-pill').click();
  await expect(f.app.getByRole('button', { name: 'Load latest' })).toBeVisible({ timeout: 13_000 });
  expect(f.row().name).toBe('Remote saved version');
  await f.app.getByRole('button', { name: 'Load latest' }).click();
  await expect(f.app.locator('.workflow-tabs')).toContainText('Remote saved version');
  expect(f.browserApi).toEqual([]);
  expect(f.unknown).toEqual([]);
});

test('full App export and structural import use the cloud editor adapter', async ({ page }) => {
  const f = await fixture(page);
  await f.app.getByRole('button', { name: /Export workflow/ }).click();
  const exportDialog = f.app.getByRole('dialog', { name: 'Export workflow' });
  await exportDialog.getByRole('button', { name: 'Snakemake', exact: true }).click();
  await exportDialog.getByRole('button', { name: 'Generate' }).click();
  await expect.poll(() => f.requests.filter(r => r.surface === 'editor' && r.path === '/api/workflow/export').length).toBe(1);
  await expect(exportDialog.getByRole('textbox')).not.toBeEmpty();
  await exportDialog.getByRole('button', { name: 'Close' }).click();
  await f.app.locator('body').press('Control+i');
  const importDialog = f.app.getByRole('dialog', { name: 'Import workflow' });
  await importDialog.getByRole('button', { name: 'Snakemake', exact: true }).click();
  await importDialog.getByRole('textbox', { name: 'Workflow source' }).fill('rule all:\n  input: "counts.tsv"');
  await importDialog.getByRole('button', { name: 'Import', exact: true }).click();
  await expect.poll(() => f.requests.filter(r => r.surface === 'editor' && r.path === '/api/workflow/import').length).toBe(1);
  expect(f.browserApi).toEqual([]);
  expect(f.unknown).toEqual([]);
});

test('full App assistant sends workflow context and text to the MCP host', async ({ page }) => {
  const f = await fixture(page);
  await f.app.getByRole('button', { name: /Open AI assistant/ }).click();
  const prompt = f.app.getByPlaceholder('Ask your host AI about this workflow...');
  await prompt.fill('Explain these normalization steps');
  await f.app.locator('.ai-input-row').getByRole('button', { name: /Send/ }).click();
  await expect.poll(() => f.protocol.some(item => item.method === 'ui/message')).toBe(true);
  expect(f.protocol.some(item => item.method === 'ui/update-model-context')).toBe(true);
  expect(f.requests.some(request => request.path.startsWith('/api/ai/'))).toBe(false);
  expect(f.browserApi).toEqual([]);
  expect(f.unknown).toEqual([]);
});

test('Workspace exposes team cloud files without local filesystem calls', async ({ page }) => {
  const f = await fixture(page);
  await f.app.locator('nav.left-rail').getByRole('button', { name: /^Workspace/ }).click();
  await expect(f.app.locator('.workspace-cloud')).toContainText('counts.tsv');
  await expect(f.app.locator('.workspace-tabs')).toHaveCount(0);
  expect(f.requests).toContainEqual(expect.objectContaining({ surface: 'website', path: '/api/files', method: 'GET' }));
  expect(f.requests.some(request => request.surface === 'editor' && request.path.startsWith('/api/workspace/'))).toBe(false);
  expect(f.browserApi).toEqual([]);
  expect(f.unknown).toEqual([]);
});

test('Workspace uploads through host presign and finalization, then binds the verified key for drag', async ({ page }) => {
  const f = await fixture(page);
  await f.app.locator('nav.left-rail').getByRole('button', { name: /^Workspace/ }).click();
  await f.app.getByLabel('Choose cloud files').setInputFiles({ name: 'staged.tsv', mimeType: 'text/tab-separated-values', buffer: Buffer.from('gene\tcount\na\t1\n') });
  await expect(f.app.locator('.workspace-file-list')).toContainText('staged.tsv');
  expect(f.calls.filter(call => call.name === 'get_upload_url')).toHaveLength(1);
  expect(f.calls.filter(call => call.name === 'complete_upload')).toEqual([{ name: 'complete_upload', args: { team_id: teamId, key: 'uploads/team-fixture/id__staged.tsv' } }]);
  const draggedKey = await page.frameLocator('iframe').locator('.workspace-file-row').filter({ hasText: 'staged.tsv' }).evaluate(element => {
    const transfer = new DataTransfer();
    element.dispatchEvent(new DragEvent('dragstart', { bubbles: true, dataTransfer: transfer }));
    return transfer.getData('application/bionodulo-workspace-file');
  });
  expect(draggedKey).toBe('uploads/team-fixture/id__staged.tsv');
  expect(f.browserApi).toEqual([]);
  expect(f.unknown).toEqual([]);
});

test('initial host run context resumes the saved run without a new submission', async ({ page }) => {
  const runId = '55555555-5555-4555-8555-555555555555';
  const f = await fixture(page, { initialRunId: runId });
  await expect.poll(() => f.requests.filter(request => request.path === `/api/runs/${runId}`).length).toBeGreaterThan(0);
  await expect(f.app.getByRole('complementary', { name: 'Runs' })).toBeVisible();
  expect(f.requests.filter(request => request.path === '/api/runs' && request.method === 'POST')).toEqual([]);
  expect(f.browserApi).toEqual([]);
  expect(f.unknown).toEqual([]);
});

test('production MCP resource loads dynamic App canvas assets from the asset origin', async ({ page }, testInfo) => {
  test.skip(testInfo.config.metadata.productionMcp !== true, 'Requires the production build and cross-origin asset server.');
  const assetOrigin = 'http://127.0.0.1:5176';
  const hostOrigin = new URL(testInfo.project.use.baseURL!).origin;
  const hostAssets: string[] = [];
  const assetFailures: string[] = [];
  const loadedStyles: string[] = [];
  const isAsset = (url: URL) => /\/(?:build\/)?assets\//.test(url.pathname);
  page.on('request', request => { const url = new URL(request.url()); if (url.origin === hostOrigin && isAsset(url)) hostAssets.push(url.href); });
  page.on('requestfailed', request => { if (isAsset(new URL(request.url()))) assetFailures.push(request.url()); });
  page.on('response', response => { const url = new URL(response.url()); if (isAsset(url) && !response.ok()) assetFailures.push(`${url.href}: ${response.status()}`); if (isAsset(url) && url.pathname.endsWith('.css') && response.ok()) loadedStyles.push(url.href); });
  await page.route(url => url.origin === hostOrigin && isAsset(url), route => route.fulfill({ status: 404, body: 'MCP host has no app assets' }));
  await page.route('https://fonts.googleapis.com/**', route => route.fulfill({ contentType: 'text/css', body: '' }));
  const f = await fixture(page, { assetOrigin });
  expect(f.resourceHtml).not.toMatch(/<base\b/i);
  await expect(f.app.locator('.react-flow__edge')).toHaveCount(1);
  await expect(f.app.locator('.react-flow__pane')).toHaveCSS('position', 'absolute');
  expect(hostAssets).toEqual([]);
  expect(assetFailures).toEqual([]);
  expect(loadedStyles.some(url => new URL(url).origin === assetOrigin)).toBe(true);
  expect(f.browserApi).toEqual([]);
  expect(f.unknown).toEqual([]);
});

test('run review requires explicit paid confirmation before submitting through MCP', async ({ page }) => {
  const f = await fixture(page);
  await f.app.locator('.topbar').getByRole('button', { name: /^Run workflow/ }).click();
  const confirmation = f.app.getByRole('dialog');
  await expect(confirmation).toContainText(/credit|compute|run/i);
  expect(f.requests.filter(r => r.path === '/api/runs' && r.method === 'POST')).toEqual([]);
  await confirmation.getByRole('button', { name: 'Confirm paid run' }).click();
  await expect.poll(() => f.requests.filter(r => r.path === '/api/runs' && r.method === 'POST').length).toBe(1);
  const submission = f.requests.find(r => r.path === '/api/runs' && r.method === 'POST')!;
  expect(submission.body).toMatchObject({
    workflowId, confirmCreditUse: true, expectedWorkflowUpdatedAt: f.row().updatedAt,
    inputs: { artifacts: { 'uploads/team-fixture/id__counts.tsv': { uploadKey: 'uploads/team-fixture/id__counts.tsv', kind: 'file' } } },
  });
  await expect.poll(() => f.requests.filter(r => r.path === '/api/runs/55555555-5555-4555-8555-555555555555').length, { timeout: 16_000 }).toBeGreaterThanOrEqual(2);
  const download = f.app.getByRole('button', { name: 'Download result.tsv' });
  await expect(download).toBeVisible();
  await download.click();
  await expect.poll(() => f.protocol.some(item => item.method === 'ui/open-link')).toBe(true);
  expect(f.requests.filter(r => r.path.endsWith('/outputs')).length).toBeGreaterThanOrEqual(2);
  await f.app.locator('.runs-drawer-header button').click();
  await f.app.locator('.bottom-console').getByRole('button', { name: 'Expand All' }).click();
  await expect(f.app.locator('.bottom-console')).toContainText(/Cloud run completed/i);
  expect(f.browserApi).toEqual([]);
  expect(f.unknown).toEqual([]);
});

test('MCP host fixture rejects an unknown cloud route with explicit 404', async ({ page }) => {
  const f = await fixture(page);
  const response = await page.evaluate(async () => (window as any).fixtureMcpTool('cloud_editor_request', { surface: 'editor', method: 'GET', path: '/api/not-real' }));
  expect(response).toMatchObject({ status: 404, body: { success: false } });
  expect(f.unknown).toContain('editor GET /api/not-real');
  expect(f.browserApi).toEqual([]);
});
