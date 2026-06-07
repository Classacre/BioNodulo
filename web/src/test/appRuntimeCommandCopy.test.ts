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

describe('App runtime command copy i18n', () => {
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

  it('returns runtime command labels and cache feedback from the active locale', async () => {
    const { default: i18n, setLanguage } = await import('../i18n');

    await setLanguage('es');

    expect(i18n.t('commandPalette.groups.workflow')).toBe('Workflow');
    expect(i18n.t('commandPalette.groups.tools')).toBe('Herramientas');
    expect(i18n.t('commandPalette.commands.cache.toggle')).toBe('Alternar cache de ejecucion');
    expect(i18n.t('commandPalette.commands.cache.clear')).toBe('Limpiar cache de ejecucion');
    expect(i18n.t('settings.cache.clearedTitle')).toBe('Cache limpiada');
    expect(i18n.t('settings.cache.entriesDeleted', { count: 1 })).toBe('1 entrada eliminada');
    expect(i18n.t('settings.cache.clearFailed')).toBe('No se pudo limpiar la cache');
    expect(i18n.t('commandPalette.commands.queue.clear')).toBe('Limpiar cola pendiente');
    expect(i18n.t('commandPalette.commands.logs.clear')).toBe('Limpiar registros de consola');
    expect(i18n.t('commandPalette.commands.help.gettingStarted')).toBe('Abrir primeros pasos');
    expect(i18n.t('commandPalette.commands.help.shortcutsAlias')).toBe('Abrir atajos de teclado (alias)');
  });

  it('keeps App runtime command copy behind i18n keys', () => {
    const appSource = readFileSync(resolve(__dirname, '../App.tsx'), 'utf8');

    [
      'commandPalette.commands.cache.toggle',
      'commandPalette.commands.cache.clear',
      'settings.cache.clearedTitle',
      'settings.cache.entriesDeleted',
      'settings.cache.clearFailed',
      'commandPalette.commands.queue.clear',
      'commandPalette.commands.logs.clear',
      'commandPalette.commands.help.gettingStarted',
      'commandPalette.commands.help.shortcutsAlias',
      'commandPalette.groups.workflow',
      'commandPalette.groups.tools',
    ].forEach(key => expect(appSource).toContain(key));

    [
      "label: 'Toggle execution cache'",
      "label: 'Clear execution cache'",
      "toast.success('Cache cleared'",
      '`${data.entries_deleted || 0} entries`',
      "toast.error('Could not clear cache'",
      "label: 'Clear pending queue'",
      "label: 'Clear console logs'",
      "label: 'Open Getting Started'",
      "label: 'Open keyboard shortcuts (alias)'",
    ].forEach(text => expect(appSource).not.toContain(text));
  });
});
