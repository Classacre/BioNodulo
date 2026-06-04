import { fireEvent, render, screen } from '@testing-library/react';
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

const users = [
  {
    user: { id: 'user-1', name: 'Ada', color: '#7c3aed' },
    cursor: null,
    selection: { nodeIds: [] },
    activity: 'active' as const,
    timestamp: Date.now(),
  },
];

describe('FollowUser i18n', () => {
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

  it('renders follow controls and activity labels from the active locale', async () => {
    const { default: FollowUser } = await import('../collab/FollowUser');
    const { setLanguage } = await import('../i18n');
    await setLanguage('es');

    const { rerender } = render(
      <FollowUser
        users={users}
        followingUserId={null}
        onFollow={() => undefined}
      />,
    );

    const followButton = screen.getByTitle('Seguir la vista de un usuario');
    expect(screen.getByText('Seguir')).toBeInTheDocument();

    fireEvent.click(followButton);

    expect(screen.getByText('Usuarios activos')).toBeInTheDocument();
    expect(screen.getByText('Activo')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Seguir' })).toBeInTheDocument();

    rerender(
      <FollowUser
        users={users}
        followingUserId="user-1"
        onFollow={() => undefined}
      />,
    );

    expect(screen.getByTitle('Siguiendo a Ada. Haz clic para dejar de seguir.')).toBeInTheDocument();
    expect(screen.getByText('Siguiendo a Ada')).toBeInTheDocument();
  });
});
