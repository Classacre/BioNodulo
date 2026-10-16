import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { act, renderHook } from '@testing-library/react';
import { useRef, useState } from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import ts from 'typescript';
import type { Workflow } from '../types';
import { useOwnedWorkflowHistory } from '../hooks/workflow/useOwnedWorkflowHistory';

function paletteCallback(bindings: Record<string, unknown>): () => void {
  const source = ts.createSourceFile('App.tsx', readFileSync(resolve(__dirname, '../App.tsx'), 'utf8'),
    ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
  let callback: ts.Expression | undefined;
  const visit = (node: ts.Node) => {
    if (ts.isObjectLiteralExpression(node) && node.properties.some(property => ts.isPropertyAssignment(property)
      && property.name.getText(source) === 'id' && property.initializer.getText(source).startsWith('`addNode.'))) {
      const property = node.properties.find(property => ts.isPropertyAssignment(property) && property.name.getText(source) === 'onSelect');
      if (property && ts.isPropertyAssignment(property)) callback = property.initializer;
    }
    ts.forEachChild(node, visit);
  };
  visit(source);
  if (!callback) throw new Error('Production dynamic palette node callback not found');
  const script = ts.transpileModule(`const callback = ${callback.getText(source)};`, {
    compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.None },
  }).outputText;
  return new Function(...Object.keys(bindings), `${script}\nreturn callback;`)(...Object.values(bindings));
}

function graph(): Workflow {
  return { id: 'owned', name: 'Synthetic palette audit', app: 'bionodulo', version: '2.0',
    nodes: ['A', 'C', 'note'].map((text, index) => ({ id: `n${index}`, type: 'string_format',
      position: [index * 400, 0], params: { template: text } })),
    edges: [{ id: 'e1', from: { node: 'n0', output: 'text' }, to: { node: 'n1', input: 'template' } }],
    groups: [{ id: 'group', name: 'kept', color: '#fff', position: [-20, -20], width: 800, height: 300, collapsed: false }],
    parameters: [{ name: 'threshold', type: 'number', default: 1 }], outputs: {} };
}

function setup() {
  const applied = vi.fn();
  const initialOwner = {};
  const hook = renderHook(({ owner, documentId }) => {
    const [workflow, setWorkflow] = useState(graph);
    const activeWorkflowRef = useRef(workflow); activeWorkflowRef.current = workflow;
    const history = useOwnedWorkflowHistory({ owner, documentId, workflow,
      getViewport: () => ({ x: 0, y: 0, scale: 1 }),
      apply: patch => { applied(patch); setWorkflow(current => ({ ...current, ...patch })); } });
    const insert = paletteCallback({ meta: { id: 'string_format', display_name: 'String Format' },
      canvasRef: { current: { getViewport: () => ({ x: 0, y: 0, scale: 1 }) } }, activeWorkflowRef,
      isCurrentHistory: history.isCurrent, commitHistoryPatch: history.commitPatch,
      defaultsFor: () => ({ template: '', variables: '{}' }),
      activeWorkflow: workflow, activeIndex: 0, updateWorkflow: (_index: number, next: Workflow) => setWorkflow(next) });
    const edit = () => {
      const nodes = workflow.nodes.map((node, index) => index === 0 ? { ...node, params: { template: 'B' } } : node);
      history.queuePatch({ nodes }); setWorkflow(current => ({ ...current, nodes }));
    };
    return { workflow, insert, edit, history };
  }, { initialProps: { owner: initialOwner, documentId: 'owned' } });
  return { ...hook, applied, initialOwner };
}

afterEach(() => vi.useRealTimers());

describe('actual dynamic command palette node insertion', () => {
  it.each([0, 350])('commits only the node after the latest pending/flushed edit (%i ms)', delay => {
    vi.useFakeTimers();
    const { result, applied } = setup();
    const earlierPaletteEntry = result.current.insert;
    act(() => result.current.edit());
    if (delay) act(() => vi.advanceTimersByTime(delay));
    act(() => earlierPaletteEntry());
    const inserted = structuredClone(result.current.workflow.nodes[3]);
    expect(result.current.workflow.nodes).toHaveLength(4);
    expect(result.current.workflow.nodes[0].params.template).toBe('B');
    expect(inserted).toMatchObject({ type: 'string_format', params: { template: '', variables: '{}' }, ui: { title: 'String Format' } });
    act(() => result.current.history.undo());
    expect(result.current.workflow.nodes).toHaveLength(3);
    expect(result.current.workflow.nodes.map(node => node.params.template)).toEqual(['B', 'C', 'note']);
    act(() => result.current.history.redo());
    expect(result.current.workflow.nodes[3]).toEqual(inserted);
    expect(result.current.workflow.edges).toEqual(graph().edges);
    expect(result.current.workflow.groups).toEqual(graph().groups);
    expect(result.current.workflow.parameters).toEqual(graph().parameters);
    expect(applied).toHaveBeenCalled();
    act(() => result.current.history.undo()); act(() => result.current.history.undo());
    expect(result.current.workflow.nodes[0].params.template).toBe('A');
  });

  it.each(['owner', 'document', 'owner ABA', 'document ABA'] as const)('rejects a retained entry after %s replacement', changed => {
    const { result, rerender, applied, initialOwner } = setup();
    const earlierPaletteEntry = result.current.insert;
    rerender({ owner: changed.startsWith('owner') ? {} : initialOwner, documentId: changed.startsWith('document') ? 'other' : 'owned' });
    if (changed.endsWith('ABA')) rerender({ owner: initialOwner, documentId: 'owned' });
    act(() => earlierPaletteEntry());
    expect(result.current.workflow.nodes).toHaveLength(3);
    expect(applied).not.toHaveBeenCalled();
  });
});
