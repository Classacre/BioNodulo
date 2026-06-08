import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const dialogMocks = vi.hoisted(() => ({
  alertDialog: vi.fn(),
}));

const loggingMock = vi.hoisted(() => ({
  logError: vi.fn(),
}));

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

describe('WorkspacePanel i18n', () => {
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
      if (url.includes('/api/workspace/root')) {
        return new Response(JSON.stringify({ root: '/analysis' }), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        });
      }
      if (url.includes('/api/workspace/files')) {
        return new Response(JSON.stringify({
          path: '/',
          entries: [
            { name: 'reads', path: '/reads', type: 'directory' },
            { name: 'workflow.json', path: '/workflow.json', type: 'file', size: 2048 },
            { name: 'sample.fastq', path: '/sample.fastq', type: 'file', size: 512 },
          ],
        }), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        });
      }
      if (url.includes('/api/workspace/file')) {
        return new Response('{not valid json', {
          status: 200,
          headers: { 'Content-Type': 'text/plain' },
        });
      }
      return new Response('{}', {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      });
    });
    loggingMock.logError.mockReset();
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

  it('renders root controls and file list labels from the active locale', async () => {
    const { default: WorkspacePanel } = await import('../components/panels/WorkspacePanel');
    const { setLanguage } = await import('../i18n');

    await setLanguage('es');

    render(
      <WorkspacePanel
        onClose={() => undefined}
        onOpenSettings={() => undefined}
        onImportWorkflow={() => undefined}
      />,
    );

    await waitFor(() => expect(screen.getByText('workflow.json')).toBeInTheDocument());

    expect(screen.getByText('Espacio de trabajo')).toBeInTheDocument();
    expect(screen.getByText('Raiz del espacio de trabajo')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('/ruta/al/espacio')).toBeInTheDocument();
    expect(screen.getByText('2,0 KB')).toBeInTheDocument();
    expect(screen.queryByText('2.0 KB')).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Definir' })).toHaveAttribute('title', 'Definir raiz del espacio de trabajo');
    expect(screen.getByRole('button', { name: 'Predeterminado' })).toHaveAttribute('title', 'Recargar raiz actual');
    expect(screen.getByTitle('Abrir ajustes')).toBeInTheDocument();

    expect(screen.getByText('reads').closest('.workspace-file-row')).toHaveAttribute('title', 'Doble clic para abrir');
    expect(screen.getByText('workflow.json').closest('.workspace-file-row')).toHaveAttribute(
      'title',
      'Doble clic para previsualizar; arrastra al lienzo para importar',
    );
    expect(screen.getByText('sample.fastq').closest('.workspace-file-row')).toHaveAttribute(
      'title',
      'Doble clic para previsualizar; arrastra al lienzo para agregar como entrada',
    );

    fireEvent.click(screen.getByText('workflow.json'));

    expect(screen.getByText('1 seleccionado')).toBeInTheDocument();

    fireEvent.doubleClick(screen.getByText('workflow.json'));

    expect(await screen.findByRole('button', { name: 'Cargar como flujo de trabajo' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Cargar como workflow' })).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Cargar como flujo de trabajo' }));

    await waitFor(() => expect(dialogMocks.alertDialog).toHaveBeenCalledWith('JSON de flujo de trabajo no valido'));
    expect(dialogMocks.alertDialog).not.toHaveBeenCalledWith('JSON de workflow no valido');
  });

  it('logs swallowed workspace load failures with stable scopes', async () => {
    const { default: WorkspacePanel } = await import('../components/panels/WorkspacePanel');
    const rootError = new TypeError('root unavailable');
    const filesError = new TypeError('files unavailable');

    fetchSpy.mockImplementation(async (input: RequestInfo | URL) => {
      const url = typeof input === 'string' ? input : input.toString();
      if (url.includes('/api/workspace/root')) throw rootError;
      if (url.includes('/api/workspace/files')) throw filesError;
      return new Response('{}', {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      });
    });

    render(<WorkspacePanel onClose={() => undefined} />);

    await waitFor(() => expect(loggingMock.logError).toHaveBeenCalledWith('workspace.root.load', rootError));
    expect(loggingMock.logError).toHaveBeenCalledWith('workspace.files.load', filesError);
    expect(screen.getByText('No files in this directory')).toBeInTheDocument();
  });

  it('logs workspace root change and preview failures with stable scopes', async () => {
    const { default: WorkspacePanel } = await import('../components/panels/WorkspacePanel');

    fetchSpy.mockImplementation(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = typeof input === 'string' ? input : input.toString();
      if (url.includes('/api/workspace/root') && init?.method === 'POST') {
        return new Response(JSON.stringify({ detail: 'denied' }), {
          status: 400,
          statusText: 'Bad Request',
          headers: { 'Content-Type': 'application/json' },
        });
      }
      if (url.includes('/api/workspace/root')) {
        return new Response(JSON.stringify({ root: '/analysis' }), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        });
      }
      if (url.includes('/api/workspace/files')) {
        return new Response(JSON.stringify({
          path: '/',
          entries: [{ name: 'sample.fastq', path: '/sample.fastq', type: 'file', size: 512 }],
        }), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        });
      }
      if (url.includes('/api/workspace/file')) {
        return new Response('missing', {
          status: 404,
          statusText: 'Not Found',
          headers: { 'Content-Type': 'text/plain' },
        });
      }
      return new Response('{}', {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      });
    });

    render(<WorkspacePanel onClose={() => undefined} />);

    await waitFor(() => expect(screen.getByText('sample.fastq')).toBeInTheDocument());

    fireEvent.change(screen.getByPlaceholderText('/path/to/workspace'), { target: { value: '/restricted' } });
    fireEvent.click(screen.getByRole('button', { name: 'Set' }));

    await waitFor(() => expect(loggingMock.logError).toHaveBeenCalledWith('workspace.root.change', expect.any(Error)));
    expect(screen.getByText('Failed to change workspace: denied')).toBeInTheDocument();

    fireEvent.doubleClick(screen.getByText('sample.fastq'));

    await waitFor(() => expect(loggingMock.logError).toHaveBeenCalledWith('workspace.file.preview', expect.any(Error)));
    expect(screen.getByDisplayValue('Error loading file: 404')).toBeInTheDocument();
  });

  it('renders file previews through the shared dialog primitive', async () => {
    const { default: WorkspacePanel } = await import('../components/panels/WorkspacePanel');

    render(<WorkspacePanel onClose={() => undefined} />);

    await waitFor(() => expect(screen.getByText('sample.fastq')).toBeInTheDocument());

    fireEvent.doubleClick(screen.getByText('sample.fastq'));

    const dialog = await screen.findByRole('dialog', { name: 'sample.fastq' });
    expect(dialog).toBeInTheDocument();
    expect(within(dialog).getByRole('button', { name: 'Close' })).toBeInTheDocument();

    fireEvent.keyDown(dialog, { key: 'Escape' });

    await waitFor(() => expect(screen.queryByRole('dialog', { name: 'sample.fastq' })).not.toBeInTheDocument());
  });

  it('keeps workspace root API detail errors behind the localized change label', async () => {
    const { default: WorkspacePanel } = await import('../components/panels/WorkspacePanel');
    const { setLanguage } = await import('../i18n');

    fetchSpy.mockImplementation(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = typeof input === 'string' ? input : input.toString();
      if (url.includes('/api/workspace/root') && init?.method === 'POST') {
        return new Response(JSON.stringify({ detail: 'backend root detail' }), {
          status: 400,
          statusText: 'Bad Request',
          headers: { 'Content-Type': 'application/json' },
        });
      }
      if (url.includes('/api/workspace/root')) {
        return new Response(JSON.stringify({ root: '/analysis' }), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        });
      }
      if (url.includes('/api/workspace/files')) {
        return new Response(JSON.stringify({ path: '/', entries: [] }), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        });
      }
      return new Response('{}', {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      });
    });

    await setLanguage('es');

    render(<WorkspacePanel onClose={() => undefined} />);

    await waitFor(() => expect(screen.getByPlaceholderText('/ruta/al/espacio')).toHaveValue('/analysis'));

    fireEvent.change(screen.getByPlaceholderText('/ruta/al/espacio'), { target: { value: '/restricted' } });
    fireEvent.click(screen.getByRole('button', { name: 'Definir' }));

    await waitFor(() => expect(screen.getByText('No se pudo cambiar el espacio de trabajo: backend root detail')).toBeInTheDocument());
    expect(screen.queryByText('backend root detail')).not.toBeInTheDocument();
  });
});
