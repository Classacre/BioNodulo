import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

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

describe('App run feedback copy i18n', () => {
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

  it('returns run feedback labels and log copy from the active locale', async () => {
    const { default: i18n, setLanguage } = await import('../i18n');

    await setLanguage('es');

    expect(i18n.t('console.actions.dryRunPreviewLog', {
      count: 1,
      nodeWord: i18n.t('console.nodesCount', { count: 1 }),
      plannedWord: i18n.t('console.actions.dryRunPreviewPlannedOne'),
    })).toBe('Vista previa sin ejecutar: 1 nodo planificado');
    expect(i18n.t('console.actions.dryRunPreviewPlannedMany')).toBe('planificados');
    expect(i18n.t('console.actions.dryRunPreviewGenerated')).toBe('Vista previa sin ejecutar generada');
    expect(i18n.t('console.actions.dryRunPreviewMessage')).toBe('Abre la consola para inspeccionar el plan de ejecucion.');
    expect(i18n.t('console.actions.runQueued')).toBe('Ejecucion en cola');
    expect(i18n.t('console.actions.runsQueued', { count: 3 })).toBe('3 ejecuciones en cola');
    expect(i18n.t('console.actions.runFailedLog', { message: 'boom' })).toBe('Ejecucion fallida: boom');
    expect(i18n.t('console.actions.sampleSheetRunsQueued', { count: 2 })).toBe('2 ejecuciones en cola desde hoja de muestras');
    expect(i18n.t('console.actions.sampleSheetBatchFailed')).toBe('Lote de hoja de muestras fallido');
    expect(i18n.t('console.actions.sampleSheetBatchFailedLog', { message: 'bad row' })).toBe('Lote de hoja de muestras fallido: bad row');
    expect(i18n.t('workflowNaming.selectionSuffix')).toBe('seleccion');
  });

  it('keeps App run feedback copy behind i18n keys', () => {
    const appSource = readFileSync(resolve(__dirname, '../App.tsx'), 'utf8');

    [
      'console.actions.dryRunPreviewLog',
      'console.actions.dryRunPreviewPlannedOne',
      'console.actions.dryRunPreviewPlannedMany',
      'console.actions.dryRunPreviewGenerated',
      'console.actions.dryRunPreviewMessage',
      'console.actions.runQueued',
      'console.actions.runsQueued',
      'console.actions.runFailedLog',
      'console.actions.sampleSheetRunsQueued',
      'console.actions.sampleSheetBatchFailed',
      'console.actions.sampleSheetBatchFailedLog',
      'workflowNaming.selectionSuffix',
      'common.untitled',
      'console.nodesCount',
      'console.nodesCount_plural',
    ].forEach(key => expect(appSource).toContain(key));

    [
      'Dry run preview:',
      'Dry run preview generated',
      'Open the console to inspect the execution plan.',
      'Run queued',
      'runs queued',
      'Run failed:',
      'runs queued from sample sheet',
      'Sample sheet batch failed',
      "name: `${activeWorkflow.name || 'Untitled'} (selection)`",
      "workflow_name: result.workflow_name || `${activeWorkflow.name || 'Untitled'} (selection)`",
    ].forEach(text => expect(appSource).not.toContain(text));
  });
});
