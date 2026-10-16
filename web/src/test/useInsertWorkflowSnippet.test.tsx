import { act, renderHook } from '@testing-library/react';
import { useCallback, useState } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { useInsertWorkflowSnippet } from '../hooks/workflow/useInsertWorkflowSnippet';
import { useOwnedWorkflowHistory } from '../hooks/workflow/useOwnedWorkflowHistory';
import { promptDialog } from '../state/dialogs';
import { toast } from '../state/notifications';
import { saveWorkflowSnippet } from '../state/workflowSnippets';
import { LOCAL_BROWSER_STORAGE_SCOPE, resolveBrowserStorageScope } from '../utils/browserStorageScope';
import type { BrowserStorageScope } from '../utils/browserStorageScope';
import type { Workflow } from '../types';

vi.mock('../state/dialogs', () => ({ promptDialog: vi.fn() }));
vi.mock('../state/notifications', () => ({ toast: { info: vi.fn(), success: vi.fn() } }));
vi.mock('react-i18next', () => {
  const t = (key: string) => key;
  return { useTranslation: () => ({ t }) };
});

function graph(id = 'draft-a', text = 'A'): Workflow {
  return { id, name: 'Synthetic editor fixture', version: '2.0', app: 'bionodulo', description: '',
    nodes: [
      { id: 'note', type: 'note', position: [-390, 0], params: { text: 'Editor test only' } },
      { id: 'source', type: 'string_format', position: [0, 0], params: { template: text, variables_json: '{}' } },
      { id: 'target', type: 'string_format', position: [440, 0], params: { template: 'Unused', variables_json: '{}' } },
    ],
    edges: [{ id: 'edge', from: { node: 'source', output: 'text' }, to: { node: 'target', input: 'template' } }],
    groups: [], parameters: [], outputs: {} };
}

function saveSnippet(workflow: Workflow, scope = LOCAL_BROWSER_STORAGE_SCOPE) {
  return saveWorkflowSnippet({ name: 'Audit snippet', nodes: workflow.nodes, edges: workflow.edges }, scope);
}

function setup(scope = LOCAL_BROWSER_STORAGE_SCOPE) {
  const applied = vi.fn();
  const viewport = { x: 5, y: 6, scale: 1.5 };
  const hook = renderHook(({ owner, storageScope }: { owner: string; storageScope: BrowserStorageScope }) => {
    const [workflow, setWorkflow] = useState(graph);
    const getViewport = useCallback(() => viewport, []);
    const history = useOwnedWorkflowHistory({ owner, documentId: workflow.id!, workflow,
      getViewport,
      apply: value => { applied(value); setWorkflow(current => ({ ...current, ...value })); },
    });
    const insert = useInsertWorkflowSnippet({ storageScope, workflow, isCurrent: history.isCurrent,
      commitPatch: history.commitPatch, getViewport });
    const edit = (text: string) => {
      const nodes = workflow.nodes.map(node => node.id === 'source'
        ? { ...node, params: { ...node.params, template: text } } : node);
      if (history.queuePatch({ nodes })) setWorkflow(current => ({ ...current, nodes }));
    };
    return { workflow, history, insert, edit, replace: setWorkflow };
  }, { initialProps: { owner: 'owner-a', storageScope: scope } });
  return { ...hook, applied, viewport };
}

describe('snippet insertion history transaction', () => {
  beforeEach(() => { vi.useFakeTimers(); localStorage.clear(); vi.clearAllMocks(); vi.mocked(promptDialog).mockResolvedValue('1'); });
  afterEach(() => { localStorage.clear(); vi.useRealTimers(); });

  it.each([0, 350])('undoes only insertion and redoes the complete snippet after an earlier text edit (%i ms flush)', async delay => {
    const { result } = setup();
    act(() => result.current.edit('B'));
    if (delay) act(() => vi.advanceTimersByTime(delay));
    saveSnippet(result.current.workflow);
    await act(async () => { await result.current.insert(); });
    const inserted = result.current.workflow;
    expect(inserted.nodes).toHaveLength(6);
    expect(inserted.edges).toHaveLength(2);
    expect(inserted.nodes.filter(node => node.type === 'string_format').map(node => node.params.template))
      .toEqual(['B', 'Unused', 'B', 'Unused']);
    expect(new Set(inserted.nodes.map(node => node.id)).size).toBe(6);
    const insertedEdge = inserted.edges[1];
    expect(insertedEdge.from.node).not.toBe('source');
    expect(insertedEdge.to.node).not.toBe('target');
    expect(inserted.nodes.some(node => node.id === insertedEdge.from.node)).toBe(true);
    expect(inserted.nodes.some(node => node.id === insertedEdge.to.node)).toBe(true);

    act(() => result.current.history.undo());
    expect(result.current.workflow.nodes).toHaveLength(3);
    expect(result.current.workflow.edges).toHaveLength(1);
    expect(result.current.workflow.nodes[1].params.template).toBe('B');
    act(() => result.current.history.redo());
    expect(result.current.workflow.nodes).toEqual(inserted.nodes);
    expect(result.current.workflow.edges).toEqual(inserted.edges);
    act(() => result.current.history.undo());
    act(() => result.current.history.undo());
    expect(result.current.workflow.nodes[1].params.template).toBe('A');
    act(() => result.current.history.redo());
    expect(result.current.workflow.nodes[1].params.template).toBe('B');
    expect(result.current.workflow.nodes).toHaveLength(3);
  });

  it('uses the latest same-document graph after the chooser opens and preserves that edit as a separate step', async () => {
    const { result } = setup();
    saveSnippet(graph());
    let choose!: (value: string) => void;
    vi.mocked(promptDialog).mockReturnValue(new Promise(resolveChoice => { choose = resolveChoice; }));
    let pending!: Promise<void>;
    await act(async () => { pending = result.current.insert(); });
    expect(promptDialog).toHaveBeenCalledOnce();
    act(() => result.current.edit('C'));
    await act(async () => { choose('1'); await pending; });
    expect(result.current.workflow.nodes[1].params.template).toBe('C');
    expect(result.current.workflow.nodes).toHaveLength(6);
    act(() => result.current.history.undo());
    expect(result.current.workflow.nodes).toHaveLength(3);
    expect(result.current.workflow.nodes[1].params.template).toBe('C');
    act(() => result.current.history.undo());
    expect(result.current.workflow.nodes[1].params.template).toBe('A');
  });

  it('keeps the command callback stable across ordinary graph renders', () => {
    const { result } = setup();
    const insert = result.current.insert;
    act(() => result.current.edit('B'));
    expect(result.current.insert).toBe(insert);
  });

  it.each(['document', 'owner', 'owner-return'] as const)('rejects a chooser result after a %s change', async transition => {
    const { result, rerender, applied } = setup();
    saveSnippet(graph());
    let choose!: (value: string) => void;
    vi.mocked(promptDialog).mockReturnValue(new Promise(resolveChoice => { choose = resolveChoice; }));
    let pending!: Promise<void>;
    await act(async () => { pending = result.current.insert(); });
    expect(promptDialog).toHaveBeenCalledOnce();
    if (transition === 'document') act(() => result.current.replace(graph('draft-b', 'Private B')));
    else {
      rerender({ owner: 'owner-b', storageScope: LOCAL_BROWSER_STORAGE_SCOPE });
      if (transition === 'owner-return') rerender({ owner: 'owner-a', storageScope: LOCAL_BROWSER_STORAGE_SCOPE });
    }
    const before = result.current.workflow;
    await act(async () => { choose('1'); await pending; });
    expect(result.current.workflow).toBe(before);
    expect(applied).not.toHaveBeenCalled();
    expect(toast.success).not.toHaveBeenCalled();
    act(() => { result.current.history.undo(); result.current.history.redo(); });
    expect(applied).not.toHaveBeenCalled();
  });

  it('does not revive the old callback after leaving and returning to the same document', async () => {
    const { result, applied } = setup();
    saveSnippet(graph());
    const oldInsert = result.current.insert;
    act(() => result.current.replace(graph('draft-b', 'Private B')));
    act(() => result.current.replace(graph()));
    await act(async () => { await oldInsert(); });
    expect(promptDialog).not.toHaveBeenCalled();
    expect(applied).not.toHaveBeenCalled();
  });

  it('rejects a chooser result after unmount', async () => {
    const { result, unmount, applied } = setup();
    saveSnippet(graph());
    let choose!: (value: string) => void;
    vi.mocked(promptDialog).mockReturnValue(new Promise(resolveChoice => { choose = resolveChoice; }));
    let pending!: Promise<void>;
    await act(async () => { pending = result.current.insert(); });
    unmount();
    await act(async () => { choose('1'); await pending; });
    expect(applied).not.toHaveBeenCalled();
    expect(toast.success).not.toHaveBeenCalled();
  });

  it.each([null, '', 'not a number'])('does not change history for cancelled or invalid input %j', async choice => {
    const { result, applied } = setup();
    saveSnippet(graph());
    vi.mocked(promptDialog).mockResolvedValue(choice);
    await act(async () => { await result.current.insert(); });
    act(() => { result.current.history.undo(); result.current.history.redo(); });
    expect(applied).not.toHaveBeenCalled();
    expect(result.current.workflow.nodes).toHaveLength(3);
  });

  it('keeps snippets scoped and makes no prompt or transaction for a guest', async () => {
    saveSnippet(graph());
    const { result } = setup(resolveBrowserStorageScope(null));
    await act(async () => { await result.current.insert(); });
    expect(promptDialog).not.toHaveBeenCalled();
    expect(toast.info).not.toHaveBeenCalled();
  });

  it('does not expose local snippets to an authenticated cloud scope', async () => {
    saveSnippet(graph());
    const scope = resolveBrowserStorageScope({ cloudMode: true, user: { id: 'user' }, team: { id: 'team' } });
    const { result } = setup(scope);
    await act(async () => { await result.current.insert(); });
    expect(promptDialog).not.toHaveBeenCalled();
    expect(toast.info).toHaveBeenCalledWith('snippets.emptyLibrary');
    saveSnippet(graph(), scope);
    await act(async () => { await result.current.insert(); });
    expect(result.current.workflow.nodes).toHaveLength(6);
  });

  it('wires the production App command to the tested callback and its owned history commit', () => {
    const source = readFileSync(resolve(__dirname, '../App.tsx'), 'utf8');
    expect(source).toContain('const handleInsertSnippet = useInsertWorkflowSnippet({');
    expect(source).toContain('commitPatch: commitHistoryPatch,');
    expect(source).toContain('isCurrent: isCurrentHistory,');
    expect(source).toContain('const getHistoryViewport = useCallback(() => canvasRef.current?.getViewport(), []);');
    expect(source).toContain('getViewport: getHistoryViewport,');
    expect(source).toContain('onSelect: () => handleInsertSnippet()');
  });
});
