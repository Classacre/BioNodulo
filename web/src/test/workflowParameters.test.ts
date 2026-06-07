import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import {
  coerceWorkflowParameterInput,
  promptWorkflowRunParameters,
  workflowParameterInitialValue,
} from '../utils/workflowParameters';
import type { WorkflowParameter } from '../types';

describe('workflow parameter run prompts', () => {
  beforeEach(() => {
    vi.stubGlobal('localStorage', {
      getItem: () => null,
      setItem: () => {},
    });
  });

  afterEach(async () => {
    const { setLanguage } = await import('../i18n');
    await setLanguage('en');
    vi.unstubAllGlobals();
  });

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

  it('uses locale copy for default prompts and validation errors', async () => {
    const { default: i18n, setLanguage } = await import('../i18n');
    await setLanguage('es');
    const prompt = vi.fn().mockResolvedValueOnce('7');

    await promptWorkflowRunParameters([{ name: 'threads', type: 'INT' }], prompt);

    expect(prompt.mock.calls[0][0].title).toBe('Parametro del flujo de trabajo');
    expect(prompt.mock.calls[0][0].title).not.toBe('Parametro del workflow');
    expect(prompt.mock.calls[0][0].confirmLabel).toBe('Usar valor');
    expect(prompt.mock.calls[0][0].cancelLabel).toBe('Cancelar ejecucion');
    expect(i18n.t('parameters.integerRequired', { name: 'threads' })).toBe("El parametro 'threads' requiere un entero");
    expect(() => coerceWorkflowParameterInput(
      { name: 'threads', type: 'INT', required: true },
      '',
    )).toThrow("El parametro 'threads' requiere un entero");
    expect(i18n.t('parameters.booleanRequired', { name: 'dry_run' })).toBe("El parametro 'dry_run' requiere verdadero o falso");
    expect(coerceWorkflowParameterInput({ name: 'dry_run', type: 'BOOLEAN' }, 'verdadero')).toBe(true);
    expect(coerceWorkflowParameterInput({ name: 'dry_run', type: 'BOOLEAN' }, 'falso')).toBe(false);
    expect(() => coerceWorkflowParameterInput(
      { name: 'dry_run', type: 'BOOLEAN', required: true },
      'maybe',
    )).toThrow("El parametro 'dry_run' requiere verdadero o falso");
  });

  it('keeps workflow parameter utility copy behind i18n keys', () => {
    const source = readFileSync(resolve(__dirname, '../utils/workflowParameters.ts'), 'utf8');

    [
      "Parameter '${parameter.name}' requires an integer",
      "Parameter '${parameter.name}' requires a number",
      "Parameter '${parameter.name}' requires true or false",
      "Parameter '${parameter.name}' requires JSON",
      "Parameter '${parameter.name}' requires valid JSON",
      "Parameter '${parameter.name}' is required",
      "'Workflow parameter'",
      "'Use value'",
      "'Cancel run'",
    ].forEach(text => expect(source).not.toContain(text));
  });
});
