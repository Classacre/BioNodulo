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

describe('App subgraph feedback copy i18n', () => {
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

  it('returns subgraph feedback and breadcrumb copy from the active locale', async () => {
    const { default: i18n, setLanguage } = await import('../i18n');

    await setLanguage('es');

    expect(i18n.t('canvas.subgraphBlockName', { name: i18n.t('common.untitled') })).toBe('Bloque de Sin titulo');
    expect(i18n.t('canvas.subgraphSelectionConverted')).toBe('Seleccion convertida en subgrafo');
    expect(i18n.t('canvas.subgraphEnterFirst')).toBe('Entra primero en un subgrafo para promover sus widgets');
    expect(i18n.t('canvas.subgraphNoPromotableWidgets', { name: 'FastQC' })).toBe('FastQC no tiene widgets promovibles');
    expect(i18n.t('canvas.subgraphPromotedWidgets', { count: 1, name: 'QC' })).toBe('1 widget promovido a QC');
    expect(i18n.t('canvas.subgraphPromotedWidgets', { count: 3, name: 'QC' })).toBe('3 widgets promovidos a QC');
    expect(i18n.t('canvas.subgraphMissingEmbeddedWorkflow')).toBe('El subgrafo no tiene workflow embebido');
    expect(i18n.t('canvas.subgraphFallbackName')).toBe('Subgrafo');
    expect(i18n.t('canvas.subgraphWorkflowFallbackName')).toBe('Workflow');
    expect(i18n.t('canvas.subgraphBreadcrumbLabel')).toBe('Subgrafo:');
    expect(i18n.t('canvas.subgraphBackToTopLevel')).toBe('Volver al workflow de nivel superior');
  });

  it('keeps App subgraph feedback and breadcrumb copy behind i18n keys', () => {
    const appSource = readFileSync(resolve(__dirname, '../App.tsx'), 'utf8');

    [
      'canvas.subgraphBlockName',
      'canvas.subgraphSelectionConverted',
      'canvas.subgraphEnterFirst',
      'canvas.subgraphNoPromotableWidgets',
      'canvas.subgraphPromotedWidgets',
      'canvas.subgraphMissingEmbeddedWorkflow',
      'canvas.subgraphFallbackName',
      'canvas.subgraphWorkflowFallbackName',
      'canvas.subgraphBreadcrumbLabel',
      'canvas.subgraphBackToTopLevel',
      'common.untitled',
    ].forEach(key => expect(appSource).toContain(key));

    [
      "`${activeWorkflow.name || 'Untitled'} block`",
      "'Selection converted to subgraph'",
      "'Enter a subgraph first to promote its widgets'",
      'has no promotable widgets',
      'Promoted ${added} widget',
      "'Subgraph has no embedded workflow'",
      "'Subgraph'",
      '>Subgraph:</span>',
      'title="Back to top-level workflow"',
      "|| 'Workflow'",
    ].forEach(text => expect(appSource).not.toContain(text));
  });
});
