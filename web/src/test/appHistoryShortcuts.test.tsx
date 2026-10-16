import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { act, renderHook } from '@testing-library/react';
import { useLayoutEffect, useState } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import ts from 'typescript';
import { useGlobalShortcut } from '../hooks/ui/useKeybindings';
import { useOwnedWorkflowHistory } from '../hooks/workflow/useOwnedWorkflowHistory';
import { installDomOverlayBridge } from '../state/overlays';
import { resetAllKeybindings, setKeybinding } from '../state/keybindings';
import type { Workflow } from '../types';

// Run App's actual registrations with the real shortcut/history hooks. This
// fails if production forgets any binding, without booting unrelated App IO.
function productionRegistrations() {
  const source = ts.createSourceFile('App.tsx', readFileSync(resolve(__dirname, '../App.tsx'), 'utf8'),
    ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
  const calls: ts.CallExpression[] = [];
  const visit = (node: ts.Node) => {
    if (ts.isCallExpression(node) && node.expression.getText(source) === 'useGlobalShortcut'
      && node.arguments[0] && ts.isStringLiteral(node.arguments[0])
      && ['canvas.undo', 'canvas.redo', 'canvas.redoAlternate'].includes(node.arguments[0].text)) calls.push(node);
    ts.forEachChild(node, visit);
  };
  visit(source);
  if (calls.length !== 3) throw new Error('App must register all three history shortcuts exactly once');
  const script = ts.transpileModule(calls.map(call => `${call.getText(source)};`).join('\n'), {
    compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.None },
  }).outputText;
  return new Function('useGlobalShortcut', 'undo', 'redo', script) as (
    register: typeof useGlobalShortcut, undo: () => void, redo: () => void,
  ) => void;
}
const registerProduction = productionRegistrations();

function graph(id = 'doc-a'): Workflow {
  return { id, name: 'Synthetic shortcut audit', app: 'bionodulo', version: '2.0',
    nodes: ['B', 'C', 'note'].map((text, index) => ({ id: `n${index}`, type: 'string_format',
      position: [index * 400, 0], params: { template: text } })),
    edges: [{ id: 'e1', from: { node: 'n0', output: 'text' }, to: { node: 'n1', input: 'template' } }],
    groups: [], parameters: [{ name: 'threshold', type: 'number', default: 1 }], outputs: {} };
}
function key(target: EventTarget, value = 'z', modifiers: KeyboardEventInit = {}) {
  const event = new KeyboardEvent('keydown', { key: value, ctrlKey: true, bubbles: true, cancelable: true, ...modifiers });
  target.dispatchEvent(event);
  return event;
}
function setup() {
  const applied = vi.fn();
  const initialOwner = {};
  const hook = renderHook(({ owner, documentId, duringLayout }: {
    owner: object; documentId: string; duringLayout?: () => void;
  }) => {
    const [workflow, setWorkflow] = useState(graph);
    const current = { ...workflow, id: documentId };
    const history = useOwnedWorkflowHistory({ owner, documentId, workflow: current,
      getViewport: () => undefined,
      apply: patch => { applied(patch); setWorkflow(previous => ({ ...previous, ...patch })); } });
    registerProduction(useGlobalShortcut, history.undo, history.redo);
    useLayoutEffect(() => { duringLayout?.(); }, [duringLayout]);
    const insert = () => history.commitPatch({
      nodes: [...current.nodes, ...current.nodes.map(node => ({ ...node, id: `${node.id}-copy` }))],
      edges: [...current.edges, { id: 'copy-edge', from: { node: 'n0-copy', output: 'text' }, to: { node: 'n1-copy', input: 'template' } }],
    });
    return { workflow: current, history, insert };
  }, { initialProps: { owner: initialOwner, documentId: 'doc-a' } as {
    owner: object; documentId: string; duringLayout?: () => void;
  } });
  return { ...hook, applied, initialOwner };
}
let stopOverlayBridge: (() => void) | undefined;
beforeEach(() => {
  resetAllKeybindings();
  document.body.replaceChildren();
  stopOverlayBridge = installDomOverlayBridge();
});
afterEach(() => {
  resetAllKeybindings();
  document.body.replaceChildren();
  // Refresh the shared overlay count before disconnecting its observer.
  installDomOverlayBridge()();
  stopOverlayBridge?.();
});

describe('actual App keyboard history registration', () => {
  it('uses BODY Ctrl+Z/ Ctrl+Y/ Ctrl+Shift+Z for exactly one owned transaction per event', () => {
    const { result, applied, unmount } = setup();
    act(() => { result.current.insert(); });
    expect(result.current.workflow.nodes).toHaveLength(6);
    applied.mockClear();
    act(() => { expect(key(document.body).defaultPrevented).toBe(true); });
    expect(result.current.workflow.nodes).toHaveLength(3);
    expect(result.current.workflow.nodes[0].params.template).toBe('B');
    expect(applied).toHaveBeenCalledOnce();
    act(() => { key(document.body, 'y'); });
    expect(result.current.workflow.nodes).toHaveLength(6);
    expect(result.current.workflow.edges).toHaveLength(2);
    expect(result.current.workflow.parameters).toEqual(graph().parameters);
    expect(applied).toHaveBeenCalledTimes(2);
    act(() => { key(document.body); });
    act(() => { key(document.body, 'z', { shiftKey: true }); });
    expect(result.current.workflow.nodes).toHaveLength(6);
    expect(applied).toHaveBeenCalledTimes(4);
    unmount();
  });

  it.each(['input', 'textarea', 'select', 'contenteditable'] as const)('preserves native editing in %s', tag => {
    const { result, applied, unmount } = setup();
    act(() => { result.current.insert(); });
    applied.mockClear();
    const target = document.createElement(tag === 'contenteditable' ? 'span' : tag);
    if (tag === 'contenteditable') {
      const parent = document.createElement('div'); parent.setAttribute('contenteditable', 'true');
      parent.append(target); document.body.append(parent);
    } else document.body.append(target);
    act(() => { expect(key(target).defaultPrevented).toBe(false); });
    expect(result.current.workflow.nodes).toHaveLength(6);
    expect(applied).not.toHaveBeenCalled();
    unmount();
  });

  it('defers to overlays then resumes immediately after the overlay closes', async () => {
    const { result, applied, unmount } = setup();
    act(() => { result.current.insert(); });
    applied.mockClear();
    const modal = document.createElement('div'); modal.className = 'modal-overlay';
    await act(async () => { document.body.append(modal); await Promise.resolve(); });
    act(() => { expect(key(document.body).defaultPrevented).toBe(false); });
    expect(applied).not.toHaveBeenCalled();
    await act(async () => { modal.remove(); await Promise.resolve(); });
    act(() => { key(document.body); });
    expect(result.current.workflow.nodes).toHaveLength(3);
    expect(applied).toHaveBeenCalledOnce();
    unmount();
  });

  it('honors live remapping, unassignment and exact modifier matching', () => {
    const { result, applied, unmount } = setup();
    act(() => { result.current.insert(); });
    applied.mockClear();
    act(() => { setKeybinding('canvas.undo', 'Alt+U'); });
    act(() => { expect(key(document.body).defaultPrevented).toBe(false); });
    act(() => { expect(key(document.body, 'u', { ctrlKey: false, altKey: true, shiftKey: true }).defaultPrevented).toBe(false); });
    expect(applied).not.toHaveBeenCalled();
    act(() => { key(document.body, 'u', { ctrlKey: false, altKey: true }); });
    expect(applied).toHaveBeenCalledOnce();
    act(() => { setKeybinding('canvas.redo', ''); setKeybinding('canvas.redoAlternate', ''); });
    act(() => { expect(key(document.body, 'y').defaultPrevented).toBe(false); key(document.body, 'z', { shiftKey: true }); });
    expect(result.current.workflow.nodes).toHaveLength(3);
    expect(applied).toHaveBeenCalledOnce();
    unmount();
  });

  it.each(['owner', 'document'] as const)('rejects the old %s history before passive listener refresh and after unmount', changed => {
    const { result, rerender, applied, initialOwner, unmount } = setup();
    act(() => { result.current.insert(); });
    applied.mockClear();
    rerender({ owner: changed === 'owner' ? {} : initialOwner, documentId: changed === 'document' ? 'doc-b' : 'doc-a',
      duringLayout: () => { key(document.body); } });
    expect(applied).not.toHaveBeenCalled();
    act(() => { result.current.insert(); });
    applied.mockClear();
    act(() => { key(document.body); });
    expect(applied).toHaveBeenCalledOnce();
    unmount();
    applied.mockClear();
    act(() => { key(document.body); key(document.body, 'y'); });
    expect(applied).not.toHaveBeenCalled();
  });
});
