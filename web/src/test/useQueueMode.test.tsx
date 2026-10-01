import { renderHook, act } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { useQueueMode } from '../hooks/workflow/useQueueMode';
import type { RunRecord, WorkflowNode } from '../types';

const node = { id: 'one', type: 'input_file' } as WorkflowNode;
const completed = { run_id: 'run-one', status: 'completed' } as RunRecord;

afterEach(() => { vi.useRealTimers(); localStorage.clear(); });

describe('cloud editor queue mode', () => {
  it.each(['change', 'instant'] as const)('does not automatically submit a %s-mode run when disabled', mode => {
    vi.useFakeTimers();
    localStorage.setItem('bionodulo.queueMode', mode);
    const triggerRun = vi.fn();
    const { result, rerender } = renderHook(({ enabled }) => useQueueMode({
      enabled, dirty: true, isRunning: false, activeNodes: [node], runs: [completed], triggerRun,
    }), { initialProps: { enabled: false } });
    expect(result.current.queueMode).toBe('manual');
    act(() => { vi.advanceTimersByTime(2000); });
    expect(triggerRun).not.toHaveBeenCalled();
    rerender({ enabled: true });
    expect(result.current.queueMode).toBe(mode);
    act(() => { vi.advanceTimersByTime(2000); });
    expect(triggerRun).toHaveBeenCalledTimes(1);
  });
});
