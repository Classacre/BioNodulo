import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { RunRecord } from '../types';

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

function runRecord(partial: Partial<RunRecord> & Pick<RunRecord, 'run_id'>): RunRecord {
  return {
    run_id: partial.run_id,
    status: 'pending',
    workflow_name: '',
    node_statuses: [],
    node_outputs: {},
    execution_plan: [],
    previews: {},
    artifacts: {},
    ...partial,
  };
}

describe('console action copy i18n', () => {
  beforeEach(() => {
    storage.clear();
    vi.stubGlobal('localStorage', localStorageStub);
  });

  afterEach(async () => {
    const { setLanguage } = await import('../i18n');
    await setLanguage('en');
    storage.clear();
    vi.unstubAllGlobals();
  });

  it('returns queue and history action copy from the active locale', async () => {
    const { default: i18n, setLanguage } = await import('../i18n');
    const { makeConsoleActionCopy } = await import('../utils/consoleActionCopy');

    await setLanguage('es');

    const copy = makeConsoleActionCopy(i18n.t);
    const namedRun = runRecord({ run_id: 'run-1', workflow_name: 'RNA-seq' });
    const unnamedRun = runRecord({ run_id: 'run-2' });

    expect(copy.cancelRunDialog(namedRun)).toMatchObject({
      title: 'Cancelar ejecucion?',
      message: 'Cancelar RNA-seq?',
      confirmLabel: 'Cancelar ejecucion',
      tone: 'danger',
    });
    expect(copy.clearQueueDialog()).toMatchObject({
      title: 'Limpiar cola?',
      message: 'Quitar todas las ejecuciones pendientes de la cola?',
      confirmLabel: 'Limpiar cola',
      tone: 'warning',
    });
    expect(copy.clearHistoryDialog()).toMatchObject({
      title: 'Limpiar historial?',
      message: 'Quitar todas las ejecuciones completadas del historial? Esta accion no se puede deshacer.',
      confirmLabel: 'Limpiar historial',
      tone: 'warning',
    });
    expect(copy.retryWorkflowName(unnamedRun)).toBe('Flujo de trabajo sin titulo (reintento)');
    expect(copy.retryWorkflowName(unnamedRun)).not.toBe('Workflow sin titulo (reintento)');
    expect(copy.loadedRunWorkflowName(namedRun)).toBe('RNA-seq run-1');
    expect(copy.loadedRunWorkflowName(unnamedRun)).toBe('Ejecucion run-2');
    expect(copy.toast.workflowLoadedFromRun).toBe('Flujo de trabajo cargado desde la ejecucion');
    expect(copy.toast.workflowLoadedFromRun).not.toBe('Workflow cargado desde la ejecucion');
    expect(copy.toast.retryQueued).toBe('Reintento en cola');
    expect(copy.toast.queueCleared).toBe('Cola limpiada');
    expect(copy.toast.historyCleared).toBe('Historial limpiado');
    expect(copy.error.noRunWorkflowSnapshot).toBe('La ejecucion no tiene una instantanea de flujo de trabajo asociada');
    expect(copy.error.noRunWorkflowSnapshot).not.toBe('La ejecucion no tiene una instantanea de workflow asociada');
    expect(copy.error.couldNotLoadWorkflow).toBe('No se pudo cargar el flujo de trabajo');
    expect(copy.error.couldNotLoadWorkflow).not.toBe('No se pudo cargar el workflow');
    expect(copy.error.couldNotDeleteRun).toBe('No se pudo eliminar la ejecucion');
  });
});
