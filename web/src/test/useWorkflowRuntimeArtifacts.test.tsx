import { renderHook, waitFor, act } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { apiGet, apiPost } from '../api/client';
import { useWorkflowRuntimeArtifacts } from '../hooks/workflow/useWorkflowRuntimeArtifacts';

const apiMocks = vi.hoisted(() => ({
  apiGet: vi.fn(),
  apiPost: vi.fn(),
}));

vi.mock('../api/client', () => apiMocks);

describe('useWorkflowRuntimeArtifacts', () => {
  beforeEach(() => {
    vi.mocked(apiGet).mockReset();
    vi.mocked(apiPost).mockReset();
  });

  it('loads checkpoint, pause request, and workflow trigger state on refresh', async () => {
    vi.mocked(apiGet)
      .mockResolvedValueOnce({
        exists: true,
        manifest_path: '/workspace/checkpoints/checkpoint_manifest.json',
        manifest: { version: '1.0', checkpoints: { one: { checkpoint_name: 'after_qc' } } },
      })
      .mockResolvedValueOnce({
        pause_requests_dir: '/workspace/pause_requests',
        pause_requests: [{ node_id: 'pause-node', status: 'waiting', pause_file: '/workspace/pause_requests/pause-node.json' }],
        count: 1,
        errors: [],
      })
      .mockResolvedValueOnce({
        trigger_dir: '/workspace/workflow_triggers',
        triggers: [{ trigger_type: 'schedule', target_workflow: 'weekly-qc' }],
        count: 1,
        errors: [],
      });

    const { result } = renderHook(() => useWorkflowRuntimeArtifacts());

    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(apiGet).toHaveBeenCalledWith('/checkpoints/manifest');
    expect(apiGet).toHaveBeenCalledWith('/pause_requests');
    expect(apiGet).toHaveBeenCalledWith('/workflow_triggers');
    expect(result.current.checkpointManifest?.exists).toBe(true);
    expect(result.current.pauseRequests?.pause_requests[0].node_id).toBe('pause-node');
    expect(result.current.workflowTriggers?.triggers[0].target_workflow).toBe('weekly-qc');
    expect(result.current.error).toBeNull();
  });

  it('validates refresh payloads before storing runtime artifact state', async () => {
    vi.mocked(apiGet)
      .mockResolvedValueOnce({
        exists: true,
        manifest_path: '/workspace/checkpoints/checkpoint_manifest.json',
        manifest: { version: '1.0' },
      })
      .mockResolvedValueOnce({
        pause_requests_dir: '/workspace/pause_requests',
        pause_requests: [
          { node_id: 'pause-node', status: 'waiting' },
          'bad-row',
        ],
        count: 2,
        errors: ['bad-error', { pause_file: '/workspace/pause_requests/bad.json', error: 'bad json' }],
      })
      .mockResolvedValueOnce({
        trigger_dir: '/workspace/workflow_triggers',
        triggers: [
          { trigger_type: 'schedule', target_workflow: 'weekly-qc' },
          null,
        ],
        count: 2,
        errors: [],
      });

    const { result } = renderHook(() => useWorkflowRuntimeArtifacts());

    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(result.current.error).toBeNull();
    expect(result.current.pauseRequests?.pause_requests).toEqual([{ node_id: 'pause-node', status: 'waiting' }]);
    expect(result.current.pauseRequests?.count).toBe(1);
    expect(result.current.pauseRequests?.errors).toEqual([
      { pause_file: '/workspace/pause_requests/bad.json', error: 'bad json' },
    ]);
    expect(result.current.workflowTriggers?.triggers).toEqual([
      { trigger_type: 'schedule', target_workflow: 'weekly-qc' },
    ]);
    expect(result.current.workflowTriggers?.count).toBe(1);
  });

  it('surfaces validation errors from malformed runtime artifact refresh payloads', async () => {
    vi.mocked(apiGet)
      .mockResolvedValueOnce({
        exists: 'yes',
        manifest_path: '/workspace/checkpoints/checkpoint_manifest.json',
        manifest: {},
      })
      .mockResolvedValueOnce({ pause_requests_dir: '/workspace/pause_requests', pause_requests: [], count: 0, errors: [] })
      .mockResolvedValueOnce({ trigger_dir: '/workspace/workflow_triggers', triggers: [], count: 0, errors: [] });

    const { result } = renderHook(() => useWorkflowRuntimeArtifacts());

    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(result.current.error?.name).toBe('ApiValidationError');
    expect(result.current.checkpointManifest).toBeNull();
    expect(result.current.pauseRequests).toBeNull();
    expect(result.current.workflowTriggers).toBeNull();
  });

  it('evaluates triggers and resolves pause requests through the runtime artifact APIs', async () => {
    vi.mocked(apiGet)
      .mockResolvedValueOnce({ exists: false, manifest_path: '/workspace/checkpoints/checkpoint_manifest.json', manifest: {} })
      .mockResolvedValueOnce({ pause_requests_dir: '/workspace/pause_requests', pause_requests: [], count: 0, errors: [] })
      .mockResolvedValueOnce({ trigger_dir: '/workspace/workflow_triggers', triggers: [], count: 0, errors: [] });
    vi.mocked(apiPost)
      .mockResolvedValueOnce({
        due_schedule_triggers: [{ target_workflow: 'weekly-qc' }],
        due_schedule_count: 1,
        due_file_watch_triggers: [],
        due_file_watch_count: 0,
        submitted_runs: [],
        submitted_run_count: 0,
        errors: [],
      })
      .mockResolvedValueOnce({
        pause_request: { node_id: 'pause-node', status: 'approved', approved: true },
      });

    const { result } = renderHook(() => useWorkflowRuntimeArtifacts());

    await waitFor(() => expect(result.current.loading).toBe(false));

    await act(async () => {
      await result.current.evaluateWorkflowTriggers('2026-06-07T18:30:00+00:00');
      await result.current.resolvePauseRequest({
        node_id: 'pause-node',
        action: 'approve',
        reviewer: 'ana',
        comment: 'QC reviewed',
      });
    });

    expect(apiPost).toHaveBeenNthCalledWith(1, '/workflow_triggers/evaluate', {
      now: '2026-06-07T18:30:00+00:00',
    });
    expect(apiPost).toHaveBeenNthCalledWith(2, '/pause_requests/resolve', {
      node_id: 'pause-node',
      action: 'approve',
      reviewer: 'ana',
      comment: 'QC reviewed',
    });
    expect(result.current.triggerEvaluation?.due_schedule_count).toBe(1);
    expect(result.current.lastResolvedPauseRequest?.status).toBe('approved');
  });

  it('validates runtime artifact action responses before updating hook state', async () => {
    vi.mocked(apiGet)
      .mockResolvedValueOnce({ exists: false, manifest_path: '/workspace/checkpoints/checkpoint_manifest.json', manifest: {} })
      .mockResolvedValueOnce({ pause_requests_dir: '/workspace/pause_requests', pause_requests: [], count: 0, errors: [] })
      .mockResolvedValueOnce({ trigger_dir: '/workspace/workflow_triggers', triggers: [], count: 0, errors: [] });
    vi.mocked(apiPost)
      .mockResolvedValueOnce({
        due_schedule_triggers: [{ target_workflow: 'weekly-qc' }, 'bad-row'],
        due_schedule_count: 3,
        due_file_watch_triggers: [],
        due_file_watch_count: 0,
        submitted_runs: [{ status: 'submitted', run_id: 'weekly-qc-run' }, null],
        submitted_run_count: 3,
        errors: ['bad-error'],
      })
      .mockResolvedValueOnce({
        pause_request: { node_id: 'pause-node', status: 'approved', approved: true },
      });

    const { result } = renderHook(() => useWorkflowRuntimeArtifacts());

    await waitFor(() => expect(result.current.loading).toBe(false));

    await act(async () => {
      await result.current.evaluateWorkflowTriggers('2026-06-07T18:30:00+00:00');
      await result.current.resolvePauseRequest({ node_id: 'pause-node', action: 'approve' });
    });

    expect(result.current.triggerEvaluation?.due_schedule_triggers).toEqual([{ target_workflow: 'weekly-qc' }]);
    expect(result.current.triggerEvaluation?.due_schedule_count).toBe(1);
    expect(result.current.triggerEvaluation?.submitted_runs).toEqual([{ status: 'submitted', run_id: 'weekly-qc-run' }]);
    expect(result.current.triggerEvaluation?.submitted_run_count).toBe(1);
    expect(result.current.triggerEvaluation?.errors).toEqual([]);
    expect(result.current.lastResolvedPauseRequest?.approved).toBe(true);
  });

  it('submits due triggers when requested', async () => {
    vi.mocked(apiGet)
      .mockResolvedValueOnce({ exists: false, manifest_path: '/workspace/checkpoints/checkpoint_manifest.json', manifest: {} })
      .mockResolvedValueOnce({ pause_requests_dir: '/workspace/pause_requests', pause_requests: [], count: 0, errors: [] })
      .mockResolvedValueOnce({ trigger_dir: '/workspace/workflow_triggers', triggers: [], count: 0, errors: [] });
    vi.mocked(apiPost).mockResolvedValueOnce({
      due_schedule_triggers: [{ target_workflow: 'weekly-qc' }],
      due_schedule_count: 1,
      due_file_watch_triggers: [],
      due_file_watch_count: 0,
      submitted_runs: [{ status: 'submitted', run_id: 'weekly-qc-run', target_workflow: 'weekly-qc' }],
      submitted_run_count: 1,
      errors: [],
    });

    const { result } = renderHook(() => useWorkflowRuntimeArtifacts());

    await waitFor(() => expect(result.current.loading).toBe(false));

    await act(async () => {
      await result.current.evaluateWorkflowTriggers('2026-06-07T18:30:00+00:00', { submitRuns: true });
    });

    expect(apiPost).toHaveBeenCalledWith('/workflow_triggers/evaluate', {
      now: '2026-06-07T18:30:00+00:00',
      submit_runs: true,
    });
    expect(result.current.triggerEvaluation?.submitted_run_count).toBe(1);
    expect(result.current.triggerEvaluation?.submitted_runs[0].run_id).toBe('weekly-qc-run');
  });

  it('resolves checkpoints through the runtime artifact APIs', async () => {
    vi.mocked(apiGet)
      .mockResolvedValueOnce({
        exists: true,
        manifest_path: '/workspace/checkpoints/checkpoint_manifest.json',
        manifest: {
          version: '1.0',
          checkpoints: {
            '/workspace/checkpoints/after_annotation.json': {
              checkpoint_name: 'after_annotation',
              node_id: 'checkpoint-node',
            },
          },
        },
      })
      .mockResolvedValueOnce({ pause_requests_dir: '/workspace/pause_requests', pause_requests: [], count: 0, errors: [] })
      .mockResolvedValueOnce({ trigger_dir: '/workspace/workflow_triggers', triggers: [], count: 0, errors: [] })
      .mockResolvedValueOnce({
        found: true,
        manifest_path: '/workspace/checkpoints/checkpoint_manifest.json',
        checkpoint: {
          checkpoint_name: 'after_annotation',
          checkpoint_path: '/workspace/checkpoints/after_annotation.json',
          run_id: 'run-42',
          node_id: 'checkpoint-node',
        },
      });

    const { result } = renderHook(() => useWorkflowRuntimeArtifacts());

    await waitFor(() => expect(result.current.loading).toBe(false));

    await act(async () => {
      await result.current.resolveCheckpoint({ checkpoint_name: 'after_annotation' });
    });

    expect(apiGet).toHaveBeenLastCalledWith('/checkpoints/resolve?checkpoint_name=after_annotation');
    expect(result.current.lastResolvedCheckpoint?.checkpoint?.checkpoint_name).toBe('after_annotation');
  });
});
