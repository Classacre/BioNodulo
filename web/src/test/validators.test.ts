import { describe, it, expect } from 'vitest';
import {
  ApiValidationError,
  safeValidateHostStatus,
  safeValidateCheckpointManifestResponse,
  safeValidateHpcStatus,
  safeValidateRunRecord,
  safeValidateRunsList,
  safeValidateWorkflow,
  validateCheckpointManifestResponse,
  validateHostStatus,
  validateHpcStatus,
  validatePauseRequestsResponse,
  validateResolveCheckpointResponse,
  validateResolvePauseRequestResponse,
  validateRunRecord,
  validateRunsList,
  validateWorkflowTriggerEvaluationResponse,
  validateWorkflowTriggersResponse,
} from '../api/validators';

describe('validateHostStatus', () => {
  it('coerces missing fields to safe defaults', () => {
    expect(validateHostStatus({})).toEqual({
      ready: false,
      checks: {},
      missing_required: [],
      missing_optional: [],
      message: '',
    });
  });

  it('preserves a well-formed payload', () => {
    const payload = {
      ready: true,
      checks: { python: { ok: true } },
      missing_required: [],
      missing_optional: ['hpc'],
      message: 'all good',
    };
    expect(validateHostStatus(payload)).toEqual(payload);
  });

  it('rejects non-objects', () => {
    expect(() => validateHostStatus(null)).toThrow(ApiValidationError);
    expect(() => validateHostStatus('nope')).toThrow(ApiValidationError);
    const result = safeValidateHostStatus(42);
    expect(result.ok).toBe(false);
  });

  it('drops non-string entries from string arrays', () => {
    const result = validateHostStatus({
      ready: true,
      missing_required: ['python', 42, null, 'samtools'],
    });
    expect(result.missing_required).toEqual(['python', 'samtools']);
  });
});

describe('validateHpcStatus', () => {
  it('returns status when valid', () => {
    expect(validateHpcStatus({ status: 'on' })).toEqual({ status: 'on', connected: undefined });
    expect(validateHpcStatus({ status: 'off' })).toEqual({ status: 'off', connected: undefined });
    expect(validateHpcStatus({ status: 'error' })).toEqual({ status: 'error', connected: undefined });
  });

  it('treats unknown status strings as undefined', () => {
    expect(validateHpcStatus({ status: 'connecting' }).status).toBeUndefined();
    expect(validateHpcStatus({ status: 'lol' }).status).toBeUndefined();
  });

  it('falls back to connected boolean shape', () => {
    expect(validateHpcStatus({ connected: true })).toEqual({ status: undefined, connected: true });
  });

  it('rejects non-objects via safe wrapper', () => {
    const result = safeValidateHpcStatus([1, 2, 3]);
    expect(result.ok).toBe(false);
  });
});

describe('validateRunsList', () => {
  it('parses { runs: [...] } shape', () => {
    const result = validateRunsList({
      runs: [
        { run_id: 'r1', status: 'completed' },
        { run_id: 'r2', status: 'pending' },
      ],
    });
    expect(result).toHaveLength(2);
    expect(result[0].run_id).toBe('r1');
  });

  it('parses queue payloads with pending and running runs', () => {
    const result = validateRunsList({
      pending: [
        { run_id: 'pending-1', status: 'pending' },
      ],
      running: [
        { run_id: 'running-1', status: 'running', started_at: 1_710_000_000, finished_at: 1_710_000_060 },
      ],
    });

    expect(result.map(r => r.run_id)).toEqual(['pending-1', 'running-1']);
    expect(result[1].start_time).toBe(new Date(1_710_000_000 * 1000).toISOString());
    expect(result[1].end_time).toBe(new Date(1_710_000_060 * 1000).toISOString());
  });

  it('parses history payloads with a history run array', () => {
    const result = validateRunsList({
      history: [
        { run_id: 'history-1', status: 'completed' },
      ],
    });

    expect(result).toHaveLength(1);
    expect(result[0].status).toBe('completed');
  });

  it('parses a top-level array as fallback', () => {
    const result = validateRunsList([{ run_id: 'r1', status: 'pending' }]);
    expect(result).toHaveLength(1);
  });

  it('skips bad rows instead of failing the list', () => {
    const result = validateRunsList({
      runs: [
        { run_id: 'r1', status: 'completed' },
        { run_id: 42 }, // bad
        { run_id: 'r3', status: 'pending' },
      ],
    });
    expect(result.map(r => r.run_id)).toEqual(['r1', 'r3']);
  });

  it('rejects shapes that are neither array nor { runs }', () => {
    const result = safeValidateRunsList({ rubbish: true });
    expect(result.ok).toBe(false);
  });
});

describe('validateRunRecord', () => {
  it('is permissive about extra fields', () => {
    const r = validateRunRecord({
      run_id: 'r1',
      status: 'completed',
      execution_plan: ['input', 'qc'],
      extra: 'ignored',
    });
    expect(r.run_id).toBe('r1');
    expect(r.status).toBe('completed');
    expect(r.execution_plan).toEqual(['input', 'qc']);
  });

  it('normalizes backend failed status for frontend run cards', () => {
    const r = validateRunRecord({
      run_id: 'r1',
      status: 'failed',
    });
    expect(r.status).toBe('error');
  });

  it('throws on missing run_id', () => {
    const result = safeValidateRunRecord({ status: 'pending' });
    expect(result.ok).toBe(false);
  });
});

describe('runtime artifact API validators', () => {
  it('preserves a checkpoint manifest payload and rejects malformed top-level fields', () => {
    const payload = {
      exists: true,
      manifest_path: '/workspace/checkpoints/checkpoint_manifest.json',
      manifest: { version: '1.0', checkpoints: { after_qc: { checkpoint_name: 'after_qc' } } },
      resume_manifest_supported: true,
      resume_supported: true,
      resume_note: 'Executor resume is available.',
    };

    expect(validateCheckpointManifestResponse(payload)).toEqual(payload);

    const result = safeValidateCheckpointManifestResponse({
      exists: 'yes',
      manifest_path: '/workspace/checkpoints/checkpoint_manifest.json',
      manifest: {},
    });

    expect(result.ok).toBe(false);
  });

  it('normalises runtime artifact list payloads while skipping malformed rows', () => {
    const pauseRequests = validatePauseRequestsResponse({
      pause_requests_dir: '/workspace/pause_requests',
      pause_requests: [
        { node_id: 'pause-node', status: 'waiting' },
        'bad-row',
      ],
      count: 'wrong',
      errors: [{ pause_file: '/workspace/pause_requests/bad.json', error: 'bad json' }, 'bad-error'],
      review_decision_supported: true,
    });

    expect(pauseRequests.count).toBe(1);
    expect(pauseRequests.pause_requests).toEqual([{ node_id: 'pause-node', status: 'waiting' }]);
    expect(pauseRequests.errors).toEqual([{ pause_file: '/workspace/pause_requests/bad.json', error: 'bad json' }]);

    const triggers = validateWorkflowTriggersResponse({
      trigger_dir: '/workspace/workflow_triggers',
      triggers: [
        { trigger_type: 'schedule', target_workflow: 'weekly-qc' },
        null,
      ],
      count: 2,
      errors: [],
      run_submission_supported: false,
    });

    expect(triggers.count).toBe(1);
    expect(triggers.triggers).toEqual([{ trigger_type: 'schedule', target_workflow: 'weekly-qc' }]);
  });

  it('validates runtime artifact action responses', () => {
    const resolvedCheckpoint = validateResolveCheckpointResponse({
      found: true,
      manifest_path: '/workspace/checkpoints/checkpoint_manifest.json',
      checkpoint: {
        checkpoint_name: 'after_qc',
        checkpoint_path: '/workspace/checkpoints/after_qc.json',
      },
    });

    expect(resolvedCheckpoint.checkpoint?.checkpoint_name).toBe('after_qc');

    const triggerEvaluation = validateWorkflowTriggerEvaluationResponse({
      due_schedule_triggers: [{ target_workflow: 'weekly-qc' }],
      due_schedule_count: 'wrong',
      due_file_watch_triggers: [],
      due_file_watch_count: 0,
      submitted_runs: [{ run_id: 'weekly-qc-run', status: 'submitted' }],
      submitted_run_count: 3,
      errors: [],
    });

    expect(triggerEvaluation.due_schedule_count).toBe(1);
    expect(triggerEvaluation.submitted_run_count).toBe(1);

    const pauseResolution = validateResolvePauseRequestResponse({
      pause_request: { node_id: 'pause-node', status: 'approved', approved: true },
    });

    expect(pauseResolution.pause_request.status).toBe('approved');
  });
});

describe('safeValidateWorkflow', () => {
  it('returns ok=false on a missing nodes array', () => {
    const result = safeValidateWorkflow({ id: 'w1' });
    expect(result.ok).toBe(false);
  });

  it('returns ok=true with normalised workflow when valid', () => {
    const result = safeValidateWorkflow({
      id: 'w1',
      nodes: [{ id: 'n1', type: 't1', position: [10, 20] }],
      edges: [],
    });
    expect(result.ok).toBe(true);
    if (result.ok) {
      expect(result.value.nodes[0].position).toEqual([10, 20]);
    }
  });

  it('preserves workflow-level parameter definitions', () => {
    const result = safeValidateWorkflow({
      id: 'w1',
      nodes: [],
      edges: [],
      parameters: [
        {
          name: 'sample_id',
          type: 'STRING',
          required: true,
          default: 'S1',
          value: 'S2',
          description: 'Sample identifier',
        },
      ],
    });

    expect(result.ok).toBe(true);
    if (result.ok) {
      expect(result.value.parameters).toEqual([
        {
          name: 'sample_id',
          type: 'STRING',
          required: true,
          default: 'S1',
          value: 'S2',
          description: 'Sample identifier',
        },
      ]);
    }
  });

  it('rejects malformed workflow-level parameter definitions', () => {
    const result = safeValidateWorkflow({
      id: 'w1',
      nodes: [],
      edges: [],
      parameters: [
        { name: '', type: 'STRING' },
        { name: 'threshold', type: '' },
        'sample_id',
      ],
    });

    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.error.path).toBe('workflow.parameters[0].name');
    }
  });

  it('rejects duplicate workflow-level parameter names', () => {
    const result = safeValidateWorkflow({
      id: 'w1',
      nodes: [],
      edges: [],
      parameters: [
        { name: 'sample_id', type: 'STRING' },
        { name: 'sample_id', type: 'STRING' },
      ],
    });

    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.error.path).toBe('workflow.parameters[1].name');
    }
  });
});
