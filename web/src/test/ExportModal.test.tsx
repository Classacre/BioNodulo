import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { Workflow } from '../types';

const apiMocks = {
  apiPost: vi.fn(),
  ApiError: class ApiError extends Error {
    status: number;
    statusText: string;
    body: unknown;

    constructor(message: string, status: number, statusText: string, body: unknown) {
      super(message);
      this.name = 'ApiError';
      this.status = status;
      this.statusText = statusText;
      this.body = body;
    }
  },
};

vi.mock('../api/client', () => apiMocks);

const utilsMocks = vi.hoisted(() => ({
  saveToFile: vi.fn(),
}));

vi.mock('../utils', async importOriginal => {
  const actual = await importOriginal<typeof import('../utils')>();
  return {
    ...actual,
    saveToFile: utilsMocks.saveToFile,
  };
});

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

function workflow(partial: Partial<Workflow> = {}): Workflow {
  return {
    version: '2.0',
    app: 'BioNodulo',
    name: partial.name ?? 'Export example',
    description: partial.description ?? '',
    nodes: partial.nodes ?? [],
    edges: partial.edges ?? [],
    groups: partial.groups ?? [],
    outputs: partial.outputs ?? {},
    environment: partial.environment,
    dependencies: partial.dependencies,
  };
}

describe('ExportModal i18n', () => {
  beforeEach(() => {
    storage.clear();
    apiMocks.apiPost.mockReset();
    utilsMocks.saveToFile.mockReset();
    vi.stubGlobal('localStorage', localStorageStub);
  });

  afterEach(async () => {
    const { setLanguage } = await import('../i18n');
    await setLanguage('en');
    storage.clear();
    vi.unstubAllGlobals();
  });

  it('renders PNG options and generated JSON actions from the active locale', async () => {
    const { default: ExportModal } = await import('../components/modals/ExportModal');
    const { setLanguage } = await import('../i18n');

    await setLanguage('es');

    render(<ExportModal workflow={workflow()} onClose={() => undefined} />);

    expect(screen.getByRole('dialog', { name: 'Exportar workflow' })).toBeInTheDocument();
    expect(screen.getByText('Exportar workflow')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'PNG (workflow incrustado)' })).toHaveClass('active');
    expect(screen.getByText('El PNG lleva el JSON completo del workflow en un fragmento tEXt; arrastralo de vuelta al lienzo para restaurar el grafo.')).toBeInTheDocument();
    expect(screen.getByLabelText('Fondo transparente')).toBeInTheDocument();
    expect(screen.getByText('Resolucion')).toBeInTheDocument();
    expect(screen.getByLabelText('Solo JSON (omitir contenedor PNG)')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Renderizar miniatura' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Cerrar' })).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'JSON de BioNodulo' }));
    expect(screen.getByRole('button', { name: 'Generar' })).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Generar' }));

    await waitFor(() => expect(screen.getByRole('button', { name: 'Descargar' })).toBeInTheDocument());
    expect(screen.getByRole('button', { name: 'Copiar al portapapeles' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Regenerar' })).toBeInTheDocument();
  });

  it('uses the active locale for unnamed workflow download filenames', async () => {
    const { default: ExportModal } = await import('../components/modals/ExportModal');
    const { setLanguage } = await import('../i18n');

    await setLanguage('es');

    render(<ExportModal workflow={workflow({ name: '' })} onClose={() => undefined} />);

    fireEvent.click(screen.getByRole('button', { name: 'JSON de BioNodulo' }));
    fireEvent.click(screen.getByRole('button', { name: 'Generar' }));

    await waitFor(() => expect(screen.getByRole('button', { name: 'Descargar' })).toBeInTheDocument());

    fireEvent.click(screen.getByRole('button', { name: 'Descargar' }));

    expect(utilsMocks.saveToFile).toHaveBeenCalledWith(
      expect.stringContaining('"version": "2.0"'),
      'workflow-sin-titulo.json',
      'text/plain',
    );
  });

  it('shows export API errors without generating fallback downloadable content', async () => {
    const { default: ExportModal } = await import('../components/modals/ExportModal');
    apiMocks.apiPost.mockRejectedValueOnce(
      new apiMocks.ApiError('HTTP 500 Server Error (/api/workflow/export)', 500, 'Server Error', {
        detail: 'Converter for snakemake is unavailable',
      }),
    );

    render(<ExportModal workflow={workflow()} onClose={() => undefined} />);

    fireEvent.click(screen.getByRole('button', { name: 'SnakeMake' }));
    fireEvent.click(screen.getByRole('button', { name: 'Generate' }));

    await waitFor(() => {
      expect(screen.getByText('HTTP 500 Server Error (/api/workflow/export)')).toBeInTheDocument();
    });
    expect(screen.queryByRole('button', { name: 'Download' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Copy to clipboard' })).not.toBeInTheDocument();
    expect(screen.queryByDisplayValue(/"version": "2.0"/)).not.toBeInTheDocument();
  });
});
