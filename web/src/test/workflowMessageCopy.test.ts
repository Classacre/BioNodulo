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

describe('Workflow message copy i18n', () => {
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

  it('returns run-failure toast copy from the active locale', async () => {
    const { default: i18n, setLanguage } = await import('../i18n');

    await setLanguage('es');

    expect(i18n.t('console.actions.runFailedTitle')).toBe('Ejecucion fallida');
    expect(i18n.t('console.actions.workflowFallback')).toBe('Workflow');
    expect(i18n.t('console.actions.consoleDetailsFallback')).toBe('consulta la consola para mas detalles');
    expect(i18n.t('console.actions.runFailedMessage', {
      name: 'RNA-seq',
      detail: 'consulta la consola para mas detalles',
    })).toBe('RNA-seq - consulta la consola para mas detalles');
  });

  it('keeps workflow failure toast copy behind i18n keys', () => {
    const source = readFileSync(resolve(__dirname, '../hooks/workflow/useWorkflowMessages.ts'), 'utf8');

    expect(source).toContain('console.actions.runFailedTitle');
    expect(source).toContain('console.actions.runFailedMessage');
    expect(source).toContain('console.actions.consoleDetailsFallback');
    [
      "'Run failed'",
      "'Workflow'",
      'see the console for details',
    ].forEach(text => {
      expect(source).not.toContain(text);
    });
  });
});
