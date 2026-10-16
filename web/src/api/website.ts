// Website (cloud platform) API client — used ONLY in shared-editor mode.
//
// In the cloud, workflows are persisted in the website's team-scoped database
// and runs execute on cloud dispatch workers. The static editor SPA is served same-origin
// with the website (cloud.bionodulo.com), so these calls go to the website
// root API with the Clerk session cookie (credentials: 'include') — no bearer
// token plumbing. Base is configurable for cross-origin builds.
import type { CloudRunContext, Workflow } from '../types';
import { parseCloudRunContext } from '../utils/cloudRunStatus';
import { getToken } from '../collab/authStorage';
import { getMcpRuntime } from '../mcp/runtime';

const WEBSITE_API_BASE = (import.meta.env.VITE_WEBSITE_API_BASE || '/api').replace(/\/+$/, '');

// The cloud editor is same-origin with the website → cookie auth, base '/api'.
// The LOCALLY-run app is a different origin: it points at the absolute cloud API
// base (set via configureWebsiteApi from the cloud account URL) and authenticates
// with a Clerk bearer token instead of the session cookie.
let absoluteBase: string | null = null;
export function configureWebsiteApi(baseUrl: string | null): void {
  absoluteBase = baseUrl ? baseUrl.replace(/\/+$/, '') : null;
}
function isCrossOrigin(): boolean {
  return Boolean(absoluteBase);
}
function apiBase(): string {
  return absoluteBase || WEBSITE_API_BASE;
}
/** Headers + credentials for a website call: bearer cross-origin, cookie same-origin. */
function websiteInit(init: RequestInit = {}): RequestInit {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...((init.headers as Record<string, string>) || {}),
  };
  if (isCrossOrigin()) {
    const token = getToken();
    if (token && !headers.Authorization) headers.Authorization = `Bearer ${token}`;
  }
  return {
    ...init,
    headers,
    credentials: isCrossOrigin() ? 'omit' : 'include',
  };
}

interface ApiEnvelope<T> {
  success: boolean;
  data?: T;
  error?: string;
}

export const CLOUD_RUN_SUBMISSION_TIMEOUT_MS = 180_000;
export class CloudRunSubmissionError extends Error {
  constructor(message: string, readonly outcomeUnknown: boolean) {
    super(message);
    this.name = 'CloudRunSubmissionError';
  }
}

/** Bound run admission only. Aborting a response never proves no run exists. */
async function submitRunRequest(init: RequestInit): Promise<{ runId?: string; dashboardUrl?: string } & Record<string, unknown>> {
  const controller = new AbortController();
  let deadline: ReturnType<typeof setTimeout> | undefined;
  const request = (async () => {
    const response = await websiteRequest('/runs', { ...init, signal: controller.signal });
    const body = await response.json().catch(() => null) as ApiEnvelope<Record<string, unknown>> | null;
    if (!response.ok || !body?.success) {
      throw new CloudRunSubmissionError(body?.error || `Cloud run submission failed (${response.status})`, response.status >= 500 || response.ok);
    }
    if (!body.data || typeof body.data.runId !== 'string' || !body.data.runId) {
      throw new CloudRunSubmissionError('The cloud service returned an incomplete submission response.', true);
    }
    return body.data;
  })();
  try {
    // The race also bounds an MCP host call whose transport cannot be aborted.
    // Promise.race observes late rejection; neither late response can resubmit.
    return await Promise.race([request, new Promise<never>((_, reject) => {
      deadline = setTimeout(() => {
        reject(new CloudRunSubmissionError('The cloud run submission response timed out after 180 seconds.', true));
        controller.abort();
      }, CLOUD_RUN_SUBMISSION_TIMEOUT_MS);
    })]);
  } catch (error) {
    if (error instanceof CloudRunSubmissionError) throw error;
    throw new CloudRunSubmissionError(error instanceof Error ? error.message : String(error), true);
  } finally {
    clearTimeout(deadline);
  }
}

export interface WorkflowRow {
  id: string;
  name: string;
  description: string | null;
  definition: { nodes?: unknown[]; edges?: unknown[] } & Record<string, unknown>;
  updatedAt?: string;
}

export async function call<T>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await websiteRequest(path, init);
  const body = (await res.json().catch(() => null)) as ApiEnvelope<T> | null;
  if (!res.ok || !body?.success) {
    throw new Error(body?.error || `Website API ${path} failed (${res.status})`);
  }
  return body.data as T;
}

/** The same cloud APIs, through the host bridge when embedded. */
async function websiteRequest(path: string, init: RequestInit = {}): Promise<Response> {
  const mcp = getMcpRuntime();
  return mcp ? mcp.request('website', path, init) : fetch(`${apiBase()}${path}`, websiteInit(init));
}

/** Raw bytes from the authenticated, bounded, checksum-verifying preview proxy. */
export async function getCloudOutputPreview(runId: string, key: string, signal: AbortSignal, teamId: string): Promise<Blob> {
  // The current MCP bridge serializes JSON/text, not binary bodies. Keep its
  // existing Download flow instead of silently corrupting image bytes.
  if (getMcpRuntime()) throw new Error('Preview is available in the cloud website. Download this output to view it here.');
  const response = await websiteRequest(`/runs/${encodeURIComponent(runId)}/outputs/preview?key=${encodeURIComponent(key)}`, { signal, headers: { 'x-team-id': teamId } });
  if (!response.ok) {
    const error = await response.json().catch(() => null) as { error?: string } | null;
    throw new Error(error?.error || `Preview unavailable (${response.status}). Download the output instead.`);
  }
  const content = await response.blob();
  if (content.size > 2 * 1024 * 1024) throw new Error('This output is too large to preview. Download it instead.');
  return content;
}

export interface CloudWorkflowSummary {
  id: string;
  name: string;
  description: string | null;
  updatedAt?: string;
}

/** List the team's saved workflows (no definitions). */
export function listCloudWorkflows(): Promise<CloudWorkflowSummary[]> {
  return call<CloudWorkflowSummary[]>('/workflows');
}

/** Fetch a workflow row (with its definition) and map it to the editor shape. */
export async function getCloudWorkflow(id: string): Promise<Workflow> {
  const row = await call<WorkflowRow>(`/workflows/${id}`);
  return rowToWorkflow(row);
}

/** Create a new empty workflow row. The POST returns the full row, so this
 * resolves straight to the editor-shaped workflow — callers must not re-GET
 * it (that second round trip is what made new tabs feel slow). */
export interface CloudWriteContext {
  expectedUserId: string;
  expectedTeamId: string;
}

export async function createCloudWorkflow(name: string, options?: Partial<CloudWriteContext> & {
  clientRequestId?: string;
  workflow?: Workflow;
}): Promise<Workflow> {
  const row = await call<WorkflowRow>('/workflows', {
    method: 'POST',
    body: JSON.stringify(options ? {
      name,
      clientRequestId: options.clientRequestId,
      expectedUserId: options.expectedUserId,
      expectedTeamId: options.expectedTeamId,
      ...(options.workflow ? {
        ...(options.workflow.description?.trim() ? { description: options.workflow.description } : {}),
        definition: workflowDefinition(options.workflow),
      } : {}),
    } : { name }),
  });
  return rowToWorkflow(row);
}

export function workflowDefinition(wf: Workflow) {
  const {
    id: _id, name: _name, description: _description,
    cloudPending: _cloudPending, cloudRequestId: _cloudRequestId,
    ...native
  } = wf;
  return {
    ...native,
    nodes: wf.nodes ?? [], edges: wf.edges ?? [], groups: wf.groups ?? [],
    outputs: wf.outputs ?? {}, environment: wf.environment,
    dependencies: wf.dependencies, parameters: wf.parameters ?? [],
    comments: wf.comments ?? [], version: wf.version, app: wf.app,
  };
}

/** Persist the editor workflow's name/description/definition to its row. */
export function saveCloudWorkflow(wf: Workflow, context?: CloudWriteContext): Promise<WorkflowRow> {
  const { id, name, description } = wf;
  return call<WorkflowRow>(`/workflows/${id}`, {
    method: 'PUT',
    body: JSON.stringify({
      name: name || 'Untitled',
      description: description || null,
      definition: workflowDefinition(wf),
      ...context,
    }),
  });
}

export type CloudRunInputKind = 'file' | 'directory';

export interface CloudRunInputArtifact {
  uploadKey: string;
  kind: CloudRunInputKind;
}

/**
 * The compute portion of a /api/runs body: a named preset, an arbitrary custom
 * CPU/RAM spec, or the GPU preset with custom worker sizing (customVcpu /
 * customMemoryGb) — the server maps `resourceProfile: 'gpu'` onto the A10
 * worker and sizes it from the custom dims.
 */
export interface RunComputeBody {
  resourceProfile?: string;
  compute?: { vcpu: number; ramGb: number };
  customVcpu?: number;
  customMemoryGb?: number;
  gpuCount?: number;
}

/** Canonical uploaded-artifact manifest accepted by the website run API. */
export interface CloudRunInputs {
  artifacts?: Record<string, CloudRunInputArtifact>;
  /** Rolling-deploy compatibility for older saved/editor payloads. */
  files?: Record<string, string>;
}

/**
 * Submit a run to the cloud Batch runner for an already-persisted workflow.
 * `compute` carries either a named preset (resourceProfile) or an arbitrary
 * custom CPU/RAM spec; the server validates it against the team's plan.
 */
export function submitCloudRun(
  workflowId: string,
  compute?: RunComputeBody,
  inputs?: CloudRunInputs,
  parameters?: Record<string, unknown>,
): Promise<{ runId?: string; dashboardUrl?: string } & Record<string, unknown>> {
  return submitRunRequest({
    method: 'POST',
    body: JSON.stringify({
      workflowId,
      ...(compute ?? {}),
      ...(inputs ? { inputs } : {}),
      ...(parameters ? { parameters } : {}),
    }),
  });
}

/** Submit a run as a share-link GUEST: the editor invite is the bearer and
 *  the run bills to the owning (inviting) team. Same-origin cookie auth would
 *  be meaningless for an anonymous guest, so Authorization is explicit. */
export function submitCloudGuestRun(
  runToken: string,
  guestName: string,
  workflowId: string,
  compute?: RunComputeBody,
  inputs?: CloudRunInputs,
  parameters?: Record<string, unknown>,
): Promise<{ runId?: string; dashboardUrl?: string } & Record<string, unknown>> {
  return submitRunRequest({
    method: 'POST',
    headers: {
      Authorization: `Bearer ${runToken}`,
      'x-bionodulo-guest-name': guestName.slice(0, 60),
    },
    body: JSON.stringify({
      workflowId,
      ...(compute ?? {}),
      ...(inputs ? { inputs } : {}),
      ...(parameters ? { parameters } : {}),
    }),
  });
}

/** Cancel a website-managed cloud run. Local queue runs use the host API. */
export function cancelCloudRun(runId: string): Promise<{ runId: string; status: string }> {
  return call(`/runs/${encodeURIComponent(runId)}/cancel`, { method: 'POST' });
}

export interface CloudRunSnapshot {
  id: string;
  workflowId?: string | null;
  workflowContext?: CloudRunContext | null;
  status: string;
  logs: string;
  errorMessage: string | null;
  outputLocation: string | null;
  durationMs: number | null;
  creditsUsed: number | null;
  createdAt: string | null;
  completedAt: string | null;
}

export interface CloudRunSummary {
  id: string;
  workflowId: string | null;
  workflowName: string | null;
  status: string;
  createdAt: string | null;
  startedAt: string | null;
  completedAt: string | null;
  durationMs: number | null;
  creditsUsed: number | null;
}

/** Bounded, team-scoped metadata for restoring the editor's cloud run drawer. */
export async function listCloudRunSummaries(): Promise<CloudRunSummary[]> {
  const summaries = await call<CloudRunSummary[]>('/runs?view=summary');
  if (!Array.isArray(summaries)) throw new Error('Could not restore cloud run history');
  return summaries.filter(run => typeof run?.id === 'string' && typeof run.status === 'string').slice(0, 50);
}

/**
 * Poll a single run's snapshot (status + accumulated logs). Returns null on a
 * transient error so the poller can keep trying. The endpoint returns a plain
 * object (not the {success,data} envelope), so it bypasses `call`.
 */
export async function getCloudRun(runId: string): Promise<CloudRunSnapshot | null> {
  try {
    const res = await websiteRequest(`/runs/${runId}`);
    if (!res.ok) return null;
    const snapshot = await res.json() as CloudRunSnapshot;
    if (!snapshot || typeof snapshot.status !== 'string') return null;
    return { ...snapshot, workflowContext: parseCloudRunContext(snapshot.workflowContext) };
  } catch {
    return null;
  }
}

export interface CloudUser {
  id: string;
  clerkUserId?: string;
  name: string | null;
  email: string | null;
  team: { id: string; name: string; clerkOrgId?: string | null };
}

/** Current signed-in user identity (cloud editor / local app). */
export function getCurrentUser(signal?: AbortSignal): Promise<CloudUser> {
  return call<CloudUser>('/me', signal ? { signal } : {});
}

export interface CollabClientToken {
  room: string;
  token: string;
  host: string;
  expiresAt: number;
}

/**
 * Mint a per-room collaboration token for the cloud editor's Yjs WebSocket.
 * Throws if the user's team doesn't own the workflow (the website enforces it).
 */
export function getCollabClientToken(workflowId: string): Promise<CollabClientToken> {
  return call<CollabClientToken>('/collab/token', {
    method: 'POST',
    body: JSON.stringify({ workflowId }),
  });
}

/** Invite a collaborator to the team by email (Clerk sends the email). */
export function inviteCollaborator(
  email: string,
  role: 'admin' | 'member' = 'member',
): Promise<{ email: string; role: string }> {
  return call<{ email: string; role: string }>('/team/invite', {
    method: 'POST',
    body: JSON.stringify({ email, role }),
  });
}

export interface CloudCredits {
  remaining: number;
  monthlyCredits: number;
  usedCredits: number;
  plan: string;
}

/**
 * Fetch the team's credit balance for the cloud editor badge. Returns null on
 * any error (signed-out, no org, network) so the badge degrades gracefully.
 * The endpoint returns a plain object, not the {success,data} envelope.
 */
export async function getCloudCredits(): Promise<CloudCredits | null> {
  try {
    const res = await websiteRequest('/billing/credits');
    if (!res.ok) return null;
    const j = await res.json();
    if (typeof j?.remaining !== 'number') return null;
    return {
      remaining: j.remaining,
      monthlyCredits: j.monthlyCredits ?? 0,
      usedCredits: j.usedCredits ?? 0,
      plan: j.plan ?? '',
    };
  } catch {
    return null;
  }
}

export interface CloudFile {
  key: string;
  name: string;
  size: number;
  updatedAt: string;
  /** Short-lived presigned GET url for download. */
  url: string;
}

/** List the team's uploaded cloud files (with presigned download urls). */
export function listCloudFiles(): Promise<CloudFile[]> {
  return call<CloudFile[]>('/files');
}

/** Ask the cloud for a presigned S3 PUT url to upload a file under the team. */
export function presignCloudUpload(
  filename: string,
  contentType: string,
  size: number,
): Promise<{ url: string; key: string; method: string }> {
  return call<{ url: string; key: string; method: string }>('/files/presign', {
    method: 'POST',
    body: JSON.stringify({ filename, contentType, size }),
  });
}

export function rowToWorkflow(row: WorkflowRow): Workflow {
  const def = row.definition || {};
  const {
    id: _id, name: _name, description: _description,
    cloudPending: _cloudPending, cloudRequestId: _cloudRequestId,
    ...native
  } = def;
  return {
    ...native,
    id: row.id,
    version: (def.version as string) || '2.0',
    app: (def.app as string) || 'bionodulo',
    name: row.name,
    description: row.description || '',
    nodes: (def.nodes as Workflow['nodes']) ?? [],
    edges: (def.edges as Workflow['edges']) ?? [],
    groups: (def.groups as Workflow['groups']) ?? [],
    outputs: (def.outputs as Workflow['outputs']) ?? {},
    environment: def.environment as Workflow['environment'],
    dependencies: def.dependencies as Workflow['dependencies'],
    parameters: (def.parameters as Workflow['parameters']) ?? [],
    comments: (def.comments as Workflow['comments']) ?? [],
  };
}
