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

describe('App workflow tab command copy i18n', () => {
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

  it('returns workflow tab and batch command labels from the active locale', async () => {
    const { default: i18n, setLanguage } = await import('../i18n');

    await setLanguage('es');

    expect(i18n.t('commandPalette.groups.workflow')).toBe('Workflow');
    expect(i18n.t('commandPalette.commands.workflow.newTab')).toBe('Nueva pestana de workflow');
    expect(i18n.t('commandPalette.commands.workflow.closeTab')).toBe('Cerrar pestana de workflow actual');
    expect(i18n.t('workflowTabs.duplicateCurrent')).toBe('Duplicar pestana de workflow actual');
    expect(i18n.t('commandPalette.commands.workflow.batchSheet')).toBe('Lote desde hoja de muestras...');
    expect(i18n.t('commandPalette.commands.workflow.batchSheetDescription')).toBe('Encolar una ejecucion por cada fila CSV/TSV');
  });

  it('keeps App workflow tab command copy behind i18n keys', () => {
    const appSource = readFileSync(resolve(__dirname, '../App.tsx'), 'utf8');

    [
      'commandPalette.commands.workflow.newTab',
      'commandPalette.commands.workflow.closeTab',
      'workflowTabs.duplicateCurrent',
      'commandPalette.commands.workflow.batchSheet',
      'commandPalette.commands.workflow.batchSheetDescription',
      'commandPalette.groups.workflow',
    ].forEach(key => expect(appSource).toContain(key));

    [
      "label: 'New workflow tab'",
      "label: 'Close current workflow tab'",
      "label: 'Batch from sample sheet...'",
      "description: 'Queue one run per CSV/TSV row'",
    ].forEach(text => expect(appSource).not.toContain(text));
  });
});
