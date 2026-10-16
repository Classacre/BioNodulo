import { describe, expect, it } from 'vitest';
import type { CloudRunOutput, RunRecord, Workflow } from '../types';
import { cloudOutputNodeId, cloudPreviewKind, deriveCloudNodeOutputs, parseCloudPreviewGraph, sandboxedCloudHtml, withoutCloudDownloadUrl } from '../utils/cloudPreview';

const output = (node: string, name: string, run = 'run', team = 'team'): CloudRunOutput => ({ key: `${team}/${run}/${node}/tool/${name}`, name, size: 20, sha256: 'a'.repeat(64), url: 'https://signed.example/secret' });
const workflow = { id: 'wf', nodes: [{ id: 'source', type: 'plot' }, { id: 'preview', type: 'image_preview' }], edges: [{ from: { node: 'source', output: 'image' }, to: { node: 'preview', input: 'file' } }] } as Workflow;
const run = (id = 'run'): RunRecord => ({ run_id: id, workflow_id: 'wf', workflow_name: 'Test', status: 'completed', execution_plan: ['source', 'preview'], node_statuses: [], node_outputs: {}, previews: {}, artifacts: {}, start_time: '2026-10-16T01:00:00Z', options: { cloud: true }, cloud_outputs: [output('source', 'a.png', id), output('source', 'b.png', id)], cloud_preview_graph: parseCloudPreviewGraph(workflow) });

describe('verified cloud node preview association', () => {
  it('associates exact node prefixes and offers all upstream choices without guessing a port', () => {
    const previews = deriveCloudNodeOutputs([run()], workflow, 'team');
    expect(previews.preview.outputs.map(item => item.name)).toEqual(['a.png', 'b.png']);
    expect(previews.source.outputs).toHaveLength(2);
    expect(previews.preview.outputs[0]).not.toHaveProperty('url');
  });
  it.each(['running', 'error', 'cancelled'])('suppresses old evidence for a newer %s attempt, including legacy unknown plans', status => {
    const newer = { ...run('new'), status, start_time: '2026-10-16T02:00:00Z', execution_plan: [], node_statuses: [], cloud_outputs: [] } as RunRecord;
    expect(deriveCloudNodeOutputs([run(), newer], workflow, 'team')).toEqual({});
  });
  it('does not borrow same-node-ID artifacts from another workflow, team, run, or unobserved node', () => {
    const record = run();
    record.cloud_outputs = [output('source', 'wrong-team.png', 'run', 'other'), output('source', 'wrong-run.png', 'other'), output('unobserved', 'unknown.png')];
    const otherWorkflow = { ...run('other'), workflow_id: 'other-wf' };
    expect(deriveCloudNodeOutputs([record, otherWorkflow], workflow, 'team')).toEqual({});
  });
  it('preserves errors in completed continue-on-failure runs and ignores generated head previews', () => {
    const record = run(); record.node_statuses = [{ node_id: 'source', status: 'error' }];
    expect(deriveCloudNodeOutputs([record], workflow, 'team')).toEqual({});
    record.node_statuses = []; record.cloud_outputs = [{ ...output('source', 'head_preview.html'), key: 'team/run/source/tool/_head_preview/head_preview.html' }];
    expect(deriveCloudNodeOutputs([record], workflow, 'team')).toEqual({});
  });
  it('requires an unambiguous direct sink edge and uses MIME-compatible upstream artifacts', () => {
    const record = run(); record.cloud_outputs = [output('source', 'report.html')];
    expect(deriveCloudNodeOutputs([record], workflow, 'team').preview).toBeUndefined();
    expect(cloudOutputNodeId({ ...output('source', 'x.png'), key: 'team/run/source/../x.png' }, 'team', 'run')).toBeNull();
  });
  it('maps sinks from executed evidence, never from a subsequently edited saved graph', () => {
    const record = run();
    const edited = { ...workflow, edges: [{ from: { node: 'other', output: 'image' }, to: { node: 'preview', input: 'file' } }] } as Workflow;
    expect(deriveCloudNodeOutputs([record], edited, 'team').preview.outputs.map(item => item.name)).toEqual(['a.png', 'b.png']);
    record.cloud_preview_graph = undefined;
    const legacy = deriveCloudNodeOutputs([record], workflow, 'team');
    expect(legacy.source.outputs).toHaveLength(2);
    expect(legacy.preview).toBeUndefined();
  });
  it('strips parameters from executed graph evidence and rejects malformed or oversized graphs', () => {
    const graph = parseCloudPreviewGraph({ ...workflow, nodes: [{ id: 'source', type: 'plot', params: { secret: 'not retained' } }, { id: 'preview', type: 'image_preview' }] });
    expect(graph?.nodes[0]).toEqual({ id: 'source', type: 'plot' });
    expect(parseCloudPreviewGraph({ nodes: [{ id: 'x', type: 'plot' }, { id: 'x', type: 'plot' }], edges: [] })).toBeUndefined();
    expect(parseCloudPreviewGraph({ nodes: Array(2001).fill({ id: 'x', type: 'plot' }), edges: [] })).toBeUndefined();
  });
  it('allows bounded renderer formats and removes download credentials from preview state', () => {
    expect(cloudPreviewKind(output('source', 'x.html'))).toBe('html');
    expect(cloudPreviewKind(output('source', 'x.csv'))).toBe('text');
    expect(cloudPreviewKind(output('source', 'x.pdf'))).toBeNull();
    expect(withoutCloudDownloadUrl(output('source', 'x.png'))).not.toHaveProperty('url');
    expect(sandboxedCloudHtml('<html>report</html>')).toContain("default-src 'none'");
    expect(sandboxedCloudHtml('report')).not.toContain('script-src');
  });
});
