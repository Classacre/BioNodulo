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

describe('WorkflowCanvas menu and hover copy i18n', () => {
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

  it('returns hover-card and canvas menu copy from the active locale', async () => {
    const { default: i18n, setLanguage } = await import('../i18n');

    await setLanguage('es');

    expect(i18n.t('canvas.hoverInputs')).toBe('Entradas');
    expect(i18n.t('canvas.hoverOutputs')).toBe('Salidas');
    expect(i18n.t('canvas.hoverVersion')).toBe('Version');
    expect(i18n.t('canvas.addNode')).toBe('Agregar nodo');
    expect(i18n.t('canvas.addRerouteHere')).toBe('Agregar redireccion aqui');
    expect(i18n.t('canvas.fitView')).toBe('Ajustar vista');
    expect(i18n.t('canvas.groupSelectedNodes')).toBe('Agrupar nodos seleccionados');
    expect(i18n.t('canvas.selectAll')).toBe('Seleccionar todo');
    expect(i18n.t('canvas.arrangeNodes')).toBe('Organizar nodos');
    expect(i18n.t('canvas.exportThumbnail')).toBe('Exportar miniatura');
    expect(i18n.t('canvas.clearWorkflow')).toBe('Limpiar workflow');
    expect(i18n.t('canvas.insertReroute')).toBe('Insertar redireccion');
    expect(i18n.t('canvas.deleteLink')).toBe('Eliminar enlace');
    expect(i18n.t('canvas.groupFallbackName')).toBe('Grupo');
    expect(i18n.t('canvas.rerouteFallbackName')).toBe('Redireccion');
  });

  it('keeps WorkflowCanvas hover-card and context menu labels behind i18n keys', () => {
    const source = readFileSync(resolve(__dirname, '../components/canvas/WorkflowCanvas.tsx'), 'utf8');

    [
      'canvas.hoverInputs',
      'canvas.hoverOutputs',
      'canvas.hoverVersion',
      'canvas.addNode',
      'canvas.addRerouteHere',
      'canvas.fitView',
      'canvas.groupSelectedNodes',
      'canvas.selectAll',
      'canvas.arrangeNodes',
      'canvas.exportThumbnail',
      'canvas.clearWorkflow',
      'canvas.insertReroute',
      'canvas.deleteLink',
      'canvas.groupFallbackName',
      'canvas.rerouteFallbackName',
    ].forEach(key => expect(source).toContain(key));

    [
      '<span>Inputs</span>',
      '<span>Outputs</span>',
      '<span>Version</span>',
      '>Add Node<',
      '>Add Reroute Here<',
      '>Fit View<',
      '>Group Selected Nodes<',
      '>Select All<',
      '>Arrange Nodes<',
      '>Export Thumbnail<',
      '>Clear Workflow<',
      '>Insert Reroute<',
      '>Delete Link<',
    ].forEach(text => expect(source).not.toContain(text));

    expect(source).not.toMatch(/name:\s*['"]Group['"]/);
    expect(source).not.toMatch(/title:\s*['"]Reroute['"]/);
  });
});
