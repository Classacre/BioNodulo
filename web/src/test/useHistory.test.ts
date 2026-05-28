import { describe, it, expect } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useHistory } from '../hooks/useHistory';
import type { Workflow } from '../types';

function makeWorkflow(id: string, nodes: Array<{ id: string; type: string }> = []): Workflow {
  return {
    id,
    name: id,
    version: '2.0',
    nodes: nodes.map((n) => ({
      id: n.id,
      type: n.type,
      position: [0, 0],
      params: {},
      ui: {},
    })) as unknown as Workflow['nodes'],
    edges: [],
    groups: [],
  } as unknown as Workflow;
}

describe('useHistory', () => {
  it('starts at the bottom of the stack', () => {
    const { result } = renderHook(() => useHistory(makeWorkflow('a')));
    expect(result.current.canUndo).toBe(false);
    expect(result.current.canRedo).toBe(false);
  });

  it('pushes new snapshots and supports undo/redo', () => {
    const { result } = renderHook(() => useHistory(makeWorkflow('a')));
    const b = makeWorkflow('b', [{ id: 'n1', type: 'note' }]);
    act(() => result.current.push(b));
    expect(result.current.canUndo).toBe(true);

    let popped = null as ReturnType<typeof result.current.undo>;
    act(() => {
      popped = result.current.undo();
    });
    expect(popped?.workflow.id).toBe('a');
    expect(result.current.canRedo).toBe(true);

    let pushed = null as ReturnType<typeof result.current.redo>;
    act(() => {
      pushed = result.current.redo();
    });
    expect(pushed?.workflow.id).toBe('b');
  });

  it('dedups when the signature matches the current tip', () => {
    const { result } = renderHook(() => useHistory(makeWorkflow('a')));
    const a2 = makeWorkflow('a'); // identical structure
    act(() => result.current.push(a2));
    // No new snapshot should have been added.
    expect(result.current.canUndo).toBe(false);
  });

  it('captures viewport and returns it from undo', () => {
    const { result } = renderHook(() => useHistory(makeWorkflow('a')));
    const b = makeWorkflow('b', [{ id: 'n1', type: 'note' }]);
    act(() => result.current.push(b, { x: 100, y: 50, scale: 1.25 }));
    let popped = null as ReturnType<typeof result.current.undo>;
    act(() => {
      popped = result.current.undo();
    });
    expect(popped?.viewport).toEqual(undefined);
    let redone = null as ReturnType<typeof result.current.redo>;
    act(() => {
      redone = result.current.redo();
    });
    expect(redone?.viewport).toEqual({ x: 100, y: 50, scale: 1.25 });
  });

  it('collapses pushes inside a transaction into one snapshot', () => {
    const { result } = renderHook(() => useHistory(makeWorkflow('a')));
    act(() => {
      const commit = result.current.begin();
      result.current.push(makeWorkflow('b', [{ id: 'n1', type: 'note' }]));
      result.current.push(makeWorkflow('c', [{ id: 'n1', type: 'note' }, { id: 'n2', type: 'note' }]));
      result.current.push(makeWorkflow('d', [{ id: 'n1', type: 'note' }, { id: 'n2', type: 'note' }, { id: 'n3', type: 'note' }]));
      commit();
    });
    // Only one undo step — back to the original.
    let popped = null as ReturnType<typeof result.current.undo>;
    act(() => {
      popped = result.current.undo();
    });
    expect(popped?.workflow.id).toBe('a');
    expect(result.current.canUndo).toBe(false);
  });

  it('clones the workflow so external mutations do not corrupt history', () => {
    const initial = makeWorkflow('a');
    const { result } = renderHook(() => useHistory(initial));
    initial.name = 'mutated-after-init';
    let popped = null as ReturnType<typeof result.current.undo>;
    act(() => {
      // Push, then undo to the cloned initial.
      result.current.push(makeWorkflow('b', [{ id: 'x', type: 'note' }]));
      popped = result.current.undo();
    });
    expect(popped?.workflow.name).toBe('a');
  });
});
