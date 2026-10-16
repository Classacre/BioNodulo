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
import { placementBounds, placementOverlaps, snippetNodeSize } from '../utils/snippetPlacement';
import { getViewportForBounds } from '@xyflow/react';

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

function setup(scope = LOCAL_BROWSER_STORAGE_SCOPE, options: {
  viewport?: { x: number; y: number; scale: number }; onInserted?: () => void;
} = {}) {
  const applied = vi.fn();
  const viewport = options.viewport ?? { x: 5, y: 6, scale: 1.5 };
  const hook = renderHook(({ owner, storageScope }: { owner: string; storageScope: BrowserStorageScope }) => {
    const [workflow, setWorkflow] = useState(graph);
    const getViewport = useCallback(() => viewport, []);
    const history = useOwnedWorkflowHistory({ owner, documentId: workflow.id!, workflow,
      getViewport,
      apply: value => { applied(value); setWorkflow(current => ({ ...current, ...value })); },
    });
    const insert = useInsertWorkflowSnippet({ storageScope, workflow, isCurrent: history.isCurrent,
      commitPatch: history.commitPatch, getViewport, onInserted: options.onInserted });
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
  afterEach(() => {
    localStorage.clear();
    document.querySelectorAll('[data-placement-fixture]').forEach(element => element.remove());
    vi.unstubAllGlobals();
    vi.useRealTimers();
  });

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

  it('places the complete snippet clear of live measured nodes and both overlaid drawers', async () => {
    const shell = document.createElement('div');
    shell.className = 'app-shell';
    shell.dataset.placementFixture = '';
    shell.style.setProperty('--left-panel-inset', '600px');
    shell.style.setProperty('--right-panel-inset', '100px');
    shell.innerHTML = '<div class="main-canvas"><div class="react-flow"></div></div>';
    document.body.append(shell);
    const canvas = shell.querySelector<HTMLElement>('.react-flow')!;
    vi.spyOn(canvas, 'getBoundingClientRect').mockReturnValue({ width: 2200, height: 1500 } as DOMRect);
    const sizes = { note: { width: 260, height: 120 }, source: { width: 220, height: 520 }, target: { width: 220, height: 300 } };
    for (const [id, dimensions] of Object.entries(sizes)) {
      const node = document.createElement('div');
      node.className = 'react-flow__node';
      node.dataset.id = id;
      Object.defineProperties(node, { offsetWidth: { value: dimensions.width }, offsetHeight: { value: dimensions.height } });
      canvas.append(node);
    }
    const reveal = vi.fn();
    const { result } = setup(LOCAL_BROWSER_STORAGE_SCOPE, { viewport: { x: 600, y: 300, scale: 1 }, onInserted: reveal });
    act(() => result.current.edit('B'));
    const before = structuredClone(result.current.workflow);
    saveSnippet(before);
    await act(async () => { await result.current.insert(); });
    const after = result.current.workflow;
    expect(after.nodes.slice(0, 3)).toEqual(before.nodes);
    expect(after.edges[0]).toEqual(before.edges[0]);
    const added = after.nodes.slice(3);
    const insertedBounds = placementBounds(added.map(node => ({ x: node.position[0], y: node.position[1], ...snippetNodeSize(node) })));
    const obstacles = before.nodes.map(node => ({ x: node.position[0], y: node.position[1], ...sizes[node.id as keyof typeof sizes] }));
    expect(obstacles.some(rect => placementOverlaps(insertedBounds, rect))).toBe(false);
    // Actual 2200 px canvas minus 600/100 px drawers, translated by viewport.
    expect(insertedBounds.x).toBeGreaterThanOrEqual(24);
    expect(insertedBounds.x + insertedBounds.width).toBeLessThanOrEqual(1500 - 24);
    expect(insertedBounds.y).toBeGreaterThanOrEqual(-300 + 24);
    expect(insertedBounds.y + insertedBounds.height).toBeLessThanOrEqual(1200 - 24);
    for (let index = 1; index < added.length; index++) {
      expect(added[index].position.map((value, axis) => value - added[0].position[axis]))
        .toEqual(before.nodes[index].position.map((value, axis) => value - before.nodes[0].position[axis]));
      expect(added[index].params).toEqual(before.nodes[index].params);
    }
    expect(after.edges[1].from.node).toBe(added[1].id);
    expect(after.edges[1].to.node).toBe(added[2].id);
    act(() => vi.advanceTimersByTime(100));
    expect(reveal).not.toHaveBeenCalled();
    act(() => result.current.history.undo());
    expect(result.current.workflow.nodes).toEqual(before.nodes);
    act(() => result.current.history.redo());
    expect(result.current.workflow.nodes).toEqual(after.nodes);
  });

  it.each(['current', 'owner', 'document', 'undo', 'unmount'] as const)(
    'reveals an oversized insertion only after layout, while still current (%s)', async transition => {
      const reveal = vi.fn();
      const frames: FrameRequestCallback[] = [];
      vi.stubGlobal('requestAnimationFrame', (callback: FrameRequestCallback) => { frames.push(callback); return frames.length; });
      const { result, rerender, unmount } = setup(LOCAL_BROWSER_STORAGE_SCOPE, { onInserted: reveal });
      saveSnippet(graph());
      await act(async () => { await result.current.insert(); });
      expect(reveal).not.toHaveBeenCalled();
      expect(frames).toHaveLength(1);
      act(() => frames.shift()!(0));
      expect(reveal).not.toHaveBeenCalled();
      if (transition === 'owner') rerender({ owner: 'owner-b', storageScope: LOCAL_BROWSER_STORAGE_SCOPE });
      if (transition === 'document') act(() => result.current.replace(graph('draft-b')));
      if (transition === 'undo') act(() => result.current.history.undo());
      if (transition === 'unmount') unmount();
      act(() => frames.shift()!(16));
      expect(reveal).toHaveBeenCalledTimes(transition === 'current' ? 1 : 0);
    },
  );

  it('keeps insertion above the measured open BottomConsole rather than using its obscured canvas area', async () => {
    const shell = document.createElement('div');
    shell.className = 'app-shell';
    shell.dataset.placementFixture = '';
    shell.innerHTML = '<div class="main-canvas"><div class="react-flow"></div></div><div class="bottom-console"></div>';
    document.body.append(shell);
    vi.spyOn(shell.querySelector<HTMLElement>('.react-flow')!, 'getBoundingClientRect').mockReturnValue({
      x: 0, y: 100, left: 0, top: 100, right: 1800, bottom: 1100, width: 1800, height: 1000,
    } as DOMRect);
    vi.spyOn(shell.querySelector<HTMLElement>('.bottom-console')!, 'getBoundingClientRect').mockReturnValue({
      x: 0, y: 600, left: 0, top: 600, right: 1800, bottom: 1100, width: 1800, height: 500,
    } as DOMRect);
    const reveal = vi.fn();
    const { result } = setup(LOCAL_BROWSER_STORAGE_SCOPE, { viewport: { x: 600, y: 0, scale: 1 }, onInserted: reveal });
    act(() => result.current.replace({ ...graph(), nodes: graph().nodes.map(node => ({ ...node, position: [node.position[0], -300] as [number, number] })) }));
    saveSnippet(result.current.workflow);
    const before = structuredClone(result.current.workflow.nodes);
    await act(async () => { await result.current.insert(); });
    const added = result.current.workflow.nodes.slice(3);
    const bounds = placementBounds(added.map(node => ({ x: node.position[0], y: node.position[1], ...snippetNodeSize(node) })));
    expect(result.current.workflow.nodes.slice(0, 3)).toEqual(before);
    expect(bounds.y).toBeGreaterThanOrEqual(24);
    expect(bounds.y + bounds.height).toBeLessThanOrEqual(500 - 24);
    expect(before.some(node => placementOverlaps(bounds, { x: node.position[0], y: node.position[1], ...snippetNodeSize(node) }))).toBe(false);
    act(() => vi.advanceTimersByTime(100));
    expect(reveal).not.toHaveBeenCalled();
  });

  it('remeasures overlays after insertion before revealing only the new node IDs', async () => {
    const reveal = vi.fn();
    const frames: FrameRequestCallback[] = [];
    vi.stubGlobal('requestAnimationFrame', (callback: FrameRequestCallback) => { frames.push(callback); return frames.length; });
    const { result } = setup(LOCAL_BROWSER_STORAGE_SCOPE, { onInserted: reveal });
    saveSnippet(graph());
    await act(async () => { await result.current.insert(); });
    const insertedIds = result.current.workflow.nodes.slice(3).map(node => node.id);
    const shell = document.createElement('div');
    shell.className = 'app-shell';
    shell.dataset.placementFixture = '';
    shell.style.setProperty('--left-panel-inset', '400px');
    shell.style.setProperty('--right-panel-inset', '200px');
    shell.innerHTML = '<div class="main-canvas"><div class="react-flow"></div></div><div class="bottom-console"></div>';
    document.body.append(shell);
    vi.spyOn(shell.querySelector<HTMLElement>('.react-flow')!, 'getBoundingClientRect').mockReturnValue({
      x: 56, y: 76, left: 56, top: 76, right: 1256, bottom: 976, width: 1200, height: 900,
    } as DOMRect);
    vi.spyOn(shell.querySelector<HTMLElement>('.bottom-console')!, 'getBoundingClientRect').mockReturnValue({
      x: 56, y: 526, left: 56, top: 526, right: 1256, bottom: 976, width: 1200, height: 450,
    } as DOMRect);
    act(() => frames.shift()!(0));
    expect(reveal).not.toHaveBeenCalled();
    act(() => frames.shift()!(16));
    expect(reveal).toHaveBeenCalledWith({ nodes: insertedIds.map(id => ({ id })), minZoom: 0, duration: 220,
      padding: { left: '424px', right: '224px', top: '24px', bottom: '474px' } });
  });

  it('reveals above actual MiniMap, controls and activity chrome, ignoring hidden or covered chrome', async () => {
    const shell = document.createElement('div');
    shell.className = 'app-shell';
    shell.dataset.placementFixture = '';
    shell.style.setProperty('--left-panel-inset', '372px');
    shell.innerHTML = '<div class="main-canvas"><div class="react-flow"></div></div>';
    document.body.append(shell);
    const main = shell.querySelector<HTMLElement>('.main-canvas')!;
    const rect = (left: number, top: number, width: number, height: number): DOMRect => ({
      x: left, y: top, left, top, width, height, right: left + width, bottom: top + height,
    } as DOMRect);
    vi.spyOn(main.querySelector<HTMLElement>('.react-flow')!, 'getBoundingClientRect')
      .mockReturnValue(rect(56, 76, 1224, 644));
    const overlays = [
      { className: 'bottom-console', bounds: rect(428, 440, 852, 280) },
      { className: 'react-flow__minimap', bounds: rect(1064, 302, 200, 150) },
      { className: 'react-flow__controls', bounds: rect(443, 330, 28, 106) },
      { className: 'island', bounds: rect(820, 680, 64, 30) },
    ];
    for (const overlay of [...overlays,
      { className: 'react-flow__controls', bounds: rect(60, 100, 28, 106) }, // Behind Workspace.
      { className: 'react-flow__minimap', bounds: rect(1300, 100, 200, 150) }, // Outside canvas.
      { className: 'island', bounds: rect(700, 100, 200, 100), hidden: true },
    ]) {
      const element = document.createElement('div');
      element.className = overlay.className;
      if ('hidden' in overlay) element.style.visibility = 'hidden';
      vi.spyOn(element, 'getBoundingClientRect').mockReturnValue(overlay.bounds);
      main.append(element);
    }
    const reveal = vi.fn();
    const frames: FrameRequestCallback[] = [];
    vi.stubGlobal('requestAnimationFrame', (callback: FrameRequestCallback) => { frames.push(callback); return frames.length; });
    const { result } = setup(LOCAL_BROWSER_STORAGE_SCOPE, {
      viewport: { x: 600, y: 300, scale: 1 }, onInserted: reveal,
    });
    const before = structuredClone(result.current.workflow);
    saveSnippet(before);
    await act(async () => { await result.current.insert(); });
    expect(result.current.workflow.nodes.slice(0, 3)).toEqual(before.nodes);
    act(() => frames.shift()!(0));
    // The controls move higher after layout; reveal must use their new bounds.
    const controls = main.querySelector<HTMLElement>('.react-flow__controls')!;
    vi.mocked(controls.getBoundingClientRect).mockReturnValue(rect(443, 282, 28, 150));
    act(() => frames.shift()!(16));
    expect(reveal).toHaveBeenCalledOnce();
    const options = reveal.mock.calls[0][0];
    expect(options.padding.bottom).toBe('462px'); // Actual canvas bottom720 - controlstop282 + margin24.
    const added = result.current.workflow.nodes.slice(3);
    expect(options.nodes).toEqual(added.map(node => ({ id: node.id })));
    const bounds = placementBounds(added.map(node => ({ x: node.position[0], y: node.position[1], ...snippetNodeSize(node) })));
    const view = getViewportForBounds(bounds, 1224, 644, options.minZoom, 2, options.padding);
    const projected = { x: 56 + bounds.x * view.zoom + view.x, y: 76 + bounds.y * view.zoom + view.y,
      width: bounds.width * view.zoom, height: bounds.height * view.zoom };
    expect(projected.y + projected.height).toBeLessThanOrEqual(282 - 24 + 0.0001);
    expect(projected.x).toBeGreaterThanOrEqual(56 + 372 + 24 - 0.0001);
    expect(projected.x + projected.width).toBeLessThanOrEqual(56 + 1224 - 24 + 0.0001);
    for (const overlay of overlays) {
      expect(placementOverlaps(projected, { x: overlay.bounds.left, y: overlay.bounds.top,
        width: overlay.bounds.width, height: overlay.bounds.height }, 0)).toBe(false);
    }
    act(() => result.current.history.undo());
    expect(result.current.workflow.nodes).toEqual(before.nodes);
    expect(result.current.workflow.edges).toEqual(before.edges);
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
