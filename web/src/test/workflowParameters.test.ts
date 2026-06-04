import { describe, expect, it, vi } from 'vitest';
import {
  coerceWorkflowParameterInput,
  promptWorkflowRunParameters,
  workflowParameterInitialValue,
} from '../utils/workflowParameters';
import type { WorkflowParameter } from '../types';

describe('workflow parameter run prompts', () => {
  it('uses stored values as prompt defaults and coerces submitted values', async () => {
    const parameters: WorkflowParameter[] = [
      { name: 'sample_id', type: 'STRING', value: 'S1' },
      { name: 'threads', type: 'INT', default: 4 },
      { name: 'dry_run', type: 'BOOLEAN', default: false },
      { name: 'thresholds', type: 'JSON', default: { min: 0.2 } },
    ];
    const prompt = vi.fn()
      .mockResolvedValueOnce('S2')
      .mockResolvedValueOnce('8')
      .mockResolvedValueOnce('true')
      .mockResolvedValueOnce('{"min":0.8}');

    const overrides = await promptWorkflowRunParameters(parameters, prompt);

    expect(overrides).toEqual({
      sample_id: 'S2',
      threads: 8,
      dry_run: true,
      thresholds: { min: 0.8 },
    });
    expect(prompt.mock.calls.map(([options]) => options.defaultValue)).toEqual([
      'S1',
      '4',
      'false',
      '{"min":0.2}',
    ]);
  });

  it('returns null and stops prompting when the user cancels', async () => {
    const prompt = vi.fn().mockResolvedValueOnce('S1').mockResolvedValueOnce(null);

    const overrides = await promptWorkflowRunParameters([
      { name: 'sample_id', type: 'STRING' },
      { name: 'threads', type: 'INT' },
      { name: 'dry_run', type: 'BOOLEAN' },
    ], prompt);

    expect(overrides).toBeNull();
    expect(prompt).toHaveBeenCalledTimes(2);
  });

  it('omits blank optional values but rejects blank required numeric values', () => {
    expect(coerceWorkflowParameterInput({ name: 'optional_threads', type: 'INT' }, '')).toBeUndefined();

    expect(() => coerceWorkflowParameterInput(
      { name: 'threads', type: 'INT', required: true },
      '',
    )).toThrow("Parameter 'threads' requires an integer");
  });

  it('serializes initial values for prompt defaults', () => {
    expect(workflowParameterInitialValue({ name: 'payload', type: 'JSON', value: { a: 1 } })).toBe('{"a":1}');
    expect(workflowParameterInitialValue({ name: 'enabled', type: 'BOOLEAN', default: true })).toBe('true');
    expect(workflowParameterInitialValue({ name: 'missing', type: 'STRING' })).toBe('');
  });
});
