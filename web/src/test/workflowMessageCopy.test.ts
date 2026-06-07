import { act, renderHook } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import type { LogEntry, RunRecord } from '../types';

const apiMocks = vi.hoisted(() => ({
  apiGet: vi.fn(),
}));

vi.mock('../api/client', () => apiMocks);

const notificationMocks = vi.hoisted(() => ({
  toast: {
    error: vi.fn(),
  },
}));

vi.mock('../state/notifications', () => notificationMocks);

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

describe('Workflow message copy i18n', () => {
  beforeEach(() => {
    storage.clear();
    apiMocks.apiGet.mockReset();
    notificationMocks.toast.error.mockReset();
    vi.stubGlobal('localStorage', localStorageStub);
  });

  afterEach(async () => {
    const { setLanguage } = await import('../i18n');
    await setLanguage('en');
    storage.clear();
    vi.unstubAllGlobals();
  });

  it('returns run-failure toast copy from the active locale', async () => {
    const { default: i18n, setLanguage } = await import('../i18n');

    await setLanguage('es');

    expect(i18n.t('console.actions.runFailedTitle')).toBe('Ejecucion fallida');
    expect(i18n.t('console.actions.workflowFallback')).toBe('Workflow');
    expect(i18n.t('console.actions.consoleDetailsFallback')).toBe('consulta la consola para mas detalles');
    expect(i18n.t('console.actions.runFailedMessage', {
      name: 'RNA-seq',
      detail: 'consulta la consola para mas detalles',
    })).toBe('RNA-seq - consulta la consola para mas detalles');
  });

  it('logs queue errors and interruptions from the active locale', async () => {
    const { setLanguage } = await import('../i18n');
    const { useWorkflowMessages } = await import('../hooks/workflow/useWorkflowMessages');
    const logs: LogEntry[] = [];
    let handler: ((msg: unknown) => void) | undefined;
    const setRuns = vi.fn();

    await setLanguage('es');

    renderHook(() => useWorkflowMessages({
      onMessage: next => {
        handler = next;
        return () => {
          handler = undefined;
        };
      },
      addLog: entry => logs.push(entry),
      runs: [{
        run_id: 'run-1',
        status: 'running',
        workflow_name: 'RNA-seq',
        node_statuses: [],
        node_outputs: {},
        execution_plan: [],
        previews: {},
        artifacts: {},
      } as RunRecord],
      updateRun: vi.fn(),
      setRuns,
      updateNodeRunStatus: vi.fn(),
      recordNodeStart: vi.fn(),
      clearNodeRunProgress: vi.fn(),
    }));

    expect(handler).toBeDefined();

    act(() => {
      handler?.({
        type: 'queue_error',
        data: {
          run_id: 'run-1',
          error: 'boom',
          timestamp: '2026-06-07T05:00:00.000Z',
        },
      });
      handler?.({
        type: 'queue_interrupt',
        data: {
          run_id: 'run-1',
          timestamp: '2026-06-07T05:00:01.000Z',
        },
      });
    });

    expect(logs.map(log => log.message)).toContain('Error de ejecucion: boom');
    expect(logs.map(log => log.message)).toContain('Ejecucion interrumpida');
    expect(logs.map(log => log.message)).not.toContain('Run error: boom');
    expect(logs.map(log => log.message)).not.toContain('Run interrupted');
    expect(setRuns).toHaveBeenCalled();
  });

  it('keeps workflow failure toast copy behind i18n keys', () => {
    const source = readFileSync(resolve(__dirname, '../hooks/workflow/useWorkflowMessages.ts'), 'utf8');

    expect(source).toContain('console.actions.runFailedTitle');
    expect(source).toContain('console.actions.runFailedMessage');
    expect(source).toContain('console.actions.consoleDetailsFallback');
    [
      "'Run failed'",
      "'Workflow'",
      'see the console for details',
    ].forEach(text => {
      expect(source).not.toContain(text);
    });
  });
});
