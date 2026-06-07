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

describe('App view command copy i18n', () => {
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

  it('returns view command labels and descriptions from the active locale', async () => {
    const { default: i18n, setLanguage } = await import('../i18n');

    await setLanguage('es');

    expect(i18n.t('commandPalette.groups.view')).toBe('Vista');
    expect(i18n.t('commandPalette.commands.view.enterFocusMode')).toBe('Entrar en modo enfoque');
    expect(i18n.t('commandPalette.commands.view.exitFocusMode')).toBe('Salir del modo enfoque');
    expect(i18n.t('commandPalette.commands.view.focusModeDescription')).toBe('Ocultar la interfaz y maximizar el lienzo');
    expect(i18n.t('commandPalette.commands.view.fitAll')).toBe('Ajustar todos los nodos');
    expect(i18n.t('commandPalette.commands.view.fitAllDescription')).toBe('Encuadrar cada nodo del flujo de trabajo actual');
    expect(i18n.t('commandPalette.commands.view.fitAllDescription')).not.toBe('Encuadrar cada nodo del workflow actual');
    expect(i18n.t('commandPalette.commands.view.fitSelection')).toBe('Ajustar seleccion');
    expect(i18n.t('commandPalette.commands.view.fitSelectionDescription')).toBe('Encuadrar solo los nodos seleccionados');
    expect(i18n.t('commandPalette.commands.view.toggleMinimap')).toBe('Alternar minimapa');
    expect(i18n.t('commandPalette.commands.view.toggleLinks')).toBe('Alternar visibilidad de enlaces');
    expect(i18n.t('commandPalette.commands.view.toggleSnapGrid')).toBe('Alternar ajuste a cuadricula');
    expect(i18n.t('commandPalette.commands.view.toggleLockViewport')).toBe('Alternar bloqueo de vista');
    expect(i18n.t('canvas.selectNodeFirst')).toBe('Selecciona un nodo primero');
  });

  it('keeps App view command copy behind i18n keys', () => {
    const appSource = readFileSync(resolve(__dirname, '../App.tsx'), 'utf8');

    [
      'commandPalette.groups.view',
      'commandPalette.commands.view.enterFocusMode',
      'commandPalette.commands.view.exitFocusMode',
      'commandPalette.commands.view.focusModeDescription',
      'commandPalette.commands.view.fitAll',
      'commandPalette.commands.view.fitAllDescription',
      'commandPalette.commands.view.fitSelection',
      'commandPalette.commands.view.fitSelectionDescription',
      'commandPalette.commands.view.toggleMinimap',
      'commandPalette.commands.view.toggleLinks',
      'commandPalette.commands.view.toggleSnapGrid',
      'commandPalette.commands.view.toggleLockViewport',
      'canvas.selectNodeFirst',
    ].forEach(key => expect(appSource).toContain(key));

    [
      "'Exit focus mode'",
      "'Enter focus mode'",
      "description: 'Hide chrome and maximize the canvas'",
      "label: 'Fit all nodes'",
      "description: 'Frame every node in the current workflow'",
      "label: 'Fit selection'",
      "description: 'Frame only selected nodes'",
      "toast.info('Select a node first')",
      "label: 'Toggle minimap'",
      "label: 'Toggle link visibility'",
      "label: 'Toggle snap-to-grid'",
      "label: 'Toggle viewport lock'",
    ].forEach(text => expect(appSource).not.toContain(text));
  });
});
