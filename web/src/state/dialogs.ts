import type { ReactNode } from 'react';
import { useSyncExternalStore } from 'react';

export type DialogTone = 'default' | 'danger' | 'warning' | 'success';
export type DialogKind = 'alert' | 'confirm' | 'prompt';

export interface DialogOptions {
  title?: ReactNode;
  message: ReactNode;
  confirmLabel?: string;
  cancelLabel?: string;
  tone?: DialogTone;
}

export interface PromptDialogOptions extends DialogOptions {
  defaultValue?: string;
  inputLabel?: string;
  placeholder?: string;
}

export interface DialogRequest extends Required<Pick<DialogOptions, 'message'>> {
  id: string;
  kind: DialogKind;
  title?: ReactNode;
  confirmLabel?: string;
  cancelLabel?: string;
  defaultValue?: string;
  inputLabel?: string;
  placeholder?: string;
  tone: DialogTone;
  resolve: (value: boolean | string | null) => void;
}

const listeners = new Set<() => void>();
let queue: DialogRequest[] = [];

function makeId() {
  if (typeof crypto !== 'undefined' && crypto.randomUUID) return crypto.randomUUID();
  return `dialog-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

function emit() {
  listeners.forEach(listener => listener());
}

function enqueueDialog(kind: 'alert' | 'confirm', input: string | DialogOptions): Promise<boolean> {
  const options: DialogOptions = typeof input === 'string' ? { message: input } : input;
  return new Promise(resolve => {
    queue = [
      ...queue,
      {
        id: makeId(),
        kind,
        title: options.title,
        message: options.message,
        confirmLabel: options.confirmLabel,
        cancelLabel: options.cancelLabel,
        tone: options.tone ?? 'default',
        resolve: value => resolve(Boolean(value)),
      },
    ];
    emit();
  });
}

function enqueuePrompt(input: string | PromptDialogOptions): Promise<string | null> {
  const options: PromptDialogOptions = typeof input === 'string' ? { message: input } : input;
  return new Promise(resolve => {
    queue = [
      ...queue,
      {
        id: makeId(),
        kind: 'prompt',
        title: options.title,
        message: options.message,
        confirmLabel: options.confirmLabel,
        cancelLabel: options.cancelLabel,
        defaultValue: options.defaultValue,
        inputLabel: options.inputLabel,
        placeholder: options.placeholder,
        tone: options.tone ?? 'default',
        resolve: value => resolve(typeof value === 'string' ? value : null),
      },
    ];
    emit();
  });
}

export async function alertDialog(input: string | DialogOptions): Promise<void> {
  await enqueueDialog('alert', input);
}

export function confirmDialog(input: string | DialogOptions): Promise<boolean> {
  return enqueueDialog('confirm', input);
}

export function promptDialog(input: string | PromptDialogOptions): Promise<string | null> {
  return enqueuePrompt(input);
}

export const alertAction = alertDialog;
export const confirmAction = confirmDialog;
export const promptAction = promptDialog;

export function resolveDialog(id: string, value: boolean | string | null): void {
  const request = queue.find(dialog => dialog.id === id);
  if (!request) return;

  queue = queue.filter(dialog => dialog.id !== id);
  request.resolve(value);
  emit();
}

export function dismissActiveDialog(): void {
  const active = queue[0];
  if (active) resolveDialog(active.id, false);
}

export function subscribeDialogs(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function getDialogSnapshot(): DialogRequest[] {
  return queue;
}

export function useDialogQueue(): DialogRequest[] {
  return useSyncExternalStore(subscribeDialogs, getDialogSnapshot, getDialogSnapshot);
}
