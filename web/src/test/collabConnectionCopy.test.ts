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

describe('Collaboration connection copy i18n', () => {
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

  it('returns connection fallback errors from the active locale', async () => {
    const { default: i18n, setLanguage } = await import('../i18n');

    await setLanguage('es');

    expect(i18n.t('collab.connectionForbidden')).toBe('Acceso denegado');
    expect(i18n.t('collab.connectionUnauthorized')).toBe('No autorizado');
    expect(i18n.t('collab.connectionError')).toBe('Error de conexion WebSocket');
  });

  it('keeps useCollab connection fallback errors behind i18n keys', () => {
    const source = readFileSync(resolve(__dirname, '../collab/useCollab.ts'), 'utf8');

    expect(source).toContain('collab.connectionForbidden');
    expect(source).toContain('collab.connectionUnauthorized');
    expect(source).toContain('collab.connectionError');
    [
      "'Forbidden'",
      "'Unauthorized'",
      "'WebSocket connection error'",
    ].forEach(text => {
      expect(source).not.toContain(text);
    });
  });
});
