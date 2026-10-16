import { act, cleanup, renderHook, waitFor } from '@testing-library/react';
import { Provider, createStore } from 'jotai';
import type { ReactNode } from 'react';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import ts from 'typescript';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { Workflow } from '../types';
import { cloudConfigAtom } from '../state/appAtoms';
import { readOpenWorkflowRecord, writeOpenWorkflows } from '../state/openWorkflows';
import { useCollabRoomTarget } from '../hooks/collab/useCollabRoomTarget';

const website = vi.hoisted(() => ({
  listCloudWorkflows: vi.fn(), getCloudWorkflow: vi.fn(),
  createCloudWorkflow: vi.fn(), saveCloudWorkflow: vi.fn(), submitCloudRun: vi.fn(),
}));
vi.mock('../api/website', async importOriginal => ({
  ...(await importOriginal<typeof import('../api/website')>()), ...website,
}));
vi.mock('../state/logging', () => ({ logError: vi.fn() }));

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
const scope = 'user-a.team-a';
const key = `bionodulo.workflows.open.${scope}`;

function workflow(id: string): Workflow {
  return { id, version: '2.0', app: 'bionodulo', name: id, description: '',
    nodes: [{ id: `node-${id}`, type: 'input_string', position: [0, 0], params: {} }],
    edges: [], groups: [], outputs: {}, parameters: [] };
}

function cloudWrapper() {
  const store = createStore();
  store.set(cloudConfigAtom, {
    editorMode: true, cloudMode: false,
    user: { id: 'user-a', name: 'User', email: 'user@example.test' },
    team: { id: 'team-a', name: 'Team' },
    plan: null, credits: null, accountUrl: null, clerkPublishableKey: null, oauth: null,
  });
  return { store, wrapper: ({ children }: { children: ReactNode }) => <Provider store={store}>{children}</Provider> };
}

beforeEach(() => {
  storage.clear();
  vi.clearAllMocks();
  Object.defineProperty(window, 'localStorage', { value: localStorageStub, configurable: true });
  vi.stubGlobal('localStorage', localStorageStub);
  window.history.replaceState({}, '', '/');
  website.getCloudWorkflow.mockImplementation(async (id: string) => workflow(id));
  website.saveCloudWorkflow.mockResolvedValue({});
  website.submitCloudRun.mockResolvedValue({ runId: 'test-run', dashboardUrl: '/runs/test-run' });
});

function useEditorIdentity() {
  const editor = useWorkflow();
  return { ...editor, ...useCollabRoomTarget(editor.activeWorkflow.id) };
}

describe('App navigation and explicit collaboration identity', () => {
  it('keeps startup, opened and newly created document IDs distinct through template editing and submission', async () => {
    window.history.replaceState({}, '', '/?workflow=startup-assembly');
    website.listCloudWorkflows.mockResolvedValue([{ id: 'startup-assembly' }, { id: 'opened-other' }]);
    website.createCloudWorkflow.mockImplementationOnce(async (name: string, options: { workflow: Workflow }) => ({
      ...options.workflow, id: 'new-variant', name,
    }));
    const hook = renderHook(() => useEditorIdentity(), cloudWrapper());
    await waitFor(() => expect(hook.result.current.activeWorkflow.id).toBe('startup-assembly'));
    expect(hook.result.current.requestedWorkflowId).toBeNull();
    await act(async () => { await hook.result.current.openCloudWorkflow('opened-other'); });
    expect(hook.result.current.activeWorkflow.id).toBe('opened-other');
    await act(async () => { await hook.result.current.newCloudWorkflow(); });
    expect(hook.result.current.activeWorkflow.id).toBe('new-variant');
    act(() => hook.result.current.updateWorkflow(hook.result.current.activeIndex, {
      name: 'New template', nodes: workflow('template').nodes,
    }));
    await act(async () => { await hook.result.current.submitRun(hook.result.current.activeWorkflow); });
    expect(website.saveCloudWorkflow).toHaveBeenCalledWith(
      expect.objectContaining({ id: 'new-variant', name: 'New template' }),
      { expectedUserId: 'user-a', expectedTeamId: 'team-a' },
    );
    expect(website.submitCloudRun).toHaveBeenCalledWith('new-variant', undefined, undefined, undefined);
    expect(website.saveCloudWorkflow.mock.calls.every(([saved]) => saved.id === 'new-variant')).toBe(true);
    expect(hook.result.current.workflows.map(item => item.id)).toEqual(['startup-assembly', 'opened-other', 'new-variant']);
    expect(hook.result.current.workflows[0].nodes[0].id).toBe('node-startup-assembly');
  });

  it('gates an explicit room join without relabeling the current document and does not reseed on leave', async () => {
    window.history.replaceState({}, '', '/?workflow=startup');
    website.listCloudWorkflows.mockResolvedValue([{ id: 'startup' }, { id: 'joined' }]);
    const hook = renderHook(() => useEditorIdentity(), cloudWrapper());
    await waitFor(() => expect(hook.result.current.activeWorkflow.id).toBe('startup'));
    act(() => hook.result.current.setRequestedWorkflowId('joined'));
    expect(hook.result.current.requestedWorkflowPending).toBe(true);
    expect(hook.result.current.activeWorkflow.id).toBe('startup');
    await act(async () => { await hook.result.current.openCloudWorkflow('joined'); });
    expect(hook.result.current.requestedWorkflowPending).toBe(false);
    expect(hook.result.current.activeWorkflow.id).toBe('joined');
    act(() => hook.result.current.setRequestedWorkflowId(null));
    hook.rerender();
    expect(hook.result.current.requestedWorkflowId).toBeNull();
    expect(hook.result.current.workflows.map(item => item.id)).toEqual(['startup', 'joined']);
    expect(window.location.search).toBe('?workflow=startup');
    expect(website.saveCloudWorkflow).not.toHaveBeenCalled();
  });

  it('reports a failed cloud open explicitly without adopting or saving the requested room ID', async () => {
    website.listCloudWorkflows.mockResolvedValue([{ id: 'current' }]);
    const hook = renderHook(() => useEditorIdentity(), cloudWrapper());
    await waitFor(() => expect(hook.result.current.activeWorkflow.id).toBe('current'));
    act(() => hook.result.current.setRequestedWorkflowId('unavailable'));
    website.getCloudWorkflow.mockRejectedValueOnce(new Error('forbidden or unavailable'));
    let opened: boolean | undefined;
    await act(async () => { opened = await hook.result.current.openCloudWorkflow('unavailable'); });
    expect(opened).toBe(false);
    expect(hook.result.current.activeWorkflow.id).toBe('current');
    expect(hook.result.current.requestedWorkflowPending).toBe(true);
    expect(hook.result.current.workflows.map(item => item.id)).toEqual(['current']);
    expect(website.saveCloudWorkflow).not.toHaveBeenCalled();
  });

  it('reports success for an already open target without a redundant fetch', async () => {
    website.listCloudWorkflows.mockResolvedValue([{ id: 'open' }]);
    const hook = renderHook(() => useEditorIdentity(), cloudWrapper());
    await waitFor(() => expect(hook.result.current.activeWorkflow.id).toBe('open'));
    website.getCloudWorkflow.mockClear();
    let opened: boolean | undefined;
    await act(async () => { opened = await hook.result.current.openCloudWorkflow('open'); });
    expect(opened).toBe(true);
    expect(website.getCloudWorkflow).not.toHaveBeenCalled();
    expect(hook.result.current.activeWorkflow.id).toBe('open');
  });

  it('returns false for an old open callback after a team A to B to A roundtrip', async () => {
    writeOpenWorkflows(['a'], scope, 'a');
    writeOpenWorkflows(['b'], 'user-a.team-b', 'b');
    website.listCloudWorkflows.mockResolvedValueOnce([{ id: 'a' }]).mockResolvedValueOnce([{ id: 'b' }]);
    const context = cloudWrapper();
    const hook = renderHook(() => useEditorIdentity(), context);
    await waitFor(() => expect(hook.result.current.activeWorkflow.id).toBe('a'));
    const staleOpen = hook.result.current.openCloudWorkflow;
    const original = context.store.get(cloudConfigAtom)!;
    act(() => context.store.set(cloudConfigAtom, { ...original, team: { id: 'team-b', name: 'Other' } }));
    await waitFor(() => expect(hook.result.current.activeWorkflow.id).toBe('b'));
    act(() => context.store.set(cloudConfigAtom, original));
    await waitFor(() => expect(hook.result.current.activeWorkflow.id).toBe('a'));
    website.getCloudWorkflow.mockClear();
    let opened: boolean | undefined;
    await act(async () => { opened = await staleOpen('a'); });
    expect(opened).toBe(false);
    expect(website.getCloudWorkflow).not.toHaveBeenCalled();
    expect(hook.result.current.activeWorkflow.id).toBe('a');
  });

  it('allows an explicit local/guest adoption while subsequent tabs keep their own IDs', async () => {
    website.listCloudWorkflows.mockResolvedValue([]);
    const hook = renderHook(() => useEditorIdentity(), cloudWrapper());
    await waitFor(() => expect(hook.result.current.cloudRestored).toBe(true));
    act(() => {
      hook.result.current.setRequestedWorkflowId('explicit-room');
      hook.result.current.updateWorkflow(hook.result.current.activeIndex, { id: 'explicit-room' });
    });
    expect(hook.result.current.activeWorkflow.id).toBe('explicit-room');
    expect(hook.result.current.requestedWorkflowPending).toBe(false);
    act(() => hook.result.current.addCloudWorkflow(workflow('another-document')));
    expect(hook.result.current.activeWorkflow.id).toBe('another-document');
    expect(hook.result.current.requestedWorkflowPending).toBe(true);
  });

  it('prevents App effects from assigning a different room/document ID to an existing workflow', () => {
    const source = readFileSync(resolve(__dirname, '../App.tsx'), 'utf8');
    const app = ts.createSourceFile('App.tsx', source, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
    const violations: number[] = [];
    const visit = (node: ts.Node) => {
      if (ts.isCallExpression(node) && ts.isIdentifier(node.expression) && node.expression.text === 'useEffect') {
        const inspect = (child: ts.Node) => {
          if (ts.isCallExpression(child) && ts.isIdentifier(child.expression) && child.expression.text === 'updateWorkflow') {
            const patch = child.arguments[1];
            if (patch && ts.isObjectLiteralExpression(patch) && patch.properties.some(property => (
              ts.isPropertyAssignment(property) && property.name.getText(app) === 'id'
            ))) {
              let parent: ts.Node | undefined = child.parent;
              let onlyMissingId = false;
              while (parent && parent !== node) {
                if (ts.isIfStatement(parent) && parent.expression.getText(app) === '!activeWorkflow.id') onlyMissingId = true;
                parent = parent.parent;
              }
              if (!onlyMissingId) violations.push(app.getLineAndCharacterOfPosition(child.getStart(app)).line + 1);
            }
          }
          ts.forEachChild(child, inspect);
        };
        if (node.arguments[0]) inspect(node.arguments[0]);
      }
      ts.forEachChild(node, visit);
    };
    visit(app);
    expect(violations).toEqual([]);
    expect(source).toContain('useCollabRoomTarget(activeWorkflowId)');
  });
});
afterEach(() => { cleanup(); window.history.replaceState({}, '', '/'); });

describe('real cloud open-tab persistence', () => {
  it('reopens all 17 explicitly opened documents and their newest selected workflow', async () => {
    const ids = Array.from({ length: 17 }, (_, index) => `document-${index}`);
    website.listCloudWorkflows.mockResolvedValue(ids.map(id => ({ id })));
    writeOpenWorkflows(ids.slice(0, 8), scope, ids[0]);
    const first = renderHook(() => useWorkflow(), cloudWrapper());
    await waitFor(() => expect(first.result.current.cloudRestored).toBe(true));
    for (const id of ids.slice(8)) await act(async () => { await first.result.current.openCloudWorkflow(id); });
    expect(readOpenWorkflowRecord(scope)).toEqual({ version: 1, openIds: ids, activeId: ids[16] });
    first.unmount();
    website.getCloudWorkflow.mockClear();
    const second = renderHook(() => useWorkflow(), cloudWrapper());
    await waitFor(() => expect(second.result.current.cloudRestored).toBe(true));
    expect(second.result.current.workflows.map(item => item.id)).toEqual(ids);
    expect(second.result.current.activeWorkflow.id).toBe(ids[16]);
    expect(second.result.current.activeWorkflow.nodes[0].id).toBe(`node-${ids[16]}`);
    expect(website.getCloudWorkflow).toHaveBeenCalledTimes(17);
    expect(website.createCloudWorkflow).not.toHaveBeenCalled();
    expect(website.saveCloudWorkflow).not.toHaveBeenCalled();
  });

  it('persists a selection-only change without changing or saving any graph', async () => {
    website.listCloudWorkflows.mockResolvedValue([{ id: 'older' }, { id: 'newer' }]);
    writeOpenWorkflows(['older', 'newer'], scope, 'newer');
    const first = renderHook(() => useWorkflow(), cloudWrapper());
    await waitFor(() => expect(first.result.current.activeWorkflow.id).toBe('newer'));
    act(() => first.result.current.setActiveIndex(0));
    expect(readOpenWorkflowRecord(scope)?.activeId).toBe('older');
    first.unmount();
    const second = renderHook(() => useWorkflow(), cloudWrapper());
    await waitFor(() => expect(second.result.current.activeWorkflow.id).toBe('older'));
    expect(website.saveCloudWorkflow).not.toHaveBeenCalled();
  });

  it('reads a legacy array and records its restored selection in the versioned format', async () => {
    storage.set(key, JSON.stringify(['a', 'b']));
    website.listCloudWorkflows.mockResolvedValue([{ id: 'a' }, { id: 'b' }]);
    const hook = renderHook(() => useWorkflow(), cloudWrapper());
    await waitFor(() => expect(hook.result.current.cloudRestored).toBe(true));
    expect(hook.result.current.workflows.map(item => item.id)).toEqual(['a', 'b']);
    expect(readOpenWorkflowRecord(scope)).toEqual({ version: 1, openIds: ['a', 'b'], activeId: 'a' });
  });

  it('lets an explicit deep link override the remembered selection', async () => {
    writeOpenWorkflows(['a', 'b'], scope, 'b');
    window.history.replaceState({}, '', '/?workflow=explicit');
    website.listCloudWorkflows.mockResolvedValue([{ id: 'a' }, { id: 'b' }, { id: 'explicit' }]);
    const hook = renderHook(() => useWorkflow(), cloudWrapper());
    await waitFor(() => expect(hook.result.current.activeWorkflow.id).toBe('explicit'));
    expect(hook.result.current.workflows.map(item => item.id)).toEqual(['explicit', 'a', 'b']);
    expect(readOpenWorkflowRecord(scope)?.activeId).toBe('explicit');
  });

  it('preserves a newer selected tab when the initial deep-link fetch completes late', async () => {
    writeOpenWorkflows(['remembered'], scope, 'remembered');
    window.history.replaceState({}, '', '/?workflow=explicit');
    website.listCloudWorkflows.mockResolvedValue([{ id: 'remembered' }, { id: 'explicit' }]);
    let resolveExplicit!: (value: Workflow) => void;
    website.getCloudWorkflow.mockImplementation((id: string) => id === 'explicit'
      ? new Promise<Workflow>(resolve => { resolveExplicit = resolve; }) : Promise.resolve(workflow(id)));
    const hook = renderHook(() => useWorkflow(), cloudWrapper());
    await waitFor(() => expect(website.getCloudWorkflow).toHaveBeenCalledWith('explicit'));
    act(() => {
      hook.result.current.addCloudWorkflow(workflow('new-a'));
      hook.result.current.addCloudWorkflow(workflow('new-b'));
    });
    const selected = hook.result.current.workflows.findIndex(item => item.id === 'new-a');
    act(() => hook.result.current.setActiveIndex(selected));
    await act(async () => { resolveExplicit(workflow('explicit')); });
    await waitFor(() => expect(hook.result.current.cloudRestored).toBe(true));
    expect(hook.result.current.activeWorkflow.id).toBe('new-a');
    expect(readOpenWorkflowRecord(scope)).toEqual({
      version: 1, openIds: ['explicit', 'remembered', 'new-a', 'new-b'], activeId: 'new-a',
    });
  });

  it('preserves a newer manual selection even when that document is also in the restore set', async () => {
    writeOpenWorkflows(['a', 'b'], scope, 'b');
    window.history.replaceState({}, '', '/?workflow=explicit');
    website.listCloudWorkflows.mockResolvedValue([{ id: 'a' }, { id: 'b' }, { id: 'explicit' }]);
    let resolveExplicit!: (value: Workflow) => void;
    website.getCloudWorkflow.mockImplementation((id: string) => id === 'explicit'
      ? new Promise<Workflow>(resolve => { resolveExplicit = resolve; }) : Promise.resolve(workflow(id)));
    const hook = renderHook(() => useWorkflow(), cloudWrapper());
    await waitFor(() => expect(website.getCloudWorkflow).toHaveBeenCalledWith('explicit'));
    await act(async () => { await hook.result.current.openCloudWorkflow('a'); });
    expect(hook.result.current.activeWorkflow.id).toBe('a');
    await act(async () => { resolveExplicit(workflow('explicit')); });
    await waitFor(() => expect(hook.result.current.cloudRestored).toBe(true));
    expect(hook.result.current.activeWorkflow.id).toBe('a');
    expect(readOpenWorkflowRecord(scope)).toEqual({
      version: 1, openIds: ['explicit', 'a', 'b'], activeId: 'a',
    });
  });

  it('still opens only the single most recent workflow when nothing was recorded', async () => {
    website.listCloudWorkflows.mockResolvedValue([{ id: 'recent' }, { id: 'older' }]);
    const hook = renderHook(() => useWorkflow(), cloudWrapper());
    await waitFor(() => expect(hook.result.current.activeWorkflow.id).toBe('recent'));
    expect(hook.result.current.workflows.map(item => item.id)).toEqual(['recent']);
    expect(website.getCloudWorkflow).toHaveBeenCalledTimes(1);
  });

  it('honors an explicitly empty session without reopening recent work', async () => {
    writeOpenWorkflows([], scope);
    website.listCloudWorkflows.mockResolvedValue([{ id: 'recent' }]);
    const hook = renderHook(() => useWorkflow(), cloudWrapper());
    await waitFor(() => expect(hook.result.current.cloudRestored).toBe(true));
    expect(hook.result.current.activeWorkflow.nodes).toEqual([]);
    expect(website.getCloudWorkflow).not.toHaveBeenCalled();
    expect(website.createCloudWorkflow).not.toHaveBeenCalled();
    expect(readOpenWorkflowRecord(scope)).toEqual({ version: 1, openIds: [], activeId: null });
  });

  it('preserves the full remembered record after a partial fetch failure and later manual open', async () => {
    writeOpenWorkflows(['loaded', 'temporarily-unavailable'], scope, 'temporarily-unavailable');
    const before = storage.get(key);
    website.listCloudWorkflows.mockResolvedValue([{ id: 'loaded' }, { id: 'temporarily-unavailable' }, { id: 'manual' }]);
    website.getCloudWorkflow.mockImplementation(async (id: string) => {
      if (id === 'temporarily-unavailable') throw new Error('temporary fetch failure');
      return workflow(id);
    });
    const hook = renderHook(() => useWorkflow(), cloudWrapper());
    await waitFor(() => expect(hook.result.current.cloudLoadError).toBe(true));
    expect(storage.get(key)).toBe(before);
    await act(async () => { await hook.result.current.openCloudWorkflow('manual'); });
    expect(hook.result.current.activeWorkflow.id).toBe('manual');
    expect(storage.get(key)).toBe(before);
  });

  it('records a fast explicit new tab after restore failure without discarding unavailable IDs', async () => {
    writeOpenWorkflows(['unavailable'], scope, 'unavailable');
    website.listCloudWorkflows.mockRejectedValueOnce(new Error('temporary list failure'));
    website.createCloudWorkflow.mockResolvedValueOnce(workflow('created'));
    const hook = renderHook(() => useWorkflow(), cloudWrapper());
    await waitFor(() => expect(hook.result.current.cloudLoadError).toBe(true));
    await act(async () => { await hook.result.current.newCloudWorkflow(); });
    expect(hook.result.current.activeWorkflow.id).toBe('created');
    expect(readOpenWorkflowRecord(scope)).toEqual({
      version: 1, openIds: ['unavailable', 'created'], activeId: 'created',
    });
  });

  it('drops a confirmed deleted ID and selects the first remaining restored document', async () => {
    writeOpenWorkflows(['deleted', 'remaining'], scope, 'deleted');
    website.listCloudWorkflows.mockResolvedValue([{ id: 'remaining' }]);
    const hook = renderHook(() => useWorkflow(), cloudWrapper());
    await waitFor(() => expect(hook.result.current.activeWorkflow.id).toBe('remaining'));
    expect(website.getCloudWorkflow).toHaveBeenCalledTimes(1);
    expect(readOpenWorkflowRecord(scope)).toEqual({ version: 1, openIds: ['remaining'], activeId: 'remaining' });
  });

  it('keeps selected tabs and their records isolated across a live team switch and return', async () => {
    writeOpenWorkflows(['a1', 'a2'], scope, 'a2');
    writeOpenWorkflows(['b1'], 'user-a.team-b', 'b1');
    website.listCloudWorkflows.mockResolvedValueOnce([{ id: 'a1' }, { id: 'a2' }])
      .mockResolvedValueOnce([{ id: 'b1' }]);
    const context = cloudWrapper();
    const hook = renderHook(() => useWorkflow(), context);
    await waitFor(() => expect(hook.result.current.activeWorkflow.id).toBe('a2'));
    const initial = context.store.get(cloudConfigAtom)!;
    act(() => context.store.set(cloudConfigAtom, { ...initial, team: { id: 'team-b', name: 'Other team' } }));
    await waitFor(() => expect(hook.result.current.activeWorkflow.id).toBe('b1'));
    expect(readOpenWorkflowRecord(scope)?.activeId).toBe('a2');
    expect(readOpenWorkflowRecord('user-a.team-b')?.activeId).toBe('b1');
    act(() => context.store.set(cloudConfigAtom, initial));
    await waitFor(() => expect(hook.result.current.activeWorkflow.id).toBe('a2'));
    expect(readOpenWorkflowRecord(scope)?.activeId).toBe('a2');
  });
});
