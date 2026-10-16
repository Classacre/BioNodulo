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

  it('replaces a stale graph plan with immutable cloud submission IDs', () => {
    const { result } = renderHook(() => useWorkflow());
    act(() => result.current.addRun({ ...pendingRun, execution_plan: ['current-saved-node'],
      node_statuses: [{ node_id: 'current-saved-node', status: 'completed' }], options: { cloud: true } }));
    act(() => result.current.updateRun('fast-run', {
      cloud_workflow_context: { schemaVersion: 1, workflowName: 'Submitted graph', executionNodeIds: ['old-a', 'old-b'] },
      execution_plan: ['old-a', 'old-b'], node_statuses: [{ node_id: 'old-a', status: 'completed' }, { node_id: 'old-b', status: 'running' }],
    }));
    expect(result.current.runs[0].execution_plan).toEqual(['old-a', 'old-b']);
    expect(result.current.runs[0].node_statuses.map(node => node.node_id)).toEqual(['old-a', 'old-b']);
  });

  it('drops unobserved legacy IDs and does not retain an inferred completion', () => {
    const { result } = renderHook(() => useWorkflow());
    act(() => result.current.addRun({ ...pendingRun, options: { cloud: true },
      node_statuses: [{ node_id: 'input', status: 'completed' }, { node_id: 'normalize', status: 'completed' }] }));
    act(() => result.current.updateRun('fast-run', {
      cloud_workflow_context: null, execution_plan: ['input'], node_statuses: [{ node_id: 'input', status: 'running' }],
    }));
    expect(result.current.runs[0].execution_plan).toEqual(['input']);
    expect(result.current.runs[0].node_statuses).toEqual([{ node_id: 'input', status: 'running' }]);
  });

  it('labels unknown legacy runs by stable ID while retaining a captured submission name', () => {
    const { result } = renderHook(() => useWorkflow());
    act(() => result.current.addRun({ ...pendingRun, run_id: 'legacy-run-1234567890', workflow_name: '', options: { cloud: true } }));
    expect(result.current.runs[0].workflow_name).toBe('Cloud run legacy-r...7890');
    act(() => result.current.addRun({ ...pendingRun, workflow_name: 'Captured submission', options: { cloud: true } }));
    act(() => result.current.addRun({ ...pendingRun, workflow_name: '', options: { cloud: true } }));
    expect(result.current.runs.find(run => run.run_id === pendingRun.run_id)?.workflow_name).toBe('Captured submission');
  });
});
