import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { act, renderHook } from '@testing-library/react';
import { useState } from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import ts from 'typescript';
import type { Workflow } from '../types';
import { useOwnedWorkflowHistory } from '../hooks/workflow/useOwnedWorkflowHistory';

// Execute the actual production JSX callback, without booting unrelated App IO.
function dropCallback(bindings: Record<string, unknown>): (event: unknown) => Promise<void> {
  const source = ts.createSourceFile('App.tsx', readFileSync(resolve(__dirname, '../App.tsx'), 'utf8'),
    ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
  let callback: ts.Expression | undefined;
  const visit = (node: ts.Node) => {
    if (ts.isJsxOpeningElement(node) && node.tagName.getText(source) === 'div'
      && node.attributes.properties.some(attribute => ts.isJsxAttribute(attribute)
        && attribute.name.getText(source) === 'className'
        && attribute.initializer && ts.isStringLiteral(attribute.initializer)
        && attribute.initializer.text === 'main-canvas')) {
      const attribute = node.attributes.properties.find(attribute => ts.isJsxAttribute(attribute)
        && attribute.name.getText(source) === 'onDrop');
      if (attribute && ts.isJsxAttribute(attribute) && attribute.initializer
        && ts.isJsxExpression(attribute.initializer)) callback = attribute.initializer.expression;
    }
    ts.forEachChild(node, visit);
  };
  visit(source);
  if (!callback) throw new Error('Production canvas drop callback was not found');
  const script = ts.transpileModule(`const callback = ${callback.getText(source)};`, {
    compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.None },
  }).outputText;
  return new Function(...Object.keys(bindings), `${script}\nreturn callback;`)(...Object.values(bindings));
}

function graph(): Workflow {
  return { id: 'owned', name: 'Synthetic drop audit', app: 'bionodulo', version: '2.0',
    nodes: ['A', 'C', 'note'].map((text, index) => ({ id: `n${index}`, type: 'string_format',
      position: [index * 400, 0], params: { template: text }, ui: { title: text } })),
    edges: [{ id: 'e1', from: { node: 'n0', output: 'text' }, to: { node: 'n1', input: 'template' } }],
    groups: [], parameters: [{ name: 'threshold', type: 'number', default: 1 }], outputs: {} };
}

function setup() {
  const success = vi.fn();
  const bridge = vi.fn();
  const event = { preventDefault: vi.fn(), clientX: 120, clientY: 140,
    dataTransfer: { getData: (type: string) => type === 'application/bionodulo-workspace-file' ? 'uploads/verified fixture.txt' : '' } };
  const hook = renderHook(({ owner }) => {
    const [workflow, setWorkflow] = useState(graph);
    const history = useOwnedWorkflowHistory({ owner, documentId: workflow.id!, workflow,
      getViewport: () => ({ x: 0, y: 0, scale: 1 }),
      apply: patch => { bridge(patch); setWorkflow(current => ({ ...current, ...patch })); } });
    const drop = dropCallback({ objectInfo: { input_file: { id: 'input_file', display_name: 'Input file' } },
      canvasRef: { current: { screenToFlowPosition: () => ({ x: 10, y: 20 }) } },
      activeWorkflow: workflow, activeWorkflowRef: { current: workflow }, activeIndex: 0,
      updateWorkflow: (_index: number, next: Workflow) => setWorkflow(next),
      commitHistoryPatch: history.commitPatch, defaultsFor: () => ({ passthrough: 'kept' }),
      appFileActionCopy: { fileTypeFallback: 'file', error: {}, toast: { fileDropped: 'File added' } },
      toast: { success, warning: vi.fn() } });
    const edit = () => {
      const nodes = workflow.nodes.map((node, index) => index === 0 ? { ...node, params: { template: 'B' } } : node);
      history.queuePatch({ nodes }); setWorkflow(current => ({ ...current, nodes }));
    };
    return { workflow, drop, edit, history };
  }, { initialProps: { owner: {} } });
  return { ...hook, success, bridge, event };
}

afterEach(() => vi.useRealTimers());

describe('actual Workspace file-drop history transaction', () => {
  it.each([0, 350])('undoes only the drop after a pending/flushed edit (%i ms)', async delay => {
    vi.useFakeTimers();
    const { result, event, bridge } = setup();
    act(() => result.current.edit());
    if (delay) act(() => vi.advanceTimersByTime(delay));
    await act(async () => { await result.current.drop(event); });
    expect(result.current.workflow.nodes).toHaveLength(4);
    expect(result.current.workflow.nodes[3]).toMatchObject({ type: 'input_file', position: [10, 20],
      params: { file: 'uploads/verified fixture.txt', passthrough: 'kept' } });
    act(() => result.current.history.undo());
    expect(result.current.workflow.nodes).toHaveLength(3);
    expect(result.current.workflow.nodes.map(node => node.params.template)).toEqual(['B', 'C', 'note']);
    act(() => result.current.history.redo());
    expect(result.current.workflow.nodes).toHaveLength(4);
    expect(result.current.workflow.edges).toEqual(graph().edges);
    expect(result.current.workflow.parameters).toEqual(graph().parameters);
    expect(bridge).toHaveBeenCalled();
    act(() => result.current.history.undo());
    act(() => result.current.history.undo());
    expect(result.current.workflow.nodes.map(node => node.params.template)).toEqual(['A', 'C', 'note']);
  });

  it('rejects an old drop callback after owner replacement without a success notification', async () => {
    const { result, rerender, event, success } = setup();
    const oldDrop = result.current.drop;
    rerender({ owner: {} });
    await act(async () => { await oldDrop(event); });
    expect(result.current.workflow.nodes).toHaveLength(3);
    expect(success).not.toHaveBeenCalled();
  });
});
