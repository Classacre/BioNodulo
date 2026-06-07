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

describe('App workflow command copy i18n', () => {
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

  it('returns workflow command labels and descriptions from the active locale', async () => {
    const { default: i18n, setLanguage } = await import('../i18n');

    await setLanguage('es');

    expect(i18n.t('commandPalette.groups.workflow')).toBe('Workflow');
    expect(i18n.t('commandPalette.commands.workflow.run')).toBe('Ejecutar workflow');
    expect(i18n.t('commandPalette.commands.workflow.currentWorkflow')).toBe('Workflow actual');
    expect(i18n.t('commandPalette.commands.workflow.runSelected')).toBe('Ejecutar nodos seleccionados');
    expect(i18n.t('commandPalette.commands.workflow.runSelectedDescription')).toBe('Ejecutar nodos seleccionados y sus dependencias');
    expect(i18n.t('commandPalette.commands.workflow.extractSelection')).toBe('Crear subgrafo desde seleccion');
    expect(i18n.t('commandPalette.commands.workflow.extractSelectionDescription')).toBe('Abrir nodos seleccionados como nueva pestana de workflow');
    expect(i18n.t('commandPalette.commands.workflow.doctor')).toBe('Ejecutar doctor de workflow');
    expect(i18n.t('commandPalette.commands.workflow.doctorDescription')).toBe('Analizar el workflow actual en busca de entradas faltantes, salidas sin usar y pistas de dependencias');
  });

  it('keeps App workflow command copy behind i18n keys', () => {
    const appSource = readFileSync(resolve(__dirname, '../App.tsx'), 'utf8');

    [
      'commandPalette.commands.workflow.run',
      'commandPalette.commands.workflow.currentWorkflow',
      'commandPalette.commands.workflow.runSelected',
      'commandPalette.commands.workflow.runSelectedDescription',
      'commandPalette.commands.workflow.extractSelection',
      'commandPalette.commands.workflow.extractSelectionDescription',
      'commandPalette.commands.workflow.doctor',
      'commandPalette.commands.workflow.doctorDescription',
      'commandPalette.groups.workflow',
    ].forEach(key => expect(appSource).toContain(key));

    [
      "label: 'Run workflow'",
      "description: activeWorkflow.name || 'Current workflow'",
      "label: 'Run selected nodes'",
      "description: 'Execute selected nodes and their dependencies'",
      "label: 'Create subgraph from selection'",
      "description: 'Open selected nodes as a new workflow tab'",
      "label: 'Run workflow doctor'",
      "description: 'Scan the current workflow for missing inputs, unused outputs, and dependency hints'",
    ].forEach(text => expect(appSource).not.toContain(text));
  });
});
