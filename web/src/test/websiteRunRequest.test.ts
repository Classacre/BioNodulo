import { afterEach, describe, expect, it, vi } from 'vitest';
import { getCloudWorkflow, saveCloudWorkflow, submitCloudRun } from '../api/website';
import type { Workflow } from '../types';
import { SAMTOOLS_FIRST_WAVE_CATALOG_DIGEST } from '../utils/catalogCanary';

describe('submitCloudRun', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
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

    await submitCloudRun(
      'wf-1',
      { resourceProfile: 'small' },
      inputs,
      parameters,
      {
        profile: 'samtools-first-wave',
        catalog_digest: SAMTOOLS_FIRST_WAVE_CATALOG_DIGEST,
      },
    );

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(JSON.parse(String(init.body))).toEqual({
      workflowId: 'wf-1',
      resourceProfile: 'small',
      inputs,
      parameters,
      catalog_canary: {
        profile: 'samtools-first-wave',
        catalog_digest: SAMTOOLS_FIRST_WAVE_CATALOG_DIGEST,
      },
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
    };
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

    await saveCloudWorkflow(workflow);
    const restored = await getCloudWorkflow('wf-1');

    const [, saveInit] = fetchMock.mock.calls[0] as [string, RequestInit];
    const savedDefinition = JSON.parse(String(saveInit.body)).definition;
    expect(savedDefinition.environment).toEqual(workflow.environment);
    expect(savedDefinition.dependencies).toEqual(workflow.dependencies);
    expect(restored.environment).toEqual(workflow.environment);
    expect(restored.dependencies).toEqual(workflow.dependencies);
  });
});
