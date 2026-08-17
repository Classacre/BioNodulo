import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
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

const loggingMock = vi.hoisted(() => ({
  logError: vi.fn(),
}));

vi.mock('../state/logging', () => loggingMock);

const utilsMocks = vi.hoisted(() => ({
  saveToFile: vi.fn(),
}));

const thumbnailMocks = vi.hoisted(() => ({
  renderWorkflowThumbnailPng: vi.fn(async () => 'data:image/png;base64,dGh1bWI='),
}));

const pngMetadataMocks = vi.hoisted(() => ({
  embedWorkflowInPngDataUrl: vi.fn(() => new Blob(['png'], { type: 'image/png' })),
}));

vi.mock('../utils', async importOriginal => {
  const actual = await importOriginal<typeof import('../utils')>();
  return {
    ...actual,
    saveToFile: utilsMocks.saveToFile,
  };
});

vi.mock('../utils/workflowThumbnail', () => thumbnailMocks);
vi.mock('../utils/pngMetadata', () => pngMetadataMocks);

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
    loggingMock.logError.mockReset();
    utilsMocks.saveToFile.mockReset();
    thumbnailMocks.renderWorkflowThumbnailPng.mockClear();
    pngMetadataMocks.embedWorkflowInPngDataUrl.mockReset();
    pngMetadataMocks.embedWorkflowInPngDataUrl.mockReturnValue(new Blob(['png'], { type: 'image/png' }));
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

    expect(screen.getByRole('dialog', { name: 'Exportar flujo de trabajo' })).toBeInTheDocument();
    expect(screen.getByText('Exportar flujo de trabajo')).toBeInTheDocument();
    expect(screen.queryByRole('dialog', { name: 'Exportar workflow' })).not.toBeInTheDocument();
    expect(screen.queryByText('Exportar workflow')).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'PNG / JSON' })).toHaveClass('active');
    expect(screen.queryByRole('button', { name: 'PNG (flujo de trabajo incrustado)' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'JSON de BioNodulo' })).not.toBeInTheDocument();
    expect(screen.getByText('El PNG lleva el JSON completo del flujo de trabajo en un fragmento tEXt; arrastralo de vuelta al lienzo para restaurar el grafo.')).toBeInTheDocument();
    expect(screen.queryByText('El PNG lleva el JSON completo del workflow en un fragmento tEXt; arrastralo de vuelta al lienzo para restaurar el grafo.')).not.toBeInTheDocument();
    expect(screen.getByLabelText('Fondo transparente')).toBeInTheDocument();
    expect(screen.getByText('Resolucion')).toBeInTheDocument();
    expect(screen.getByLabelText('Solo JSON (omitir contenedor PNG)')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Renderizar miniatura' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Cerrar' })).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Renderizar miniatura' }));
    await waitFor(() => expect(screen.getByRole('img', { name: 'Vista previa de miniatura del flujo de trabajo' })).toBeInTheDocument());
    expect(screen.queryByRole('img', { name: 'Vista previa de miniatura del workflow' })).not.toBeInTheDocument();

    fireEvent.click(screen.getByLabelText('Solo JSON (omitir contenedor PNG)'));

    await waitFor(() => expect(screen.getByRole('button', { name: 'Descargar' })).toBeInTheDocument());
    expect(screen.getByRole('button', { name: 'Copiar al portapapeles' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Regenerar' })).toBeInTheDocument();
    expect(screen.queryByRole('img', { name: 'Vista previa de miniatura del flujo de trabajo' })).not.toBeInTheDocument();
    expect(apiMocks.apiPost).not.toHaveBeenCalled();
  });

  it('uses the active locale for unnamed workflow download filenames', async () => {
    const { default: ExportModal } = await import('../components/modals/ExportModal');
    const { setLanguage } = await import('../i18n');

    await setLanguage('es');

    render(<ExportModal workflow={workflow({ name: '' })} onClose={() => undefined} />);

    fireEvent.click(screen.getByLabelText('Solo JSON (omitir contenedor PNG)'));

    await waitFor(() => expect(screen.getByRole('button', { name: 'Descargar' })).toBeInTheDocument());

    fireEvent.click(screen.getByRole('button', { name: 'Descargar' }));

    expect(utilsMocks.saveToFile).toHaveBeenCalledWith(
      expect.stringContaining('"version": "2.0"'),
      'workflow-sin-titulo.json',
      'application/json',
    );
  });

  it('localizes PNG thumbnail render failures', async () => {
    const { default: ExportModal } = await import('../components/modals/ExportModal');
    const { setLanguage } = await import('../i18n');
    const error = new Error('Canvas 2D context unavailable');
    thumbnailMocks.renderWorkflowThumbnailPng.mockRejectedValueOnce(error);

    await setLanguage('es');

    render(<ExportModal workflow={workflow()} onClose={() => undefined} />);

    fireEvent.click(screen.getByRole('button', { name: 'Renderizar miniatura' }));

    await waitFor(() => {
      expect(screen.getByText('No se pudo renderizar la miniatura del flujo de trabajo')).toBeInTheDocument();
    });
    expect(screen.queryByText('Canvas 2D context unavailable')).not.toBeInTheDocument();
    expect(loggingMock.logError).toHaveBeenCalledWith('exportModal.generate', error);
  });

  it('shows export API errors without generating fallback downloadable content', async () => {
    const { default: ExportModal } = await import('../components/modals/ExportModal');
    const exportError = new apiMocks.ApiError('HTTP 500 Server Error (/api/workflow/export)', 500, 'Server Error', {
      detail: 'Converter for snakemake is unavailable',
    });
    apiMocks.apiPost.mockRejectedValueOnce(exportError);

    render(<ExportModal workflow={workflow()} onClose={() => undefined} />);

    fireEvent.click(screen.getByRole('button', { name: 'SnakeMake' }));
    fireEvent.click(screen.getByRole('button', { name: 'Generate' }));

    await waitFor(() => {
      expect(screen.getByText('HTTP 500 Server Error (/api/workflow/export)')).toBeInTheDocument();
    });
    expect(loggingMock.logError).toHaveBeenCalledWith('exportModal.generate', exportError);
    expect(screen.queryByRole('button', { name: 'Download' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Copy to clipboard' })).not.toBeInTheDocument();
    expect(screen.queryByDisplayValue(/"version": "2.0"/)).not.toBeInTheDocument();
  });

  it('logs PNG download embedding failures while preserving the inline error', async () => {
    const { default: ExportModal } = await import('../components/modals/ExportModal');
    const { setLanguage } = await import('../i18n');
    const downloadError = new Error('metadata write failed');
    pngMetadataMocks.embedWorkflowInPngDataUrl.mockImplementationOnce(() => {
      throw downloadError;
    });

    await setLanguage('es');

    render(<ExportModal workflow={workflow()} onClose={() => undefined} />);

    fireEvent.click(screen.getByRole('button', { name: 'Renderizar miniatura' }));
    await waitFor(() => expect(screen.getByRole('img', { name: 'Vista previa de miniatura del flujo de trabajo' })).toBeInTheDocument());

    fireEvent.click(screen.getByRole('button', { name: 'Descargar PNG' }));

    expect(await screen.findByText('No se pudieron incrustar los metadatos del flujo de trabajo en el PNG')).toBeInTheDocument();
    expect(screen.queryByText('metadata write failed')).not.toBeInTheDocument();
    expect(loggingMock.logError).toHaveBeenCalledWith('exportModal.downloadPng', downloadError);
  });

  it('renders the references tab and generates RIS automatically on open', async () => {
    const { default: ExportModal } = await import('../components/modals/ExportModal');
    const risContent = 'TY  - JOUR\nTI  - A genome-scan method\nER  - \n';
    apiMocks.apiPost.mockResolvedValueOnce({ format: 'ris', content: risContent });

    render(<ExportModal workflow={workflow()} onClose={() => undefined} />);

    fireEvent.click(screen.getByRole('button', { name: 'References' }));

    await waitFor(() => expect(apiMocks.apiPost).toHaveBeenCalledWith('/workflow/export', {
      workflow: expect.objectContaining({ name: 'Export example' }),
      format: 'ris',
    }));
    await waitFor(() => expect(screen.getByRole('textbox')).toHaveValue(risContent));

    fireEvent.click(screen.getByRole('button', { name: 'Download' }));

    expect(utilsMocks.saveToFile).toHaveBeenCalledWith(
      risContent,
      'Export example.ris',
      'application/x-research-info-systems',
    );
  });

  it('regenerates references when the sub-format switches', async () => {
    const { default: ExportModal } = await import('../components/modals/ExportModal');
    apiMocks.apiPost
      .mockResolvedValueOnce({ format: 'ris', content: 'TY  - JOUR\n' })
      .mockResolvedValueOnce({ format: 'bibtex', content: '@misc{bionodulo_ab12cd34,\n}' })
      .mockResolvedValueOnce({ format: 'csv', content: 'node_id\n' });

    render(<ExportModal workflow={workflow()} onClose={() => undefined} />);

    fireEvent.click(screen.getByRole('button', { name: 'References' }));
    await waitFor(() => expect(screen.getByRole('textbox')).toHaveValue('TY  - JOUR\n'));

    fireEvent.click(screen.getByRole('button', { name: 'BibTeX' }));
    await waitFor(() => expect(apiMocks.apiPost).toHaveBeenCalledWith('/workflow/export', {
      workflow: expect.anything(),
      format: 'bibtex',
    }));
    await waitFor(() => expect(screen.getByRole('textbox')).toHaveValue('@misc{bionodulo_ab12cd34,\n}'));

    fireEvent.click(screen.getByRole('button', { name: 'CSV' }));
    await waitFor(() => expect(apiMocks.apiPost).toHaveBeenCalledWith('/workflow/export', {
      workflow: expect.anything(),
      format: 'csv',
    }));
    await waitFor(() => expect(screen.getByRole('textbox')).toHaveValue('node_id\n'));

    fireEvent.click(screen.getByRole('button', { name: 'Download' }));

    expect(utilsMocks.saveToFile).toHaveBeenCalledWith(
      'node_id\n',
      'Export example.csv',
      'text/csv',
    );
  });

  it('shows a friendly empty state when the references export has no content', async () => {
    const { default: ExportModal } = await import('../components/modals/ExportModal');
    apiMocks.apiPost.mockResolvedValueOnce({ format: 'ris', content: '' });

    render(<ExportModal workflow={workflow()} onClose={() => undefined} />);

    fireEvent.click(screen.getByRole('button', { name: 'References' }));

    await waitFor(() => {
      expect(screen.getByText('No references found: none of the nodes in this workflow declares citation metadata.')).toBeInTheDocument();
    });
    expect(screen.queryByRole('button', { name: 'Download' })).not.toBeInTheDocument();
    expect(screen.queryByRole('textbox')).not.toBeInTheDocument();
  });

  it('keeps ExportModal on the shared Dialog primitive', () => {
    const source = readFileSync(resolve(__dirname, '../components/modals/ExportModal.tsx'), 'utf8');

    expect(source).toContain("import Dialog from '../ui/Dialog';");
    expect(source).toContain('<Dialog');
    expect(source).not.toContain("import { useFocusTrap } from '../../hooks/ui';");
    expect(source).not.toContain('<div className="modal-overlay"');
    expect(source).not.toContain('role="dialog"');
  });
});
