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

describe('App workflow file and node search command copy i18n', () => {
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

  it('returns workflow import/export and node search command copy from the active locale', async () => {
    const { default: i18n, setLanguage } = await import('../i18n');

    await setLanguage('es');

    expect(i18n.t('commandPalette.groups.panels')).toBe('Paneles');
    expect(i18n.t('commandPalette.commands.workflow.export')).toBe('Exportar flujo de trabajo');
    expect(i18n.t('commandPalette.commands.workflow.import')).toBe('Importar flujo de trabajo');
    expect(i18n.t('commandPalette.commands.workflow.export')).not.toBe('Exportar workflow');
    expect(i18n.t('commandPalette.commands.workflow.import')).not.toBe('Importar workflow');
    expect(i18n.t('commandPalette.commands.nodes.search')).toBe('Buscar nodos');
    expect(i18n.t('commandPalette.commands.nodes.searchDescription')).toBe('Abrir la biblioteca difusa de nodos');
  });

  it('keeps App workflow import/export and node search copy behind i18n keys', () => {
    const appSource = readFileSync(resolve(__dirname, '../App.tsx'), 'utf8');

    [
      'commandPalette.groups.panels',
      'commandPalette.commands.workflow.export',
      'commandPalette.commands.workflow.import',
      'commandPalette.commands.nodes.search',
      'commandPalette.commands.nodes.searchDescription',
    ].forEach(key => expect(appSource).toContain(key));

    [
      "label: 'Export workflow'",
      "label: 'Import workflow'",
      "label: 'Search nodes'",
      "description: 'Open the fuzzy node library'",
    ].forEach(text => expect(appSource).not.toContain(text));
  });
});
