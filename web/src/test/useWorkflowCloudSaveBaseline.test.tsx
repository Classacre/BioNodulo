import { act, renderHook } from '@testing-library/react';
import { Provider, createStore } from 'jotai';
import type { ReactNode } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { Workflow } from '../types';
import { cloudConfigAtom } from '../state/appAtoms';
import { useOwnedWorkflowHistory } from '../hooks/workflow/useOwnedWorkflowHistory';

const website = vi.hoisted(() => ({ listCloudWorkflows: vi.fn(), getCloudWorkflow: vi.fn(),
  createCloudWorkflow: vi.fn(), saveCloudWorkflow: vi.fn(), submitCloudRun: vi.fn() }));
vi.mock('../api/website', async importOriginal => ({
  ...(await importOriginal<typeof import('../api/website')>()), ...website,
}));
vi.mock('../state/logging', () => ({ logError: vi.fn() }));

import { useWorkflow } from '../hooks/workflow/useWorkflow';

function original(): Workflow {
  return { id: 'saved-a', name: 'Owned baseline fixture', app: 'bionodulo', version: '2.0',
    nodes: [{ id: 'text', type: 'string_format', position: [0, 0], params: { template: 'A' } }],
    edges: [], groups: [], parameters: [], outputs: {} };
}

const writeContext = { expectedUserId: 'user-a', expectedTeamId: 'team-a' };

function setup() {
  const store = createStore();
  store.set(cloudConfigAtom, { cloudMode: false, editorMode: true,
    user: { id: 'user-a', name: 'A', email: 'a@example.test' },
    team: { id: 'team-a', name: 'A' }, plan: null, credits: null, accountUrl: null,
    clerkPublishableKey: null, oauth: null });
  function Wrapper({ children }: { children: ReactNode }) { return <Provider store={store}>{children}</Provider>; }
  const hook = renderHook(() => {
    const workflow = useWorkflow();
    const history = useOwnedWorkflowHistory({ owner: store.get(cloudConfigAtom)?.team?.id,
      documentId: workflow.activeWorkflow.id!, workflow: workflow.activeWorkflow,
      getViewport: () => ({ x: 0, y: 0, scale: 1 }),
      // App restores viewport separately; it is not persisted as graph content.
      apply: patch => workflow.updateWorkflow(workflow.activeIndex, {
        nodes: patch.nodes, edges: patch.edges, groups: patch.groups, parameters: patch.parameters,
      }) });
    const edit = (text: string) => {
      const nodes = workflow.activeWorkflow.nodes.map(node => ({ ...node, params: { ...node.params, template: text } }));
      history.queuePatch({ nodes });
      workflow.updateWorkflow(workflow.activeIndex, { nodes });
    };
    return { ...workflow, history, edit };
  }, { wrapper: Wrapper });
  const switchTeam = (id: string) => act(() => store.set(cloudConfigAtom,
    { ...store.get(cloudConfigAtom)!, team: { id, name: id } }));
  return { ...hook, switchTeam };
}

async function tick(milliseconds = 0) { await act(async () => { await vi.advanceTimersByTimeAsync(milliseconds); }); }
function savedTexts() { return website.saveCloudWorkflow.mock.calls.map(([workflow]) => workflow.nodes[0].params.template); }

describe('cloud save baseline follows successful persistence', () => {
  beforeEach(() => {
    vi.useFakeTimers(); localStorage.clear(); vi.resetAllMocks();
    website.listCloudWorkflows.mockResolvedValueOnce([{ id: 'saved-a' }]).mockResolvedValue([]);
    website.getCloudWorkflow.mockResolvedValue(original());
    website.saveCloudWorkflow.mockResolvedValue(undefined);
  });
  afterEach(() => vi.useRealTimers());

  it('persists real history Undo to initial A after successful B, then Redo B', async () => {
    const hook = setup(); await tick();
    expect(hook.result.current.cloudRestored).toBe(true);
    act(() => hook.result.current.edit('B')); await tick(1200);
    expect(savedTexts()).toEqual(['B']);
    expect(hook.result.current.cloudSaveStates['saved-a']).toBeUndefined();
    act(() => hook.result.current.history.undo());
    expect(hook.result.current.activeWorkflow.nodes[0].params.template).toBe('A');
    await tick(1200);
    expect(savedTexts()).toEqual(['B', 'A']);
    expect(website.saveCloudWorkflow).toHaveBeenLastCalledWith(expect.objectContaining({ id: 'saved-a' }), writeContext);
    expect(hook.result.current.cloudSaveStates['saved-a']).toBeUndefined();
    act(() => hook.result.current.history.redo()); await tick(1200);
    expect(savedTexts()).toEqual(['B', 'A', 'B']);
    await tick(2400); expect(savedTexts()).toEqual(['B', 'A', 'B']);
    hook.unmount();
  });

  it('cancels unsent B on Undo A, but persists later saved B and Undo A', async () => {
    const hook = setup(); await tick();
    act(() => hook.result.current.edit('B')); await tick(350);
    act(() => hook.result.current.history.undo()); await tick(1500);
    expect(savedTexts()).toEqual([]);
    act(() => hook.result.current.history.redo()); await tick(1200);
    expect(savedTexts()).toEqual(['B']);
    act(() => hook.result.current.history.undo()); await tick(1200);
    expect(savedTexts()).toEqual(['B', 'A']);
    hook.unmount();
  });

  it.each([0, 1200])('keeps Undo A behind an in-flight B with %i ms of queued debounce', async delay => {
    let finishB!: () => void;
    website.saveCloudWorkflow.mockImplementationOnce(() => new Promise<void>(resolve => { finishB = resolve; }));
    const hook = setup(); await tick();
    act(() => hook.result.current.edit('B')); await tick(1200);
    act(() => hook.result.current.history.undo()); await tick(delay);
    expect(savedTexts()).toEqual(['B']);
    expect(hook.result.current.cloudSaveStates['saved-a']).toBeDefined();
    await act(async () => { finishB(); }); await tick(1200);
    expect(savedTexts()).toEqual(['B', 'A']);
    expect(hook.result.current.activeWorkflow.nodes[0].params.template).toBe('A');
    expect(hook.result.current.cloudSaveStates['saved-a']).toBeUndefined();
    hook.unmount();
  });

  it('ignores retired owner save completion and preserves returning dirty draft and baseline', async () => {
    let finishRetired!: () => void;
    website.saveCloudWorkflow.mockImplementationOnce(() => new Promise<void>(resolve => { finishRetired = resolve; }));
    const hook = setup(); await tick();
    act(() => hook.result.current.edit('B')); await tick(1200);
    hook.switchTeam('team-b'); await tick();
    expect(hook.result.current.workflows.some(workflow => workflow.id === 'saved-a')).toBe(false);
    await act(async () => { finishRetired(); });
    expect(hook.result.current.cloudSaveStates).toEqual({});
    hook.switchTeam('team-a'); await tick();
    expect(hook.result.current.activeWorkflow).toMatchObject({ id: 'saved-a', nodes: [{ params: { template: 'B' } }] });
    expect(hook.result.current.cloudSaveStates['saved-a']?.phase).toBe('error');
    expect(savedTexts()).toEqual(['B']);
    act(() => hook.result.current.retryCloudSave('saved-a')); await tick();
    expect(savedTexts()).toEqual(['B', 'B']);
    expect(hook.result.current.cloudSaveStates['saved-a']).toBeUndefined();
    act(() => hook.result.current.edit('A')); await tick(1200);
    expect(savedTexts()).toEqual(['B', 'B', 'A']);
    expect(website.saveCloudWorkflow.mock.calls.every(([, context]) => context.expectedTeamId === 'team-a')).toBe(true);
    expect(website.createCloudWorkflow).not.toHaveBeenCalled();
    hook.unmount();
  });
});
