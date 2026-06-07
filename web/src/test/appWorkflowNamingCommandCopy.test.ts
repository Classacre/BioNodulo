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

describe('App workflow naming command copy i18n', () => {
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

  it('returns workflow auto-name command labels and feedback from the active locale', async () => {
    const { default: i18n, setLanguage } = await import('../i18n');

    await setLanguage('es');

    expect(i18n.t('commandPalette.commands.workflow.autoName')).toBe('Sugerir nombre de workflow');
    expect(i18n.t('commandPalette.commands.workflow.autoNameDescription')).toBe('Cambiar el nombre de la pestana actual segun las herramientas dominantes del workflow');
    expect(i18n.t('workflowNaming.toast.needsNodes')).toBe('Agrega algunos nodos reales antes de nombrar automaticamente');
    expect(i18n.t('workflowNaming.toast.renamed')).toBe('Workflow renombrado');
  });

  it('keeps App workflow auto-name command copy behind i18n keys', () => {
    const appSource = readFileSync(resolve(__dirname, '../App.tsx'), 'utf8');

    [
      'commandPalette.commands.workflow.autoName',
      'commandPalette.commands.workflow.autoNameDescription',
      'workflowNaming.toast.needsNodes',
      'workflowNaming.toast.renamed',
    ].forEach(key => expect(appSource).toContain(key));

    [
      "label: 'Suggest workflow name'",
      "description: 'Rename the current tab based on the dominant tools in the workflow'",
      "toast.info('Add a few real nodes before auto-naming')",
      "toast.success('Workflow renamed'",
    ].forEach(text => expect(appSource).not.toContain(text));
  });
});
