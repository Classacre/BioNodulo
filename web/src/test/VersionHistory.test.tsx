import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const apiMocks = vi.hoisted(() => ({
  apiDelete: vi.fn(),
  apiGet: vi.fn(),
  apiPost: vi.fn(),
}));

const dialogMocks = vi.hoisted(() => ({
  confirmDialog: vi.fn(),
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

describe('VersionHistory i18n', () => {
  beforeEach(() => {
    storage.clear();
    vi.stubGlobal('localStorage', localStorageStub);
    apiMocks.apiDelete.mockReset();
    apiMocks.apiGet.mockReset();
    apiMocks.apiPost.mockReset();
    dialogMocks.confirmDialog.mockReset();
    dialogMocks.promptDialog.mockReset();
    loggingMock.logError.mockReset();
  });

  afterEach(async () => {
    const { setLanguage } = await import('../i18n');
    await setLanguage('en');
    storage.clear();
    vi.unstubAllGlobals();
  });

  it('renders version history chrome and version rows from the active locale', async () => {
    const { default: VersionHistory } = await import('../collab/VersionHistory');
    const { setLanguage } = await import('../i18n');

    await setLanguage('es');
    apiMocks.apiGet.mockResolvedValue({
      versions: [
        {
          id: 'version-1',
          workflow_id: 'workflow-1',
          user_id: 'user-1',
          user_name: 'Mika',
          name: null,
          auto_save: true,
          node_count: 2,
          edge_count: 3,
          created_at: new Date().toISOString(),
        },
      ],
      count: 1,
    });

    render(
      <VersionHistory
        workflowId="workflow-1"
        isOpen
        onClose={() => undefined}
        onRestore={() => undefined}
      />,
    );

    await waitFor(() => expect(screen.getByText('Guardado automatico #1')).toBeInTheDocument());

    expect(screen.getByText('Historial de versiones')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '+ Guardar' })).toBeInTheDocument();
    expect(screen.getByTitle('Cerrar')).toBeInTheDocument();
    expect(screen.getByTitle('Guardado automatico')).toBeInTheDocument();
    expect(screen.getByText('Guardado automatico #1')).toBeInTheDocument();
    expect(screen.getByText(/ahora/)).toBeInTheDocument();
    expect(screen.getByText(/2 nodos, 3 enlaces/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Restaurar' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Eliminar' })).toBeInTheDocument();
  });

  it('uses localized save prompt labels and fallback errors', async () => {
    const { default: VersionHistory } = await import('../collab/VersionHistory');
    const { setLanguage } = await import('../i18n');

    await setLanguage('es');
    const saveError = new Error('version save failed');
    apiMocks.apiGet.mockResolvedValue({ versions: [], count: 0 });
    apiMocks.apiPost.mockRejectedValue(saveError);
    dialogMocks.promptDialog.mockResolvedValue('Version candidata');

    render(
      <VersionHistory
        workflowId="workflow-1"
        isOpen
        onClose={() => undefined}
        onRestore={() => undefined}
      />,
    );

    await waitFor(() => expect(screen.getByText('No hay versiones guardadas todavia.')).toBeInTheDocument());
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: '+ Guardar' }));
    });

    await waitFor(() => expect(dialogMocks.promptDialog).toHaveBeenCalledWith({
      title: 'Guardar version',
      message: 'Nombra esta version del flujo de trabajo.',
      inputLabel: 'Nombre de version',
      placeholder: 'Opcional',
      confirmLabel: 'Guardar version',
    }));
    await waitFor(() => expect(screen.getByText('No se pudo guardar la version')).toBeInTheDocument());
    expect(screen.queryByText('version save failed')).not.toBeInTheDocument();
    expect(loggingMock.logError).toHaveBeenCalledWith('collab.versionHistory.save', saveError);
  });

  it('uses localized restore and delete confirmations with fallback errors', async () => {
    const { default: VersionHistory } = await import('../collab/VersionHistory');
    const { setLanguage } = await import('../i18n');

    await setLanguage('es');
    const restoreError = new Error('version restore failed');
    const deleteError = new Error('version delete failed');
    apiMocks.apiGet.mockResolvedValue({
      versions: [
        {
          id: 'version-1',
          workflow_id: 'workflow-1',
          user_id: 'user-1',
          user_name: 'Mika',
          name: 'Manual',
          auto_save: false,
          node_count: 2,
          edge_count: 3,
          created_at: new Date().toISOString(),
        },
      ],
      count: 1,
    });
    apiMocks.apiPost.mockRejectedValue(restoreError);
    apiMocks.apiDelete.mockRejectedValue(deleteError);
    dialogMocks.confirmDialog.mockResolvedValue(true);

    render(
      <VersionHistory
        workflowId="workflow-1"
        isOpen
        onClose={() => undefined}
        onRestore={() => undefined}
      />,
    );

    await waitFor(() => expect(screen.getByText('Manual')).toBeInTheDocument());

    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: 'Restaurar' }));
    });
    await waitFor(() => expect(dialogMocks.confirmDialog).toHaveBeenCalledWith({
      title: 'Restaurar version?',
      message: 'Restaurar esta version? Esto creara una nueva rama del flujo de trabajo actual.',
      confirmLabel: 'Restaurar',
      tone: 'warning',
    }));
    await waitFor(() => expect(screen.getByText('No se pudo restaurar la version')).toBeInTheDocument());
    expect(screen.queryByText('version restore failed')).not.toBeInTheDocument();
    expect(loggingMock.logError).toHaveBeenCalledWith('collab.versionHistory.restore', restoreError);

    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: 'Eliminar' }));
    });
    await waitFor(() => expect(dialogMocks.confirmDialog).toHaveBeenCalledWith({
      title: 'Eliminar version?',
      message: 'Eliminar esta version?',
      confirmLabel: 'Eliminar',
      tone: 'danger',
    }));
    await waitFor(() => expect(screen.getByText('No se pudo eliminar la version')).toBeInTheDocument());
    expect(screen.queryByText('version delete failed')).not.toBeInTheDocument();
    expect(loggingMock.logError).toHaveBeenCalledWith('collab.versionHistory.delete', deleteError);
  });

  it('logs swallowed version-history load and diff failures with stable scopes', async () => {
    const { default: VersionHistory } = await import('../collab/VersionHistory');
    const { setLanguage } = await import('../i18n');

    await setLanguage('es');
    const loadError = new Error('version load failed');
    const diffError = new Error('diff failed');

    apiMocks.apiGet.mockRejectedValueOnce(loadError);
    const loadView = render(
      <VersionHistory
        workflowId="workflow-1"
        isOpen
        onClose={() => undefined}
        onRestore={() => undefined}
      />,
    );

    await waitFor(() => expect(loggingMock.logError).toHaveBeenCalledWith('collab.versionHistory.load', loadError));
    expect(screen.getByText('No se pudieron cargar las versiones')).toBeInTheDocument();
    expect(screen.queryByText('version load failed')).not.toBeInTheDocument();
    loadView.unmount();

    apiMocks.apiGet
      .mockResolvedValueOnce({
        versions: [
          {
            id: 'version-new',
            workflow_id: 'workflow-1',
            user_id: 'user-1',
            user_name: 'Mika',
            name: 'New',
            auto_save: false,
            node_count: 2,
            edge_count: 3,
            created_at: new Date().toISOString(),
          },
          {
            id: 'version-old',
            workflow_id: 'workflow-1',
            user_id: 'user-1',
            user_name: 'Mika',
            name: 'Old',
            auto_save: false,
            node_count: 1,
            edge_count: 2,
            created_at: new Date(Date.now() - 60_000).toISOString(),
          },
        ],
        count: 2,
      })
      .mockRejectedValueOnce(diffError);

    render(
      <VersionHistory
        workflowId="workflow-1"
        isOpen
        onClose={() => undefined}
        onRestore={() => undefined}
      />,
    );

    await waitFor(() => expect(screen.getByText('New')).toBeInTheDocument());
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: 'Diferencias' }));
    });

    await waitFor(() => expect(loggingMock.logError).toHaveBeenCalledWith('collab.versionHistory.diff', diffError));
    expect(screen.getByText('No se pudieron cargar las diferencias')).toBeInTheDocument();
    expect(screen.queryByText('diff failed')).not.toBeInTheDocument();
  });

  it('uses a localized auto-save fallback name in the diff modal', async () => {
    const { default: VersionHistory } = await import('../collab/VersionHistory');
    const { setLanguage } = await import('../i18n');

    await setLanguage('es');
    apiMocks.apiGet
      .mockResolvedValueOnce({
        versions: [
          {
            id: 'version-new',
            workflow_id: 'workflow-1',
            user_id: 'user-1',
            user_name: 'Mika',
            name: null,
            auto_save: true,
            node_count: 2,
            edge_count: 3,
            created_at: new Date().toISOString(),
          },
          {
            id: 'version-old',
            workflow_id: 'workflow-1',
            user_id: 'user-1',
            user_name: 'Mika',
            name: null,
            auto_save: true,
            node_count: 1,
            edge_count: 2,
            created_at: new Date(Date.now() - 60_000).toISOString(),
          },
        ],
        count: 2,
      })
      .mockResolvedValueOnce({
        nodes: { added: [], removed: [], modified: [] },
        edges: { added: [], removed: [], modified: [] },
        groups: { added: [], removed: [], modified: [] },
        meta_changes: {},
      });

    render(
      <VersionHistory
        workflowId="workflow-1"
        isOpen
        onClose={() => undefined}
        onRestore={() => undefined}
      />,
    );

    await waitFor(() => expect(screen.getByText('Guardado automatico #2')).toBeInTheDocument());
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: 'Diferencias' }));
    });

    await waitFor(() => expect(screen.getByText('Diferencias de versiones')).toBeInTheDocument());
    expect(screen.getAllByText(/Guardado automatico/).length).toBeGreaterThanOrEqual(2);
    expect(screen.queryByRole('button', { name: 'Diff' })).not.toBeInTheDocument();
    expect(screen.queryByText('Diff de versiones')).not.toBeInTheDocument();
    expect(screen.queryAllByText(/Auto-save/)).toHaveLength(0);
  });
});
