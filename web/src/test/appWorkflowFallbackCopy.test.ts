import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

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

describe('App workflow fallback copy i18n', () => {
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

  it('returns workflow tab, import, and recent command copy from the active locale', async () => {
    const { default: i18n, setLanguage } = await import('../i18n');

    await setLanguage('es');

    expect(i18n.t('workflowTabs.duplicateName', { name: i18n.t('common.untitled') })).toBe('Sin titulo (copia)');
    expect(i18n.t('workflowTabs.duplicateCurrent')).toBe('Duplicar pestana de workflow actual');
    expect(i18n.t('workflowTabs.thisWorkflow')).toBe('este workflow');
    expect(i18n.t('workflowTabs.closeUnsavedTitle')).toBe('Cerrar pestana con cambios sin guardar?');
    expect(i18n.t('workflowTabs.closeUnsavedMessage', { name: 'RNA-seq' })).toBe('RNA-seq tiene cambios sin guardar. Cerrar de todos modos?');
    expect(i18n.t('workflowImport.importedFallbackName')).toBe('Workflow importado');
    expect(i18n.t('workflowImport.loadedFromUrl')).toBe('Workflow cargado desde URL');
    expect(i18n.t('workflowImport.untitledLower')).toBe('sin titulo');
    expect(i18n.t('commandPalette.openRecentWorkflow', { name: 'QC' })).toBe('Abrir reciente: QC');
    expect(i18n.t('commandPalette.recentWorkflowFallback')).toBe('workflow reciente');
  });

  it('keeps App workflow fallback strings behind i18n keys', () => {
    const appSource = readFileSync(resolve(__dirname, '../App.tsx'), 'utf8');

    expect(appSource).toContain('workflowTabs.duplicateName');
    [
      'Imported workflow',
      'Loaded workflow from URL',
      'Duplicate current workflow tab',
      'Open recent:',
      'recent workflow',
      'this workflow',
      'Close tab with unsaved changes?',
      'has unsaved changes. Close anyway?',
    ].forEach(text => {
      expect(appSource).not.toContain(text);
    });
  });
});
