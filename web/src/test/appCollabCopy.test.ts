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

describe('App collaboration copy i18n', () => {
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

  it('returns create, join, and leave collaboration copy from the active locale', async () => {
    const { default: i18n, setLanguage } = await import('../i18n');
    const { makeAppCollabCopy } = await import('../collab/appCollabCopy');

    await setLanguage('es');

    const copy = makeAppCollabCopy(i18n.t);

    expect(copy.createLinkCopiedMessage(true)).toBe('Compartelo con colaboradores mientras esta app se ejecuta.');
    expect(copy.createLinkCopiedMessage(false)).toBe('Este es un enlace local. Inicia un tunel o usa un host publico antes de compartir fuera de esta maquina.');
    expect(copy.createLinkReadyMessage(true)).toBe('Abre Compartir workflow para copiarlo.');
    expect(copy.createLinkReadyMessage(false)).toBe('Abre Compartir workflow para copiar el enlace local, o inicia BioNodulo mediante un tunel publico.');
    expect(copy.joinPrompt()).toMatchObject({
      title: 'Unirse a colaboracion',
      message: 'Pega un enlace de colaboracion de BioNodulo o ID de sala.',
      inputLabel: 'Enlace compartido',
      placeholder: 'https://bionodulo.example/?workflow=...&invite=...',
      confirmLabel: 'Unirse',
    });
    expect(copy.connectedAsRole('editor')).toBe('Conectado como Editor.');
    expect(copy.connectedAsRole('viewer')).toBe('Conectado como Lector.');
    expect(copy.workflowFallback('workflow-1234567890abcdef')).toBe('Workflow workflow-123');
    expect(copy.toast.linkCopied).toBe('Enlace de colaboracion copiado');
    expect(copy.toast.linkReady).toBe('Enlace de colaboracion listo');
    expect(copy.toast.joined).toBe('Colaboracion unida');
    expect(copy.toast.stopped).toBe('Colaboracion detenida');
    expect(copy.toast.offlineModeRestored).toBe('Este navegador vuelve al modo sin conexion.');
    expect(copy.error.invalidLinkTitle).toBe('Enlace de colaboracion invalido');
    expect(copy.error.invalidLinkMessage).toBe('Se esperaba una URL de BioNodulo con ?workflow=... o un ID de sala.');
    expect(copy.error.createLinkFailed).toBe('No se pudo crear el enlace de colaboracion');
    expect(copy.error.joinFailed).toBe('No se pudo unir a la colaboracion');
  });

  it('keeps App collaboration create/join/leave copy behind i18n helpers', () => {
    const appSource = readFileSync(resolve(__dirname, '../App.tsx'), 'utf8');

    expect(appSource).toContain('makeAppCollabCopy');
    [
      'Collaboration link copied',
      'Share it with collaborators while this app is running.',
      'This is a local link. Start a tunnel or use a public host before sharing outside this machine.',
      'Collaboration link ready',
      'Open Share workflow to copy it.',
      'Open Share workflow to copy the local link, or start BioNodulo through a public tunnel.',
      'Could not create collaboration link',
      'Join Collaboration',
      'Paste a BioNodulo collaboration link or room ID.',
      'Share link',
      'Invalid collaboration link',
      'Expected a BioNodulo URL with ?workflow=... or a room ID.',
      'Joined collaboration',
      'Connected as ${joined.role}.',
      'Could not join collaboration',
      'Collaboration stopped',
      'This browser is back in offline mode.',
    ].forEach(text => {
      expect(appSource).not.toContain(text);
    });
  });
});
