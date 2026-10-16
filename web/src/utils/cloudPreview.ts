import type { CloudRunOutput, RunRecord, Workflow } from '../types';

export const CLOUD_PREVIEW_MAX_BYTES = 2 * 1024 * 1024;
export type CloudPreviewOutput = Omit<CloudRunOutput, 'url'>;
export type CloudPreviewKind = 'image' | 'html' | 'text';

export function parseCloudPreviewGraph(value: unknown): RunRecord['cloud_preview_graph'] | undefined {
  if (!value || typeof value !== 'object') return undefined;
  const graph = value as Record<string, unknown>;
  if (!Array.isArray(graph.nodes) || !Array.isArray(graph.edges) || graph.nodes.length > 2000 || graph.edges.length > 5000) return undefined;
  const nodes: NonNullable<RunRecord['cloud_preview_graph']>['nodes'] = [];
  const ids = new Set<string>();
  for (const raw of graph.nodes) {
    if (!raw || typeof raw !== 'object') return undefined;
    const node = raw as Record<string, unknown>;
    if (typeof node.id !== 'string' || !node.id || typeof node.type !== 'string' || !node.type || ids.has(node.id)) return undefined;
    ids.add(node.id); nodes.push({ id: node.id, type: node.type });
  }
  const edges: NonNullable<RunRecord['cloud_preview_graph']>['edges'] = [];
  for (const raw of graph.edges) {
    if (!raw || typeof raw !== 'object') return undefined;
    const edge = raw as { id?: unknown; from?: { node?: unknown; output?: unknown }; to?: { node?: unknown; input?: unknown } };
    if (!edge.from || !edge.to || typeof edge.from.node !== 'string' || typeof edge.from.output !== 'string'
      || typeof edge.to.node !== 'string' || typeof edge.to.input !== 'string' || !ids.has(edge.from.node) || !ids.has(edge.to.node)) return undefined;
    edges.push({ id: typeof edge.id === 'string' ? edge.id : `edge-${edges.length}`, from: { node: edge.from.node, output: edge.from.output }, to: { node: edge.to.node, input: edge.to.input } });
  }
  return { nodes, edges };
}

export function latestCloudRunForWorkflow(runs: RunRecord[], workflowId?: string): RunRecord | undefined {
  const time = (run: RunRecord) => Date.parse(run.start_time || run.end_time || '') || 0;
  return workflowId ? runs.filter(run => run.options?.cloud === true && run.workflow_id === workflowId).sort((a, b) => time(b) - time(a))[0] : undefined;
}

export function cloudPreviewKind(output: Pick<CloudRunOutput, 'name'>): CloudPreviewKind | null {
  const ext = output.name.split('.').pop()?.toLowerCase();
  if (['png', 'jpg', 'jpeg', 'gif', 'webp', 'svg'].includes(ext || '')) return 'image';
  if (['html', 'htm'].includes(ext || '')) return 'html';
  if (['csv', 'tsv', 'tab', 'txt', 'json'].includes(ext || '')) return 'text';
  return null;
}

export function withoutCloudDownloadUrl(output: CloudRunOutput): CloudPreviewOutput {
  const { url: _url, ...metadata } = output;
  return metadata;
}

/** Only exact committed run/node prefixes may associate an artifact with a node. */
export function cloudOutputNodeId(output: CloudPreviewOutput, teamId: string, runId: string): string | null {
  const prefix = `${teamId}/${runId}/`;
  if (!output.key.startsWith(prefix)) return null;
  const parts = output.key.slice(prefix.length).split('/');
  if (parts.length < 2 || parts.some(part => !part || part === '.' || part === '..')) return null;
  return parts[0];
}

/**
 * Evidence belongs to the latest attempt of this workflow. A newer incomplete
 * or failed attempt suppresses every older cloud preview, even for legacy runs
 * whose complete execution plan is unknown.
 */
export function deriveCloudNodeOutputs(runs: RunRecord[], workflow: Workflow, teamId: string): Record<string, { runId: string; outputs: CloudPreviewOutput[] }> {
  if (!workflow.id || !teamId) return {};
  const run = latestCloudRunForWorkflow(runs, workflow.id);
  if (!run || run.status !== 'completed') return {};
  const observed = new Set([...run.execution_plan, ...run.node_statuses.map(node => node.node_id)]);
  const failedNodes = new Set(run.node_statuses.filter(node => node.status === 'error' || node.status === 'skipped').map(node => node.node_id));
  const byNode = new Map<string, CloudPreviewOutput[]>();
  for (const raw of run.cloud_outputs || []) {
    const output = withoutCloudDownloadUrl(raw);
    const nodeId = cloudOutputNodeId(output, teamId, run.run_id);
    if (!nodeId || !observed.has(nodeId) || failedNodes.has(nodeId) || !cloudPreviewKind(output)) continue;
    // Generated head summaries are useful in history, but do not replace the
    // actual plot/report of a node on the canvas.
    if (output.key.includes('/_head_preview/')) continue;
    byNode.set(nodeId, [...(byNode.get(nodeId) || []), output]);
  }
  const result: Record<string, { runId: string; outputs: CloudPreviewOutput[] }> = {};
  for (const node of workflow.nodes) {
    if (!observed.has(node.id) || failedNodes.has(node.id)) continue;
    const executedNode = run.cloud_preview_graph?.nodes.find(candidate => candidate.id === node.id);
    if (run.cloud_preview_graph && executedNode?.type !== node.type) continue;
    let outputs = byNode.get(node.id) || [];
    if (['image_preview', 'html_preview'].includes(node.type) && outputs.length === 0 && run.cloud_preview_graph) {
      const incoming = run.cloud_preview_graph.edges.filter(edge => edge.to.node === node.id && edge.to.input === 'file');
      if (incoming.length === 1 && observed.has(incoming[0].from.node)) {
        // The immutable output manifest lacks output-port metadata. Present all
        // compatible artifacts from the exact upstream node for explicit choice,
        // rather than guessing a port from a filename or choosing the first one.
        outputs = (byNode.get(incoming[0].from.node) || []).filter(output => cloudPreviewKind(output) === (node.type === 'image_preview' ? 'image' : 'html'));
      }
    }
    if (outputs.length) result[node.id] = { runId: run.run_id, outputs };
  }
  return result;
}

/** Blob/srcdoc responses cannot inherit HTTP CSP headers. Deny all networking. */
export function sandboxedCloudHtml(html: string): string {
  return `<meta http-equiv="Content-Security-Policy" content="default-src 'none'; img-src data: blob:; style-src 'unsafe-inline'; font-src data:; base-uri 'none'; form-action 'none'">${html}`;
}
