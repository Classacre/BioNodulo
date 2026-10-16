// Derive runs-drawer + canvas node state from a cloud run snapshot.
//
// Cloud dispatch workers report progress to the website API, which
// persists a run-level status plus an accumulated plaintext log blob (the
// per-node `nodeId` the worker sends is only published to the live SSE channel,
// not stored as a queryable column). So when the editor SPA polls the run
// snapshot, the log blob is the only durable record of per-node transitions.
//
// To make per-node state recoverable from that blob, run_worker.py tags each
// node-level line with a trailing " [node:<id>]" marker (see _id_tag). We parse
// those markers back into NodeStatus values, keyed directly by node id — no
// fragile name->id matching, since the worker's labels and the SPA's titles can
// diverge. The marker is stripped before the line is shown to the user.

import type { CloudRunContext, NodeStatus, RunRecord, Workflow } from '../types';

/** Local submission evidence only; saved node IDs cannot prove an unchanged graph. */
export function cloudRunWorkflowKey(workflow: Workflow): string {
  return JSON.stringify({
    id: workflow.id, version: workflow.version, app: workflow.app,
    nodes: workflow.nodes.map(node => ({
      id: node.id, type: node.type, params: node.params,
      muted: node.ui?.muted, bypassed: node.ui?.bypassed,
      promotedInputs: node.ui?.promotedInputs, validation: node.ui?.validation,
    })),
    edges: workflow.edges.map(edge => ({ from: edge.from, to: edge.to })),
    outputs: workflow.outputs, environment: workflow.environment,
    dependencies: workflow.dependencies, parameters: workflow.parameters,
  });
}

export function canProjectCloudRunOntoWorkflow(run: RunRecord, workflow: Workflow, submittedKey?: string): boolean {
  return Boolean(workflow.id && run.workflow_id === workflow.id && submittedKey
    && submittedKey === cloudRunWorkflowKey(workflow));
}

/** Reject malformed or unsupported metadata rather than trusting graph-shaped hints. */
export function parseCloudRunContext(value: unknown): CloudRunContext | null {
  if (!value || typeof value !== 'object') return null;
  const context = value as Record<string, unknown>;
  if (context.schemaVersion !== 1
    || (context.workflowName !== null && typeof context.workflowName !== 'string')
    || (context.executionNodeIds !== null && (!Array.isArray(context.executionNodeIds)
      || !context.executionNodeIds.every(id => typeof id === 'string' && id.length > 0)))) return null;
  return {
    schemaVersion: 1,
    workflowName: context.workflowName as string | null,
    executionNodeIds: context.executionNodeIds === null ? null : [...new Set(context.executionNodeIds as string[])],
  };
}

/** Map a cloud run's coarse status onto the local RunRecord status union. */
export function mapCloudRunStatus(status: string): RunRecord['status'] {
  switch (status) {
    case 'queued':
      return 'pending';
    case 'running':
      return 'running';
    case 'completed':
      return 'completed';
    case 'cancelled':
      return 'cancelled';
    case 'failed':
    case 'interrupted':
      return 'error';
    default:
      return 'running';
  }
}

/** True once the run can no longer change — stop polling. */
export function isTerminalCloudStatus(status: string): boolean {
  return status === 'completed' || status === 'failed'
    || status === 'cancelled' || status === 'interrupted';
}

const ID_TAG_RE = /\s*\[node:([^\]]+)\]\s*$/;
const STARTED_RE = /\bstarted$/;
const DONE_RE = /\b(completed|cache hit|skipped|bypassed)$/;

/** Strip the worker's "[node:<id>]" marker from a log line for display. */
export function stripNodeTag(message: string): string {
  return message.replace(ID_TAG_RE, '');
}

/** Extract the node id from a tagged log line, or null if untagged. */
export function nodeIdFromTag(message: string): string | null {
  const m = ID_TAG_RE.exec(message);
  return m ? m[1] : null;
}

function doneStatus(word: string): NodeStatus['status'] {
  switch (word) {
    case 'cache hit':
      return 'cached';
    case 'skipped':
    case 'bypassed':
      return 'skipped';
    default:
      return 'completed';
  }
}

const SETTLED: ReadonlySet<NodeStatus['status']> = new Set(['completed', 'cached', 'skipped']);

/**
 * Parse a cloud run's accumulated log blob into a node-id -> status map. Later
 * lines win, so a node that started then completed ends as completed. Only
 * lines carrying a "[node:<id>]" marker contribute; everything else is ignored.
 *
 * `logsText` is the raw blob, each line shaped "[<iso>] <LEVEL>: <message>".
 */
export function deriveCloudNodeStatuses(
  logsText: string,
  previous?: ReadonlyMap<string, NodeStatus['status']>,
): Map<string, NodeStatus['status']> {
  const out = new Map<string, NodeStatus['status']>(previous);
  if (!logsText) return out;
  for (const raw of logsText.split('\n')) {
    const id = nodeIdFromTag(raw);
    if (!id) continue;
    const core = stripNodeTag(raw).trim();
    const isError = /\bERROR:/.test(raw);
    const done = DONE_RE.exec(core);
    if (done) {
      out.set(id, doneStatus(done[1]));
      continue;
    }
    if (isError) {
      out.set(id, 'error');
      continue;
    }
    if (STARTED_RE.test(core) && !SETTLED.has(out.get(id) ?? 'pending')) {
      out.set(id, 'running');
    }
  }
  return out;
}

/**
 * Build the NodeStatus[] for a cloud run by overlaying log-derived statuses on
 * an execution-plan baseline of `pending`. On a terminal success any node not
 * explicitly seen is promoted to `completed` (the whole run succeeded); on a
 * terminal failure, still-running nodes become `error`. Legacy snapshots must
 * disable success inference: a run-level completion cannot establish an
 * unobserved per-node transition when the submitted plan is unknown.
 */
export function buildCloudNodeStatuses(
  executionPlan: readonly string[],
  derived: ReadonlyMap<string, NodeStatus['status']>,
  runStatus: RunRecord['status'],
  errorMessage?: string | null,
  inferTerminalSuccess = true,
): NodeStatus[] {
  const terminalOk = inferTerminalSuccess && runStatus === 'completed';
  const failed = runStatus === 'error';
  return executionPlan.map((nodeId): NodeStatus => {
    let status = derived.get(nodeId) ?? 'pending';
    if (terminalOk && status !== 'error' && !SETTLED.has(status)) {
      status = 'completed';
    } else if (failed && status === 'running') {
      status = 'error';
    }
    const ns: NodeStatus = { node_id: nodeId, status };
    if (status === 'error' && errorMessage) ns.error = errorMessage;
    return ns;
  });
}
