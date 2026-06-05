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
});
