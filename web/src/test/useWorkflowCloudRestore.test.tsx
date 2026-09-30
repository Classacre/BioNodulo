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
const openTabs = vi.hoisted(() => ({ writeOpenWorkflows: vi.fn() }));
vi.mock('../api/website', () => website);
vi.mock('../state/openWorkflows', () => ({ readOpenWorkflows: () => null, ...openTabs }));
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
    expect(openTabs.writeOpenWorkflows).not.toHaveBeenCalled();
    act(() => result.current.addWorkflow(workflow('doi-local')));
    expect(result.current.workflows.some(wf => wf.id === 'doi-local')).toBe(true);
    expect(openTabs.writeOpenWorkflows).not.toHaveBeenCalled();
  });

  it('does not replace remembered tabs when listing cloud workflows fails', async () => {
    website.listCloudWorkflows.mockRejectedValue(new Error('temporary outage'));
    const { result } = renderHook(() => useWorkflow(), { wrapper: cloudWrapper() });
    await waitFor(() => expect(result.current.cloudRestored).toBe(true));
    expect(website.createCloudWorkflow).not.toHaveBeenCalled();
    expect(openTabs.writeOpenWorkflows).not.toHaveBeenCalled();
  });

  it('does not replace remembered tabs when a listed workflow cannot be fetched', async () => {
    website.listCloudWorkflows.mockResolvedValue([{ id: 'unavailable' }]);
    website.getCloudWorkflow.mockRejectedValue(new Error('temporary outage'));
    const { result } = renderHook(() => useWorkflow(), { wrapper: cloudWrapper() });
    await waitFor(() => expect(result.current.cloudRestored).toBe(true));
    expect(openTabs.writeOpenWorkflows).not.toHaveBeenCalled();
  });

  it('autosaves an explicitly created cloud workflow after restoration fails', async () => {
    website.listCloudWorkflows.mockRejectedValue(new Error('temporary outage'));
    website.createCloudWorkflow.mockResolvedValue(workflow('created'));
    const { result } = renderHook(() => useWorkflow(), { wrapper: cloudWrapper() });
    await waitFor(() => expect(result.current.cloudLoadError).toBe(true));
    await act(async () => { await result.current.newCloudWorkflow(); });
    const createdIndex = result.current.workflows.findIndex(wf => wf.id === 'created');
    expect(createdIndex).toBeGreaterThanOrEqual(0);
    act(() => result.current.updateWorkflow(createdIndex, { name: 'Edited created' }));
    await waitFor(() => expect(website.saveCloudWorkflow).toHaveBeenCalledWith(
      expect.objectContaining({ id: 'created', name: 'Edited created' }),
    ), { timeout: 3000 });
    expect(openTabs.writeOpenWorkflows).not.toHaveBeenCalled();
  });

  it('autosaves a server-backed DOI tab added after cloud restoration', async () => {
    website.listCloudWorkflows.mockResolvedValue([{ id: 'first' }]);
    website.getCloudWorkflow.mockResolvedValue(workflow('first'));
    const { result } = renderHook(() => useWorkflow(), { wrapper: cloudWrapper() });
    await waitFor(() => expect(result.current.cloudRestored).toBe(true));
    act(() => result.current.addCloudWorkflow(workflow('doi-server')));
    const index = result.current.workflows.findIndex(wf => wf.id === 'doi-server');
    act(() => result.current.updateWorkflow(index, { name: 'Built from DOI' }));
    await waitFor(() => expect(website.saveCloudWorkflow).toHaveBeenCalledWith(
      expect.objectContaining({ id: 'doi-server', name: 'Built from DOI' }),
    ), { timeout: 3000 });
  });

  it('autosaves a server-backed DOI tab even when the initial restore failed', async () => {
    website.listCloudWorkflows.mockRejectedValue(new Error('temporary outage'));
    const { result } = renderHook(() => useWorkflow(), { wrapper: cloudWrapper() });
    await waitFor(() => expect(result.current.cloudLoadError).toBe(true));
    act(() => result.current.addCloudWorkflow(workflow('doi-server')));
    const index = result.current.workflows.findIndex(wf => wf.id === 'doi-server');
    act(() => result.current.updateWorkflow(index, { name: 'Built from DOI' }));
    await waitFor(() => expect(website.saveCloudWorkflow).toHaveBeenCalledWith(
      expect.objectContaining({ id: 'doi-server', name: 'Built from DOI' }),
    ), { timeout: 3000 });
    expect(openTabs.writeOpenWorkflows).not.toHaveBeenCalled();
  });

  it('marks local cloud-editor drafts unsaved without attempting a server PUT', async () => {
    website.listCloudWorkflows.mockResolvedValue([{ id: 'first' }]);
    website.getCloudWorkflow.mockResolvedValue(workflow('first'));
    const { result } = renderHook(() => useWorkflow(), { wrapper: cloudWrapper() });
    await waitFor(() => expect(result.current.cloudRestored).toBe(true));
    act(() => result.current.addWorkflow(workflow('local-draft')));
    await waitFor(() => expect(result.current.cloudSaveStates['local-draft']?.phase).toBe('local'));
    expect(website.saveCloudWorkflow).not.toHaveBeenCalledWith(
      expect.objectContaining({ id: 'local-draft' }),
    );
  });

  it('marks a local draft unsaved during a cloud listing outage', async () => {
    website.listCloudWorkflows.mockRejectedValue(new Error('temporary outage'));
    const { result } = renderHook(() => useWorkflow(), { wrapper: cloudWrapper() });
    await waitFor(() => expect(result.current.cloudLoadError).toBe(true));
    act(() => result.current.addWorkflow(workflow('local-draft')));
    await waitFor(() => expect(result.current.cloudSaveStates['local-draft']?.phase).toBe('local'));
    expect(website.saveCloudWorkflow).not.toHaveBeenCalled();
  });

  it('saves an edited cloud tab after switching to another tab during the debounce', async () => {
    website.listCloudWorkflows.mockResolvedValue([{ id: 'first' }]);
    website.getCloudWorkflow.mockResolvedValue(workflow('first'));
    const { result } = renderHook(() => useWorkflow(), { wrapper: cloudWrapper() });
    await waitFor(() => expect(result.current.cloudRestored).toBe(true));

    act(() => {
      result.current.updateWorkflow(0, { name: 'Edited first' });
      result.current.addWorkflow(workflow('second'));
    });
    expect(result.current.activeWorkflow.id).toBe('second');
    await waitFor(() => expect(website.saveCloudWorkflow).toHaveBeenCalledWith(
      expect.objectContaining({ id: 'first', name: 'Edited first' }),
    ), { timeout: 3000 });
  });

  it('keeps a failed save unsaved until the user retries successfully', async () => {
    website.listCloudWorkflows.mockResolvedValue([{ id: 'first' }]);
    website.getCloudWorkflow.mockResolvedValue(workflow('first'));
    const { result } = renderHook(() => useWorkflow(), { wrapper: cloudWrapper() });
    await waitFor(() => expect(result.current.cloudRestored).toBe(true));
    await waitFor(() => expect(website.saveCloudWorkflow).toHaveBeenCalled(), { timeout: 3000 });
    website.saveCloudWorkflow.mockClear();
    website.saveCloudWorkflow.mockRejectedValueOnce(new Error('offline'));
    act(() => result.current.updateWorkflow(0, { name: 'Unsaved edit' }));
    await waitFor(() => expect(result.current.cloudSaveStates.first?.phase).toBe('error'), { timeout: 3000 });
    expect(website.saveCloudWorkflow).toHaveBeenCalledWith(expect.objectContaining({ name: 'Unsaved edit' }));
    act(() => result.current.retryCloudSave('first'));
    await waitFor(() => expect(result.current.cloudSaveStates.first).toBeUndefined());
    expect(website.saveCloudWorkflow).toHaveBeenCalledTimes(2);
  });

  it('clears failed-save state when the user closes that tab', async () => {
    website.listCloudWorkflows.mockResolvedValue([{ id: 'first' }]);
    website.getCloudWorkflow.mockResolvedValue(workflow('first'));
    const { result } = renderHook(() => useWorkflow(), { wrapper: cloudWrapper() });
    await waitFor(() => expect(result.current.cloudRestored).toBe(true));
    await waitFor(() => expect(website.saveCloudWorkflow).toHaveBeenCalled(), { timeout: 3000 });
    website.saveCloudWorkflow.mockClear();
    website.saveCloudWorkflow.mockRejectedValueOnce(new Error('offline'));
    act(() => result.current.updateWorkflow(0, { name: 'Unsaved edit' }));
    await waitFor(() => expect(result.current.cloudSaveStates.first?.phase).toBe('error'), { timeout: 3000 });
    act(() => result.current.closeTab(0));
    expect(result.current.cloudSaveStates.first).toBeUndefined();
    expect(result.current.workflows[0].cloudPending).toBeFalsy();
  });

  it('does not mark a newer edit saved when an older request finishes', async () => {
    website.listCloudWorkflows.mockResolvedValue([{ id: 'first' }]);
    website.getCloudWorkflow.mockResolvedValue(workflow('first'));
    const { result } = renderHook(() => useWorkflow(), { wrapper: cloudWrapper() });
    await waitFor(() => expect(result.current.cloudRestored).toBe(true));
    await waitFor(() => expect(website.saveCloudWorkflow).toHaveBeenCalled(), { timeout: 3000 });
    website.saveCloudWorkflow.mockClear();
    let resolveFirst!: () => void;
    let resolveSecond!: () => void;
    website.saveCloudWorkflow
      .mockImplementationOnce(() => new Promise<void>(resolve => { resolveFirst = resolve; }))
      .mockImplementationOnce(() => new Promise<void>(resolve => { resolveSecond = resolve; }));
    act(() => result.current.updateWorkflow(0, { name: 'First edit' }));
    await waitFor(() => expect(website.saveCloudWorkflow).toHaveBeenCalledTimes(1), { timeout: 3000 });
    act(() => result.current.updateWorkflow(0, { name: 'Latest edit' }));
    await act(async () => { resolveFirst(); });
    expect(result.current.cloudSaveStates.first).toBeDefined();
    await waitFor(() => expect(website.saveCloudWorkflow).toHaveBeenCalledTimes(2), { timeout: 3000 });
    expect(website.saveCloudWorkflow).toHaveBeenLastCalledWith(expect.objectContaining({ name: 'Latest edit' }));
    expect(result.current.cloudSaveStates.first).toBeDefined();
    await act(async () => { resolveSecond(); });
    await waitFor(() => expect(result.current.cloudSaveStates.first).toBeUndefined());
  }, 8000);
});
