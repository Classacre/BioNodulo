import { render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const apiMocks = vi.hoisted(() => ({
  apiGet: vi.fn(),
  apiPost: vi.fn(),
}));

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

describe('TemplateGallery i18n', () => {
  beforeEach(() => {
    storage.clear();
    vi.stubGlobal('localStorage', localStorageStub);
    apiMocks.apiGet.mockReset();
    apiMocks.apiPost.mockReset();
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
});
