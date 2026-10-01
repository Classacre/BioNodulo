import type { CloudConfig } from '../state/appAtoms';
import type { Workflow } from '../types';
import { contextDraft } from './context';
import { record, type OpenContext, type WorkbenchHost } from './host';

export type CloudSurface = 'editor' | 'website';
export interface CloudReply { status: number; body: unknown; content_type: string }
export interface PaidRunReview {
  workflowId: string;
  teamId: string;
  remaining: number;
  creditsPerHour: number;
  vcpu: number;
  ramGb: number;
  gpuCount?: number;
}
export type ConfirmPaidRun = (review: PaidRunReview) => Promise<boolean>;

let activeRuntime: McpCloudRuntime | undefined;
export function getMcpRuntime(): McpCloudRuntime | undefined { return activeRuntime; }
export function installMcpRuntime(runtime: McpCloudRuntime | undefined): void { activeRuntime = runtime; }

function apiPath(path: string): string {
  if (!path.startsWith('/') || path.startsWith('//') || /[\\#]/.test(path)
    || [...path].some(char => char.charCodeAt(0) < 32 || char.charCodeAt(0) === 127))
    throw new Error('Only cloud API paths are supported inside the MCP app.');
  const pathname = path.split('?')[0];
  if (pathname.split('/').some(segment => {
    const decoded = decodeURIComponent(segment);
    return decoded === '.' || decoded === '..' || /[/\\]/.test(decoded);
  })) throw new Error('Invalid cloud API path.');
  return path.startsWith('/api/') ? path : `/api${path}`;
}

async function confirmPaidRun(review: PaidRunReview): Promise<boolean> {
  const { confirmDialog } = await import('../components/ui');
  return confirmDialog({
    title: 'Review paid cloud run',
    message: `Run the saved workflow ${review.workflowId} on ${review.vcpu} vCPU / ${review.ramGb} GB RAM${review.gpuCount ? ` / ${review.gpuCount} A10 GPU(s)` : ''} for team ${review.teamId}? The rate is ${review.creditsPerHour} BioNodulo credits per hour; ${review.remaining} credits remain. The final charge depends on duration. This authorizes one run attempt.`,
    confirmLabel: 'Confirm paid run',
    cancelLabel: 'Cancel',
  });
}

/** The existing cloud editor's transport. It never stores an account token,
 * sends cookies, patches fetch, or treats a host connection as a local backend. */
export class McpCloudRuntime {
  readonly revisions = new Map<string, string>();
  teamId?: string;
  config?: CloudConfig;
  initialContext?: OpenContext;
  private readonly listeners = new Set<(context: OpenContext) => void>();
  private runPending = false;
  private scopeEpoch = 0;
  private teamSelection = 0;

  constructor(readonly host: WorkbenchHost, private readonly review = confirmPaidRun) {
    host.onOpen(context => {
      this.initialContext = context;
      for (const listener of this.listeners) listener(context);
    });
  }

  async connect(): Promise<CloudConfig> {
    await this.host.connect();
    return this.selectTeam(this.initialContext?.team_id);
  }

  async selectTeam(teamId?: string): Promise<CloudConfig> {
    if (this.runPending) throw new Error('Finish or cancel the paid run review before switching teams.');
    const selection = ++this.teamSelection;
    const account = await this.host.tool('get_account_info', teamId ? { team_id: teamId } : {});
    const team = record(account.team);
    if (typeof account.id !== 'string' || typeof team.id !== 'string')
      throw new Error('BioNodulo did not return a verified cloud account and team. Reconnect the app.');
    const balance = await this.host.tool('get_credit_balance', { team_id: team.id }).catch(() => ({}));
    if (selection !== this.teamSelection || this.runPending) throw new Error('The cloud destination changed while connecting. Try opening the team again.');
    this.scopeEpoch += 1;
    this.teamId = team.id;
    this.revisions.clear();
    this.config = {
      cloudMode: true, editorMode: true,
      user: { id: account.id, name: String(account.name || account.email || account.id), email: String(account.email || '') },
      team: { id: team.id, name: String(team.name || team.id) },
      plan: typeof record(balance).plan === 'string' ? String(record(balance).plan) : null,
      credits: { remaining: typeof record(balance).remaining === 'number' ? Number(record(balance).remaining) : null, total: typeof record(balance).monthlyCredits === 'number' ? Number(record(balance).monthlyCredits) : null },
      accountUrl: 'https://bionodulo.com',
      clerkPublishableKey: null, oauth: null,
    };
    return this.config;
  }

  onOpen(listener: (context: OpenContext) => void): () => void {
    this.listeners.add(listener);
    if (this.initialContext) listener(this.initialContext);
    return () => { this.listeners.delete(listener); };
  }

  acceptRevision(id: string, revision: string): void { this.revisions.set(id, revision); }

  private async call(surface: CloudSurface, path: string, method: string, body?: unknown): Promise<CloudReply> {
    const reply = await this.host.tool<CloudReply>('cloud_editor_request', {
      surface, path, method, ...(body !== undefined ? { body } : {}),
      ...(this.teamId ? { team_id: this.teamId } : {}),
    });
    if (!Number.isInteger(reply.status) || reply.status < 200 || reply.status > 599)
      throw new Error('The cloud adapter returned an invalid HTTP response.');
    return reply;
  }

  async request(surface: CloudSurface, path: string, init: RequestInit = {}): Promise<Response> {
    const epoch = this.scopeEpoch;
    const destination = this.teamId;
    const normalized = apiPath(path);
    const method = (init.method || 'GET').toUpperCase();
    if (!['GET', 'POST', 'PUT', 'DELETE'].includes(method)) throw new Error('Unsupported cloud API method.');
    if (init.headers && new Headers(init.headers).has('Authorization'))
      throw new Error('The MCP host manages authentication; browser credentials are not accepted.');
    if (init.signal?.aborted) throw new DOMException('The request was aborted.', 'AbortError');
    if (surface === 'editor' && normalized === '/api/config' && method === 'GET') {
      if (!this.config) throw new Error('The cloud account has not connected.');
      return Response.json(this.config);
    }
    let body: unknown;
    if (init.body !== undefined && init.body !== null) {
      if (typeof init.body !== 'string') throw new Error('Cloud API requests must contain JSON; upload bytes through the cloud file panel.');
      body = JSON.parse(init.body);
    }
    const workflowId = surface === 'website' ? /^\/api\/workflows\/([^/?]+)$/.exec(normalized)?.[1] : undefined;
    if (workflowId && method === 'PUT') {
      const revision = this.revisions.get(workflowId);
      if (!revision) throw new Error('Read the saved workflow before updating it. Its revision is unavailable.');
      body = { ...record(body), expectedUpdatedAt: revision };
    }
    let reply: CloudReply;
    if (surface === 'website' && normalized === '/api/runs' && method === 'POST') {
      if (this.runPending) throw new Error('A paid run review or submission is already in progress.');
      this.runPending = true;
      try {
        const args = record(body);
        const id = String(args.workflowId || '');
        const revision = this.revisions.get(id);
        if (!id || !revision || !this.teamId) throw new Error('Save the workflow before reviewing a paid run.');
        const [balanceReply, estimateReply] = await Promise.all([
          this.call('website', '/api/billing/credits', 'GET'),
          this.call('website', '/api/billing/estimate', 'POST', { resourceProfile: args.resourceProfile, compute: args.compute, customVcpu: args.customVcpu, customMemoryGb: args.customMemoryGb, gpuCount: args.gpuCount }),
        ]);
        if (balanceReply.status !== 200 || estimateReply.status !== 200) throw new Error('Could not verify the current balance and cloud cost. No run was submitted.');
        const balance = record(balanceReply.body), estimate = record(estimateReply.body);
        if (!(Number(balance.remaining) > 0) || estimate.allowed !== true || !(Number(estimate.creditsPerHour) > 0)
          || !(Number(estimate.vcpu) > 0) || !(Number(estimate.ramGb) > 0))
          throw new Error(String(estimate.error || 'Your plan or credit balance does not allow this cloud run.'));
        if (!await this.review({ workflowId: id, teamId: this.teamId, remaining: Number(balance.remaining), creditsPerHour: Number(estimate.creditsPerHour), vcpu: Number(estimate.vcpu), ramGb: Number(estimate.ramGb), ...(estimate.gpuCount ? { gpuCount: Number(estimate.gpuCount) } : {}) }))
          throw new Error('Paid run cancelled. No compute was submitted.');
        if (this.scopeEpoch !== epoch || this.teamId !== destination || this.revisions.get(id) !== revision)
          throw new Error('The saved workflow or team changed during review. Review the current run again; no compute was submitted.');
        if (init.signal?.aborted) throw new DOMException('The request was aborted.', 'AbortError');
        reply = await this.call(surface, normalized, method, { ...args, confirmCreditUse: true, expectedWorkflowUpdatedAt: revision });
      } finally { this.runPending = false; }
    } else reply = await this.call(surface, normalized, method, body);
    if (this.scopeEpoch !== epoch || this.teamId !== destination) throw new Error('The cloud destination changed while the request was in progress.');
    if (init.signal?.aborted) throw new DOMException('The request was aborted.', 'AbortError');
    if (surface === 'website' && reply.status >= 200 && reply.status < 300) {
      const envelope = record(reply.body);
      const row = record(envelope.success === true ? envelope.data : envelope);
      if (typeof row.id === 'string' && typeof row.updatedAt === 'string' &&
          (method === 'POST' || method === 'PUT' || !this.revisions.has(row.id)))
        this.revisions.set(row.id, row.updatedAt);
    }
    const contentType = reply.content_type || 'application/json';
    return new Response(reply.status === 204 ? null : contentType.includes('json') ? JSON.stringify(reply.body) : String(reply.body ?? ''), {
      status: reply.status, headers: { 'content-type': contentType },
    });
  }

  async sendMessage(text: string, workflow?: Workflow): Promise<void> {
    if (workflow) await this.host.context(record(contextDraft({ workflow, team_id: this.teamId })));
    await this.host.message(text);
  }
  async openLink(url: string): Promise<void> { await this.host.openLink(url); }
}
