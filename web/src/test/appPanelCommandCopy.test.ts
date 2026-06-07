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

describe('App panel command copy i18n', () => {
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

  it('returns panel and tool command labels from the active locale', async () => {
    const { default: i18n, setLanguage } = await import('../i18n');

    await setLanguage('es');

    expect(i18n.t('commandPalette.groups.tools')).toBe('Herramientas');
    expect(i18n.t('commandPalette.commands.rail.workspace')).toBe('Abrir espacio de trabajo');
    expect(i18n.t('commandPalette.commands.rail.nodes')).toBe('Abrir nodos');
    expect(i18n.t('commandPalette.commands.rail.inspector')).toBe('Abrir inspector');
    expect(i18n.t('commandPalette.commands.rail.templates')).toBe('Abrir plantillas');
    expect(i18n.t('commandPalette.commands.rail.environment')).toBe('Abrir entornos');
    expect(i18n.t('commandPalette.commands.rail.runtimeArtifacts')).toBe('Abrir artefactos de ejecucion');
    expect(i18n.t('commandPalette.commands.rail.hpc')).toBe('Abrir HPC');
    expect(i18n.t('commandPalette.commands.rail.help')).toBe('Abrir ayuda');
    expect(i18n.t('commandPalette.commands.rail.console')).toBe('Abrir consola');
    expect(i18n.t('commandPalette.commands.console.toggle')).toBe('Alternar consola');
    expect(i18n.t('commandPalette.commands.settings.toggle')).toBe('Alternar ajustes');
    expect(i18n.t('commandPalette.commands.ai.open')).toBe('Abrir constructor de workflows con IA');
    expect(i18n.t('commandPalette.commands.shortcuts.open')).toBe('Atajos de teclado');
  });

  it('keeps App panel and tool command copy behind i18n keys', () => {
    const appSource = readFileSync(resolve(__dirname, '../App.tsx'), 'utf8');

    [
      'commandPalette.groups.panels',
      'commandPalette.groups.tools',
      'commandPalette.commands.rail.workspace',
      'commandPalette.commands.rail.nodes',
      'commandPalette.commands.rail.inspector',
      'commandPalette.commands.rail.templates',
      'commandPalette.commands.rail.environment',
      'commandPalette.commands.rail.runtimeArtifacts',
      'commandPalette.commands.rail.hpc',
      'commandPalette.commands.rail.help',
      'commandPalette.commands.rail.console',
      'commandPalette.commands.console.toggle',
      'commandPalette.commands.settings.toggle',
      'commandPalette.commands.ai.open',
      'commandPalette.commands.shortcuts.open',
    ].forEach(key => expect(appSource).toContain(key));

    [
      "label: 'Open workspace'",
      "label: 'Open nodes'",
      "label: 'Open inspector'",
      "label: 'Open templates'",
      "label: 'Open environments'",
      "label: 'Open runtime artifacts'",
      "label: 'Open HPC'",
      "label: 'Open help'",
      "label: 'Open console'",
      "label: 'Toggle console'",
      "label: 'Toggle settings'",
      "label: 'Open AI workflow builder'",
      "label: 'Keyboard shortcuts'",
    ].forEach(text => expect(appSource).not.toContain(text));
  });
});
