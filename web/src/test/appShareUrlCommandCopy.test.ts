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

describe('App share URL command copy i18n', () => {
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

  it('returns share URL command labels and feedback from the active locale', async () => {
    const { default: i18n, setLanguage } = await import('../i18n');

    await setLanguage('es');

    expect(i18n.t('commandPalette.commands.share.copyUrl')).toBe('Copiar URL compartible');
    expect(i18n.t('commandPalette.commands.share.copyUrlDescription')).toBe('Codificar el flujo de trabajo actual en un hash de URL y copiarlo al portapapeles');
    expect(i18n.t('commandPalette.commands.share.copyUrlDescription')).not.toBe('Codificar el workflow actual en un hash de URL y copiarlo al portapapeles');
    expect(i18n.t('workflowShare.copyUrlBuildError')).toBe('No se pudo crear la URL compartible');
    expect(i18n.t('workflowShare.copyUrlTooLarge')).toBe('La URL supera 32 KB');
    expect(i18n.t('workflowShare.copyUrlTooLargeMessage')).toBe('Algunas herramientas de chat pueden truncarla. Considera exportar en su lugar.');
    expect(i18n.t('workflowShare.copyUrlCopied')).toBe('URL compartible copiada');
    expect(i18n.t('workflowShare.copyUrlSizeKB', { size: '31,3' })).toBe('31,3 KB');
    expect(i18n.t('workflowShare.copyUrlDialogTitle')).toBe('URL compartible');
  });

  it('keeps App share URL command copy behind i18n keys', () => {
    const appSource = readFileSync(resolve(__dirname, '../App.tsx'), 'utf8');

    [
      'commandPalette.commands.share.copyUrl',
      'commandPalette.commands.share.copyUrlDescription',
      'workflowShare.copyUrlBuildError',
      'workflowShare.copyUrlTooLarge',
      'workflowShare.copyUrlTooLargeMessage',
      'workflowShare.copyUrlCopied',
      'workflowShare.copyUrlSizeKB',
      'workflowShare.copyUrlDialogTitle',
    ].forEach(key => expect(appSource).toContain(key));

    [
      "label: 'Copy share URL'",
      "description: 'Encode the current workflow into a URL hash and copy to clipboard'",
      "toast.error('Could not build share URL')",
      "toast.warning('URL exceeds 32 KB'",
      "message: 'Some chat tools may truncate. Consider exporting instead.'",
      "toast.success('Share URL copied'",
      "message: `${(url.length / 1024).toFixed(1)} KB`",
      "title: 'Share URL'",
    ].forEach(text => expect(appSource).not.toContain(text));
  });
});
