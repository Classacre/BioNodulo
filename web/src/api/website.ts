// Website (cloud platform) API client — used ONLY in shared-editor mode.
//
// In the cloud, workflows are persisted in the website's team-scoped database
// and runs execute on AWS Batch. The static editor SPA is served same-origin
// with the website (cloud.bionodulo.com), so these calls go to the website
// root API with the Clerk session cookie (credentials: 'include') — no bearer
// token plumbing. Base is configurable for cross-origin builds.
import type { Workflow } from '../types';
import { getToken } from '../collab/authStorage';

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

interface WorkflowRow {
  id: string;
  name: string;
  description: string | null;
  definition: { nodes?: unknown[]; edges?: unknown[] } & Record<string, unknown>;
}

async function call<T>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await fetch(`${apiBase()}${path}`, websiteInit(init));
  const body = (await res.json().catch(() => null)) as ApiEnvelope<T> | null;
  if (!res.ok || !body?.success) {
    throw new Error(body?.error || `Website API ${path} failed (${res.status})`);
  }
  return body.data as T;
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

/** Create a new empty workflow row; returns its id. */
export async function createCloudWorkflow(name: string): Promise<string> {
  const row = await call<WorkflowRow>('/workflows', {
    method: 'POST',
    body: JSON.stringify({ name }),
  });
  return row.id;
}

/** Persist the editor workflow's name/description/definition to its row. */
export function saveCloudWorkflow(wf: Workflow): Promise<WorkflowRow> {
  const { id, name, description, ...rest } = wf;
  return call<WorkflowRow>(`/workflows/${id}`, {
    method: 'PUT',
    body: JSON.stringify({
      name: name || 'Untitled',
      description: description || null,
      definition: {
        nodes: rest.nodes ?? [],
        edges: rest.edges ?? [],
        groups: rest.groups ?? [],
        outputs: rest.outputs ?? {},
        parameters: rest.parameters ?? [],
        comments: rest.comments ?? [],
        version: rest.version,
        app: rest.app,
      },
    }),
  });
}

/** Submit a run to the cloud Batch runner for an already-persisted workflow. */
export function submitCloudRun(
  workflowId: string,
  resourceProfile?: string,
): Promise<{ runId?: string; dashboardUrl?: string } & Record<string, unknown>> {
  return call('/runs', {
    method: 'POST',
    body: JSON.stringify({ workflowId, resourceProfile }),
  });
}

export interface CloudRunSnapshot {
  id: string;
  status: string;
  logs: string;
  errorMessage: string | null;
  outputLocation: string | null;
  durationMs: number | null;
  creditsUsed: number | null;
  createdAt: string | null;
  completedAt: string | null;
}

/**
 * Poll a single run's snapshot (status + accumulated logs). Returns null on a
 * transient error so the poller can keep trying. The endpoint returns a plain
 * object (not the {success,data} envelope), so it bypasses `call`.
 */
export async function getCloudRun(runId: string): Promise<CloudRunSnapshot | null> {
  try {
    const res = await fetch(`${apiBase()}/runs/${runId}`, websiteInit());
    if (!res.ok) return null;
    return (await res.json()) as CloudRunSnapshot;
  } catch {
    return null;
  }
}

export interface CloudUser {
  id: string;
  name: string | null;
  email: string | null;
  team: { id: string; name: string };
}

/** Current signed-in user identity (cloud editor / local app). */
export function getCurrentUser(): Promise<CloudUser> {
  return call<CloudUser>('/me');
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
    const res = await fetch(`${apiBase()}/billing/credits`, websiteInit());
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

function rowToWorkflow(row: WorkflowRow): Workflow {
  const def = row.definition || {};
  return {
    id: row.id,
    version: (def.version as string) || '2.0',
    app: (def.app as string) || 'bionodulo',
    name: row.name,
    description: row.description || '',
    nodes: (def.nodes as Workflow['nodes']) ?? [],
    edges: (def.edges as Workflow['edges']) ?? [],
    groups: (def.groups as Workflow['groups']) ?? [],
    outputs: (def.outputs as Workflow['outputs']) ?? {},
    parameters: (def.parameters as Workflow['parameters']) ?? [],
    comments: (def.comments as Workflow['comments']) ?? [],
  };
}
