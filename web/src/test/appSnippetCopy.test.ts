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

describe('App snippet copy i18n', () => {
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

  it('returns save and insert snippet feedback from the active locale', async () => {
    const { default: i18n, setLanguage } = await import('../i18n');

    await setLanguage('es');

    expect(i18n.t('snippets.selectAtLeastOne')).toBe('Selecciona al menos un nodo para guardar como snippet');
    expect(i18n.t('snippets.singleDefaultName', { name: 'FASTQ' })).toBe('FASTQ snippet');
    expect(i18n.t('snippets.multiDefaultName', { count: 3 })).toBe('Snippet de 3 nodos');
    expect(i18n.t('snippets.savePromptTitle')).toBe('Guardar seleccion como snippet');
    expect(i18n.t('snippets.savePromptMessage')).toBe('Los nodos seleccionados y los enlaces entre ellos se guardaran localmente para reutilizarlos.');
    expect(i18n.t('snippets.savePromptInputLabel')).toBe('Nombre del snippet');
    expect(i18n.t('snippets.savedTitle')).toBe('Snippet guardado');
    expect(i18n.t('snippets.savedMessage', { count: 2 })).toBe('2 nodos');
    expect(i18n.t('snippets.emptyLibrary')).toBe('Aun no hay snippets; selecciona nodos y ejecuta "Guardar seleccion como snippet"');
    expect(i18n.t('snippets.insertPromptTitle')).toBe('Insertar snippet');
    expect(i18n.t('snippets.insertPromptMessage', { labels: '1. QC (2n)' })).toBe('Elige un snippet por numero:\n1. QC (2n)');
    expect(i18n.t('snippets.insertPromptInputLabel')).toBe('Numero');
    expect(i18n.t('snippets.insertedTitle')).toBe('Snippet insertado');
  });

  it('keeps App snippet prompts and toasts behind i18n keys', () => {
    const appSource = readFileSync(resolve(__dirname, '../App.tsx'), 'utf8');

    expect(appSource).toContain('snippets.selectAtLeastOne');
    [
      'Select at least one node to save as a snippet',
      'Save selection as snippet',
      'The selected nodes and the edges between them will be saved locally for reuse.',
      'Snippet name',
      'Snippet saved',
      'No snippets yet',
      'Insert snippet',
      'Pick a snippet by number',
      'Snippet inserted',
    ].forEach(text => {
      expect(appSource).not.toContain(text);
    });
  });
});
