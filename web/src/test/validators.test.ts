import { describe, it, expect } from 'vitest';
import {
  ApiValidationError,
  safeValidateHostStatus,
  safeValidateHpcStatus,
  safeValidateRunRecord,
  safeValidateRunsList,
  safeValidateWorkflow,
  validateHostStatus,
  validateHpcStatus,
  validateRunRecord,
  validateRunsList,
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
      extra: 'ignored',
    });
    expect(r.run_id).toBe('r1');
    expect(r.status).toBe('completed');
  });

  it('throws on missing run_id', () => {
    const result = safeValidateRunRecord({ status: 'pending' });
    expect(result.ok).toBe(false);
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
