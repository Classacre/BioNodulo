import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

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
      return new Response('{}', {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      });
    });
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
  });
});
