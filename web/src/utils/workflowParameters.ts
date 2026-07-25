import type { ReactNode } from 'react';
import i18n from '../i18n';
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
  if (['true', '1', 'yes', 'on', 'verdadero'].includes(normalized)) return true;
  if (['false', '0', 'no', 'off', 'falso'].includes(normalized)) return false;
  throw new Error('Expected true or false');
}

type ParameterErrorKey =
  | 'integerRequired'
  | 'numberRequired'
  | 'booleanRequired'
  | 'jsonRequired'
  | 'validJsonRequired'
  | 'parameterRequired';

function parameterError(parameter: WorkflowParameter, key: ParameterErrorKey): string {
  return String(i18n.t(`parameters.${key}`, { name: parameter.name }));
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
    if (value === '') throw new Error(parameterError(parameter, 'integerRequired'));
    const parsed = Number.parseInt(value, 10);
    if (!Number.isFinite(parsed) || String(parsed) !== value) {
      throw new Error(parameterError(parameter, 'integerRequired'));
    }
    return parsed;
  }
  if (type === 'FLOAT' || type === 'NUMBER') {
    if (value === '') throw new Error(parameterError(parameter, 'numberRequired'));
    const parsed = Number(value);
    if (!Number.isFinite(parsed)) {
      throw new Error(parameterError(parameter, 'numberRequired'));
    }
    return parsed;
  }
  if (type === 'BOOLEAN' || type === 'BOOL') {
    if (value === '') throw new Error(parameterError(parameter, 'booleanRequired'));
    try {
      return booleanFromString(value);
    } catch (err) {
      void err;
      throw new Error(parameterError(parameter, 'booleanRequired'));
    }
  }
  if (type === 'JSON') {
    if (value === '') throw new Error(parameterError(parameter, 'jsonRequired'));
    try {
      return JSON.parse(value);
    } catch (err) {
      void err;
      throw new Error(parameterError(parameter, 'validJsonRequired'));
    }
  }
  if (type.includes('LIST')) {
    if (value === '') {
      throw new Error(parameterError(parameter, 'parameterRequired'));
    }
    if (value.startsWith('[')) {
      try {
        const parsed = JSON.parse(value) as unknown;
        if (!Array.isArray(parsed)) throw new Error('not a list');
        return parsed;
      } catch (err) {
        void err;
        throw new Error(parameterError(parameter, 'validJsonRequired'));
      }
    }
    return rawValue
      .split(/\r?\n|,/)
      .map(item => item.trim())
      .filter(Boolean);
  }
  if (value === '' && parameter.required) {
    throw new Error(parameterError(parameter, 'parameterRequired'));
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
      title: copy.title ?? i18n.t('parameters.runParameterPromptTitle'),
      message: copy.message?.(parameter) ?? `${parameter.name} (${normalizedType(parameter)})`,
      inputLabel: parameter.name,
      defaultValue: workflowParameterInitialValue(parameter),
      placeholder: parameter.description,
      confirmLabel: copy.confirmLabel ?? i18n.t('parameters.runPromptConfirm'),
      cancelLabel: copy.cancelLabel ?? i18n.t('parameters.runPromptCancel'),
    });
    if (response === null) return null;
    const value = coerceWorkflowParameterInput(parameter, response);
    if (value !== undefined) {
      overrides[parameter.name] = value;
    }
  }
  return overrides;
}
