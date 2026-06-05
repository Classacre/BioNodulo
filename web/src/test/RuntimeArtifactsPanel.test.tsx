import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const storage = new Map<string, string>();
const localStorageStub: Storage = {
  get length() {
    return storage.size;
  },
  clear: () => storage.clear(),
  getItem: (key: string) => storage.get(key) ?? null,
  key: (index: number) => Array.from(storage.keys())[index] ?? null,
  removeItem: (key: string) => {
    storage.delete(key);
  },
  setItem: (key: string, value: string) => {
    storage.set(key, String(value));
  },
};

const runtimeMocks = vi.hoisted(() => ({
  useWorkflowRuntimeArtifacts: vi.fn(),
}));

vi.mock('../hooks/workflow/useWorkflowRuntimeArtifacts', () => runtimeMocks);

describe('RuntimeArtifactsPanel', () => {
  const evaluateWorkflowTriggers = vi.fn();
  const resolveCheckpoint = vi.fn();
  const resolvePauseRequest = vi.fn();
  const refresh = vi.fn();
  const onClose = vi.fn();
  let originalLocalStorage: Storage;

  beforeEach(() => {
    storage.clear();
    originalLocalStorage = window.localStorage;
    vi.stubGlobal('localStorage', localStorageStub);
    evaluateWorkflowTriggers.mockReset();
    resolveCheckpoint.mockReset();
    resolvePauseRequest.mockReset();
    refresh.mockReset();
    onClose.mockReset();
    runtimeMocks.useWorkflowRuntimeArtifacts.mockReset();
    runtimeMocks.useWorkflowRuntimeArtifacts.mockReturnValue({
      checkpointManifest: {
        exists: true,
        manifest_path: '/workspace/checkpoints/checkpoint_manifest.json',
        manifest: {
          checkpoints: {
            after_qc: { checkpoint_name: 'after_qc', node_id: 'qc-node' },
            after_align: { checkpoint_name: 'after_align', node_id: 'align-node' },
          },
        },
      },
      pauseRequests: {
        pause_requests_dir: '/workspace/pause_requests',
        count: 2,
        pause_requests: [
          {
            node_id: 'pause-node',
            status: 'waiting',
            message: 'Review sample QC',
            pause_file: '/workspace/pause_requests/pause-node.json',
          },
          {
            node_id: 'approved-node',
            status: 'approved',
            approved: true,
          },
        ],
        errors: [],
      },
      workflowTriggers: {
        trigger_dir: '/workspace/workflow_triggers',
        count: 2,
        triggers: [
          { trigger_type: 'schedule', target_workflow: 'weekly-qc', status: 'active' },
          { trigger_type: 'file_watch', target_workflow: 'import-watch', status: 'active' },
        ],
        errors: [],
      },
      triggerEvaluation: {
        due_schedule_triggers: [{ trigger_type: 'schedule', target_workflow: 'weekly-qc' }],
        due_schedule_count: 1,
        due_file_watch_triggers: [{ trigger_type: 'file_watch', target_workflow: 'import-watch' }],
        due_file_watch_count: 1,
        errors: [],
      },
      lastResolvedCheckpoint: null,
      lastResolvedPauseRequest: null,
      loading: false,
      error: null,
      refresh,
      evaluateWorkflowTriggers,
      resolveCheckpoint,
      resolvePauseRequest,
    });
  });

  afterEach(async () => {
    const { setLanguage } = await import('../i18n');
    await setLanguage('en');
    storage.clear();
    vi.unstubAllGlobals();
    Object.defineProperty(window, 'localStorage', {
      configurable: true,
      value: originalLocalStorage,
    });
  });

  it('renders runtime artifacts and exposes trigger and pause actions', async () => {
    const { default: RuntimeArtifactsPanel } = await import('../components/panels/RuntimeArtifactsPanel');
    const { setLanguage } = await import('../i18n');
    await setLanguage('en');

    render(<RuntimeArtifactsPanel onClose={onClose} />);

    expect(screen.getByText('Runtime artifacts')).toBeInTheDocument();
    expect(screen.getByText('2 checkpoints')).toBeInTheDocument();
    expect(screen.getByText('after_qc')).toBeInTheDocument();
    expect(screen.getByText('Review sample QC')).toBeInTheDocument();
    expect(screen.getByText('weekly-qc')).toBeInTheDocument();
    expect(screen.getByText('1 schedule trigger due')).toBeInTheDocument();
    expect(screen.getByText('1 file-watch trigger due')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Evaluate triggers' }));
    await waitFor(() => expect(evaluateWorkflowTriggers).toHaveBeenCalledTimes(1));

    fireEvent.click(screen.getByRole('button', { name: 'Resolve after_qc' }));
    await waitFor(() => expect(resolveCheckpoint).toHaveBeenCalledWith({ checkpoint_name: 'after_qc' }));

    fireEvent.click(screen.getByRole('button', { name: 'Approve pause-node' }));
    await waitFor(() => expect(resolvePauseRequest).toHaveBeenCalledWith({
      action: 'approve',
      node_id: 'pause-node',
      pause_file: '/workspace/pause_requests/pause-node.json',
    }));

    fireEvent.click(screen.getByRole('button', { name: 'Reject pause-node' }));
    await waitFor(() => expect(resolvePauseRequest).toHaveBeenLastCalledWith({
      action: 'reject',
      node_id: 'pause-node',
      pause_file: '/workspace/pause_requests/pause-node.json',
    }));
  });

  it('renders loading and error states', async () => {
    const { default: RuntimeArtifactsPanel } = await import('../components/panels/RuntimeArtifactsPanel');
    const { setLanguage } = await import('../i18n');
    await setLanguage('en');

    runtimeMocks.useWorkflowRuntimeArtifacts.mockReturnValue({
      checkpointManifest: null,
      pauseRequests: null,
      workflowTriggers: null,
      triggerEvaluation: null,
      lastResolvedCheckpoint: null,
      lastResolvedPauseRequest: null,
      loading: true,
      error: null,
      refresh,
      evaluateWorkflowTriggers,
      resolveCheckpoint,
      resolvePauseRequest,
    });

    const { rerender } = render(<RuntimeArtifactsPanel onClose={onClose} />);

    expect(screen.getByText('Loading...')).toBeInTheDocument();

    runtimeMocks.useWorkflowRuntimeArtifacts.mockReturnValue({
      checkpointManifest: null,
      pauseRequests: null,
      workflowTriggers: null,
      triggerEvaluation: null,
      lastResolvedCheckpoint: null,
      lastResolvedPauseRequest: null,
      loading: false,
      error: new Error('backend unavailable'),
      refresh,
      evaluateWorkflowTriggers,
      resolveCheckpoint,
      resolvePauseRequest,
    });

    rerender(<RuntimeArtifactsPanel onClose={onClose} />);

    expect(screen.getByText('backend unavailable')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Refresh' }));
    expect(refresh).toHaveBeenCalledTimes(1);
  });

  it('surfaces the latest resolved checkpoint', async () => {
    const { default: RuntimeArtifactsPanel } = await import('../components/panels/RuntimeArtifactsPanel');
    const { setLanguage } = await import('../i18n');
    await setLanguage('en');

    runtimeMocks.useWorkflowRuntimeArtifacts.mockReturnValue({
      checkpointManifest: {
        exists: true,
        manifest_path: '/workspace/checkpoints/checkpoint_manifest.json',
        manifest: { checkpoints: {} },
      },
      pauseRequests: { pause_requests_dir: '/workspace/pause_requests', count: 0, pause_requests: [], errors: [] },
      workflowTriggers: { trigger_dir: '/workspace/workflow_triggers', count: 0, triggers: [], errors: [] },
      triggerEvaluation: null,
      lastResolvedCheckpoint: {
        found: true,
        manifest_path: '/workspace/checkpoints/checkpoint_manifest.json',
        checkpoint: {
          checkpoint_name: 'after_annotation',
          checkpoint_path: '/workspace/checkpoints/after_annotation.json',
          node_id: 'checkpoint-node',
        },
      },
      lastResolvedPauseRequest: null,
      loading: false,
      error: null,
      refresh,
      evaluateWorkflowTriggers,
      resolveCheckpoint,
      resolvePauseRequest,
    });

    render(<RuntimeArtifactsPanel onClose={onClose} />);

    expect(screen.getByText('Resolved checkpoint')).toBeInTheDocument();
    expect(screen.getByText('after_annotation')).toBeInTheDocument();
    expect(screen.getByText('/workspace/checkpoints/after_annotation.json')).toBeInTheDocument();
  });

  it('labels checkpoints as manifest-only when executor resume is unavailable', async () => {
    const { default: RuntimeArtifactsPanel } = await import('../components/panels/RuntimeArtifactsPanel');
    const { setLanguage } = await import('../i18n');
    await setLanguage('en');

    runtimeMocks.useWorkflowRuntimeArtifacts.mockReturnValue({
      checkpointManifest: {
        exists: true,
        manifest_path: '/workspace/checkpoints/checkpoint_manifest.json',
        resume_manifest_supported: true,
        resume_supported: false,
        resume_note: 'Checkpoint artifact and resume manifest written; executor-level resume is not implemented yet.',
        manifest: {
          version: '1.0',
          checkpoints: {
            '/workspace/checkpoints/after_annotation.json': {
              checkpoint_name: 'after_annotation',
              node_id: 'checkpoint-node',
            },
          },
        },
      },
      pauseRequests: { pause_requests_dir: '/workspace/pause_requests', count: 0, pause_requests: [], errors: [] },
      workflowTriggers: { trigger_dir: '/workspace/workflow_triggers', count: 0, triggers: [], errors: [] },
      triggerEvaluation: null,
      lastResolvedCheckpoint: {
        found: true,
        manifest_path: '/workspace/checkpoints/checkpoint_manifest.json',
        resume_manifest_supported: true,
        resume_supported: false,
        resume_note: 'Checkpoint artifact and resume manifest written; executor-level resume is not implemented yet.',
        checkpoint: {
          checkpoint_name: 'after_annotation',
          checkpoint_path: '/workspace/checkpoints/after_annotation.json',
          node_id: 'checkpoint-node',
        },
      },
      lastResolvedPauseRequest: null,
      loading: false,
      error: null,
      refresh,
      evaluateWorkflowTriggers,
      resolveCheckpoint,
      resolvePauseRequest,
    });

    render(<RuntimeArtifactsPanel onClose={onClose} />);

    expect(screen.getByText('Manifest only')).toBeInTheDocument();
    expect(screen.getAllByText('Executor resume unavailable')).toHaveLength(2);
  });
});
