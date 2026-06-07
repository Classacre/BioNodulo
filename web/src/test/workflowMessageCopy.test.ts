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

  it('logs workflow lifecycle events from the active locale', async () => {
    const { setLanguage } = await import('../i18n');
    const { useWorkflowMessages } = await import('../hooks/workflow/useWorkflowMessages');
    const logs: LogEntry[] = [];
    let handler: ((msg: unknown) => void) | undefined;

    await setLanguage('es');
    apiMocks.apiGet.mockResolvedValue({});

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
      setRuns: vi.fn(),
      updateNodeRunStatus: vi.fn(),
      recordNodeStart: vi.fn(),
      clearNodeRunProgress: vi.fn(),
    }));

    expect(handler).toBeDefined();

    act(() => {
      handler?.({
        type: 'start',
        data: {
          run_id: 'run-1',
          total_nodes: 3,
          timestamp: '2026-06-07T05:00:00.000Z',
        },
      });
      handler?.({
        type: 'node_start',
        data: {
          run_id: 'run-1',
          node_id: 'node-1',
          progress: '1/3',
          node_type: 'CsvReader',
          timestamp: '2026-06-07T05:00:01.000Z',
        },
      });
      handler?.({
        type: 'node_complete',
        data: {
          run_id: 'run-1',
          node_id: 'node-1',
          timestamp: '2026-06-07T05:00:02.000Z',
        },
      });
      handler?.({
        type: 'node_error',
        data: {
          run_id: 'run-1',
          node_id: 'node-2',
          error: 'boom',
          timestamp: '2026-06-07T05:00:03.000Z',
        },
      });
      handler?.({
        type: 'node_skip',
        data: {
          run_id: 'run-1',
          node_id: 'node-3',
          reason: 'upstream failed',
          timestamp: '2026-06-07T05:00:04.000Z',
        },
      });
      handler?.({
        type: 'node_bypass',
        data: {
          run_id: 'run-1',
          node_id: 'node-4',
          timestamp: '2026-06-07T05:00:05.000Z',
        },
      });
      handler?.({
        type: 'node_cache_hit',
        data: {
          run_id: 'run-1',
          node_id: 'node-5',
          timestamp: '2026-06-07T05:00:06.000Z',
        },
      });
      handler?.({
        type: 'complete',
        data: {
          run_id: 'run-1',
          status: 'completed',
          timestamp: '2026-06-07T05:00:07.000Z',
        },
      });
      handler?.({
        type: 'error',
        data: {
          run_id: 'run-1',
          message: 'engine stopped',
          timestamp: '2026-06-07T05:00:08.000Z',
        },
      });
      handler?.({
        type: 'cancelled',
        data: {
          run_id: 'run-1',
          timestamp: '2026-06-07T05:00:09.000Z',
        },
      });
      handler?.({
        type: 'queue_submit',
        data: {
          run_id: 'run-1',
          timestamp: '2026-06-07T05:00:10.000Z',
        },
      });
      handler?.({
        type: 'queue_start',
        data: {
          run_id: 'run-1',
          timestamp: '2026-06-07T05:00:11.000Z',
        },
      });
      handler?.({
        type: 'queue_finish',
        data: {
          run_id: 'run-1',
          status: 'completed',
          timestamp: '2026-06-07T05:00:12.000Z',
        },
      });
    });

    expect(logs.map(log => log.message)).toEqual(expect.arrayContaining([
      'Workflow iniciado (3 nodos)',
      'Nodo iniciado [1/3] CsvReader',
      'Nodo completado',
      'Error de nodo: boom',
      'Nodo omitido (upstream failed)',
      'Nodo omitido por bypass',
      'Resultado en cache - omitiendo ejecucion',
      'Workflow completado',
      'Error de workflow: engine stopped',
      'Workflow cancelado',
      'Ejecucion enviada',
      'Ejecucion iniciada',
      'Ejecucion terminada (completado)',
    ]));
    [
      'Workflow started (3 nodes)',
      'Node start [1/3] CsvReader',
      'Node completed',
      'Node error: boom',
      'Node skipped (upstream failed)',
      'Node bypassed',
      'Cache hit - skipping execution',
      'Workflow completed',
      'Workflow error: engine stopped',
      'Workflow cancelled',
      'Run submitted',
      'Run started',
      'Run finished (completed)',
    ].forEach(message => {
      expect(logs.map(log => log.message)).not.toContain(message);
    });
  });

  it('uses localized fallback copy for node errors without details', async () => {
    const { setLanguage } = await import('../i18n');
    const { useWorkflowMessages } = await import('../hooks/workflow/useWorkflowMessages');
    const logs: LogEntry[] = [];
    let handler: ((msg: unknown) => void) | undefined;
    const updateNodeRunStatus = vi.fn();

    await setLanguage('es');

    renderHook(() => useWorkflowMessages({
      onMessage: next => {
        handler = next;
        return () => {
          handler = undefined;
        };
      },
      addLog: entry => logs.push(entry),
      runs: [],
      updateRun: vi.fn(),
      setRuns: vi.fn(),
      updateNodeRunStatus,
      recordNodeStart: vi.fn(),
      clearNodeRunProgress: vi.fn(),
    }));

    expect(handler).toBeDefined();

    act(() => {
      handler?.({
        type: 'node_error',
        data: {
          run_id: 'run-1',
          node_id: 'node-2',
          timestamp: '2026-06-07T05:00:03.000Z',
        },
      });
    });

    expect(updateNodeRunStatus).toHaveBeenCalledWith('run-1', 'node-2', 'error', 'Error de nodo');
    expect(logs.map(log => log.message)).toContain('Error de nodo: Error de nodo');
    expect(logs.map(log => log.message)).not.toContain('Node error: Node error');
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

  it('keeps node error fallback copy behind i18n keys', () => {
    const source = readFileSync(resolve(__dirname, '../hooks/workflow/useWorkflowMessages.ts'), 'utf8');

    expect(source).toContain('console.actions.nodeErrorFallback');
    expect(source).not.toContain("'Node error'");
  });
});
