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

describe('App file action copy i18n', () => {
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

  it('returns pasted and dropped file feedback from the active locale', async () => {
    const { default: i18n, setLanguage } = await import('../i18n');

    await setLanguage('es');

    expect(i18n.t('workspace.pastedFileAdded')).toBe('Archivo pegado agregado');
    expect(i18n.t('workspace.fileDropped')).toBe('Archivo soltado');
    expect(i18n.t('workspace.missingInputFileForPaste')).toBe('No hay nodo input_file registrado; no se puede conectar el archivo pegado');
    expect(i18n.t('workspace.couldNotUploadPastedFile')).toBe('No se pudo subir el archivo pegado');
    expect(i18n.t('workspace.missingInputFileForDrop')).toBe('No hay nodo input_file registrado; no se puede crear un nodo para el archivo soltado');
    expect(i18n.t('workspace.fileTypeFallback')).toBe('archivo');
  });

  it('keeps App pasted and dropped file feedback behind i18n helpers', () => {
    const appSource = readFileSync(resolve(__dirname, '../App.tsx'), 'utf8');

    expect(appSource).toContain('makeAppFileActionCopy');
    [
      'No input_file node registered; cannot wire pasted file',
      'Pasted file added',
      'Could not upload pasted file',
      'No input_file node registered; cannot create node for dropped file',
      'File dropped',
    ].forEach(text => {
      expect(appSource).not.toContain(text);
    });
  });
});
