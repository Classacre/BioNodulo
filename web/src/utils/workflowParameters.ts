import type { ReactNode } from 'react';
import type { PromptDialogOptions } from '../state/dialogs';
import type { WorkflowParameter } from '../types';

type PromptFunction = (input: PromptDialogOptions) => Promise<string | null>;

function normalizedType(parameter: WorkflowParameter): string {
  return String(parameter.type || 'STRING').trim().toUpperCase();
}

function parameterValue(parameter: WorkflowParameter): unknown {
  if (parameter.value !== undefined) return parameter.value;
  return parameter.default;
}

function booleanFromString(value: string): boolean {
  const normalized = value.trim().toLowerCase();
  if (['true', '1', 'yes', 'on'].includes(normalized)) return true;
  if (['false', '0', 'no', 'off'].includes(normalized)) return false;
  throw new Error('Expected true or false');
}

export function workflowParameterInitialValue(parameter: WorkflowParameter): string {
  const value = parameterValue(parameter);
  if (value === undefined || value === null) return '';
  if (typeof value === 'object') return JSON.stringify(value);
  return String(value);
}

export function coerceWorkflowParameterInput(parameter: WorkflowParameter, rawValue: string): unknown {
  const value = rawValue.trim();
  if (value === '' && !parameter.required) return undefined;
  const type = normalizedType(parameter);

  if (type === 'INT' || type === 'INTEGER') {
    if (value === '') throw new Error(`Parameter '${parameter.name}' requires an integer`);
    const parsed = Number.parseInt(value, 10);
    if (!Number.isFinite(parsed) || String(parsed) !== value) {
      throw new Error(`Parameter '${parameter.name}' requires an integer`);
    }
    return parsed;
  }
  if (type === 'FLOAT' || type === 'NUMBER') {
    if (value === '') throw new Error(`Parameter '${parameter.name}' requires a number`);
    const parsed = Number(value);
    if (!Number.isFinite(parsed)) {
      throw new Error(`Parameter '${parameter.name}' requires a number`);
    }
    return parsed;
  }
  if (type === 'BOOLEAN' || type === 'BOOL') {
    if (value === '') throw new Error(`Parameter '${parameter.name}' requires true or false`);
    try {
      return booleanFromString(value);
    } catch (err) {
      void err;
      throw new Error(`Parameter '${parameter.name}' requires true or false`);
    }
  }
  if (type === 'JSON') {
    if (value === '') throw new Error(`Parameter '${parameter.name}' requires JSON`);
    try {
      return JSON.parse(value);
    } catch (err) {
      void err;
      throw new Error(`Parameter '${parameter.name}' requires valid JSON`);
    }
  }
  if (value === '' && parameter.required) {
    throw new Error(`Parameter '${parameter.name}' is required`);
  }
  return rawValue;
}

export async function promptWorkflowRunParameters(
  parameters: WorkflowParameter[] | undefined,
  prompt: PromptFunction,
  copy: {
    title?: ReactNode;
    message?: (parameter: WorkflowParameter) => ReactNode;
    confirmLabel?: string;
    cancelLabel?: string;
  } = {},
): Promise<Record<string, unknown> | null> {
  const overrides: Record<string, unknown> = {};
  for (const parameter of parameters ?? []) {
    const response = await prompt({
      title: copy.title ?? 'Workflow parameter',
      message: copy.message?.(parameter) ?? `${parameter.name} (${normalizedType(parameter)})`,
      inputLabel: parameter.name,
      defaultValue: workflowParameterInitialValue(parameter),
      placeholder: parameter.description,
      confirmLabel: copy.confirmLabel ?? 'Use value',
      cancelLabel: copy.cancelLabel ?? 'Cancel run',
    });
    if (response === null) return null;
    const value = coerceWorkflowParameterInput(parameter, response);
    if (value !== undefined) {
      overrides[parameter.name] = value;
    }
  }
  return overrides;
}
