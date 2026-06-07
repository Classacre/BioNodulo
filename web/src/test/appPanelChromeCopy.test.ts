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

describe('App panel chrome copy i18n', () => {
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

  it('returns panel docking, loading, and resize copy from the active locale', async () => {
    const { default: i18n, setLanguage } = await import('../i18n');

    await setLanguage('es');

    expect(i18n.t('panels.dockLeftDropzone')).toBe('Acoplar a la izquierda');
    expect(i18n.t('panels.dockRightDropzone')).toBe('Acoplar a la derecha');
    expect(i18n.t('panels.dockToLeftSide')).toBe('Acoplar al lado izquierdo');
    expect(i18n.t('panels.dockToRightSide')).toBe('Acoplar al lado derecho');
    expect(i18n.t('panels.moveToLeftSide')).toBe('Mover panel al lado izquierdo');
    expect(i18n.t('panels.moveToRightSide')).toBe('Mover panel al lado derecho');
    expect(i18n.t('panels.dockPanel')).toBe('Acoplar panel');
    expect(i18n.t('panels.floatPanel')).toBe('Hacer flotante el panel');
    expect(i18n.t('panels.loadingPanel', { name: i18n.t('panels.nodes') })).toBe('Cargando Nodos...');
    expect(i18n.t('panels.resizePanel', { name: i18n.t('panels.nodes') })).toBe('Redimensionar panel Nodos');
  });

  it('keeps App panel chrome copy behind i18n keys', () => {
    const appSource = readFileSync(resolve(__dirname, '../App.tsx'), 'utf8');

    [
      'panels.dockLeftDropzone',
      'panels.dockRightDropzone',
      'panels.dockToLeftSide',
      'panels.dockToRightSide',
      'panels.moveToLeftSide',
      'panels.moveToRightSide',
      'panels.dockPanel',
      'panels.floatPanel',
      'panels.loadingPanel',
      'panels.resizePanel',
    ].forEach(key => expect(appSource).toContain(key));

    [
      '<span>Dock left</span>',
      '<span>Dock right</span>',
      "'Dock to left side'",
      "'Dock to right side'",
      "'Move panel to left side'",
      "'Move panel to right side'",
      "'Dock panel'",
      "'Float panel'",
      '`Loading ${tab}',
      '`Resize ${tab} panel`',
    ].forEach(text => expect(appSource).not.toContain(text));
  });
});
