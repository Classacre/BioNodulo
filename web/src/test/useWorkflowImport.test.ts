import { renderHook, act } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { apiPost, apiRequest } from '../api/client';
import { useWorkflow } from '../hooks/workflow/useWorkflow';
import type { Workflow } from '../types';

const storage = new Map<string, string>();
const localStorageStub: Storage = {
  get length() {
    return storage.size;
  },
  clear: () => storage.clear(),
  getItem: (key: string) => storage.get(key) ?? null,
  key: (index: number) => Array.from(storage.keys())[index] ?? null,
  removeItem: (key: string) => {
    storage.delete(key);
  },
  setItem: (key: string, value: string) => {
    storage.set(key, String(value));
  },
};

vi.mock('../api/client', () => ({
  apiPost: vi.fn(),
  apiRequest: vi.fn(),
}));

describe('useWorkflow importWorkflow', () => {
  beforeEach(() => {
    storage.clear();
    vi.stubGlobal('localStorage', localStorageStub);
    vi.mocked(apiPost).mockReset();
  });

  it('posts external workflow imports using the backend request contract', async () => {
    const importedWorkflow = {
      version: '2.0',
      app: 'bionodulo',
      name: 'Imported NextFlow Workflow',
      description: '',
      nodes: [],
      edges: [],
      groups: [],
      outputs: {},
    } as Workflow;
    const nextflow = 'process fastqc { script: "fastqc reads.fastq" }';
    vi.mocked(apiPost).mockResolvedValueOnce({ workflow: importedWorkflow });
    const { result } = renderHook(() => useWorkflow());

    let imported: Workflow | null = null;
    await act(async () => {
      imported = await result.current.importWorkflow(nextflow, 'nextflow');
    });

    expect(apiPost).toHaveBeenCalledWith('/workflow/import', {
      source: 'nextflow',
      content: nextflow,
    });
    expect(imported).toBe(importedWorkflow);
  });
});

describe('useWorkflow exportWorkflow', () => {
  beforeEach(() => {
    storage.clear();
    vi.stubGlobal('localStorage', localStorageStub);
    vi.mocked(apiPost).mockReset();
  });

  it('rejects failed external workflow exports instead of returning mislabeled JSON', async () => {
    const workflow = {
      version: '2.0',
      app: 'bionodulo',
      name: 'QC workflow',
      description: '',
      nodes: [],
      edges: [],
      groups: [],
      outputs: {},
    } as Workflow;
    vi.mocked(apiPost).mockRejectedValueOnce(new Error('converter unavailable'));
    const { result } = renderHook(() => useWorkflow());

    await expect(result.current.exportWorkflow(workflow, 'snakemake')).rejects.toThrow('converter unavailable');

    expect(apiPost).toHaveBeenCalledWith('/workflow/export', {
      workflow,
      format: 'snakemake',
    });
  });
});

describe('useWorkflow submitRun', () => {
  beforeEach(() => {
    storage.clear();
    vi.stubGlobal('localStorage', localStorageStub);
    vi.mocked(apiRequest).mockReset();
  });

  it('posts runtime workflow parameter overrides to the run API', async () => {
    const workflow = {
      id: 'wf-1',
      version: '2.0',
      app: 'bionodulo',
      name: 'Parameterized workflow',
      description: '',
      nodes: [],
      edges: [],
      groups: [],
      outputs: {},
      parameters: [
        { name: 'sample_id', type: 'STRING', required: true },
      ],
    } as Workflow;
    vi.mocked(apiRequest).mockResolvedValueOnce(new Response(JSON.stringify({
      run_id: 'run-1',
      status: 'pending',
      workflow_name: 'Parameterized workflow',
      node_statuses: [],
      node_outputs: {},
      execution_plan: [],
      previews: {},
      artifacts: {},
    })));
    const { result } = renderHook(() => useWorkflow());

    await act(async () => {
      await result.current.submitRun(workflow, {
        no_cache: true,
        parameters: { sample_id: 'S1' },
      });
    });

    expect(apiRequest).toHaveBeenCalledWith('/runs', {
      method: 'POST',
      json: expect.objectContaining({
        workflow,
        workflow_id: 'wf-1',
        no_cache: true,
        parameters: { sample_id: 'S1' },
      }),
    });
  });

  it('posts backend preview options to the run API payload', async () => {
    const workflow = {
      id: 'wf-preview',
      version: '2.0',
      app: 'bionodulo',
      name: 'Previewable workflow',
      description: '',
      nodes: [],
      edges: [],
      groups: [],
      outputs: {},
      parameters: [
        { name: 'sample_id', type: 'STRING', required: true },
      ],
    } as Workflow;
    const resumeCheckpoint = {
      run_id: 'run-source',
      node_outputs: {
        fastqc: { report: 'fastqc.html' },
      },
    };
    vi.mocked(apiRequest).mockResolvedValueOnce(new Response(JSON.stringify({
      run_id: 'run-preview',
      status: 'pending',
      workflow_name: 'Previewable workflow',
      node_statuses: [],
      node_outputs: {},
      execution_plan: [],
      previews: {},
      artifacts: {},
    })));
    const { result } = renderHook(() => useWorkflow());

    await act(async () => {
      await result.current.submitRun(workflow, {
        name: 'Preview run',
        environment: 'local',
        no_cache: false,
        force_nodes: ['fastqc'],
        target_nodes: ['multiqc'],
        parameters: { sample_id: 'S1' },
        dry_run: true,
        resume_checkpoint: resumeCheckpoint,
      });
    });

    expect(apiRequest).toHaveBeenCalledWith('/runs', {
      method: 'POST',
      json: {
        workflow,
        workflow_id: 'wf-preview',
        name: 'Preview run',
        no_cache: false,
        environment: 'local',
        force_nodes: ['fastqc'],
        target_nodes: ['multiqc'],
        parameters: { sample_id: 'S1' },
        dry_run: true,
        resume_checkpoint: resumeCheckpoint,
      },
    });
  });
});
