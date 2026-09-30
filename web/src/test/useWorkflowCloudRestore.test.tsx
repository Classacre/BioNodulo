import { act, renderHook, waitFor } from '@testing-library/react';
import { Provider, createStore } from 'jotai';
import type { ReactNode } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { Workflow } from '../types';
import { cloudConfigAtom } from '../state/appAtoms';

const website = vi.hoisted(() => ({
  listCloudWorkflows: vi.fn(),
  getCloudWorkflow: vi.fn(),
  createCloudWorkflow: vi.fn(),
  saveCloudWorkflow: vi.fn(),
  submitCloudRun: vi.fn(),
}));
vi.mock('../api/website', () => website);
vi.mock('../state/openWorkflows', () => ({ readOpenWorkflows: () => null, writeOpenWorkflows: vi.fn() }));
vi.mock('../state/logging', () => ({ logError: vi.fn() }));

import { useWorkflow } from '../hooks/workflow/useWorkflow';

function workflow(id: string): Workflow {
  return { id, version: '2.0', app: 'bionodulo', name: id, description: '', nodes: [], edges: [], groups: [], outputs: {}, parameters: [] };
}

function cloudWrapper() {
  const store = createStore();
  store.set(cloudConfigAtom, {
    cloudMode: false, editorMode: true, user: null, team: null, plan: null,
    credits: null, accountUrl: null, clerkPublishableKey: null, oauth: null,
  });
  return function Wrapper({ children }: { children: ReactNode }) {
    return <Provider store={store}>{children}</Provider>;
  };
}

describe('cloud workflow restoration', () => {
  beforeEach(() => {
    localStorage.clear();
    vi.clearAllMocks();
    website.saveCloudWorkflow.mockResolvedValue({});
  });

  it('preserves a DOI tab created while cloud restore is still loading', async () => {
    let resolveList!: (value: Array<{ id: string }>) => void;
    website.listCloudWorkflows.mockReturnValue(new Promise(resolve => { resolveList = resolve; }));
    website.getCloudWorkflow.mockResolvedValue(workflow('restored'));
    const { result } = renderHook(() => useWorkflow(), { wrapper: cloudWrapper() });
    await waitFor(() => expect(website.listCloudWorkflows).toHaveBeenCalledOnce());
    act(() => result.current.addWorkflow(workflow('doi-new')));
    expect(result.current.workflows.some(wf => wf.id === 'doi-new')).toBe(true);
    await act(async () => { resolveList([{ id: 'restored' }]); });
    await waitFor(() => expect(result.current.cloudRestored).toBe(true));
    expect(result.current.workflows.map(wf => wf.id)).toEqual(['restored', 'doi-new']);
    expect(result.current.activeWorkflow.id).toBe('doi-new');
  });

  it('settles restoration after a guest cloud-create failure so local import can continue', async () => {
    website.listCloudWorkflows.mockRejectedValue(new Error('unauthorized'));
    website.createCloudWorkflow.mockRejectedValue(new Error('unauthorized'));
    const { result } = renderHook(() => useWorkflow(), { wrapper: cloudWrapper() });
    await waitFor(() => expect(result.current.cloudRestored).toBe(true));
    act(() => result.current.addWorkflow(workflow('doi-local')));
    expect(result.current.workflows.some(wf => wf.id === 'doi-local')).toBe(true);
  });
});
