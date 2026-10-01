import { afterEach, describe, expect, it, vi } from 'vitest';
import { McpCloudRuntime, installMcpRuntime, type ConfirmPaidRun } from './runtime';
import type { WorkbenchHost, RecordValue } from './host';
import { apiGet } from '../api/client';
import { getCloudWorkflow } from '../api/website';

const row = { id: 'workflow', name: 'Cloud graph', description: null, definition: { nodes: [], edges: [] }, updatedAt: '2026-10-01T00:00:00Z' };
function fixture(review: ConfirmPaidRun = vi.fn(async () => true)) {
  const tool = vi.fn(async (name: string, args: RecordValue = {}) => {
    if (name === 'get_account_info') return { id: 'user', name: 'User', team: { id: String(args.team_id || 'team'), name: 'Team' } };
    if (name === 'get_credit_balance') return { plan: 'free', remaining: 10, monthlyCredits: 200 };
    if (name !== 'cloud_editor_request') throw new Error(`Unexpected tool ${name}`);
    const body = args.path === '/api/billing/credits' ? { remaining: 10 }
      : args.path === '/api/billing/estimate' ? { allowed: true, creditsPerHour: 5, vcpu: 1, ramGb: 4 }
      : args.path === '/api/runs' ? { success: true, data: { runId: 'run' } }
      : { success: true, data: row };
    return { status: 200, content_type: 'application/json', body };
  });
  const host = { connect: vi.fn(async () => {}), tool, onOpen: vi.fn(() => () => {}),
    context: vi.fn(async () => {}), message: vi.fn(async () => {}), openLink: vi.fn(async () => {}),
  } as unknown as WorkbenchHost;
  return { tool, host, runtime: new McpCloudRuntime(host, review) };
}
afterEach(() => { installMcpRuntime(undefined); vi.unstubAllGlobals(); });
describe('Full cloud app MCP transport', () => {
  it('boots as the cloud editor with verified identity and no Clerk credentials', async () => {
    const { runtime, tool } = fixture();
    const config = await runtime.connect();
    expect(config).toMatchObject({ cloudMode: true, editorMode: true, user: { id: 'user' }, team: { id: 'team' }, plan: 'free', clerkPublishableKey: null, oauth: null });
    const before = tool.mock.calls.length;
    expect(await (await runtime.request('editor', '/api/config')).json()).toEqual(config);
    expect(tool).toHaveBeenCalledTimes(before);
  });
  it('routes both existing API clients through the bridge, with no direct fetch', async () => {
    const { runtime, tool } = fixture();
    await runtime.connect(); installMcpRuntime(runtime);
    const directFetch = vi.fn(() => { throw new Error('Unexpected direct fetch'); }); vi.stubGlobal('fetch', directFetch);
    await apiGet('/object_info'); await getCloudWorkflow('workflow');
    expect(tool).toHaveBeenCalledWith('cloud_editor_request', expect.objectContaining({ surface: 'editor', path: '/api/object_info', method: 'GET', team_id: 'team' }));
    expect(tool).toHaveBeenCalledWith('cloud_editor_request', expect.objectContaining({ surface: 'website', path: '/api/workflows/workflow' }));
    expect(directFetch).not.toHaveBeenCalled();
  });
  it.each(['https://evil.test/api/me', '//evil.test/api/me', '/api/../me', '/api/%2e%2e/me', '/api/a%2fb', '/api/a\\b', '/api/me#fragment'])('rejects unsafe path %s before making a tool call', async path => {
    const { runtime, tool } = fixture();
    await expect(runtime.request('website', path)).rejects.toThrow(); expect(tool).not.toHaveBeenCalled();
  });
  it('requires a saved revision and does not adopt a background read over that baseline', async () => {
    const { runtime, tool } = fixture(); await runtime.connect();
    await expect(runtime.request('website', '/workflows/workflow', { method: 'PUT', body: '{}' })).rejects.toThrow('revision');
    await runtime.request('website', '/workflows/workflow');
    tool.mockImplementationOnce(async () => ({ status: 200, content_type: 'application/json', body: { success: true, data: { ...row, updatedAt: '2026-10-01T01:00:00Z' } } }));
    await runtime.request('website', '/workflows/workflow');
    await runtime.request('website', '/workflows/workflow', { method: 'PUT', body: JSON.stringify({ definition: row.definition }) });
    expect(tool).toHaveBeenLastCalledWith('cloud_editor_request', expect.objectContaining({ body: { definition: row.definition, expectedUpdatedAt: row.updatedAt } }));
  });
  it('requires explicit review, charges once and preserves the reviewed revision', async () => {
    const review = vi.fn(async () => true);
    const { runtime, tool } = fixture(review); await runtime.connect(); runtime.acceptRevision('workflow', row.updatedAt);
    await runtime.request('website', '/runs', { method: 'POST', body: JSON.stringify({ workflowId: 'workflow', compute: { vcpu: 1, ramGb: 4 } }) });
    expect(review).toHaveBeenCalledWith({ workflowId: 'workflow', teamId: 'team', remaining: 10, creditsPerHour: 5, vcpu: 1, ramGb: 4 });
    const submitted = tool.mock.calls.filter(([, args]) => args?.path === '/api/runs');
    expect(submitted).toHaveLength(1);
    expect(submitted[0][1]?.body).toMatchObject({ confirmCreditUse: true, expectedWorkflowUpdatedAt: row.updatedAt });
  });
  it('forwards GPU compute to the cost estimate and shows the GPU count in review', async () => {
    const review = vi.fn(async () => true);
    const { runtime, tool } = fixture(review);
    await runtime.connect(); runtime.acceptRevision('workflow', row.updatedAt);
    tool.mockImplementation(async (name: string, args: RecordValue = {}) => {
      if (name !== 'cloud_editor_request') throw new Error(`Unexpected tool ${name}`);
      const body = args.path === '/api/billing/credits' ? { remaining: 10 }
        : args.path === '/api/billing/estimate' ? { allowed: true, creditsPerHour: 12, vcpu: 8, ramGb: 64, gpuCount: 1 }
        : { success: true, data: { runId: 'gpu-run' } };
      return { status: 200, content_type: 'application/json', body };
    });
    await runtime.request('website', '/runs', { method: 'POST', body: JSON.stringify({
      workflowId: 'workflow', resourceProfile: 'gpu', compute: { vcpu: 8, ramGb: 64, gpuCount: 1 },
      customVcpu: 8, customMemoryGb: 64, gpuCount: 1,
    }) });
    expect(tool).toHaveBeenCalledWith('cloud_editor_request', expect.objectContaining({
      path: '/api/billing/estimate', body: expect.objectContaining({ gpuCount: 1, customVcpu: 8, customMemoryGb: 64 }),
    }));
    expect(review).toHaveBeenCalledWith(expect.objectContaining({ gpuCount: 1, vcpu: 8, ramGb: 64, creditsPerHour: 12 }));
    expect(tool).toHaveBeenCalledWith('cloud_editor_request', expect.objectContaining({
      path: '/api/runs', body: expect.objectContaining({ gpuCount: 1, confirmCreditUse: true }),
    }));
  });
  it('does not submit after cancellation, a changed revision or an aborted review', async () => {
    for (const scenario of ['cancel', 'revision', 'abort']) {
      const abort = new AbortController();
      let runtime: McpCloudRuntime;
      const current = fixture(async () => {
        if (scenario === 'revision') runtime.acceptRevision('workflow', 'new');
        if (scenario === 'abort') abort.abort();
        return scenario !== 'cancel';
      }); runtime = current.runtime;
      await runtime.connect(); runtime.acceptRevision('workflow', row.updatedAt);
      await expect(runtime.request('website', '/runs', { method: 'POST', body: JSON.stringify({ workflowId: 'workflow' }), signal: abort.signal })).rejects.toThrow();
      expect(current.tool.mock.calls.filter(([, args]) => args?.path === '/api/runs')).toHaveLength(0);
    }
  });
  it('rejects team switches during review and concurrent run submissions', async () => {
    let release!: (value: boolean) => void;
    const { runtime, tool } = fixture(() => new Promise(resolve => { release = resolve; }));
    await runtime.connect(); runtime.acceptRevision('workflow', row.updatedAt);
    const pending = runtime.request('website', '/runs', { method: 'POST', body: JSON.stringify({ workflowId: 'workflow' }) });
    await vi.waitFor(() => expect(release).toBeDefined());
    await expect(runtime.selectTeam('another')).rejects.toThrow('switching teams');
    await expect(runtime.request('website', '/runs', { method: 'POST', body: '{}' })).rejects.toThrow('already in progress');
    release(false); await expect(pending).rejects.toThrow('cancelled');
    expect(tool.mock.calls.filter(([, args]) => args?.path === '/api/runs')).toHaveLength(0);
  });
  it('does not write stale response revisions after a team change', async () => {
    const { runtime, tool } = fixture(); await runtime.connect();
    let release!: (value: unknown) => void;
    tool.mockImplementationOnce(() => new Promise(resolve => { release = resolve; }) as never);
    const pending = runtime.request('website', '/workflows/workflow');
    await runtime.selectTeam('another');
    release({ status: 200, body: { success: true, data: row }, content_type: 'application/json' });
    await expect(pending).rejects.toThrow('destination changed'); expect(runtime.revisions.size).toBe(0);
  });
  it('sends redacted workflow context to the host and propagates message failures', async () => {
    const { runtime, host } = fixture();
    await runtime.sendMessage('Help me', { nodes: [{ params: { apiKey: 'secret', url: 'https://user:password@example.test/a?token=secret' } }], edges: [] } as never);
    const context = JSON.stringify(vi.mocked(host.context).mock.calls);
    expect(context).not.toContain('password'); expect(context).not.toContain('token=secret');
    vi.mocked(host.message).mockRejectedValueOnce(new Error('Host refused'));
    await expect(runtime.sendMessage('Retry')).rejects.toThrow('Host refused');
  });
});
