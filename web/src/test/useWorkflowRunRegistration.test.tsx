import { act, renderHook } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { useWorkflow } from '../hooks/workflow/useWorkflow';
import type { RunRecord } from '../types';

const pendingRun: RunRecord = {
  run_id: 'fast-run', workflow_name: 'Tiny workflow', status: 'pending',
  node_statuses: [], execution_plan: ['input', 'normalize'], node_outputs: {}, previews: {}, artifacts: {},
  start_time: '2026-09-19T12:00:01.000Z',
};

describe('local run registration and event ordering', () => {
  beforeEach(() => {
    vi.stubGlobal('localStorage', { getItem: () => null, setItem: vi.fn(), removeItem: vi.fn() });
  });
  afterEach(() => vi.unstubAllGlobals());

  it.each(['completed', 'error', 'cancelled'] as const)('retains an early %s event when the pending submission response arrives later', status => {
    const { result } = renderHook(() => useWorkflow());
    act(() => result.current.updateRun('fast-run', {
      status,
      start_time: '2026-09-19T12:00:00.000Z',
      end_time: '2026-09-19T12:00:00.044Z',
      node_statuses: [{ node_id: 'input', status: 'completed' }, { node_id: 'normalize', status: 'cached' }],
      previews: { normalize: 'cached.tsv' },
      execution_plan: ['input'],
    }));
    act(() => result.current.addRun(pendingRun));
    expect(result.current.runs).toHaveLength(1);
    expect(result.current.runs[0]).toMatchObject({
      status, workflow_name: 'Tiny workflow',
      start_time: '2026-09-19T12:00:00.000Z', end_time: '2026-09-19T12:00:00.044Z',
      execution_plan: ['input', 'normalize'], previews: { normalize: 'cached.tsv' },
      node_statuses: [{ node_id: 'input', status: 'completed' }, { node_id: 'normalize', status: 'cached' }],
    });
    // Repeated registration or a late start must not revive a terminal run.
    act(() => {
      result.current.addRun(pendingRun);
      result.current.updateRun('fast-run', { status: 'running' });
    });
    expect(result.current.runs).toHaveLength(1);
    expect(result.current.runs[0].status).toBe(status);
  });

  it('merges same-batch start/registration/finish updates without dropping the run or its plan', () => {
    const { result } = renderHook(() => useWorkflow());
    act(() => {
      result.current.updateRun('fast-run', { status: 'running' });
      result.current.addRun(pendingRun);
      result.current.updateRun('fast-run', { status: 'completed' });
    });
    expect(result.current.runs).toHaveLength(1);
    expect(result.current.runs[0].status).toBe('completed');
    expect(result.current.runs[0].execution_plan).toEqual(['input', 'normalize']);
  });
});
