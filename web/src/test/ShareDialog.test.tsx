import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const apiMocks = vi.hoisted(() => ({
  apiDelete: vi.fn(),
  apiGet: vi.fn(),
  apiPost: vi.fn(),
}));

const toastMock = vi.hoisted(() => ({
  info: vi.fn(),
  success: vi.fn(),
}));

vi.mock('../api/client', () => apiMocks);
vi.mock('../components/ui', () => ({
  toast: toastMock,
}));

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

describe('ShareDialog i18n', () => {
  beforeEach(() => {
    storage.clear();
    vi.stubGlobal('localStorage', localStorageStub);
    Object.defineProperty(navigator, 'clipboard', {
      configurable: true,
      value: {
        writeText: vi.fn().mockResolvedValue(undefined),
      },
    });
    apiMocks.apiDelete.mockReset();
    apiMocks.apiGet.mockReset();
    apiMocks.apiPost.mockReset();
    toastMock.info.mockReset();
    toastMock.success.mockReset();
  });

  afterEach(async () => {
    const { setLanguage } = await import('../i18n');
    await setLanguage('en');
    storage.clear();
    vi.unstubAllGlobals();
  });

  it('renders offline room-link copy from the active locale', async () => {
    const { default: ShareDialog } = await import('../collab/ShareDialog');
    const { setLanguage } = await import('../i18n');

    apiMocks.apiGet.mockResolvedValue({ shares: [] });
    await setLanguage('es');

    render(
      <ShareDialog
        workflowId="workflow-1"
        isOpen
        onClose={() => undefined}
      />,
    );

    expect(screen.getByRole('dialog', { name: 'Compartir flujo de trabajo' })).toBeInTheDocument();
    expect(screen.queryByRole('dialog', { name: 'Compartir workflow' })).not.toBeInTheDocument();
    expect(screen.getByText('La colaboracion esta sin conexion. Crea una sala temporal antes de compartir este flujo de trabajo.')).toBeInTheDocument();
    expect(screen.queryByText('La colaboracion esta sin conexion. Crea una sala temporal antes de compartir este workflow.')).not.toBeInTheDocument();
    expect(screen.getByPlaceholderText('Usuario o email')).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Invitar' })).toBeDisabled();
    expect(screen.getByText('Enlace de sala de colaboracion')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Crear enlace' })).toBeDisabled();
    expect(screen.getByText('Crea una sala temporal de colaboracion para generar un enlace compartible.')).toBeInTheDocument();
    expect(screen.getByText('Este enlace local solo funciona en esta maquina o LAN. Usa un tunel Cloudflare/ngrok o una URL alojada para colaboradores externos.')).toBeInTheDocument();
    await waitFor(() => expect(screen.getByText('Sin compartidos todavia')).toBeInTheDocument());
  });

  it('uses the shared dialog primitive dismissal behavior', async () => {
    const { default: ShareDialog } = await import('../collab/ShareDialog');
    const onClose = vi.fn();

    apiMocks.apiGet.mockResolvedValue({ shares: [] });

    const { rerender } = render(
      <ShareDialog
        workflowId="workflow-1"
        isOpen
        onClose={onClose}
      />,
    );

    const dialog = screen.getByRole('dialog', { name: 'Share workflow' });
    expect(dialog).toHaveAttribute('aria-modal', 'true');

    fireEvent.keyDown(dialog, { key: 'Escape' });
    expect(onClose).toHaveBeenCalledTimes(1);

    rerender(
      <ShareDialog
        workflowId="workflow-1"
        isOpen
        onClose={onClose}
      />,
    );

    fireEvent.click(dialog.parentElement as HTMLElement);
    expect(onClose).toHaveBeenCalledTimes(2);
  });

  it('renders active shares and copy feedback from the active locale', async () => {
    const { default: ShareDialog } = await import('../collab/ShareDialog');
    const { setLanguage } = await import('../i18n');

    apiMocks.apiGet.mockResolvedValue({
      shares: [{ id: 'share-1', user_id: 'user-1', name: 'Mika', role: 'viewer' }],
    });
    await setLanguage('es');

    render(
      <ShareDialog
        workflowId="workflow-1"
        isOpen
        onClose={() => undefined}
        collabEnabled
        inviteToken="invite-token"
        shareLink="https://bionodulo.example/invite"
      />,
    );

    await waitFor(() => expect(screen.getByText('Mika')).toBeInTheDocument());

    expect(screen.getByRole('option', { name: 'Editor' })).toBeInTheDocument();
    expect(screen.getByRole('option', { name: 'Lector' })).toBeInTheDocument();
    expect(screen.getByText('Compartido con')).toBeInTheDocument();
    expect(screen.getAllByText('Lector')).toHaveLength(2);
    expect(screen.getByRole('button', { name: 'Revocar' })).toBeInTheDocument();
    expect(screen.getByText('Los enlaces funcionan mientras este servidor BioNodulo este ejecutandose. Deten la app para invalidar enlaces temporales.')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Copiar' }));

    await waitFor(() => expect(toastMock.success).toHaveBeenCalledWith('Enlace de colaboracion copiado'));
    expect(navigator.clipboard.writeText).toHaveBeenCalledWith('https://bionodulo.example/invite');
  });

  it('keeps ShareDialog on the shared Dialog primitive', () => {
    const source = readFileSync(resolve(__dirname, '../collab/ShareDialog.tsx'), 'utf8');

    expect(source).toContain("import Dialog from '../components/ui/Dialog';");
    expect(source).toContain('<Dialog');
    expect(source).not.toContain('<div className="modal-overlay"');
  });
});
