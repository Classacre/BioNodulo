import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const authMocks = vi.hoisted(() => ({
  fetchToken: vi.fn(),
  generateGuestName: vi.fn(() => 'Guest User'),
  isAuthTokenError: vi.fn((err: unknown) => Boolean(err && typeof err === 'object' && 'code' in err)),
  setAuthSession: vi.fn(),
}));

const loggingMock = vi.hoisted(() => ({
  logError: vi.fn(),
}));

vi.mock('../collab/auth', () => authMocks);
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

describe('AuthDialog i18n', () => {
  beforeEach(() => {
    storage.clear();
    vi.stubGlobal('localStorage', localStorageStub);
    authMocks.fetchToken.mockReset();
    authMocks.generateGuestName.mockReturnValue('Guest User');
    authMocks.isAuthTokenError.mockImplementation((err: unknown) => Boolean(err && typeof err === 'object' && 'code' in err));
    authMocks.setAuthSession.mockReset();
    loggingMock.logError.mockReset();
  });

  afterEach(async () => {
    const { setLanguage } = await import('../i18n');
    await setLanguage('en');
    storage.clear();
    vi.unstubAllGlobals();
  });

  it('renders join controls from the active locale', async () => {
    const { default: AuthDialog } = await import('../collab/AuthDialog');
    const { setLanguage } = await import('../i18n');
    await setLanguage('es');

    render(
      <AuthDialog
        isOpen
        onLogin={() => undefined}
        onClose={() => undefined}
      />,
    );

    expect(screen.getByRole('heading', { name: 'Unirse a colaboracion' })).toBeInTheDocument();
    expect(screen.getByText('Ingresa tu nombre visible para colaborar en flujos de trabajo en tiempo real.')).toBeInTheDocument();
    expect(screen.queryByText('Ingresa tu nombre visible para colaborar en workflows en tiempo real.')).not.toBeInTheDocument();
    expect(screen.getByText('Nombre visible')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('Tu nombre')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Unirse' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Continuar como invitado' })).toBeInTheDocument();
    expect(screen.getByText('Tu sesion esta autenticada con un token seguro.')).toBeInTheDocument();
  });

  it('renders known auth token failures from the active locale', async () => {
    const { default: AuthDialog } = await import('../collab/AuthDialog');
    const { setLanguage } = await import('../i18n');
    await setLanguage('es');
    authMocks.fetchToken.mockRejectedValueOnce({
      code: 'api_failed',
      status: 401,
      body: 'credenciales invalidas',
    });

    render(
      <AuthDialog
        isOpen
        onLogin={() => undefined}
        onClose={() => undefined}
      />,
    );

    await userEvent.click(screen.getByRole('button', { name: 'Unirse' }));

    expect(await screen.findByText('No se pudo autenticar (401): credenciales invalidas')).toBeInTheDocument();
  });

  it('renders missing auth token responses from the active locale', async () => {
    const { default: AuthDialog } = await import('../collab/AuthDialog');
    const { setLanguage } = await import('../i18n');
    await setLanguage('es');
    authMocks.fetchToken.mockRejectedValueOnce({ code: 'missing_token' });

    render(
      <AuthDialog
        isOpen
        onLogin={() => undefined}
        onClose={() => undefined}
      />,
    );

    await userEvent.click(screen.getByRole('button', { name: 'Unirse' }));

    expect(await screen.findByText('La respuesta de autenticacion no incluyo token')).toBeInTheDocument();
  });

  it('logs swallowed auth join failures with stable scopes', async () => {
    const { default: AuthDialog } = await import('../collab/AuthDialog');
    const joinError = new Error('join failed');
    const guestError = new Error('guest failed');

    authMocks.fetchToken.mockRejectedValueOnce(joinError);
    const joinView = render(
      <AuthDialog
        isOpen
        onLogin={() => undefined}
        onClose={() => undefined}
      />,
    );

    await userEvent.click(screen.getByRole('button', { name: 'Join' }));

    expect(await screen.findByText('join failed')).toBeInTheDocument();
    expect(loggingMock.logError).toHaveBeenCalledWith('collab.auth.join', joinError);
    joinView.unmount();

    authMocks.fetchToken.mockRejectedValueOnce(guestError);
    render(
      <AuthDialog
        isOpen
        onLogin={() => undefined}
        onClose={() => undefined}
      />,
    );

    await userEvent.click(screen.getByRole('button', { name: 'Continue as Guest' }));

    expect(await screen.findByText('guest failed')).toBeInTheDocument();
    expect(loggingMock.logError).toHaveBeenCalledWith('collab.auth.guest', guestError);
  });
});
