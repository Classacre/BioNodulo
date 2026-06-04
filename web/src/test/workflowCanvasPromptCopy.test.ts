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

describe('WorkflowCanvas prompt and toast copy i18n', () => {
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

  it('returns node rename, subgraph library, and preset copy from the active locale', async () => {
    const { default: i18n, setLanguage } = await import('../i18n');

    await setLanguage('es');

    expect(i18n.t('canvas.renameNodeTitle')).toBe('Renombrar nodo');
    expect(i18n.t('canvas.renameNodeMessage')).toBe('Elige un nombre visible para este nodo.');
    expect(i18n.t('canvas.nodeNameInput')).toBe('Nombre del nodo');
    expect(i18n.t('canvas.saveSubgraphLibraryOnlySubgraph')).toBe('Guardar en biblioteca solo funciona en nodos de subgrafo');
    expect(i18n.t('canvas.subgraphMissingEmbeddedWorkflow')).toBe('El subgrafo no tiene workflow embebido');
    expect(i18n.t('canvas.subgraphFallbackName')).toBe('Subgrafo');
    expect(i18n.t('canvas.subgraphLibrarySaved')).toBe('Guardado en la biblioteca de subgrafos');
    expect(i18n.t('canvas.presetDefaultName', { name: 'FastQC' })).toBe('Preset de FastQC');
    expect(i18n.t('canvas.savePresetTitle')).toBe('Guardar preset de parametros');
    expect(i18n.t('canvas.savePresetMessage')).toBe('Los valores de parametros actuales se guardaran para este tipo de nodo.');
    expect(i18n.t('canvas.presetNameInput')).toBe('Nombre del preset');
    expect(i18n.t('canvas.presetSaved')).toBe('Preset guardado');
    expect(i18n.t('canvas.noPresetsForNodeType')).toBe('Aun no hay presets guardados para este tipo de nodo');
    expect(i18n.t('canvas.applyPresetTitle')).toBe('Aplicar preset');
    expect(i18n.t('canvas.applyPresetMessage', { labels: '1. Default' })).toBe('Elige un preset por numero:\n1. Default');
    expect(i18n.t('canvas.presetNumberInput')).toBe('Numero');
    expect(i18n.t('canvas.presetApplied')).toBe('Preset aplicado');
  });

  it('keeps WorkflowCanvas prompt and toast strings behind i18n keys', () => {
    const source = readFileSync(resolve(__dirname, '../components/canvas/WorkflowCanvas.tsx'), 'utf8');

    expect(source).toContain('canvas.renameNodeTitle');
    [
      'Rename node',
      'Choose a display name for this node.',
      'Node name',
      'Save to library only works on subgraph nodes',
      'Subgraph has no embedded workflow',
      "'Subgraph'",
      'Saved to subgraph library',
      'Save parameter preset',
      'The current parameter values will be saved for this node type.',
      'Preset name',
      'Preset saved',
      'No presets saved for this node type yet',
      'Apply preset',
      'Pick a preset by number:',
      'Preset applied',
    ].forEach(text => expect(source).not.toContain(text));
  });
});
