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

  it('returns workflow search, notes, accessibility, and toast chrome from the active locale', async () => {
    const { default: i18n, setLanguage } = await import('../i18n');

    await setLanguage('es');

    expect(i18n.t('search.workflowSearch')).toBe('Buscar en flujo de trabajo');
    expect(i18n.t('search.workflowSearchPlaceholder')).toBe('Buscar nodo por nombre, tipo o parametro');
    expect(i18n.t('search.noResults')).toBe('No hay nodos coincidentes');
    expect(i18n.t('search.matchCount', { count: 1 })).toBe('1 coincidencia');
    expect(i18n.t('search.matchCount', { count: 3 })).toBe('3 coincidencias');
    expect(i18n.t('search.nextMatch')).toBe('Siguiente coincidencia');
    expect(i18n.t('search.previousMatch')).toBe('Coincidencia anterior');
    expect(i18n.t('drawerNotes.placeholder')).toBe('Agregar notas sobre este flujo de trabajo...');
    expect(i18n.t('drawerNotes.saveHint')).toBe('Las notas se guardan con el flujo de trabajo');
    expect(i18n.t('ariaLabels.closeDialog')).toBe('Cerrar dialogo');
    expect(i18n.t('ariaLabels.filterColumn')).toBe('Filtrar columna');
    expect(i18n.t('ariaLabels.chooseColor')).toBe('Elegir color');
    expect(i18n.t('toasts.workflowSaved')).toBe('Flujo de trabajo guardado');
    expect(i18n.t('toasts.workflowSaveFailed')).toBe('No se pudo guardar el flujo de trabajo');
    expect(i18n.t('toasts.copiedToClipboard')).toBe('Copiado al portapapeles');
    expect(i18n.t('toasts.snapshotRestored')).toBe('Instantanea restaurada');
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
