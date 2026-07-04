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

    expect(i18n.t('commandPalette.groups.workflow')).toBe('Flujo de trabajo');
    expect(i18n.t('commandPalette.commands.workflow.run')).toBe('Ejecutar flujo de trabajo');
    expect(i18n.t('commandPalette.commands.workflow.currentWorkflow')).toBe('Flujo de trabajo actual');
    expect(i18n.t('commandPalette.commands.workflow.runSelected')).toBe('Ejecutar nodos seleccionados');
    expect(i18n.t('commandPalette.commands.workflow.runSelectedDescription')).toBe('Ejecutar nodos seleccionados y sus dependencias');
    expect(i18n.t('commandPalette.commands.workflow.extractSelection')).toBe('Crear subgrafo desde seleccion');
    expect(i18n.t('commandPalette.commands.workflow.extractSelectionDescription')).toBe('Abrir nodos seleccionados como nueva pestana de flujo de trabajo');
    expect(i18n.t('commandPalette.commands.workflow.doctor')).toBe('Ejecutar doctor de flujo de trabajo');
    expect(i18n.t('commandPalette.commands.workflow.doctorDescription')).toBe('Analizar el flujo de trabajo actual en busca de entradas faltantes, salidas sin usar y pistas de dependencias');
    expect(i18n.t('nodePalette.addNode')).toBe('Agregar nodo');
    expect(i18n.t('nodePalette.addNodeTitle', { name: 'FastQC' })).toBe('Agregar FastQC');

    const workflowCommandCopy = i18n.t('commandPalette.commands.workflow', { returnObjects: true }) as Record<string, string>;

    [
      'Ejecutar workflow',
      'Workflow actual',
      'Abrir nodos seleccionados como nueva pestana de workflow',
      'Ejecutar doctor de workflow',
      'Analizar el workflow actual en busca de entradas faltantes, salidas sin usar y pistas de dependencias',
    ].forEach(text => expect(Object.values(workflowCommandCopy)).not.toContain(text));
  });

  it('keeps App workflow command copy behind i18n keys', () => {
    const appSource = readFileSync(resolve(__dirname, '../App.tsx'), 'utf8');

    [
      'commandPalette.commands.workflow.run',
      'commandPalette.commands.workflow.currentWorkflow',
      'commandPalette.commands.workflow.runSelected',
      'commandPalette.commands.workflow.runSelectedDescription',
      'commandPalette.commands.workflow.doctor',
      'commandPalette.commands.workflow.doctorDescription',
      'commandPalette.groups.workflow',
      'nodePalette.addNode',
      'nodePalette.addNodeTitle',
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
      "label: `Add: ${meta.display_name}`",
    ].forEach(text => expect(appSource).not.toContain(text));
  });

  it('keeps add-node command group identity canonical while localizing the heading', () => {
    const appSource = readFileSync(resolve(__dirname, '../App.tsx'), 'utf8');

    expect(appSource).not.toContain("group: t('nodePalette.addNode')");
    expect(appSource).toContain("group: 'Add Node'");
    expect(appSource).toContain("groupLabelKey: 'nodePalette.addNode'");
  });

  it('pairs workflow command group fallbacks with the workflow group i18n key', () => {
    const appSource = readFileSync(resolve(__dirname, '../App.tsx'), 'utf8');
    const appLines = appSource.split('\n');

    appLines.forEach((line, index) => {
      if (!line.includes("group: 'Workflow'")) return;

      expect(
        appLines[index + 1],
        `Workflow command group at App.tsx:${index + 1} should use commandPalette.groups.workflow`,
      ).toContain("groupLabelKey: 'commandPalette.groups.workflow'");
    });
  });

  it('keeps command palette group identities canonical while localizing headings', () => {
    const appSource = readFileSync(resolve(__dirname, '../App.tsx'), 'utf8');
    const appLines = appSource.split('\n');

    expect(appSource).not.toContain("group: t('commandPalette.groups.");

    [
      ['Workflow', 'commandPalette.groups.workflow'],
      ['Edit', 'commandPalette.groups.edit'],
      ['View', 'commandPalette.groups.view'],
      ['Panels', 'commandPalette.groups.panels'],
      ['Tools', 'commandPalette.groups.tools'],
      ['Appearance', 'commandPalette.groups.appearance'],
    ].forEach(([group, key]) => {
      appLines.forEach((line, index) => {
        if (!line.includes(`group: '${group}'`)) return;

        expect(
          appLines[index + 1],
          `${group} command group at App.tsx:${index + 1} should use ${key}`,
        ).toContain(`groupLabelKey: '${key}'`);
      });
    });
  });
});
