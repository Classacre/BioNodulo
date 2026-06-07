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

describe('App validation feedback copy i18n', () => {
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

  it('returns validation and selected-run feedback from the active locale', async () => {
    const { default: i18n, setLanguage } = await import('../i18n');

    await setLanguage('es');

    expect(i18n.t('console.actions.validationFailed', { count: 2 })).toBe('Validacion fallida (2)');
    expect(i18n.t('console.actions.jumpToNode')).toBe('Saltar al nodo');
    expect(i18n.t('console.actions.selectedRunFailedLog', { message: 'boom' })).toBe('Ejecucion seleccionada fallida: boom');
  });

  it('keeps App validation feedback copy behind i18n keys', () => {
    const appSource = readFileSync(resolve(__dirname, '../App.tsx'), 'utf8');

    [
      'console.actions.validationFailed',
      'console.actions.jumpToNode',
      'console.actions.selectedRunFailedLog',
    ].forEach(key => expect(appSource).toContain(key));

    [
      'Validation failed (${v.errors.length})',
      "label: 'Jump to node'",
      'Selected run failed: ${msg}',
    ].forEach(text => expect(appSource).not.toContain(text));
  });
});
