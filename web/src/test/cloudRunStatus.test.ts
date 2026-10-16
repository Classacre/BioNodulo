import { describe, it, expect } from 'vitest';
import {
  mapCloudRunStatus,
  isTerminalCloudStatus,
  deriveCloudNodeStatuses,
  buildCloudNodeStatuses,
  nodeIdFromTag,
  stripNodeTag,
  parseCloudRunContext,
  cloudRunWorkflowKey,
  canProjectCloudRunOntoWorkflow,
} from '../utils/cloudRunStatus';
import type { RunRecord, Workflow } from '../types';

// Build a worker-shaped log blob: each line "[<iso>] <LEVEL>: <message>".
function line(message: string, level = 'INFO'): string {
  return `[2026-06-16T00:00:00Z] ${level}: ${message}`;
}

describe('mapCloudRunStatus', () => {
  it('maps coarse cloud statuses onto the RunRecord union', () => {
    expect(mapCloudRunStatus('queued')).toBe('pending');
    expect(mapCloudRunStatus('running')).toBe('running');
    expect(mapCloudRunStatus('completed')).toBe('completed');
    expect(mapCloudRunStatus('cancelled')).toBe('cancelled');
    expect(mapCloudRunStatus('failed')).toBe('error');
    expect(mapCloudRunStatus('interrupted')).toBe('error');
    expect(mapCloudRunStatus('weird')).toBe('running');
  });
});

describe('isTerminalCloudStatus', () => {
  it('treats completed/failed/cancelled/interrupted as terminal', () => {
    expect(isTerminalCloudStatus('completed')).toBe(true);
    expect(isTerminalCloudStatus('failed')).toBe(true);
    expect(isTerminalCloudStatus('cancelled')).toBe(true);
    expect(isTerminalCloudStatus('interrupted')).toBe(true);
    expect(isTerminalCloudStatus('running')).toBe(false);
    expect(isTerminalCloudStatus('queued')).toBe(false);
  });
});

describe('node tag parsing', () => {
  it('extracts and strips the [node:<id>] marker', () => {
    expect(nodeIdFromTag('node Foo started [node:abc-1]')).toBe('abc-1');
    expect(nodeIdFromTag('no marker here')).toBeNull();
    expect(stripNodeTag('node Foo started [node:abc-1]')).toBe('node Foo started');
    expect(stripNodeTag('plain line')).toBe('plain line');
  });

  it('handles ids containing colons or dashes', () => {
    expect(nodeIdFromTag('node X completed [node:wf:1:node-2]')).toBe('wf:1:node-2');
  });
});

describe('deriveCloudNodeStatuses', () => {
  it('returns empty for empty logs', () => {
    expect(deriveCloudNodeStatuses('').size).toBe(0);
  });

  it('marks a started node running and a completed node completed', () => {
    const blob = [
      line('node Align started [node:n1]'),
      line('node Align completed [node:n1]'),
      line('node Count started [node:n2]'),
    ].join('\n');
    const m = deriveCloudNodeStatuses(blob);
    expect(m.get('n1')).toBe('completed');
    expect(m.get('n2')).toBe('running');
  });

  it('maps cache hit and skip/bypass onto cached/skipped', () => {
    const blob = [
      line('node A cache hit [node:a]'),
      line('node B skipped [node:b]'),
      line('node C bypassed [node:c]'),
    ].join('\n');
    const m = deriveCloudNodeStatuses(blob);
    expect(m.get('a')).toBe('cached');
    expect(m.get('b')).toBe('skipped');
    expect(m.get('c')).toBe('skipped');
  });

  it('records a node error from an ERROR-level tagged line', () => {
    const blob = [
      line('node D started [node:d]'),
      line('boom: traceback [node:d]', 'ERROR'),
    ].join('\n');
    expect(deriveCloudNodeStatuses(blob).get('d')).toBe('error');
  });

  it('does not downgrade a settled node back to running', () => {
    const blob = [
      line('node E started [node:e]'),
      line('node E completed [node:e]'),
      line('node E started [node:e]'), // stray re-emit
    ].join('\n');
    expect(deriveCloudNodeStatuses(blob).get('e')).toBe('completed');
  });

  it('ignores untagged lines', () => {
    const blob = [
      line('Installing 12 dependencies'),
      line('run started (2 nodes)'),
    ].join('\n');
    expect(deriveCloudNodeStatuses(blob).size).toBe(0);
  });
});

describe('buildCloudNodeStatuses', () => {
  const plan = ['n1', 'n2', 'n3'];

  it('overlays derived statuses on a pending baseline while running', () => {
    const derived = new Map<string, 'running' | 'completed'>([['n1', 'completed'], ['n2', 'running']]);
    const out = buildCloudNodeStatuses(plan, derived, 'running');
    expect(out).toEqual([
      { node_id: 'n1', status: 'completed' },
      { node_id: 'n2', status: 'running' },
      { node_id: 'n3', status: 'pending' },
    ]);
  });

  it('promotes unseen nodes to completed on terminal success', () => {
    const derived = new Map<string, 'cached'>([['n1', 'cached']]);
    const out = buildCloudNodeStatuses(plan, derived, 'completed');
    expect(out.map(n => n.status)).toEqual(['cached', 'completed', 'completed']);
  });

  it('preserves an observed node error when the overall run continues to completion', () => {
    const derived = new Map<string, 'error'>([['n1', 'error']]);
    expect(buildCloudNodeStatuses(plan, derived, 'completed').map(node => node.status))
      .toEqual(['error', 'completed', 'completed']);
  });

  it('preserves observed states without inventing completion for an unknown legacy plan', () => {
    const observed = new Map<string, 'completed' | 'running'>([['seen-done', 'completed'], ['seen-started', 'running']]);
    expect(buildCloudNodeStatuses([...observed.keys()], observed, 'completed', null, false)).toEqual([
      { node_id: 'seen-done', status: 'completed' }, { node_id: 'seen-started', status: 'running' },
    ]);
  });

  it('turns still-running nodes into errors on failure and attaches the message', () => {
    const derived = new Map<string, 'completed' | 'running'>([['n1', 'completed'], ['n2', 'running']]);
    const out = buildCloudNodeStatuses(plan, derived, 'error', 'kaboom');
    expect(out[0]).toEqual({ node_id: 'n1', status: 'completed' });
    expect(out[1]).toEqual({ node_id: 'n2', status: 'error', error: 'kaboom' });
    expect(out[2]).toEqual({ node_id: 'n3', status: 'pending' });
  });
});

describe('immutable cloud submission context', () => {
  it('retains observed node progress when a bounded log window rolls over', () => {
    const earlier = deriveCloudNodeStatuses(line('node input completed [node:old-observed]'));
    const later = deriveCloudNodeStatuses(line('node plot started [node:new-observed]'), earlier);
    expect([...later]).toEqual([['old-observed', 'completed'], ['new-observed', 'running']]);
  });

  it('keeps a submitted name and plan without consulting a saved workflow', () => {
    expect(parseCloudRunContext({ schemaVersion: 1, workflowName: 'Submitted graph', executionNodeIds: ['old-a', 'old-b', 'old-a'] }))
      .toEqual({ schemaVersion: 1, workflowName: 'Submitted graph', executionNodeIds: ['old-a', 'old-b'] });
  });

  it('retains a known name when the submitted plan is explicitly unknown', () => {
    expect(parseCloudRunContext({ schemaVersion: 1, workflowName: 'Large graph', executionNodeIds: null }))
      .toEqual({ schemaVersion: 1, workflowName: 'Large graph', executionNodeIds: null });
  });

  it.each([undefined, null, true, {}, { schemaVersion: 2, workflowName: 'Future', executionNodeIds: [] },
    { schemaVersion: 1, workflowName: 'Invalid', executionNodeIds: true },
    { schemaVersion: 1, workflowName: 'Invalid', executionNodeIds: ['node', 1] }])('rejects absent or malformed context %#', value => {
    expect(parseCloudRunContext(value)).toBeNull();
  });
});

describe('cloud canvas submission isolation', () => {
  const workflow: Workflow = {
    id: 'workflow-a', version: '2.0', app: 'bionodulo', name: 'Submitted', description: '',
    nodes: [{ id: 'shared-node', type: 'input_file', position: [0, 0], params: { file: 'original.tsv' } }],
    edges: [], groups: [], outputs: {},
  };
  const run = { workflow_id: workflow.id } as RunRecord;

  it('requires evidence of the actual locally submitted graph, not matching node IDs', () => {
    expect(canProjectCloudRunOntoWorkflow(run, workflow)).toBe(false);
    const submitted = cloudRunWorkflowKey(workflow);
    expect(canProjectCloudRunOntoWorkflow(run, workflow, submitted)).toBe(true);
    expect(canProjectCloudRunOntoWorkflow(run, { ...workflow, id: 'workflow-b' }, submitted)).toBe(false);
    expect(canProjectCloudRunOntoWorkflow(run, { ...workflow,
      nodes: [{ ...workflow.nodes[0], params: { file: 'edited.tsv' } }],
    }, submitted)).toBe(false);
  });

  it('allows cosmetic movement but invalidates changed execution settings', () => {
    const submitted = cloudRunWorkflowKey(workflow);
    expect(canProjectCloudRunOntoWorkflow(run, { ...workflow, name: 'Renamed',
      nodes: [{ ...workflow.nodes[0], position: [500, 400], ui: { color: 'blue' } }],
    }, submitted)).toBe(true);
    for (const changed of [
      { ...workflow, nodes: [{ ...workflow.nodes[0], ui: { muted: true } }] },
      { ...workflow, environment: { TOOL_MODE: 'changed' } },
      { ...workflow, parameters: [{ name: 'input', type: 'STRING', value: 'changed' }] },
      { ...workflow, outputs: { result: 'shared-node.file' } },
    ]) expect(canProjectCloudRunOntoWorkflow(run, changed, submitted)).toBe(false);
  });
});
