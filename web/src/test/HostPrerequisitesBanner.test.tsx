import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { HostStatus } from '../types';

const loggingMock = vi.hoisted(() => ({
  logError: vi.fn(),
}));

vi.mock('../api/client', () => ({
  apiPost: vi.fn(),
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

function hostStatus(): HostStatus {
  return {
    ready: false,
    missing_required: ['pixi', 'docker'],
    missing_optional: [],
    message: '',
    checks: {
      pixi: {
        available: false,
        path: null,
        required: true,
        auto_installable: true,
        description: 'Pixi package manager',
      },
      docker: {
        available: false,
        path: null,
        required: true,
        auto_installable: false,
        description: 'Docker engine',
      },
    },
  };
}

describe('HostPrerequisitesBanner i18n', () => {
  beforeEach(() => {
    storage.clear();
    loggingMock.logError.mockReset();
    vi.stubGlobal('localStorage', localStorageStub);
  });

  afterEach(async () => {
    const { setLanguage } = await import('../i18n');
    const { apiPost } = await import('../api/client');
    await setLanguage('en');
    vi.mocked(apiPost).mockReset();
    storage.clear();
    vi.unstubAllGlobals();
  });

  it('renders host prerequisite summary and expanded checks from the active locale', async () => {
    const { default: HostPrerequisitesBanner } = await import('../components/layout/HostPrerequisitesBanner');
    const { setLanguage } = await import('../i18n');

    await setLanguage('es');

    render(
      <HostPrerequisitesBanner
        status={hostStatus()}
        onDismiss={() => undefined}
        onOpenConsole={() => undefined}
        onRecheck={() => undefined}
      />,
    );

    expect(screen.getByText('Falta un prerrequisito del host:')).toBeInTheDocument();
    expect(screen.getByText('2 herramientas requeridas faltantes')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Instalar Pixi automaticamente/ })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Detalles' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Descartar' })).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Detalles' }));

    expect(screen.getByRole('heading', { name: 'Comprobaciones del host' })).toBeInTheDocument();
    expect(screen.getByText('Instala manualmente y asegurate de que este en PATH')).toBeInTheDocument();
    expect(screen.getByText('Se puede instalar automaticamente')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Ocultar' })).toBeInTheDocument();
  });

  it('renders Pixi install status messages from the active locale', async () => {
    const { apiPost } = await import('../api/client');
    const { default: HostPrerequisitesBanner } = await import('../components/layout/HostPrerequisitesBanner');
    const { setLanguage } = await import('../i18n');
    const onOpenConsole = vi.fn();
    const onRecheck = vi.fn();
    vi.mocked(apiPost).mockResolvedValue({ success: true, already_installed: false });

    await setLanguage('es');

    render(
      <HostPrerequisitesBanner
        status={hostStatus()}
        onDismiss={() => undefined}
        onOpenConsole={onOpenConsole}
        onRecheck={onRecheck}
      />,
    );

    fireEvent.click(screen.getByRole('button', { name: /Instalar Pixi automaticamente/ }));

    expect(screen.getByText('Instalando...')).toBeInTheDocument();
    await waitFor(() => expect(screen.getByText('Instalado correctamente - recarga la pagina para activar.')).toBeInTheDocument());
    expect(onOpenConsole).toHaveBeenCalledTimes(1);
    expect(onRecheck).toHaveBeenCalledTimes(1);
  });

  it('keeps backend Pixi install failure details out of localized feedback', async () => {
    const { apiPost } = await import('../api/client');
    const { default: HostPrerequisitesBanner } = await import('../components/layout/HostPrerequisitesBanner');
    const { setLanguage } = await import('../i18n');
    const rawBackendMessage = 'pixi installation failed. Check server logs for details.';
    vi.mocked(apiPost).mockResolvedValueOnce({ success: false, message: rawBackendMessage });

    await setLanguage('es');

    const { container } = render(
      <HostPrerequisitesBanner
        status={hostStatus()}
        onDismiss={() => undefined}
        onOpenConsole={() => undefined}
        onRecheck={() => undefined}
      />,
    );

    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /Instalar Pixi automaticamente/ }));
    });

    await waitFor(() => expect(screen.getByText('La instalacion fallo - revisa los registros del servidor.')).toBeInTheDocument());
    expect(container).not.toHaveTextContent(rawBackendMessage);
    expect(container).not.toHaveTextContent(`Instalacion fallida: ${rawBackendMessage}`);
  });

  it('logs Pixi install request failures while preserving localized feedback', async () => {
    const { apiPost } = await import('../api/client');
    const { default: HostPrerequisitesBanner } = await import('../components/layout/HostPrerequisitesBanner');
    const { setLanguage } = await import('../i18n');
    const installError = new Error('install endpoint unavailable');
    const onRecheck = vi.fn();
    vi.mocked(apiPost).mockRejectedValueOnce(installError);

    await setLanguage('es');

    render(
      <HostPrerequisitesBanner
        status={hostStatus()}
        onDismiss={() => undefined}
        onOpenConsole={() => undefined}
        onRecheck={onRecheck}
      />,
    );

    fireEvent.click(screen.getByRole('button', { name: /Instalar Pixi automaticamente/ }));

    await waitFor(() => expect(screen.getByText('La solicitud de instalacion fallo - revisa los registros del servidor.')).toBeInTheDocument());
    expect(loggingMock.logError).toHaveBeenCalledWith('hostStatus.installPixi', installError);
    expect(onRecheck).toHaveBeenCalledTimes(1);
  });
});
