import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { getDefaultStore } from 'jotai';
import { cloudConfigAtom } from '../state/appAtoms';

const runtimeMock = vi.hoisted(() => ({ current: undefined as unknown }));
vi.mock('../mcp/runtime', () => ({ getMcpRuntime: () => runtimeMock.current }));

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

describe('WorkspacePanel', () => {
  let fetchSpy: ReturnType<typeof vi.spyOn>;
  let originalLocalStorage: Storage;

  beforeEach(() => {
    runtimeMock.current = undefined;
    getDefaultStore().set(cloudConfigAtom, null);
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
          path: '.',
          entries: [
            { name: 'reads', path: 'reads', type: 'directory' },
            { name: 'workflow.json', path: 'workflow.json', type: 'file', size: 2048 },
            { name: 'sample.fastq', path: 'sample.fastq', type: 'file', size: 512 },
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
    runtimeMock.current = undefined;
    getDefaultStore().set(cloudConfigAtom, null);
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

  it('shows workspace listing failures instead of an empty directory and logs their scopes', async () => {
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
    expect(await screen.findByRole('alert')).toHaveTextContent('Could not list workspace files.');
    expect(screen.queryByText('No files in this directory')).not.toBeInTheDocument();
  });

  it('uses cloud files only in editor mode without requesting local workspace endpoints', async () => {
    const { default: WorkspacePanel } = await import('../components/panels/WorkspacePanel');
    getDefaultStore().set(cloudConfigAtom, {
      cloudMode: true, editorMode: true, user: null, team: null, plan: null,
      credits: null, accountUrl: null, clerkPublishableKey: null, oauth: null,
    });
    fetchSpy.mockResolvedValue(new Response(JSON.stringify({ success: true, data: [] }), {
      status: 200, headers: { 'Content-Type': 'application/json' },
    }));
    render(<WorkspacePanel onClose={() => undefined} />);
    await waitFor(() => expect(screen.getByText('No cloud files yet.')).toBeInTheDocument());
    expect(screen.queryByText('Local')).not.toBeInTheDocument();
    expect(fetchSpy.mock.calls.some(([input]) => String(input).includes('/workspace/'))).toBe(false);
  });

  it('uses MCP host file tools, verifies browser uploads, and exposes upload keys for canvas drag', async () => {
    const { default: WorkspacePanel } = await import('../components/panels/WorkspacePanel');
    const tool = vi.fn(async (name: string) => {
      if (name === 'get_upload_url') return { key: 'uploads/team-a/new.fastq', url: 'https://uploads.example/new' };
      return {};
    });
    const openLink = vi.fn().mockResolvedValue(undefined);
    const request = vi.fn(async () => Response.json({ success: true, data: [
      { key: 'uploads/team-a/reads.fastq', name: 'reads.fastq', size: 3, source: 'upload', url: 'https://files.example/reads' },
      { key: 'uploads/team-a/pending.fastq', name: 'pending.fastq', size: 3, source: 'upload', verificationPending: true, url: '' },
    ] }));
    runtimeMock.current = { teamId: 'team-a', host: { tool }, request, openLink };
    const meta = document.createElement('meta');
    meta.name = 'bionodulo-upload-origins';
    meta.content = 'https://uploads.example';
    document.head.append(meta);
    fetchSpy.mockResolvedValue(new Response('', { status: 200 }));
    try {
      render(<WorkspacePanel onClose={() => undefined} />);
      const row = (await screen.findByText('reads.fastq')).closest('.workspace-file-row')!;
      const data = new Map<string, string>();
      fireEvent.dragStart(row, { dataTransfer: { setData: (type: string, value: string) => data.set(type, value), effectAllowed: '' } });
      expect(data.get('application/bionodulo-workspace-file')).toBe('uploads/team-a/reads.fastq');
      fireEvent.doubleClick(row);
      await waitFor(() => expect(openLink).toHaveBeenCalledWith('https://files.example/reads'));
      const pending = screen.getByText('pending.fastq').closest('.workspace-file-row')!;
      expect(pending).toHaveAttribute('draggable', 'false');
      fireEvent.doubleClick(pending);
      await waitFor(() => expect(tool).toHaveBeenCalledWith('complete_upload', { team_id: 'team-a', key: 'uploads/team-a/pending.fastq' }));
      const input = screen.getByLabelText('Choose cloud files');
      fireEvent.change(input, { target: { files: [new File(['abc'], 'new.fastq', { type: 'application/octet-stream' })] } });
      await waitFor(() => expect(tool).toHaveBeenCalledWith('complete_upload', { team_id: 'team-a', key: 'uploads/team-a/new.fastq' }));
      expect(request).toHaveBeenCalledWith('website', '/files', {});
      expect(fetchSpy).toHaveBeenCalledWith('https://uploads.example/new', expect.objectContaining({ method: 'PUT', credentials: 'omit', redirect: 'error' }));
      expect(fetchSpy.mock.calls.some(([input]) => String(input).includes('/workspace/'))).toBe(false);
    } finally { meta.remove(); }
  });

  it('reports MCP cloud listing failures without falling back to local workspace calls', async () => {
    const { default: WorkspacePanel } = await import('../components/panels/WorkspacePanel');
    const request = vi.fn().mockRejectedValue(new Error('Host disconnected'));
    runtimeMock.current = { teamId: 'team-a', request, host: { tool: vi.fn() }, openLink: vi.fn() };
    render(<WorkspacePanel onClose={() => undefined} />);
    await waitFor(() => expect(screen.getByText('Could not list cloud files. Reconnect the MCP host and retry.')).toBeInTheDocument());
    expect(screen.queryByText('Local')).not.toBeInTheDocument();
    expect(fetchSpy.mock.calls.some(([input]) => String(input).includes('/workspace/'))).toBe(false);
    fireEvent.click(screen.getByTitle('Refresh'));
    await waitFor(() => expect(request).toHaveBeenCalledTimes(2));
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
          path: '.',
          entries: [{ name: 'sample.fastq', path: 'sample.fastq', type: 'file', size: 512 }],
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
        return new Response(JSON.stringify({ path: '.', entries: [] }), {
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

  it.each([
    { host: 'Windows', separator: '\\', rootPath: '.' },
    { host: 'POSIX', separator: '/', rootPath: '' },
  ])('navigates $host relative folders and returns to the workspace root', async ({ separator, rootPath }) => {
    const { default: WorkspacePanel } = await import('../components/panels/WorkspacePanel');
    const listedPaths: string[] = [];
    let previewPath: string | null = null;
    const json = (data: unknown) => new Response(JSON.stringify(data), {
      status: 200, headers: { 'Content-Type': 'application/json' },
    });
    fetchSpy.mockImplementation(async (input: RequestInfo | URL) => {
      const url = new URL(String(input), 'http://localhost');
      if (url.pathname.endsWith('/workspace/root')) return json({ root: 'D:\\workspace' });
      const requestedPath = url.searchParams.get('path') ?? '';
      if (url.pathname.endsWith('/workspace/files')) {
        listedPaths.push(requestedPath);
        if (requestedPath === '') return json({ path: rootPath, entries: [{ name: 'reads', path: 'reads', type: 'directory' }] });
        if (requestedPath === 'reads') return json({ path: 'reads', entries: [{ name: 'nested', path: `reads${separator}nested`, type: 'directory' }] });
        if (requestedPath === 'reads/nested') return json({
          path: `reads${separator}nested`,
          entries: [{ name: 'sample.fastq', path: `reads${separator}nested${separator}sample.fastq`, type: 'file' }],
        });
        return new Response(JSON.stringify({ detail: 'Unexpected absolute or malformed path' }), { status: 400 });
      }
      if (url.pathname.endsWith('/workspace/file')) {
        previewPath = requestedPath;
        return new Response('fixture reads');
      }
      return json({});
    });

    render(<WorkspacePanel onClose={() => undefined} />);
    fireEvent.doubleClick(await screen.findByText('reads'));
    fireEvent.doubleClick(await screen.findByText('nested'));
    fireEvent.doubleClick(await screen.findByText('sample.fastq'));
    const dialog = await screen.findByRole('dialog', { name: 'sample.fastq' });
    await waitFor(() => expect(previewPath).toBe('reads/nested/sample.fastq'));
    fireEvent.click(within(dialog).getByRole('button', { name: 'Close' }));
    const parentButton = screen.getByRole('button', { name: 'Go up' });
    expect(parentButton.querySelector('svg')).toBeInTheDocument();
    fireEvent.click(parentButton);
    await screen.findByText('nested');
    fireEvent.click(screen.getByRole('button', { name: 'Go up' }));
    await screen.findByText('reads');

    expect(listedPaths).toEqual(['', 'reads', 'reads/nested', 'reads', '']);
    expect(screen.queryByTitle('Go up')).not.toBeInTheDocument();
    expect(document.querySelector('.workspace-breadcrumb-path')).toHaveTextContent('/');
  });

  it('uses the relative root after setting or reloading the workspace root', async () => {
    const { default: WorkspacePanel } = await import('../components/panels/WorkspacePanel');
    render(<WorkspacePanel onClose={() => undefined} />);
    await screen.findByText('sample.fastq');
    const paths = () => fetchSpy.mock.calls
      .map(([input]) => new URL(String(input), 'http://localhost'))
      .filter(url => url.pathname.endsWith('/workspace/files'))
      .map(url => url.searchParams.get('path'));

    fireEvent.change(screen.getByPlaceholderText('/path/to/workspace'), { target: { value: 'D:\\workspace' } });
    fireEvent.click(screen.getByRole('button', { name: 'Set' }));
    await waitFor(() => expect(paths()).toEqual(['', '']));
    fireEvent.click(screen.getByRole('button', { name: 'Default' }));
    await waitFor(() => expect(paths()).toEqual(['', '', '']));
  });

  it('shows API listing details and retries the failed relative directory', async () => {
    const { default: WorkspacePanel } = await import('../components/panels/WorkspacePanel');
    const listedPaths: string[] = [];
    let fail = true;
    const json = (data: unknown, status = 200) => new Response(JSON.stringify(data), {
      status, headers: { 'Content-Type': 'application/json' },
    });
    fetchSpy.mockImplementation(async (input: RequestInfo | URL) => {
      const url = new URL(String(input), 'http://localhost');
      if (url.pathname.endsWith('/workspace/root')) return json({ root: 'D:\\workspace' });
      if (url.pathname.endsWith('/workspace/files')) {
        const requestedPath = url.searchParams.get('path') ?? '';
        listedPaths.push(requestedPath);
        if (!requestedPath) return json({ path: '.', entries: [{ name: 'locked', path: 'locked', type: 'directory' }] });
        if (fail) return json({ detail: 'Permission denied: locked' }, 403);
        return json({ path: 'locked', entries: [{ name: 'recovered.csv', path: 'locked\\recovered.csv', type: 'file' }] });
      }
      return json({});
    });

    render(<WorkspacePanel onClose={() => undefined} />);
    fireEvent.doubleClick(await screen.findByText('locked'));
    expect(await screen.findByRole('alert')).toHaveTextContent('Could not list workspace files. Permission denied: locked');
    expect(screen.queryByText('No files in this directory')).not.toBeInTheDocument();
    fail = false;
    fireEvent.click(screen.getByRole('button', { name: 'Retry' }));
    await screen.findByText('recovered.csv');
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
    expect(listedPaths).toEqual(['', 'locked', 'locked']);
  });
});
