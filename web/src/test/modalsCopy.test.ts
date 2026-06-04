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

describe('Modals shell copy i18n', () => {
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

  it('returns lazy-loading labels and bulk-apply toast copy from the active locale', async () => {
    const { default: i18n, setLanguage } = await import('../i18n');

    await setLanguage('es');

    expect(i18n.t('outputDiff.loading')).toBe('Cargando comparacion de ejecuciones');
    expect(i18n.t('doctor.loading')).toBe('Cargando doctor');
    expect(i18n.t('paramBulk.loading')).toBe('Cargando editor masivo');
    expect(i18n.t('paramBulk.appliedTitle')).toBe('Edicion masiva aplicada');
    expect(i18n.t('paramBulk.appliedParamCount', { count: 1 })).toBe('1 parametro');
    expect(i18n.t('paramBulk.appliedParamCount', { count: 2 })).toBe('2 parametros');
    expect(i18n.t('paramBulk.appliedNodeCount', { count: 1 })).toBe('1 nodo');
    expect(i18n.t('paramBulk.appliedNodeCount', { count: 3 })).toBe('3 nodos');
    expect(i18n.t('paramBulk.appliedMessage', { params: '2 parametros', nodes: '3 nodos' })).toBe('2 parametros -> 3 nodos');
  });

  it('keeps modal shell spinner and bulk toast copy behind i18n keys', () => {
    const source = readFileSync(resolve(__dirname, '../components/modals/Modals.tsx'), 'utf8');

    expect(source).toContain('outputDiff.loading');
    expect(source).toContain('paramBulk.appliedMessage');
    [
      'Loading run diff',
      'Loading doctor',
      'Loading bulk editor',
      'Bulk edit applied',
      '${changes.length} param',
      '${selectedNodes.length} node',
    ].forEach(text => expect(source).not.toContain(text));
  });
});
