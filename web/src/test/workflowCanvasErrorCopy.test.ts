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

describe('WorkflowCanvas widget and error copy i18n', () => {
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

  it('returns widget-copy and node-error copy from the active locale', async () => {
    const { default: i18n, setLanguage } = await import('../i18n');

    await setLanguage('es');

    expect(i18n.t('canvas.copyWidgetValueHint')).toBe('Clic derecho para copiar este valor a los nodos seleccionados');
    expect(i18n.t('canvas.widgetTooltipWithCopyHint', {
      hint: 'Clic derecho para copiar este valor a los nodos seleccionados',
      tooltip: 'Parametro de ejemplo',
    })).toBe('Parametro de ejemplo\n\n(Clic derecho para copiar este valor a los nodos seleccionados)');
    expect(i18n.t('canvas.nodeErrorAria', { message: 'fallo' })).toBe('Error: fallo');
    expect(i18n.t('canvas.nodeErrorTitle')).toBe('Error del nodo');
    expect(i18n.t('canvas.nodeErrorDismissHint')).toBe('Edita los parametros del nodo para descartarlo.');
  });

  it('keeps WorkflowCanvas widget-copy and node-error labels behind i18n keys', () => {
    const source = readFileSync(resolve(__dirname, '../components/canvas/WorkflowCanvas.tsx'), 'utf8');

    [
      'canvas.copyWidgetValueHint',
      'canvas.widgetTooltipWithCopyHint',
      'canvas.nodeErrorAria',
      'canvas.nodeErrorTitle',
      'canvas.nodeErrorDismissHint',
    ].forEach(key => expect(source).toContain(key));

    [
      'Right-click to copy this value to selected nodes',
      '`Error: ${message.slice(0, 80)}`',
      '>Node error<',
      "Edit the node's parameters to dismiss.",
    ].forEach(text => expect(source).not.toContain(text));
  });
});
