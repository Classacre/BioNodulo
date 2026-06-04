import { render, screen, waitFor } from '@testing-library/react';
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

vi.mock('../api/client', () => apiMocks);
vi.mock('../components/ui', () => dialogMocks);

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
});
