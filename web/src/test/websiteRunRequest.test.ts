import { afterEach, describe, expect, it, vi } from 'vitest';
import { createCloudWorkflow, getCloudWorkflow, saveCloudWorkflow, submitCloudRun, getCloudOutputPreview, CloudRunSubmissionError, CLOUD_RUN_SUBMISSION_TIMEOUT_MS } from '../api/website';
import type { Workflow } from '../types';

describe('submitCloudRun', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.useRealTimers();
  });

  it('fetches preview bytes only through the authenticated team-pinned proxy and preserves cancellation', async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response('data', { headers: { 'Content-Type': 'image/png' } }));
    vi.stubGlobal('fetch', fetchMock);
    const signal = new AbortController().signal;
    const blob = await getCloudOutputPreview('run/id', 'team/run/node/a.png', signal, 'team');
    expect(blob.size).toBe(4);
    expect(fetchMock).toHaveBeenCalledWith('/api/runs/run%2Fid/outputs/preview?key=team%2Frun%2Fnode%2Fa.png', expect.objectContaining({ credentials: 'include', signal, headers: expect.objectContaining({ 'x-team-id': 'team' }) }));
  });

  it('bounds admission, aborts the response, and safely observes a late rejection without retrying', async () => {
    vi.useFakeTimers();
    let rejectLate!: (error: Error) => void;
    const fetchMock = vi.fn().mockImplementation(() => new Promise((_, reject) => { rejectLate = reject; }));
    vi.stubGlobal('fetch', fetchMock);
    const outcome = submitCloudRun('wf-1').catch(error => error);
    await vi.advanceTimersByTimeAsync(CLOUD_RUN_SUBMISSION_TIMEOUT_MS);
    const error = await outcome;
    expect(error).toBeInstanceOf(CloudRunSubmissionError);
    expect(error.outcomeUnknown).toBe(true);
    expect(error.message).toContain('180 seconds');
    expect((fetchMock.mock.calls[0][1] as RequestInit).signal?.aborted).toBe(true);
    rejectLate(new Error('Late connection rejection'));
    await vi.advanceTimersByTimeAsync(120_000);
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it.each([[422, false], [502, true], [200, true]])('classifies HTTP%s rejection without treating ambiguous responses as safe to retry', async (status, outcomeUnknown) => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({
      success: false, error: 'Dispatch rejected the request',
    }), { status: status as number })));
    await expect(submitCloudRun('wf-1')).rejects.toMatchObject({
      name: 'CloudRunSubmissionError', outcomeUnknown, message: 'Dispatch rejected the request',
    });
  });

  it('treats a successful response missing its run ID as an unknown outcome', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({ success: true, data: {} }), { status: 202 })));
    await expect(submitCloudRun('wf-1')).rejects.toMatchObject({
      name: 'CloudRunSubmissionError', outcomeUnknown: true,
    });
  });

  it('sends parameters and the canonical nested file manifest', async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({
      success: true,
      data: { runId: 'run-1' },
    }), { status: 200, headers: { 'Content-Type': 'application/json' } }));
    vi.stubGlobal('fetch', fetchMock);
    const inputs = {
      files: {
        '/workspace/tiny.sam': 'uploads/team-id/123e4567-e89b-12d3-a456-426614174000__tiny.sam',
      },
    };
    const parameters = { tiny_sam: '/workspace/tiny.sam' };

    await submitCloudRun('wf-1', { resourceProfile: 'small' }, inputs, parameters);

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(JSON.parse(String(init.body))).toEqual({
      workflowId: 'wf-1',
      resourceProfile: 'small',
      inputs,
      parameters,
    });
  });

  it('persists and restores workflow environment and dependencies', async () => {
    const workflow: Workflow = {
      id: 'wf-1',
      version: '2.0',
      app: 'bionodulo',
      name: 'Pinned workflow',
      description: '',
      nodes: [],
      edges: [],
      groups: [],
      outputs: {},
      environment: { id: 'env-samtools', packages: ['samtools=1.23.1'] },
      dependencies: { samtools: '1.23.1' },
      cloudPending: true,
      cloudRequestId: '123e4567-e89b-42d3-a456-426614174000',
      provenance: { paperDoi: '10.1000/example' },
      annotations: [{ text: 'keep this annotation' }],
      references: [{ doi: '10.1000/example' }],
    } as Workflow;
    const row = {
      id: 'wf-1',
      name: workflow.name,
      description: null,
      definition: {
        nodes: [], edges: [], groups: [], outputs: {},
        version: workflow.version,
        app: workflow.app,
        environment: workflow.environment,
        dependencies: workflow.dependencies,
        provenance: { paperDoi: '10.1000/example' },
        annotations: [{ text: 'keep this annotation' }],
        references: [{ doi: '10.1000/example' }],
        id: 'injected-definition-id', name: 'injected name',
        cloudPending: true, cloudRequestId: 'injected-request-id',
      },
    };
    const response = () => new Response(JSON.stringify({ success: true, data: row }), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    });
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(response())
      .mockResolvedValueOnce(response());
    vi.stubGlobal('fetch', fetchMock);

    await saveCloudWorkflow(workflow, { expectedUserId: 'user-a', expectedTeamId: 'team-a' });
    const restored = await getCloudWorkflow('wf-1');

    const [, saveInit] = fetchMock.mock.calls[0] as [string, RequestInit];
    const savedDefinition = JSON.parse(String(saveInit.body)).definition;
    expect(savedDefinition.environment).toEqual(workflow.environment);
    expect(savedDefinition.dependencies).toEqual(workflow.dependencies);
    expect(savedDefinition.provenance).toEqual({ paperDoi: '10.1000/example' });
    expect(savedDefinition.annotations).toEqual([{ text: 'keep this annotation' }]);
    expect(savedDefinition.references).toEqual([{ doi: '10.1000/example' }]);
    for (const localField of ['id', 'name', 'description', 'cloudPending', 'cloudRequestId']) {
      expect(savedDefinition).not.toHaveProperty(localField);
    }
    expect(JSON.parse(String(saveInit.body))).toMatchObject({
      expectedUserId: 'user-a', expectedTeamId: 'team-a',
    });
    expect(restored.environment).toEqual(workflow.environment);
    expect(restored.dependencies).toEqual(workflow.dependencies);
    expect(restored).toMatchObject({
      id: 'wf-1', name: 'Pinned workflow',
      provenance: { paperDoi: '10.1000/example' },
      annotations: [{ text: 'keep this annotation' }],
      references: [{ doi: '10.1000/example' }],
    });
    expect(restored.cloudPending).toBeUndefined();
    expect(restored.cloudRequestId).toBeUndefined();
  });

  it('creates a workflow atomically with its definition and stable request ID', async () => {
    const workflow: Workflow = {
      id: 'local-import', version: '2.0', app: 'bionodulo', name: 'Imported',
      description: 'from a file', nodes: [], edges: [], groups: [], outputs: {},
      parameters: [{ name: 'sample', type: 'string', value: 'reads.fastq' }],
    };
    const row = { id: 'server-import', name: workflow.name,
      description: workflow.description, definition: workflow };
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ success: true, data: row }), {
      status: 201, headers: { 'Content-Type': 'application/json' },
    }));
    vi.stubGlobal('fetch', fetchMock);
    const created = await createCloudWorkflow(workflow.name, {
      clientRequestId: '123e4567-e89b-42d3-a456-426614174000', workflow,
      expectedUserId: 'user-a', expectedTeamId: 'team-a',
    });
    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(JSON.parse(String(init.body))).toMatchObject({
      name: 'Imported', description: 'from a file',
      clientRequestId: '123e4567-e89b-42d3-a456-426614174000',
      expectedUserId: 'user-a', expectedTeamId: 'team-a',
      definition: { parameters: workflow.parameters, nodes: [], edges: [] },
    });
    expect(created.id).toBe('server-import');
    expect(created.parameters).toEqual(workflow.parameters);
  });

  it('omits an empty description from create POST while retaining native metadata', async () => {
    const workflow = {
      id: 'local-draft', version: '2.0', app: 'bionodulo', name: 'Imported',
      description: '', nodes: [], edges: [], groups: [], outputs: {},
      cloudPending: true, cloudRequestId: '123e4567-e89b-42d3-a456-426614174000',
      provenance: { importer: 'cwl' },
    } as Workflow;
    const row = { id: 'server-import', name: 'Imported', description: null,
      definition: { version: '2.0', app: 'bionodulo', nodes: [], edges: [], groups: [], outputs: {},
        provenance: { importer: 'cwl' } } };
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ success: true, data: row }), {
      status: 201, headers: { 'Content-Type': 'application/json' },
    }));
    vi.stubGlobal('fetch', fetchMock);
    const created = await createCloudWorkflow('Imported', {
      clientRequestId: '123e4567-e89b-42d3-a456-426614174000', workflow,
      expectedUserId: 'user-a', expectedTeamId: 'team-a',
    });
    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    const body = JSON.parse(String(init.body));
    expect(body).not.toHaveProperty('description');
    expect(body.definition.provenance).toEqual({ importer: 'cwl' });
    for (const localField of ['id', 'name', 'description', 'cloudPending', 'cloudRequestId']) {
      expect(body.definition).not.toHaveProperty(localField);
    }
    expect(created).toMatchObject({ id: 'server-import', description: '', provenance: { importer: 'cwl' } });
  });
});
