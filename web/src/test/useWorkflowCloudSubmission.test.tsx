import { act, renderHook } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { Workflow } from '../types';

const websiteMocks = vi.hoisted(() => ({
  createCloudWorkflow: vi.fn(),
  getCloudWorkflow: vi.fn(),
  listCloudWorkflows: vi.fn(),
  saveCloudWorkflow: vi.fn(),
  submitCloudRun: vi.fn(),
}));

const loggingMocks = vi.hoisted(() => ({ logError: vi.fn() }));

vi.mock('../api/website', () => websiteMocks);
vi.mock('../state/logging', () => loggingMocks);

import { useWorkflow } from '../hooks/workflow/useWorkflow';

const storage = new Map<string, string>();
const localStorageStub: Storage = {
  get length() { return storage.size; },
  clear: () => storage.clear(),
  getItem: key => storage.get(key) ?? null,
  key: index => Array.from(storage.keys())[index] ?? null,
  removeItem: key => { storage.delete(key); },
  setItem: (key, value) => { storage.set(key, String(value)); },
};

const workflow: Workflow = {
  id: 'wf-local-client-id',
  version: '2.0',
  app: 'bionodulo',
  name: 'Cloud canary',
  description: '',
  nodes: [],
  edges: [],
  groups: [],
  outputs: {},
  parameters: [{ name: 'tiny_sam', type: 'SAM', required: true }],
};

describe('useWorkflow cloud submission', () => {
  beforeEach(() => {
    storage.clear();
    vi.stubGlobal('localStorage', localStorageStub);
    vi.clearAllMocks();
    websiteMocks.createCloudWorkflow.mockResolvedValue('wf-cloud-server');
    websiteMocks.saveCloudWorkflow.mockResolvedValue({ id: workflow.id });
    websiteMocks.submitCloudRun.mockResolvedValue({ runId: 'run-cloud' });
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('creates a cloud row for a local id, persists it, then submits canonical inputs', async () => {
    const { result } = renderHook(() => useWorkflow());
    const parameters = { tiny_sam: '/workspace/tiny.sam' };
    const inputs = {
      files: {
        '/workspace/tiny.sam': 'uploads/team-id/123e4567-e89b-12d3-a456-426614174000__tiny.sam',
      },
    };

    await act(async () => {
      await result.current.submitRun(workflow, {
        forceCloud: true,
        parameters,
        inputs,
      });
    });

    expect(websiteMocks.createCloudWorkflow).toHaveBeenCalledWith('Cloud canary');
    expect(websiteMocks.saveCloudWorkflow).toHaveBeenCalledWith({
      ...workflow,
      id: 'wf-cloud-server',
    });
    expect(websiteMocks.submitCloudRun).toHaveBeenCalledWith(
      'wf-cloud-server',
      undefined,
      inputs,
      parameters,
    );
    expect(websiteMocks.saveCloudWorkflow.mock.invocationCallOrder[0]).toBeLessThan(
      websiteMocks.submitCloudRun.mock.invocationCallOrder[0],
    );
  });

  it('does not submit when workflow persistence fails', async () => {
    const persistenceError = new Error('workflow persistence failed');
    websiteMocks.saveCloudWorkflow.mockRejectedValueOnce(persistenceError);
    const { result } = renderHook(() => useWorkflow());

    await expect(act(async () => {
      await result.current.submitRun(workflow, { forceCloud: true });
    })).rejects.toThrow('workflow persistence failed');

    expect(loggingMocks.logError).toHaveBeenCalledWith('cloud.run.save', persistenceError);
    expect(websiteMocks.submitCloudRun).not.toHaveBeenCalled();
  });

  it('fails closed when selected-node execution is requested in the cloud', async () => {
    const { result } = renderHook(() => useWorkflow());

    await expect(act(async () => {
      await result.current.submitRun(workflow, {
        forceCloud: true,
        target_nodes: ['selected-node'],
      });
    })).rejects.toThrow('target_nodes');

    expect(websiteMocks.createCloudWorkflow).not.toHaveBeenCalled();
    expect(websiteMocks.saveCloudWorkflow).not.toHaveBeenCalled();
    expect(websiteMocks.submitCloudRun).not.toHaveBeenCalled();
  });

  it('fails before persistence when a local runtime file has not been staged', async () => {
    const { result } = renderHook(() => useWorkflow());

    await expect(act(async () => {
      await result.current.submitRun(workflow, {
        forceCloud: true,
        parameters: { tiny_sam: '/workspace/unstaged.sam' },
      });
    })).rejects.toThrow('/workspace/unstaged.sam');

    expect(websiteMocks.createCloudWorkflow).not.toHaveBeenCalled();
    expect(websiteMocks.saveCloudWorkflow).not.toHaveBeenCalled();
    expect(websiteMocks.submitCloudRun).not.toHaveBeenCalled();
  });
});
