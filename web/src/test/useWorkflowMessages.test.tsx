import { useCallback, useState } from 'react';
import { act, renderHook, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import '../i18n';
import { useWorkflowMessages } from '../hooks/workflow/useWorkflowMessages';
import type { NodeStatus, RunRecord } from '../types';

const mocks = vi.hoisted(() => ({ apiGet: vi.fn(), toastError: vi.fn() }));
vi.mock('../api/client', () => ({ apiGet: mocks.apiGet }));
vi.mock('../state/notifications', () => ({ toast: { error: mocks.toastError } }));

describe('workflow completion progress', () => {
  beforeEach(() => vi.clearAllMocks());

  it.each([
    { status: 'completed', secondStatus: 'completed', includeResult: true },
    { status: 'completed', secondStatus: 'cached', includeResult: false },
    { status: 'failed', secondStatus: 'error', includeResult: true },
  ] as const)('recovers missed node events from a $status snapshot (result=$includeResult)', async ({ status, secondStatus, includeResult }) => {
    const nodeStatuses: NodeStatus[] = [
      { node_id: 'input', status: 'completed' },
      { node_id: 'normalize', status: secondStatus, ...(secondStatus === 'error' ? { error: 'Invalid counts' } : {}) },
    ];
    mocks.apiGet.mockResolvedValue({
      run_id: 'fast-run', status, node_statuses: nodeStatuses,
      execution_plan: ['input', 'normalize'],
      ...(includeResult ? { result: { previews: [{ node_id: 'input', path: 'counts.tsv' }] } } : {}),
    });
    let messageHandler: ((data: unknown) => void) | undefined;
    const onMessage = (handler: (data: unknown) => void) => {
      messageHandler = handler;
      return () => { if (messageHandler === handler) messageHandler = undefined; };
    };
    const { result } = renderHook(() => {
      const [runs, setRuns] = useState<RunRecord[]>([{
        run_id: 'fast-run', workflow_name: 'Tiny workflow', status: 'pending',
        node_statuses: [], node_outputs: {}, execution_plan: ['stale-plan'], previews: {}, artifacts: {},
      }]);
      const updateRun = useCallback((id: string, patch: Partial<RunRecord>) => {
        setRuns(previous => previous.map(run => run.run_id === id ? { ...run, ...patch } : run));
      }, []);
      useWorkflowMessages({
        onMessage, runs, setRuns, updateRun,
        addLog: vi.fn(), updateNodeRunStatus: vi.fn(), recordNodeStart: vi.fn(), clearNodeRunProgress: vi.fn(),
      });
      return runs;
    });

    // Deliberately omit node_start/node_complete: the server snapshot is the
    // only available source of node progress, as in a fast browser run.
    act(() => messageHandler?.({ type: 'queue_finish', data: { run_id: 'fast-run', status } }));
    await waitFor(() => expect(result.current[0].node_statuses).toEqual(nodeStatuses));
    expect(result.current[0].execution_plan).toEqual(['input', 'normalize']);
    expect(result.current[0].status).toBe(status === 'failed' ? 'error' : 'completed');
    expect(mocks.apiGet).toHaveBeenCalledWith('/api/runs/fast-run');
    if (includeResult) expect(result.current[0].previews).toEqual({ input: 'counts.tsv' });
  });

  it('recovers a cache hit omitted by the older top-level run summary', async () => {
    mocks.apiGet.mockResolvedValue({
      run_id: 'cached-run', status: 'completed',
      execution_plan: ['input'], node_statuses: [{ node_id: 'input', status: 'completed' }],
      result: {
        node_results: {
          input: { status: 'completed' },
          normalize: { status: 'cached' },
          unreported: { outputs: {} },
        },
      },
    });
    let messageHandler: ((data: unknown) => void) | undefined;
    const updateRun = vi.fn();
    renderHook(() => useWorkflowMessages({
      onMessage: handler => { messageHandler = handler; return () => {}; },
      runs: [], setRuns: vi.fn(), updateRun,
      addLog: vi.fn(), updateNodeRunStatus: vi.fn(), recordNodeStart: vi.fn(), clearNodeRunProgress: vi.fn(),
    }));
    act(() => messageHandler?.({ type: 'queue_finish', data: { run_id: 'cached-run', status: 'completed' } }));
    await waitFor(() => expect(updateRun).toHaveBeenCalledWith('cached-run', expect.objectContaining({
      status: 'completed', execution_plan: ['input', 'normalize'],
      node_statuses: [{ node_id: 'input', status: 'completed' }, { node_id: 'normalize', status: 'cached' }],
    })));
    expect(JSON.stringify(updateRun.mock.calls)).not.toContain('unreported');
  });

  it('reconciles queue_error so completed upstream nodes stay completed', async () => {
    mocks.apiGet.mockResolvedValue({
      run_id: 'failed-run', status: 'failed',
      // Reproduce the older/in-flight top-level snapshot seen by the browser.
      node_statuses: [{ node_id: 'input', status: 'completed' }],
      execution_plan: ['input', 'validate'],
      result: {
        node_results: {
          input: { status: 'completed' },
          validate: { status: 'failed', error: 'BED coordinates contradict declaration' },
        },
      },
    });
    let messageHandler: ((data: unknown) => void) | undefined;
    const onMessage = (handler: (data: unknown) => void) => {
      messageHandler = handler;
      return () => { if (messageHandler === handler) messageHandler = undefined; };
    };
    const { result } = renderHook(() => {
      const [runs, setRuns] = useState<RunRecord[]>([{
        run_id: 'failed-run', workflow_name: 'Coordinate validation', status: 'running',
        node_statuses: [
          { node_id: 'input', status: 'running' },
          { node_id: 'validate', status: 'running' },
        ],
        node_outputs: {}, execution_plan: ['input', 'validate'], previews: {}, artifacts: {},
      }]);
      const updateRun = useCallback((id: string, patch: Partial<RunRecord>) => {
        setRuns(previous => previous.map(run => run.run_id === id ? { ...run, ...patch } : run));
      }, []);
      useWorkflowMessages({
        onMessage, runs, setRuns, updateRun,
        addLog: vi.fn(), updateNodeRunStatus: vi.fn(), recordNodeStart: vi.fn(), clearNodeRunProgress: vi.fn(),
      });
      return runs;
    });

    act(() => messageHandler?.({
      type: 'queue_error', data: { run_id: 'failed-run', error: 'Workflow failed' },
    }));
    await waitFor(() => expect(result.current[0].node_statuses).toEqual([
      { node_id: 'input', status: 'completed' },
      { node_id: 'validate', status: 'error', error: 'BED coordinates contradict declaration' },
    ]));
    expect(result.current[0].status).toBe('error');
    expect(mocks.apiGet).toHaveBeenCalledWith('/api/runs/failed-run');
  });
});
