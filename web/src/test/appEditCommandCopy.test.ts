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

describe('App edit command copy i18n', () => {
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

  it('returns edit command labels and descriptions from the active locale', async () => {
    const { default: i18n, setLanguage } = await import('../i18n');

    await setLanguage('es');

    expect(i18n.t('commandPalette.groups.edit')).toBe('Editar');
    expect(i18n.t('commandPalette.commands.edit.undo')).toBe('Deshacer');
    expect(i18n.t('commandPalette.commands.edit.redo')).toBe('Rehacer');
    expect(i18n.t('commandPalette.commands.edit.autoLayout')).toBe('Autoordenar (nodos seleccionados)');
    expect(i18n.t('commandPalette.commands.edit.autoLayoutDescription')).toBe(
      'Organizar nodos seleccionados (o todos los nodos) en columnas topologicas',
    );
  });

  it('keeps App edit command copy behind i18n keys', () => {
    const appSource = readFileSync(resolve(__dirname, '../App.tsx'), 'utf8');

    [
      'commandPalette.groups.edit',
      'commandPalette.commands.edit.undo',
      'commandPalette.commands.edit.redo',
      'commandPalette.commands.edit.autoLayout',
      'commandPalette.commands.edit.autoLayoutDescription',
    ].forEach(key => expect(appSource).toContain(key));

    [
      "label: 'Undo'",
      "label: 'Redo'",
      "label: 'Auto-layout (selected nodes)'",
      "description: 'Arrange selected nodes (or all nodes) in topological columns'",
    ].forEach(text => expect(appSource).not.toContain(text));
  });
});
