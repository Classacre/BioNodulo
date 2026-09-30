import { act, renderHook } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import type { Workflow } from '../types';
import { useAutoSave } from '../hooks/workflow/useAutoSave';

function workflow(name: string): Workflow {
  return { id: 'wf', version: '2.0', app: 'bionodulo', name, description: '',
    nodes: [], edges: [], groups: [], outputs: {}, parameters: [] };
}

describe('useAutoSave collaboration persistence', () => {
  afterEach(() => vi.useRealTimers());

  it('keeps changes dirty when publishing fails', async () => {
    vi.useFakeTimers();
    const setDirty = vi.fn();
    const publish = vi.fn().mockRejectedValue(new Error('offline'));
    renderHook(() => useAutoSave({ autoSaveSetting: '30s', collabEnabled: true,
      latestWorkflow: workflow('draft'), publishCollabWorkflowSnapshot: publish, setDirty }));
    await act(async () => { await vi.advanceTimersByTimeAsync(30000); });
    expect(publish).toHaveBeenCalledOnce();
    expect(setDirty).not.toHaveBeenCalledWith(false);
  });

  it('does not mark newer edits clean when an older publish finishes', async () => {
    vi.useFakeTimers();
    let finish!: () => void;
    const publish = vi.fn(() => new Promise<void>(resolve => { finish = resolve; }));
    const setDirty = vi.fn();
    const first = workflow('first');
    const second = workflow('second');
    const { rerender } = renderHook(({ latestWorkflow }) => useAutoSave({
      autoSaveSetting: '30s', collabEnabled: true, latestWorkflow,
      publishCollabWorkflowSnapshot: publish, setDirty,
    }), { initialProps: { latestWorkflow: first } });
    act(() => { vi.advanceTimersByTime(30000); });
    rerender({ latestWorkflow: second });
    await act(async () => { finish(); });
    expect(setDirty).not.toHaveBeenCalledWith(false);
  });
});
