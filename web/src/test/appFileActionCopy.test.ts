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
    expect(i18n.t('workspace.uploadResponseMissingPath')).toBe('La respuesta de subida no incluyo ruta');
    expect(i18n.t('workspace.upload')).toBe('Subir archivos');
    expect(i18n.t('workspace.uploadDrop')).toBe('Suelta archivos para subirlos');
    expect(i18n.t('workspace.uploadProgress', { name: 'reads.fastq' })).toBe('Subiendo reads.fastq...');
    expect(i18n.t('workspace.uploadSuccess', { name: 'reads.fastq' })).toBe('reads.fastq subido');
  });

  it('returns workspace file management labels from the active locale', async () => {
    const { default: i18n, setLanguage } = await import('../i18n');

    await setLanguage('es');

    expect(i18n.t('workspace.newFolder')).toBe('Nueva carpeta');
    expect(i18n.t('workspace.newFolderName')).toBe('Nombre de carpeta');
    expect(i18n.t('workspace.pathCopied')).toBe('Ruta copiada');
    expect(i18n.t('workspace.revealInExplorer')).toBe('Mostrar en el gestor de archivos');
    expect(i18n.t('workspace.deletePromptTitle')).toBe('Eliminar archivo?');
    expect(i18n.t('workspace.deletePromptBody', { name: 'reads.fastq' })).toBe('Eliminar reads.fastq permanentemente?');
    expect(i18n.t('workspace.fileEmpty')).toBe('Espacio de trabajo vacio; arrastra archivos para empezar');
    expect(i18n.t('workspace.fileCount', { count: 1 })).toBe('1 archivo');
    expect(i18n.t('workspace.fileCount', { count: 4 })).toBe('4 archivos');
    expect(i18n.t('workspace.folderCount', { count: 1 })).toBe('1 carpeta');
    expect(i18n.t('workspace.folderCount', { count: 3 })).toBe('3 carpetas');
  });

  it('keeps App pasted and dropped file feedback behind i18n helpers', () => {
    const appSource = readFileSync(resolve(__dirname, '../App.tsx'), 'utf8');

    expect(appSource).toContain('makeAppFileActionCopy');
    [
      'No input_file node registered; cannot wire pasted file',
      'Pasted file added',
      'Could not upload pasted file',
      'Upload response missing path',
      'No input_file node registered; cannot create node for dropped file',
      'File dropped',
      "|| 'file'",
    ].forEach(text => {
      expect(appSource).not.toContain(text);
    });
  });
});
