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

describe('App bulk parameter command copy i18n', () => {
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

  it('returns bulk parameter command labels and feedback from the active locale', async () => {
    const { default: i18n, setLanguage } = await import('../i18n');

    await setLanguage('es');

    expect(i18n.t('commandPalette.groups.edit')).toBe('Editar');
    expect(i18n.t('commandPalette.commands.edit.bulkParams')).toBe('Editar parametros en masa (seleccion)...');
    expect(i18n.t('commandPalette.commands.edit.bulkParamsDescription')).toBe('Editar parametros compartidos por todos los nodos seleccionados a la vez');
    expect(i18n.t('paramBulk.selectAtLeastTwo')).toBe('Selecciona 2+ nodos para editar en masa sus parametros compartidos');
  });

  it('keeps App bulk parameter command copy behind i18n keys', () => {
    const appSource = readFileSync(resolve(__dirname, '../App.tsx'), 'utf8');

    [
      'commandPalette.groups.edit',
      'commandPalette.commands.edit.bulkParams',
      'commandPalette.commands.edit.bulkParamsDescription',
      'paramBulk.selectAtLeastTwo',
    ].forEach(key => expect(appSource).toContain(key));

    [
      "label: 'Bulk edit parameters (selection)…'",
      "description: 'Edit parameters shared across all selected nodes at once'",
      "toast.info('Select 2+ nodes to bulk-edit their shared parameters')",
    ].forEach(text => expect(appSource).not.toContain(text));
  });
});
