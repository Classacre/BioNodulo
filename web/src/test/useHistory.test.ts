import { describe, it, expect, vi } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useHistory } from '../hooks/useHistory';
import type { Workflow } from '../types';

function makeWorkflow(label: string): Workflow {
  return {
    id: `wf-${label}`,
    name: `wf-${label}`,
    version: '2.0',
    nodes: [],
    edges: [],
    groups: [],
  } as unknown as Workflow;
}

describe('useHistory', () => {
  it('starts with the initial workflow and cannot undo', () => {
    const onChange = vi.fn();
    const initial = makeWorkflow('a');
    const { result } = renderHook(() => useHistory(initial, onChange));
    expect(result.current.canUndo).toBe(false);
    expect(result.current.canRedo).toBe(false);
  });

  it('pushes new workflows and supports undo/redo', () => {
    const onChange = vi.fn();
    const initial = makeWorkflow('a');
    const { result } = renderHook(() => useHistory(initial, onChange));
    act(() => result.current.push(makeWorkflow('b')));
    expect(result.current.canUndo).toBe(true);

    act(() => result.current.undo());
    expect(onChange).toHaveBeenCalledTimes(1);
    expect(onChange.mock.calls[0]![0]!.id).toBe('wf-a');

    act(() => result.current.redo());
    expect(onChange).toHaveBeenCalledTimes(2);
    expect(onChange.mock.calls[1]![0]!.id).toBe('wf-b');
  });
});
