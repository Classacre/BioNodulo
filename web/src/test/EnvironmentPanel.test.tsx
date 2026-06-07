import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('../components/ui', () => ({
  confirmDialog: vi.fn(async () => true),
}));

const loggingMock = vi.hoisted(() => ({
  logError: vi.fn(),
}));

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

const environmentsResponse = {
  environments: [
    {
      id: 'env-alpha-001',
      name: 'rna env',
      path: '/analysis/.bionodulo/envs/rna',
      package_count: 2,
      ready: true,
      status: 'ready',
      packages: [
        { name: 'fastqc', version: '0.12.1' },
        { name: 'multiqc', version: '1.22' },
      ],
    },
  ],
};

describe('EnvironmentPanel i18n', () => {
  let fetchSpy: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    storage.clear();
    vi.stubGlobal('localStorage', localStorageStub);
    loggingMock.logError.mockReset();
    fetchSpy = vi.spyOn(globalThis, 'fetch').mockImplementation(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = typeof input === 'string' ? input : input.toString();
      const method = init?.method || 'GET';

      if (url.includes('/api/manager/environments') && method === 'GET') {
        return new Response(JSON.stringify(environmentsResponse), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        });
      }

      if (url.includes('/api/manager/environments/env-alpha-001/duplicate')) {
        return new Response(JSON.stringify({}), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        });
      }

      if (url.includes('/api/manager/environments/env-alpha-001/packages/fastqc/remove')) {
        return new Response(JSON.stringify({}), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        });
      }

      return new Response(JSON.stringify({ detail: 'unexpected request' }), {
        status: 500,
        headers: { 'Content-Type': 'application/json' },
      });
    });
  });

  afterEach(async () => {
    const { setLanguage } = await import('../i18n');
    await setLanguage('en');
    storage.clear();
    vi.unstubAllGlobals();
    fetchSpy.mockRestore();
  });

  it('renders environment controls and package actions from the active locale', async () => {
    const { default: EnvironmentPanel } = await import('../components/panels/EnvironmentPanel');
    const { confirmDialog } = await import('../components/ui');
    const { setLanguage } = await import('../i18n');

    await setLanguage('es');

    render(<EnvironmentPanel onClose={() => undefined} />);

    await waitFor(() => expect(screen.getByText('rna env')).toBeInTheDocument());

    expect(screen.getByText('Entornos')).toBeInTheDocument();
    expect(screen.getByTitle('Cerrar')).toBeInTheDocument();

    fireEvent.click(screen.getByTitle('Mostrar paquetes'));

    expect(screen.getByText('2 paquetes')).toBeInTheDocument();
    expect(screen.getByTitle('Contraer paquetes')).toBeInTheDocument();
    expect(screen.getByTitle('Opciones')).toBeInTheDocument();
    expect(screen.getByTitle('Eliminar fastqc')).toBeInTheDocument();

    fireEvent.click(screen.getByTitle('Opciones'));

    expect(screen.getByText('Renombrar')).toBeInTheDocument();
    expect(screen.getByText('Duplicar')).toBeInTheDocument();
    expect(screen.getByText('Eliminar')).toBeInTheDocument();

    fireEvent.click(screen.getByText('Duplicar'));

    await waitFor(() => expect(screen.getByText("Duplicado 'rna env'")).toBeInTheDocument());

    fireEvent.click(screen.getByTitle('Eliminar fastqc'));

    await waitFor(() => {
      expect(vi.mocked(confirmDialog)).toHaveBeenCalledWith(expect.objectContaining({
        title: 'Eliminar paquete?',
        message: "Eliminar paquete 'fastqc' del entorno 'rna env'?",
        confirmLabel: 'Eliminar',
      }));
    });

    await waitFor(() => expect(screen.getByText("Eliminado 'fastqc'")).toBeInTheDocument());
  });

  it('renders localized empty and loading states', async () => {
    let resolveFetch: (response: Response) => void = () => undefined;
    fetchSpy.mockImplementation(async () => new Promise<Response>((resolve) => {
      resolveFetch = resolve;
    }));

    const { default: EnvironmentPanel } = await import('../components/panels/EnvironmentPanel');
    const { setLanguage } = await import('../i18n');

    await setLanguage('es');

    render(<EnvironmentPanel onClose={() => undefined} />);

    expect(await screen.findByText('Cargando entornos...')).toBeInTheDocument();

    await act(async () => {
      resolveFetch(new Response(JSON.stringify({ environments: [] }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }));
    });

    await waitFor(() => {
      const emptyState = screen.getByText(/No hay entornos todavia/);
      expect(emptyState).toHaveTextContent('No hay entornos todavia.Ejecuta un flujo de trabajo para crear uno.');
      expect(emptyState).not.toHaveTextContent('Ejecuta un workflow para crear uno.');
    });
  });

  it('logs swallowed environment API failures with stable scopes', async () => {
    const { default: EnvironmentPanel } = await import('../components/panels/EnvironmentPanel');
    const { confirmDialog } = await import('../components/ui');

    const queueFetches = (failure: { method: string; path: string; error: Error }) => {
      fetchSpy.mockImplementation(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = typeof input === 'string' ? input : input.toString();
        const method = init?.method || 'GET';
        if (method === failure.method && url.includes(failure.path)) throw failure.error;
        if (url.includes('/api/manager/environments') && method === 'GET') {
          return new Response(JSON.stringify(environmentsResponse), {
            status: 200,
            headers: { 'Content-Type': 'application/json' },
          });
        }
        return new Response(JSON.stringify({ detail: 'unexpected request' }), {
          status: 500,
          headers: { 'Content-Type': 'application/json' },
        });
      });
    };

    const loadError = new Error('environment load failed');
    fetchSpy.mockRejectedValueOnce(loadError);
    const loadView = render(<EnvironmentPanel onClose={() => undefined} />);
    await waitFor(() => expect(loggingMock.logError).toHaveBeenCalledWith('environment.list.load', loadError));
    loadView.unmount();

    const renameError = new Error('rename failed');
    queueFetches({ method: 'POST', path: '/api/manager/environments/env-alpha-001/rename', error: renameError });
    const renameView = render(<EnvironmentPanel onClose={() => undefined} />);
    await waitFor(() => expect(screen.getByText('rna env')).toBeInTheDocument());
    fireEvent.click(screen.getByTitle('Options'));
    fireEvent.click(screen.getByText('Rename'));
    await waitFor(() => expect(screen.getByDisplayValue('rna env')).toBeInTheDocument());
    fireEvent.change(screen.getByDisplayValue('rna env'), { target: { value: 'renamed env' } });
    fireEvent.keyDown(screen.getByDisplayValue('renamed env'), { key: 'Enter' });
    await waitFor(() => expect(loggingMock.logError).toHaveBeenCalledWith('environment.rename', renameError));
    expect(screen.getByText('Network error')).toBeInTheDocument();
    renameView.unmount();

    const deleteError = new Error('delete failed');
    queueFetches({ method: 'DELETE', path: '/api/manager/environments/env-alpha-001', error: deleteError });
    const deleteView = render(<EnvironmentPanel onClose={() => undefined} />);
    await waitFor(() => expect(screen.getByText('rna env')).toBeInTheDocument());
    fireEvent.click(screen.getByTitle('Options'));
    fireEvent.click(screen.getByText('Delete'));
    await waitFor(() => expect(vi.mocked(confirmDialog)).toHaveBeenCalled());
    await waitFor(() => expect(loggingMock.logError).toHaveBeenCalledWith('environment.delete', deleteError));
    deleteView.unmount();

    const duplicateError = new Error('duplicate failed');
    queueFetches({ method: 'POST', path: '/api/manager/environments/env-alpha-001/duplicate', error: duplicateError });
    const duplicateView = render(<EnvironmentPanel onClose={() => undefined} />);
    await waitFor(() => expect(screen.getByText('rna env')).toBeInTheDocument());
    fireEvent.click(screen.getByTitle('Options'));
    fireEvent.click(screen.getByText('Duplicate'));
    await waitFor(() => expect(loggingMock.logError).toHaveBeenCalledWith('environment.duplicate', duplicateError));
    duplicateView.unmount();

    const packageError = new Error('package removal failed');
    queueFetches({
      method: 'POST',
      path: '/api/manager/environments/env-alpha-001/packages/fastqc/remove',
      error: packageError,
    });
    const packageView = render(<EnvironmentPanel onClose={() => undefined} />);
    await waitFor(() => expect(screen.getByText('rna env')).toBeInTheDocument());
    fireEvent.click(screen.getByTitle('Show packages'));
    fireEvent.click(screen.getByTitle('Remove fastqc'));
    await waitFor(() => expect(loggingMock.logError).toHaveBeenCalledWith('environment.package.remove', packageError));
    packageView.unmount();
  });
});
