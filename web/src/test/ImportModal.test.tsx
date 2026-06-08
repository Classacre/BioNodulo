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

const dialogMocks = vi.hoisted(() => ({
  alertDialog: vi.fn(),
}));

const loggingMock = vi.hoisted(() => ({
  logError: vi.fn(),
}));

const pngMetadataMocks = vi.hoisted(() => ({
  extractWorkflowFromPng: vi.fn(),
}));

vi.mock('../components/ui', () => dialogMocks);
vi.mock('../state/logging', () => loggingMock);
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

function workflowJson(name: string): string {
  return JSON.stringify({
    version: '2.0',
    app: 'BioNodulo',
    name,
    description: '',
    nodes: [],
    edges: [],
    groups: [],
    outputs: {},
  });
}

describe('ImportModal i18n', () => {
  beforeEach(() => {
    storage.clear();
    apiMocks.apiPost.mockReset();
    dialogMocks.alertDialog.mockReset();
    loggingMock.logError.mockReset();
    pngMetadataMocks.extractWorkflowFromPng.mockReset();
    pngMetadataMocks.extractWorkflowFromPng.mockReturnValue(undefined);
    vi.stubGlobal('localStorage', localStorageStub);
  });

  afterEach(async () => {
    const { setLanguage } = await import('../i18n');
    await setLanguage('en');
    storage.clear();
    vi.unstubAllGlobals();
  });

  it('renders import chrome from the active locale and imports JSON workflows', async () => {
    const { default: ImportModal } = await import('../components/modals/ImportModal');
    const { setLanguage } = await import('../i18n');
    const onImport = vi.fn<(workflow: Workflow) => void>();
    const onClose = vi.fn();

    await setLanguage('es');

    render(<ImportModal onImport={onImport} onClose={onClose} />);

    expect(screen.getByRole('dialog', { name: 'Importar flujo de trabajo' })).toBeInTheDocument();
    expect(screen.getByText('Importar flujo de trabajo')).toBeInTheDocument();
    expect(screen.queryByRole('dialog', { name: 'Importar workflow' })).not.toBeInTheDocument();
    expect(screen.queryByText('Importar workflow')).not.toBeInTheDocument();
    expect(screen.getByText(/Pega codigo de flujo de trabajo arriba/)).toBeInTheDocument();
    expect(screen.queryByText(/Pega codigo de workflow arriba/)).not.toBeInTheDocument();
    expect(screen.queryByText(/metadatos de workflow incrustados/)).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Cancelar' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Importar' })).toBeDisabled();

    fireEvent.change(screen.getByPlaceholderText(/"version": "2.0"/), {
      target: { value: workflowJson('Imported workflow') },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Importar' }));

    await waitFor(() => expect(onClose).toHaveBeenCalledTimes(1));

    expect(onImport).toHaveBeenCalledTimes(1);
    expect(onImport.mock.calls[0][0].name).toBe('Imported workflow');
  });

  it('renders import format labels and placeholders from the active locale', async () => {
    const { default: ImportModal } = await import('../components/modals/ImportModal');
    const { setLanguage } = await import('../i18n');

    await setLanguage('es');

    render(<ImportModal onImport={() => undefined} onClose={() => undefined} />);

    expect(screen.getByRole('button', { name: 'JSON de BioNodulo' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'SnakeMake' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'NextFlow' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'CWL' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Galaxy (.ga)' })).toBeInTheDocument();
    expect(screen.getByPlaceholderText(/"version": "2.0"/)).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'SnakeMake' }));
    expect(screen.getByPlaceholderText(/regla ejemplo/)).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'NextFlow' }));
    expect(screen.getByPlaceholderText(/proceso alinear/)).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'CWL' }));
    expect(screen.getByPlaceholderText(/clase: Workflow/)).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Galaxy (.ga)' }));
    expect(screen.getByPlaceholderText(/"a_galaxy_workflow": "true"/)).toBeInTheDocument();
  });

  it('posts external workflow imports using the backend request contract', async () => {
    const { default: ImportModal } = await import('../components/modals/ImportModal');
    const onImport = vi.fn<(workflow: Workflow) => void>();
    const onClose = vi.fn();
    const snakefile = 'rule fastqc:\n    shell: "fastqc reads.fastq"';
    const importedWorkflow = {
      version: '2.0',
      app: 'bionodulo',
      name: 'Imported SnakeMake Workflow',
      description: '',
      nodes: [],
      edges: [],
      groups: [],
      outputs: {},
    } as Workflow;
    apiMocks.apiPost.mockResolvedValueOnce({ workflow: importedWorkflow });

    render(<ImportModal onImport={onImport} onClose={onClose} />);
    fireEvent.click(screen.getByRole('button', { name: 'SnakeMake' }));
    fireEvent.change(screen.getByPlaceholderText(/rule example/), {
      target: { value: snakefile },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Import' }));

    await waitFor(() => expect(onClose).toHaveBeenCalledTimes(1));

    expect(apiMocks.apiPost).toHaveBeenCalledWith('/workflow/import', {
      source: 'snakemake',
      content: snakefile,
    });
    expect(onImport).toHaveBeenCalledWith(importedWorkflow);
  });

  it('uses localized parse-format errors from the active locale', async () => {
    const { default: ImportModal } = await import('../components/modals/ImportModal');
    const { setLanguage } = await import('../i18n');
    const converterError = new apiMocks.ApiError('converter unavailable', 503, 'Unavailable', null);

    await setLanguage('es');
    apiMocks.apiPost.mockRejectedValueOnce(converterError);

    render(<ImportModal onImport={() => undefined} onClose={() => undefined} />);
    fireEvent.click(screen.getByRole('button', { name: 'SnakeMake' }));
    fireEvent.change(screen.getByPlaceholderText(/regla ejemplo/), {
      target: { value: 'not valid snakemake or json' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Importar' }));

    await waitFor(() => expect(dialogMocks.alertDialog).toHaveBeenCalledWith(
      'No se pudo analizar el flujo de trabajo. Asegurate de que el formato sea correcto.',
    ));
    expect(loggingMock.logError).toHaveBeenCalledWith('importModal.backendImport', converterError);
    expect(dialogMocks.alertDialog).not.toHaveBeenCalledWith(
      'No se pudo analizar el workflow. Asegurate de que el formato sea correcto.',
    );
  });

  it('uses localized PNG-without-workflow errors from the active locale', async () => {
    const { default: ImportModal } = await import('../components/modals/ImportModal');
    const { setLanguage } = await import('../i18n');

    await setLanguage('es');

    const { container } = render(<ImportModal onImport={() => undefined} onClose={() => undefined} />);
    const fileInput = container.querySelector('input[type="file"]') as HTMLInputElement;
    const file = new File([new Uint8Array([0, 1, 2, 3])], 'thumbnail.png', { type: 'image/png' });

    fireEvent.change(fileInput, { target: { files: [file] } });

    await waitFor(() => expect(dialogMocks.alertDialog).toHaveBeenCalledWith({
      title: 'No se encontro ningun flujo de trabajo',
      message: 'Este PNG no contiene un fragmento tEXt de flujo de trabajo de BioNodulo. Exporta con la opcion "PNG (flujo de trabajo incrustado)" para generar uno.',
    }));
    expect(dialogMocks.alertDialog).not.toHaveBeenCalledWith(expect.objectContaining({
      title: 'No se encontro ningun workflow',
    }));
    expect(loggingMock.logError).not.toHaveBeenCalled();
  });

  it('logs PNG workflow extraction failures while showing the generic alert', async () => {
    const { default: ImportModal } = await import('../components/modals/ImportModal');
    const extractionError = new Error('bad png metadata');
    pngMetadataMocks.extractWorkflowFromPng.mockImplementationOnce(() => {
      throw extractionError;
    });

    const { container } = render(<ImportModal onImport={() => undefined} onClose={() => undefined} />);
    const fileInput = container.querySelector('input[type="file"]') as HTMLInputElement;
    const file = new File([new Uint8Array([0, 1, 2, 3])], 'workflow.png', { type: 'image/png' });

    fireEvent.change(fileInput, { target: { files: [file] } });

    await waitFor(() => expect(dialogMocks.alertDialog).toHaveBeenCalledWith({
      title: 'PNG read failed',
      message: 'Could not read the workflow PNG. Export the workflow again or import the JSON file instead.',
    }));
    expect(loggingMock.logError).toHaveBeenCalledWith('importModal.pngRead', extractionError);
  });

  it('localizes PNG workflow extraction failures from the active locale', async () => {
    const { default: ImportModal } = await import('../components/modals/ImportModal');
    const { setLanguage } = await import('../i18n');
    const extractionError = new Error('bad png metadata');
    pngMetadataMocks.extractWorkflowFromPng.mockImplementationOnce(() => {
      throw extractionError;
    });

    await setLanguage('es');

    const { container } = render(<ImportModal onImport={() => undefined} onClose={() => undefined} />);
    const fileInput = container.querySelector('input[type="file"]') as HTMLInputElement;
    const file = new File([new Uint8Array([0, 1, 2, 3])], 'workflow.png', { type: 'image/png' });

    fireEvent.change(fileInput, { target: { files: [file] } });

    await waitFor(() => expect(dialogMocks.alertDialog).toHaveBeenCalledWith({
      title: 'No se pudo leer el PNG',
      message: 'No se pudo leer el PNG del flujo de trabajo. Exporta el flujo de trabajo de nuevo o importa el archivo JSON.',
    }));
    expect(dialogMocks.alertDialog).not.toHaveBeenCalledWith(expect.objectContaining({
      message: 'bad png metadata',
    }));
    expect(loggingMock.logError).toHaveBeenCalledWith('importModal.pngRead', extractionError);
  });

  it('uses the shared Dialog primitive for modal chrome', () => {
    const source = readFileSync(resolve(__dirname, '../components/modals/ImportModal.tsx'), 'utf8');

    expect(source).toContain("import Dialog from '../ui/Dialog';");
    expect(source).not.toContain("import { useFocusTrap } from '../../hooks/ui';");
    expect(source).not.toContain('<div className="modal-overlay"');
    expect(source).not.toContain('role="dialog"');
  });
});
