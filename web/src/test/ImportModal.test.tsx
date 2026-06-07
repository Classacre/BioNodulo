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

    expect(screen.getByRole('dialog', { name: 'Importar workflow' })).toBeInTheDocument();
    expect(screen.getByText('Importar workflow')).toBeInTheDocument();
    expect(screen.getByText(/Pega codigo de workflow arriba/)).toBeInTheDocument();
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
});
