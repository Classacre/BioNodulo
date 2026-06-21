// Website (cloud platform) API client — used ONLY in shared-editor mode.
//
// In the cloud, workflows are persisted in the website's team-scoped database
// and runs execute on AWS Batch. The static editor SPA is served same-origin
// with the website (cloud.bionodulo.com), so these calls go to the website
// root API with the Clerk session cookie (credentials: 'include') — no bearer
// token plumbing. Base is configurable for cross-origin builds.
import type { Workflow } from '../types';

const WEBSITE_API_BASE = (import.meta.env.VITE_WEBSITE_API_BASE || '/api').replace(/\/+$/, '');

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
  const res = await fetch(`${WEBSITE_API_BASE}${path}`, {
    credentials: 'include',
    headers: { 'Content-Type': 'application/json', ...(init.headers || {}) },
    ...init,
  });
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
  };
}
