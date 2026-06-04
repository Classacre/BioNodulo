import { fireEvent, render, screen, waitFor } from '@testing-library/react';
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

const templatesPayload = {
  templates: [
    {
      id: 'rna-qc',
      name: 'RNA QC',
      description: 'Quality control for RNA-seq reads',
      category: 'RNA-Seq',
      tags: ['qc', 'rna'],
      tools: ['fastqc', 'multiqc'],
      node_count: 4,
      filename: 'rna_qc.json',
      preview_steps: ['fastqc', 'multiqc'],
    },
  ],
};

describe('TemplatesPanel i18n', () => {
  let fetchSpy: ReturnType<typeof vi.spyOn>;
  let originalLocalStorage: Storage;

  beforeEach(() => {
    storage.clear();
    originalLocalStorage = window.localStorage;
    vi.stubGlobal('localStorage', localStorageStub);
    Object.defineProperty(window, 'localStorage', {
      configurable: true,
      value: localStorageStub,
    });
    fetchSpy = vi.spyOn(globalThis, 'fetch').mockImplementation(async (input: RequestInfo | URL) => {
      const url = typeof input === 'string' ? input : input.toString();
      if (url.endsWith('/api/workflow_templates')) {
        return new Response(JSON.stringify(templatesPayload), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        });
      }
      return new Response('{}', {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      });
    });
  });

  afterEach(async () => {
    const { setLanguage } = await import('../i18n');
    await setLanguage('en');
    storage.clear();
    vi.unstubAllGlobals();
    Object.defineProperty(window, 'localStorage', {
      configurable: true,
      value: originalLocalStorage,
    });
    fetchSpy.mockRestore();
  });

  it('renders search, sort, save, and card labels from the active locale', async () => {
    const { default: TemplatesPanel } = await import('../components/panels/TemplatesPanel');
    const { setLanguage } = await import('../i18n');

    await setLanguage('es');

    render(
      <TemplatesPanel
        onClose={() => undefined}
        onLoadTemplate={() => undefined}
        onSaveTemplate={() => undefined}
        showSaveTemplateAction
      />,
    );

    await waitFor(() => expect(screen.getByText('RNA QC')).toBeInTheDocument());

    expect(screen.getByRole('dialog', { name: 'Plantillas' })).toBeInTheDocument();
    expect(screen.getByTitle('Guardar workflow como plantilla')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /Guardar$/ }));

    expect(screen.getByPlaceholderText('Nombre de plantilla')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('Descripcion')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('Categoria')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('etiquetas, separadas por comas')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Cancelar' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Guardar plantilla' })).toBeInTheDocument();

    expect(screen.getByPlaceholderText('Buscar plantillas...')).toBeInTheDocument();
    expect(screen.getByRole('textbox', { name: 'Buscar plantillas' })).toBeInTheDocument();
    expect(screen.getByRole('combobox', { name: 'Ordenar plantillas' })).toHaveDisplayValue('Mejor coincidencia');
    expect(screen.getByText('1 de 1 plantillas')).toBeInTheDocument();
    expect(screen.getByTitle('Cargar RNA QC')).toBeInTheDocument();
    expect(screen.getByTitle('Ranking de coincidencia de plantilla')).toBeInTheDocument();
    expect(screen.getByLabelText('Pasos de vista previa del workflow')).toBeInTheDocument();
    expect(screen.getByText('4 nodos')).toBeInTheDocument();

    fireEvent.change(screen.getByRole('textbox', { name: 'Buscar plantillas' }), {
      target: { value: 'zz' },
    });

    expect(screen.getByText('Clasificado por coincidencia difusa')).toBeInTheDocument();
    expect(screen.getByText('Ninguna plantilla coincide con tu busqueda.')).toBeInTheDocument();
  });

  it('keeps saved template category data stable when the UI is localized', async () => {
    const { default: TemplatesPanel } = await import('../components/panels/TemplatesPanel');
    const { setLanguage } = await import('../i18n');
    const onSaveTemplate = vi.fn();

    await setLanguage('es');

    render(
      <TemplatesPanel
        onClose={() => undefined}
        onLoadTemplate={() => undefined}
        onSaveTemplate={onSaveTemplate}
        saveTemplateInitialName="QC copy"
        showSaveTemplateAction
      />,
    );

    await waitFor(() => expect(screen.getByText('RNA QC')).toBeInTheDocument());

    fireEvent.click(screen.getByTitle('Guardar workflow como plantilla'));
    fireEvent.click(screen.getByRole('button', { name: 'Guardar plantilla' }));

    await waitFor(() => expect(onSaveTemplate).toHaveBeenCalledWith(expect.objectContaining({
      category: 'Custom',
    })));
  });
});
