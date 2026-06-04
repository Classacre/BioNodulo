import { fireEvent, render, screen } from '@testing-library/react';
import { Provider } from 'jotai';
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

describe('CollabBadge i18n', () => {
  beforeEach(() => {
    storage.clear();
    vi.stubGlobal('localStorage', localStorageStub);
  });

  afterEach(async () => {
    const { setLanguage } = await import('../i18n');
    await setLanguage('en');
    storage.clear();
    vi.unstubAllGlobals();
  });

  it('renders offline join-link status and menu actions from the active locale', async () => {
    const { default: CollabBadge } = await import('../collab/CollabBadge');
    const { setLanguage } = await import('../i18n');
    await setLanguage('es');

    render(
      <Provider>
        <CollabBadge
          enabled={false}
          connected={false}
          connecting={false}
          activeUsers={[]}
          currentWorkflowId="workflow-1"
          followingUserId={null}
          isShared={false}
          onFollow={() => undefined}
          onOpenSettings={() => undefined}
          onCreateSession={() => undefined}
          onJoinSession={() => undefined}
          onLeaveSession={() => undefined}
          hasJoinLink
        />
      </Provider>,
    );

    const badge = screen.getByTitle('Colaboracion: Enlace de colaboracion listo');
    expect(screen.getByText('Unirse')).toBeInTheDocument();

    fireEvent.click(badge);

    expect(screen.getByText('Enlace de colaboracion listo')).toBeInTheDocument();
    expect(screen.getByText('Modo sin conexion activo. Inicia una sala temporal o unete desde un enlace compartido de BioNodulo.')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Crear enlace de colaboracion' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Unirse a colaboracion' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Comentarios' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Historial de versiones' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Registro de auditoria' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Ajustes de colaboracion' })).toBeInTheDocument();
  });
});
