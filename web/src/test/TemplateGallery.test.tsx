import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const apiMocks = vi.hoisted(() => ({
  apiGet: vi.fn(),
  apiPost: vi.fn(),
}));

const dialogMocks = vi.hoisted(() => ({
  promptDialog: vi.fn(),
}));

const loggingMock = vi.hoisted(() => ({
  logError: vi.fn(),
}));

vi.mock('../api/client', () => apiMocks);
vi.mock('../components/ui', () => dialogMocks);
vi.mock('../state/logging', () => loggingMock);

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

describe('TemplateGallery i18n', () => {
  beforeEach(() => {
    storage.clear();
    vi.stubGlobal('localStorage', localStorageStub);
    apiMocks.apiGet.mockReset();
    apiMocks.apiPost.mockReset();
    dialogMocks.promptDialog.mockReset();
    loggingMock.logError.mockReset();
  });

  afterEach(async () => {
    const { setLanguage } = await import('../i18n');
    await setLanguage('en');
    storage.clear();
    vi.unstubAllGlobals();
  });

  it('renders template gallery chrome and card actions from the active locale', async () => {
    const { default: TemplateGallery } = await import('../collab/TemplateGallery');
    const { setLanguage } = await import('../i18n');

    await setLanguage('es');
    apiMocks.apiGet.mockResolvedValue({
      templates: [
        {
          id: 'template-1',
          workflow_id: 'workflow-1',
          user_id: 'user-abc123',
          title: 'RNA QC',
          description: 'Quality control for reads',
          tags: 'rna, qc',
          is_public: true,
          fork_count: 4,
          created_at: new Date().toISOString(),
        },
      ],
      count: 1,
    });

    render(
      <TemplateGallery
        isOpen
        currentWorkflowId="workflow-1"
        onClose={() => undefined}
        onFork={() => undefined}
      />,
    );

    await waitFor(() => expect(screen.getByText('RNA QC')).toBeInTheDocument());

    expect(screen.getByText('Galeria de plantillas')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '+ Guardar' })).toBeInTheDocument();
    expect(screen.getByTitle('Cerrar galeria de plantillas')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('Buscar plantillas...')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Todas' })).toBeInTheDocument();
    expect(screen.getByText('ahora')).toBeInTheDocument();
    expect(screen.getByText('por user-abc')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Bifurcar' })).toBeInTheDocument();
  });

  it('uses localized save-template prompts and fallback save errors', async () => {
    const { default: TemplateGallery } = await import('../collab/TemplateGallery');
    const { setLanguage } = await import('../i18n');

    await setLanguage('es');
    apiMocks.apiGet.mockResolvedValue({ templates: [], count: 0 });
    apiMocks.apiPost.mockRejectedValue('save-failed');
    dialogMocks.promptDialog
      .mockResolvedValueOnce('Plantilla candidata')
      .mockResolvedValueOnce('Descripcion corta')
      .mockResolvedValueOnce('rna, qc');

    render(
      <TemplateGallery
        isOpen
        currentWorkflowId="workflow-1"
        onClose={() => undefined}
        onFork={() => undefined}
      />,
    );

    await waitFor(() => expect(screen.getByText('No se encontraron plantillas.')).toBeInTheDocument());
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: '+ Guardar' }));
    });

    await waitFor(() => expect(dialogMocks.promptDialog).toHaveBeenNthCalledWith(1, {
      title: 'Guardar plantilla',
      message: 'Nombra esta plantilla compartida de flujo de trabajo.',
      inputLabel: 'Titulo de plantilla',
      confirmLabel: 'Siguiente',
    }));
    expect(dialogMocks.promptDialog).toHaveBeenNthCalledWith(2, {
      title: 'Descripcion de plantilla',
      message: 'Agrega una descripcion breve para esta plantilla.',
      inputLabel: 'Descripcion',
      confirmLabel: 'Siguiente',
    });
    expect(dialogMocks.promptDialog).toHaveBeenNthCalledWith(3, {
      title: 'Etiquetas de plantilla',
      message: 'Agrega etiquetas separadas por comas.',
      inputLabel: 'Etiquetas',
      placeholder: 'rna, alineamiento, qc',
      confirmLabel: 'Guardar plantilla',
    });
    await waitFor(() => expect(screen.getByText('No se pudo guardar la plantilla')).toBeInTheDocument());
  });

  it('uses localized load and fork fallback errors', async () => {
    const { default: TemplateGallery } = await import('../collab/TemplateGallery');
    const { setLanguage } = await import('../i18n');

    await setLanguage('es');
    apiMocks.apiGet.mockRejectedValueOnce('load-failed');

    const { rerender } = render(
      <TemplateGallery
        isOpen
        currentWorkflowId="workflow-1"
        onClose={() => undefined}
        onFork={() => undefined}
      />,
    );

    await waitFor(() => expect(screen.getByText('No se pudieron cargar las plantillas')).toBeInTheDocument());

    apiMocks.apiGet.mockResolvedValue({
      templates: [
        {
          id: 'template-1',
          workflow_id: 'workflow-1',
          user_id: 'user-abc123',
          title: 'RNA QC',
          description: 'Quality control for reads',
          tags: 'rna, qc',
          is_public: true,
          fork_count: 4,
          created_at: new Date().toISOString(),
        },
      ],
      count: 1,
    });
    apiMocks.apiPost.mockRejectedValue('fork-failed');

    rerender(
      <TemplateGallery
        isOpen={false}
        currentWorkflowId="workflow-1"
        onClose={() => undefined}
        onFork={() => undefined}
      />,
    );
    rerender(
      <TemplateGallery
        isOpen
        currentWorkflowId="workflow-1"
        onClose={() => undefined}
        onFork={() => undefined}
      />,
    );

    await waitFor(() => expect(screen.getByText('RNA QC')).toBeInTheDocument());
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: 'Bifurcar' }));
    });

    await waitFor(() => expect(screen.getByText('No se pudo bifurcar')).toBeInTheDocument());
  });

  it('logs swallowed template API failures with stable scopes', async () => {
    const { default: TemplateGallery } = await import('../collab/TemplateGallery');
    const loadError = new Error('templates unavailable');
    const forkError = new Error('fork unavailable');
    const saveError = new Error('save unavailable');

    apiMocks.apiGet.mockRejectedValueOnce(loadError);

    const { rerender } = render(
      <TemplateGallery
        isOpen
        currentWorkflowId="workflow-1"
        onClose={() => undefined}
        onFork={() => undefined}
      />,
    );

    await waitFor(() => expect(loggingMock.logError).toHaveBeenCalledWith('collab.templateGallery.load', loadError));

    apiMocks.apiGet.mockResolvedValueOnce({
      templates: [
        {
          id: 'template-1',
          workflow_id: 'workflow-1',
          user_id: 'user-abc123',
          title: 'RNA QC',
          description: 'Quality control for reads',
          tags: 'rna, qc',
          is_public: true,
          fork_count: 4,
          created_at: new Date().toISOString(),
        },
      ],
      count: 1,
    });
    apiMocks.apiPost.mockRejectedValueOnce(forkError);

    rerender(
      <TemplateGallery
        isOpen={false}
        currentWorkflowId="workflow-1"
        onClose={() => undefined}
        onFork={() => undefined}
      />,
    );
    rerender(
      <TemplateGallery
        isOpen
        currentWorkflowId="workflow-1"
        onClose={() => undefined}
        onFork={() => undefined}
      />,
    );

    await waitFor(() => expect(screen.getByText('RNA QC')).toBeInTheDocument());
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: 'Fork' }));
    });
    await waitFor(() => expect(loggingMock.logError).toHaveBeenCalledWith('collab.templateGallery.fork', forkError));

    apiMocks.apiPost.mockRejectedValueOnce(saveError);
    dialogMocks.promptDialog
      .mockResolvedValueOnce('Candidate template')
      .mockResolvedValueOnce('Short description')
      .mockResolvedValueOnce('rna, qc');

    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: '+ Save' }));
    });

    await waitFor(() => expect(loggingMock.logError).toHaveBeenCalledWith('collab.templateGallery.save', saveError));
  });
});
