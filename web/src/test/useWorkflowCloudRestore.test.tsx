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
const openTabs = vi.hoisted(() => ({ readOpenWorkflows: vi.fn((): string[] | null => null), writeOpenWorkflows: vi.fn() }));
vi.mock('../api/website', async importOriginal => ({
  ...(await importOriginal<typeof import('../api/website')>()), ...website,
}));
vi.mock('../state/openWorkflows', () => openTabs);
vi.mock('../state/logging', () => ({ logError: vi.fn() }));

import { useWorkflow } from '../hooks/workflow/useWorkflow';

function workflow(id: string): Workflow {
  return { id, version: '2.0', app: 'bionodulo', name: id, description: '', nodes: [], edges: [], groups: [], outputs: {}, parameters: [] };
}

const writeContext = { expectedUserId: 'user-a', expectedTeamId: 'team-a' };

function cloudWrapper(userId = 'user-a', teamId = 'team-a', onStore?: (store: ReturnType<typeof createStore>) => void) {
  const store = createStore();
  store.set(cloudConfigAtom, {
    cloudMode: false, editorMode: true,
    user: { id: userId, name: userId, email: `${userId}@example.test` },
    team: { id: teamId, name: teamId }, plan: null,
    credits: null, accountUrl: null, clerkPublishableKey: null, oauth: null,
  });
  onStore?.(store);
  return function Wrapper({ children }: { children: ReactNode }) {
    return <Provider store={store}>{children}</Provider>;
  };
}

describe('cloud workflow restoration', () => {
  beforeEach(() => {
    localStorage.clear();
    vi.clearAllMocks();
    openTabs.readOpenWorkflows.mockReturnValue(null);
    website.createCloudWorkflow.mockReset();
    website.createCloudWorkflow.mockImplementation(async (name: string, options?: { clientRequestId: string; workflow: Workflow }) => ({
      ...(options?.workflow || workflow('new')),
      id: options ? `server-${options.clientRequestId}` : 'new',
      name,
      cloudPending: false,
      cloudRequestId: undefined,
    }));
    website.saveCloudWorkflow.mockResolvedValue({});
  });

  it('preserves and creates a draft added while cloud restore is still loading', async () => {
    let resolveList!: (value: Array<{ id: string }>) => void;
    website.listCloudWorkflows.mockReturnValue(new Promise(resolve => { resolveList = resolve; }));
    website.getCloudWorkflow.mockResolvedValue(workflow('restored'));
    const { result } = renderHook(() => useWorkflow(), { wrapper: cloudWrapper() });
    await waitFor(() => expect(website.listCloudWorkflows).toHaveBeenCalledOnce());
    let draftId = '';
    act(() => { draftId = result.current.addWorkflow(workflow('doi-new'))!; });
    expect(result.current.workflows.some(wf => wf.id === draftId)).toBe(true);
    await act(async () => { resolveList([{ id: 'restored' }]); });
    await waitFor(() => expect(result.current.cloudRestored).toBe(true));
    expect(result.current.workflows[0].id).toBe('restored');
    expect(result.current.workflows[1].name).toBe('doi-new');
    await waitFor(() => expect(result.current.activeWorkflow.id?.startsWith('server-')).toBe(true));
  });

  it('does not create a blank server row on repeated visits to an empty team', async () => {
    website.listCloudWorkflows.mockResolvedValue([]);
    openTabs.readOpenWorkflows.mockReturnValue([]);
    const first = renderHook(() => useWorkflow(), { wrapper: cloudWrapper() });
    await waitFor(() => expect(first.result.current.cloudRestored).toBe(true));
    expect(first.result.current.workflows).toHaveLength(1);
    expect(website.createCloudWorkflow).not.toHaveBeenCalled();
    first.unmount();
    const second = renderHook(() => useWorkflow(), { wrapper: cloudWrapper() });
    await waitFor(() => expect(second.result.current.cloudRestored).toBe(true));
    expect(website.createCloudWorkflow).not.toHaveBeenCalled();
  });

  it('settles restoration after a guest cloud-create failure so local import can continue', async () => {
    website.listCloudWorkflows.mockRejectedValue(new Error('unauthorized'));
    website.createCloudWorkflow.mockRejectedValue(new Error('unauthorized'));
    const { result } = renderHook(() => useWorkflow(), { wrapper: cloudWrapper() });
    await waitFor(() => expect(result.current.cloudRestored).toBe(true));
    expect(openTabs.writeOpenWorkflows).not.toHaveBeenCalled();
    act(() => result.current.addWorkflow(workflow('doi-local')));
    expect(result.current.workflows.some(wf => wf.name === 'doi-local')).toBe(true);
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
      writeContext,
    ), { timeout: 3000 });
    expect(openTabs.writeOpenWorkflows).toHaveBeenCalledWith(['created'], 'user-a.team-a');
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
      writeContext,
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
      writeContext,
    ), { timeout: 3000 });
    expect(openTabs.writeOpenWorkflows).not.toHaveBeenCalled();
  });

  it('treats changes to imported native metadata as new cloud revisions', async () => {
    website.listCloudWorkflows.mockResolvedValue([{ id: 'first' }]);
    website.getCloudWorkflow.mockResolvedValue(workflow('first'));
    const { result } = renderHook(() => useWorkflow(), { wrapper: cloudWrapper() });
    await waitFor(() => expect(result.current.cloudRestored).toBe(true));
    act(() => result.current.updateWorkflow(0, { provenance: { revision: 1 } } as Partial<Workflow>));
    await waitFor(() => expect(website.saveCloudWorkflow).toHaveBeenCalledWith(
      expect.objectContaining({ id: 'first', provenance: { revision: 1 } }), writeContext,
    ), { timeout: 3000 });
    act(() => result.current.updateWorkflow(0, { provenance: { revision: 2 } } as Partial<Workflow>));
    await waitFor(() => expect(website.saveCloudWorkflow).toHaveBeenCalledWith(
      expect.objectContaining({ id: 'first', provenance: { revision: 2 } }), writeContext,
    ), { timeout: 3000 });
  });

  it('creates and saves a cloud row for a newly added workflow', async () => {
    website.listCloudWorkflows.mockResolvedValue([{ id: 'first' }]);
    website.getCloudWorkflow.mockResolvedValue(workflow('first'));
    const { result } = renderHook(() => useWorkflow(), { wrapper: cloudWrapper() });
    await waitFor(() => expect(result.current.cloudRestored).toBe(true));
    let draftId = '';
    act(() => { draftId = result.current.addWorkflow(workflow('local-draft'))!; });
    await waitFor(() => expect(website.createCloudWorkflow).toHaveBeenCalledWith('local-draft',
      expect.objectContaining({ ...writeContext, clientRequestId: expect.any(String), workflow: expect.objectContaining({ id: draftId }) })));
    await waitFor(() => expect(result.current.workflows.some(wf => wf.id?.startsWith('server-'))).toBe(true));
    await waitFor(() => expect(result.current.cloudSaveStates[draftId]).toBeUndefined());
  });

  it('creates distinct rows for repeated imports carrying an open server ID', async () => {
    website.listCloudWorkflows.mockResolvedValue([{ id: 'original-server' }]);
    website.getCloudWorkflow.mockResolvedValue(workflow('original-server'));
    const { result } = renderHook(() => useWorkflow(), { wrapper: cloudWrapper() });
    await waitFor(() => expect(result.current.cloudRestored).toBe(true));
    act(() => {
      result.current.addWorkflow(workflow('original-server'));
      result.current.addWorkflow(workflow('original-server'));
    });
    await waitFor(() => expect(website.createCloudWorkflow).toHaveBeenCalledTimes(2));
    const calls = website.createCloudWorkflow.mock.calls;
    expect(calls[0][1].workflow.id).not.toBe('original-server');
    expect(calls[1][1].workflow.id).not.toBe('original-server');
    expect(calls[0][1].workflow.id).not.toBe(calls[1][1].workflow.id);
    expect(calls[0][1].clientRequestId).not.toBe(calls[1][1].clientRequestId);
    await waitFor(() => expect(result.current.workflows.filter(wf => wf.id?.startsWith('server-'))).toHaveLength(2));
    expect(result.current.workflows.some(wf => wf.id === 'original-server')).toBe(true);
    expect(website.saveCloudWorkflow.mock.calls.some(([wf]) => wf.id === 'original-server')).toBe(false);
  });

  it('creates a cloud row for a draft during a cloud listing outage', async () => {
    website.listCloudWorkflows.mockRejectedValue(new Error('temporary outage'));
    const { result } = renderHook(() => useWorkflow(), { wrapper: cloudWrapper() });
    await waitFor(() => expect(result.current.cloudLoadError).toBe(true));
    act(() => result.current.addWorkflow(workflow('local-draft')));
    await waitFor(() => expect(website.createCloudWorkflow).toHaveBeenCalledWith('local-draft', expect.any(Object)));
    await waitFor(() => expect(result.current.workflows.some(wf => wf.id?.startsWith('server-'))).toBe(true));
  });

  it('keeps edits made during creation and saves the latest revision under the server ID', async () => {
    website.listCloudWorkflows.mockResolvedValue([{ id: 'first' }]);
    website.getCloudWorkflow.mockResolvedValue(workflow('first'));
    let finishCreate!: (created: Workflow) => void;
    website.createCloudWorkflow.mockReturnValueOnce(new Promise<Workflow>(resolve => { finishCreate = resolve; }));
    const { result } = renderHook(() => useWorkflow(), { wrapper: cloudWrapper() });
    await waitFor(() => expect(result.current.cloudRestored).toBe(true));
    let draftId = '';
    act(() => { draftId = result.current.addWorkflow(workflow('import-draft'))!; });
    await waitFor(() => expect(website.createCloudWorkflow).toHaveBeenCalledTimes(1));
    act(() => result.current.retryCloudSave(draftId));
    expect(website.createCloudWorkflow).toHaveBeenCalledTimes(1);
    act(() => result.current.updateWorkflow(result.current.workflows.findIndex(wf => wf.id === draftId), {
      name: 'Edited during creation',
    }));
    await act(async () => { finishCreate(workflow('server-import')); });
    await waitFor(() => expect(website.saveCloudWorkflow).toHaveBeenCalledWith(
      expect.objectContaining({ id: 'server-import', name: 'Edited during creation' }),
      writeContext,
    ), { timeout: 3000 });
    expect(result.current.workflows.some(wf => wf.id === draftId)).toBe(false);
  });

  it('retries a failed creation with the same request ID and preserves its draft', async () => {
    website.listCloudWorkflows.mockResolvedValue([{ id: 'first' }]);
    website.getCloudWorkflow.mockResolvedValue(workflow('first'));
    website.createCloudWorkflow.mockRejectedValueOnce(new Error('lost response'));
    const { result } = renderHook(() => useWorkflow(), { wrapper: cloudWrapper() });
    await waitFor(() => expect(result.current.cloudRestored).toBe(true));
    let draftId = '';
    act(() => { draftId = result.current.addWorkflow(workflow('retry-draft'))!; });
    await waitFor(() => expect(result.current.cloudSaveStates[draftId]?.phase).toBe('error'));
    const firstRequestId = website.createCloudWorkflow.mock.calls[0][1].clientRequestId;
    expect(result.current.workflows.some(wf => wf.id === draftId)).toBe(true);
    act(() => result.current.retryCloudSave(draftId));
    await waitFor(() => expect(website.createCloudWorkflow).toHaveBeenCalledTimes(2));
    expect(website.createCloudWorkflow.mock.calls[1][1].clientRequestId).toBe(firstRequestId);
    await waitFor(() => expect(result.current.workflows.some(wf => wf.id?.startsWith('server-'))).toBe(true));
  });

  it('replays a saved draft with its original request ID after remount', async () => {
    website.listCloudWorkflows.mockResolvedValue([{ id: 'first' }]);
    website.getCloudWorkflow.mockResolvedValue(workflow('first'));
    website.createCloudWorkflow.mockRejectedValueOnce(new Error('lost response'));
    const first = renderHook(() => useWorkflow(), { wrapper: cloudWrapper() });
    await waitFor(() => expect(first.result.current.cloudRestored).toBe(true));
    let draftId = '';
    act(() => { draftId = first.result.current.addWorkflow(workflow('replay-draft'))!; });
    await waitFor(() => expect(first.result.current.cloudSaveStates[draftId]?.phase).toBe('error'));
    const requestId = website.createCloudWorkflow.mock.calls[0][1].clientRequestId;
    expect(JSON.parse(localStorage.getItem('bionodulo.cloud.drafts.user-a.team-a') || '[]')[0].cloudRequestId).toBe(requestId);
    first.unmount();

    renderHook(() => useWorkflow(), { wrapper: cloudWrapper() });
    await waitFor(() => expect(website.createCloudWorkflow).toHaveBeenCalledTimes(2));
    expect(website.createCloudWorkflow.mock.calls[1][1].clientRequestId).toBe(requestId);
  });

  it('restores every unresolved draft beyond the server open-tab limit', async () => {
    const drafts = Array.from({ length: 9 }, (_, index) => ({
      ...workflow(`draft-${index}`), cloudRequestId: `123e4567-e89b-42d3-a456-42661417400${index}`,
    }));
    localStorage.setItem('bionodulo.cloud.drafts.user-a.team-a', JSON.stringify(drafts));
    website.listCloudWorkflows.mockResolvedValue([]);
    website.createCloudWorkflow.mockRejectedValue(new Error('offline'));
    openTabs.readOpenWorkflows.mockReturnValue([]);
    const { result } = renderHook(() => useWorkflow(), { wrapper: cloudWrapper() });
    await waitFor(() => expect(result.current.cloudRestored).toBe(true));
    expect(result.current.workflows.map(wf => wf.name)).toEqual(drafts.map(wf => wf.name));
    await waitFor(() => expect(website.createCloudWorkflow).toHaveBeenCalledTimes(9));
  });

  it('recovers an ambiguous create response, saves later edits, and restores the server tab', async () => {
    let serverWorkflow: Workflow | null = null;
    let originalRequestId = '';
    website.listCloudWorkflows.mockImplementation(async () => serverWorkflow ? [{ id: serverWorkflow.id }] : []);
    website.getCloudWorkflow.mockImplementation(async () => serverWorkflow);
    website.createCloudWorkflow.mockImplementation(async (_name: string, options: { clientRequestId: string; workflow: Workflow }) => {
      if (!serverWorkflow) {
        originalRequestId = options.clientRequestId;
        serverWorkflow = { ...options.workflow, id: 'server-import' };
        throw new Error('response lost after commit');
      }
      expect(options.clientRequestId).toBe(originalRequestId);
      return serverWorkflow;
    });
    website.saveCloudWorkflow.mockImplementation(async (wf: Workflow) => { serverWorkflow = wf; });
    openTabs.readOpenWorkflows.mockReturnValue([]);
    const first = renderHook(() => useWorkflow(), { wrapper: cloudWrapper() });
    await waitFor(() => expect(first.result.current.cloudRestored).toBe(true));
    let draftId = '';
    act(() => { draftId = first.result.current.addWorkflow(workflow('import-draft'))!; });
    await waitFor(() => expect(first.result.current.cloudSaveStates[draftId]?.phase).toBe('error'));
    act(() => first.result.current.updateWorkflow(1, { name: 'Imported then edited' }));
    first.unmount();

    // The POST committed before its response was lost; the list already shows
    // that server row when this browser reloads with its unresolved draft.
    openTabs.readOpenWorkflows.mockReturnValue(null);
    const replay = renderHook(() => useWorkflow(), { wrapper: cloudWrapper() });
    await waitFor(() => expect(website.createCloudWorkflow).toHaveBeenCalledTimes(2));
    await waitFor(() => expect(website.saveCloudWorkflow).toHaveBeenCalledWith(
      expect.objectContaining({ id: 'server-import', name: 'Imported then edited' }),
      writeContext,
    ), { timeout: 3000 });
    await waitFor(() => expect(replay.result.current.workflows.some(wf => wf.id === 'server-import')).toBe(true));
    expect(replay.result.current.workflows.filter(wf => wf.id === 'server-import')).toHaveLength(1);
    replay.unmount();

    openTabs.readOpenWorkflows.mockReturnValue(['server-import']);
    const restored = renderHook(() => useWorkflow(), { wrapper: cloudWrapper() });
    await waitFor(() => expect(restored.result.current.cloudRestored).toBe(true));
    expect(restored.result.current.workflows.some(wf => wf.id === 'server-import' && wf.name === 'Imported then edited')).toBe(true);
    expect(website.createCloudWorkflow).toHaveBeenCalledTimes(2);
  });

  it('does not replay an account or team draft into another destination', async () => {
    website.listCloudWorkflows.mockResolvedValue([]);
    openTabs.readOpenWorkflows.mockReturnValue([]);
    website.createCloudWorkflow.mockRejectedValueOnce(new Error('offline'));
    const first = renderHook(() => useWorkflow(), { wrapper: cloudWrapper('user-a', 'team-a') });
    await waitFor(() => expect(first.result.current.cloudRestored).toBe(true));
    let draftId = '';
    act(() => { draftId = first.result.current.addWorkflow(workflow('private-draft'))!; });
    await waitFor(() => expect(first.result.current.cloudSaveStates[draftId]?.phase).toBe('error'));
    first.unmount();
    const otherTeam = renderHook(() => useWorkflow(), { wrapper: cloudWrapper('user-a', 'team-b') });
    await waitFor(() => expect(otherTeam.result.current.cloudRestored).toBe(true));
    expect(otherTeam.result.current.workflows.some(wf => wf.name === 'private-draft')).toBe(false);
    otherTeam.unmount();
    const otherUser = renderHook(() => useWorkflow(), { wrapper: cloudWrapper('user-b', 'team-a') });
    await waitFor(() => expect(otherUser.result.current.cloudRestored).toBe(true));
    expect(otherUser.result.current.workflows.some(wf => wf.name === 'private-draft')).toBe(false);
    expect(website.createCloudWorkflow).toHaveBeenCalledTimes(1);
  });

  it('isolates an in-memory draft when the active team changes without remounting', async () => {
    website.listCloudWorkflows.mockResolvedValue([]);
    openTabs.readOpenWorkflows.mockReturnValue([]);
    website.createCloudWorkflow.mockRejectedValueOnce(new Error('offline'));
    let store!: ReturnType<typeof createStore>;
    const { result } = renderHook(() => useWorkflow(), {
      wrapper: cloudWrapper('user-a', 'team-a', value => { store = value; }),
    });
    await waitFor(() => expect(result.current.cloudRestored).toBe(true));
    let draftId = '';
    act(() => { draftId = result.current.addWorkflow(workflow('team-a-draft'))!; });
    await waitFor(() => expect(result.current.cloudSaveStates[draftId]?.phase).toBe('error'));
    act(() => store.set(cloudConfigAtom, {
      ...store.get(cloudConfigAtom)!,
      team: { id: 'team-b', name: 'Team B' },
    }));
    await waitFor(() => expect(result.current.cloudRestored).toBe(true));
    expect(result.current.workflows.some(wf => wf.name === 'team-a-draft')).toBe(false);
    expect(JSON.parse(localStorage.getItem('bionodulo.cloud.drafts.user-a.team-a') || '[]')[0].name).toBe('team-a-draft');
    expect(website.createCloudWorkflow).toHaveBeenCalledTimes(1);
  });

  it('waits for /api/me before cloud restore and carries only edits made while identity loads', async () => {
    localStorage.setItem('bionodulo.local.workflows', JSON.stringify({
      workflows: [workflow('old-local-work')], activeIndex: 0,
    }));
    website.listCloudWorkflows.mockResolvedValue([]);
    openTabs.readOpenWorkflows.mockReturnValue([]);
    const store = createStore();
    store.set(cloudConfigAtom, { cloudMode: false, editorMode: true, user: null, team: null,
      plan: null, credits: null, accountUrl: null, clerkPublishableKey: null, oauth: null });
    const Wrapper = ({ children }: { children: ReactNode }) => <Provider store={store}>{children}</Provider>;
    const { result } = renderHook(() => useWorkflow(), { wrapper: Wrapper });
    expect(website.listCloudWorkflows).not.toHaveBeenCalled();
    act(() => result.current.addWorkflow(workflow('fresh-import')));
    act(() => store.set(cloudConfigAtom, { ...store.get(cloudConfigAtom)!,
      user: { id: 'user-a', name: 'A', email: 'a@example.test' },
      team: { id: 'team-a', name: 'A' },
    }));
    await waitFor(() => expect(result.current.cloudRestored).toBe(true));
    await waitFor(() => expect(website.createCloudWorkflow).toHaveBeenCalledOnce());
    expect(website.createCloudWorkflow.mock.calls[0][1].workflow.name).toBe('fresh-import');
    expect(result.current.workflows.some(wf => wf.name === 'old-local-work')).toBe(false);
  });

  it('keeps pre-identity edits in memory if draft storage fails during identity arrival', async () => {
    website.listCloudWorkflows.mockResolvedValue([]);
    openTabs.readOpenWorkflows.mockReturnValue([]);
    const store = createStore();
    store.set(cloudConfigAtom, { cloudMode: false, editorMode: true, user: null, team: null,
      plan: null, credits: null, accountUrl: null, clerkPublishableKey: null, oauth: null });
    const Wrapper = ({ children }: { children: ReactNode }) => <Provider store={store}>{children}</Provider>;
    const { result } = renderHook(() => useWorkflow(), { wrapper: Wrapper });
    let draftId = '';
    act(() => { draftId = result.current.addWorkflow(workflow('before-identity'))!; });
    const originalSetItem = localStorage.setItem.bind(localStorage);
    const storage = vi.spyOn(Storage.prototype, 'setItem').mockImplementation((key, value) => {
      if (key.startsWith('bionodulo.cloud.drafts.')) throw new DOMException('Quota exceeded', 'QuotaExceededError');
      originalSetItem(key, value);
    });
    try {
      act(() => store.set(cloudConfigAtom, { ...store.get(cloudConfigAtom)!,
        user: { id: 'user-a', name: 'A', email: 'a@example.test' },
        team: { id: 'team-a', name: 'A' },
      }));
      await waitFor(() => expect(result.current.cloudSaveStates[draftId]?.phase).toBe('error'));
      expect(result.current.workflows.some(wf => wf.name === 'before-identity')).toBe(true);
      expect(website.createCloudWorkflow).not.toHaveBeenCalled();
      storage.mockRestore();
      act(() => result.current.retryCloudSave(draftId));
      await waitFor(() => expect(result.current.cloudRestored).toBe(true));
      await waitFor(() => expect(website.createCloudWorkflow).toHaveBeenCalledOnce());
    } finally { storage.mockRestore(); }
  });

  it('keeps a draft visible and retryable when browser storage rejects its request key', async () => {
    website.listCloudWorkflows.mockResolvedValue([]);
    openTabs.readOpenWorkflows.mockReturnValue([]);
    const originalSetItem = localStorage.setItem.bind(localStorage);
    const storage = vi.spyOn(Storage.prototype, 'setItem').mockImplementation((key, value) => {
      if (key.startsWith('bionodulo.cloud.drafts.')) throw new DOMException('Quota exceeded', 'QuotaExceededError');
      originalSetItem(key, value);
    });
    try {
      const { result } = renderHook(() => useWorkflow(), { wrapper: cloudWrapper() });
      await waitFor(() => expect(result.current.cloudRestored).toBe(true));
      let draftId = '';
      act(() => { draftId = result.current.addWorkflow(workflow('quota-draft'))!; });
      await waitFor(() => expect(result.current.cloudSaveStates[draftId]?.phase).toBe('error'));
      expect(result.current.workflows.some(wf => wf.name === 'quota-draft')).toBe(true);
      expect(website.createCloudWorkflow).not.toHaveBeenCalled();
      storage.mockRestore();
      act(() => result.current.retryCloudSave(draftId));
      await waitFor(() => expect(website.createCloudWorkflow).toHaveBeenCalledOnce());
    } finally { storage.mockRestore(); }
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
    expect(result.current.activeWorkflow.name).toBe('second');
    await waitFor(() => expect(website.saveCloudWorkflow).toHaveBeenCalledWith(
      expect.objectContaining({ id: 'first', name: 'Edited first' }),
      writeContext,
    ), { timeout: 3000 });
  });

  it('keeps a failed save unsaved until the user retries successfully', async () => {
    website.listCloudWorkflows.mockResolvedValue([{ id: 'first' }]);
    website.getCloudWorkflow.mockResolvedValue(workflow('first'));
    const { result } = renderHook(() => useWorkflow(), { wrapper: cloudWrapper() });
    await waitFor(() => expect(result.current.cloudRestored).toBe(true));
    website.saveCloudWorkflow.mockRejectedValueOnce(new Error('offline'));
    act(() => result.current.updateWorkflow(0, { name: 'Unsaved edit' }));
    await waitFor(() => expect(result.current.cloudSaveStates.first?.phase).toBe('error'), { timeout: 3000 });
    expect(website.saveCloudWorkflow).toHaveBeenCalledWith(expect.objectContaining({ name: 'Unsaved edit' }), writeContext);
    act(() => result.current.retryCloudSave('first'));
    await waitFor(() => expect(result.current.cloudSaveStates.first).toBeUndefined());
    expect(website.saveCloudWorkflow).toHaveBeenCalledTimes(2);
  });

  it('clears failed-save state when the user closes that tab', async () => {
    website.listCloudWorkflows.mockResolvedValue([{ id: 'first' }]);
    website.getCloudWorkflow.mockResolvedValue(workflow('first'));
    const { result } = renderHook(() => useWorkflow(), { wrapper: cloudWrapper() });
    await waitFor(() => expect(result.current.cloudRestored).toBe(true));
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
    expect(website.saveCloudWorkflow).toHaveBeenLastCalledWith(expect.objectContaining({ name: 'Latest edit' }), writeContext);
    expect(result.current.cloudSaveStates.first).toBeDefined();
    await act(async () => { resolveSecond(); });
    await waitFor(() => expect(result.current.cloudSaveStates.first).toBeUndefined());
  }, 8000);

  it('does not send a queued old-team save after switching teams', async () => {
    website.listCloudWorkflows.mockResolvedValueOnce([{ id: 'first' }]).mockResolvedValue([]);
    website.getCloudWorkflow.mockResolvedValue(workflow('first'));
    let finishFirst!: () => void;
    website.saveCloudWorkflow.mockImplementationOnce(() => new Promise<void>(resolve => { finishFirst = resolve; }));
    let store!: ReturnType<typeof createStore>;
    const { result } = renderHook(() => useWorkflow(), {
      wrapper: cloudWrapper('user-a', 'team-a', value => { store = value; }),
    });
    await waitFor(() => expect(result.current.cloudRestored).toBe(true));
    act(() => result.current.updateWorkflow(0, { name: 'First revision' }));
    await waitFor(() => expect(website.saveCloudWorkflow).toHaveBeenCalledTimes(1), { timeout: 3000 });
    act(() => result.current.updateWorkflow(0, { name: 'Queued revision' }));
    await new Promise(resolve => setTimeout(resolve, 1300));
    expect(website.saveCloudWorkflow).toHaveBeenCalledTimes(1);
    act(() => store.set(cloudConfigAtom, {
      ...store.get(cloudConfigAtom)!, team: { id: 'team-b', name: 'Team B' },
    }));
    await act(async () => { finishFirst(); });
    await waitFor(() => expect(result.current.cloudRestored).toBe(true));
    await new Promise(resolve => setTimeout(resolve, 1300));
    expect(website.saveCloudWorkflow).toHaveBeenCalledTimes(1);
    expect(result.current.workflows.some(wf => wf.name === 'Queued revision')).toBe(true);
    expect(result.current.cloudSaveStates.first?.phase).toBe('error');
    act(() => store.set(cloudConfigAtom, {
      ...store.get(cloudConfigAtom)!, team: { id: 'team-a', name: 'Team A' },
    }));
    act(() => result.current.retryCloudSave('first'));
    await waitFor(() => expect(website.saveCloudWorkflow).toHaveBeenCalledTimes(2));
    expect(website.saveCloudWorkflow).toHaveBeenLastCalledWith(expect.objectContaining({
      id: 'first', name: 'Queued revision',
    }), writeContext);
  }, 9000);
});
