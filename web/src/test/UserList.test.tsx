import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const apiMocks = vi.hoisted(() => ({
  apiDelete: vi.fn(),
  apiGet: vi.fn(),
  apiPost: vi.fn(),
}));

const loggingMock = vi.hoisted(() => ({
  logError: vi.fn(),
}));

vi.mock('../api/client', () => apiMocks);
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

describe('UserList i18n', () => {
  beforeEach(() => {
    storage.clear();
    vi.stubGlobal('localStorage', localStorageStub);
    apiMocks.apiDelete.mockReset();
    apiMocks.apiGet.mockReset();
    apiMocks.apiPost.mockReset();
    loggingMock.logError.mockReset();
    localStorage.setItem('bionodulo_auth_token', 'test-token');
  });

  afterEach(async () => {
    const { setLanguage } = await import('../i18n');
    await setLanguage('en');
    storage.clear();
    vi.unstubAllGlobals();
  });

  it('renders active users, roles, and access menu from the active locale', async () => {
    const { default: UserList } = await import('../collab/UserList');
    const { setLanguage } = await import('../i18n');
    await setLanguage('es');
    apiMocks.apiGet.mockResolvedValue({
      shares: [
        { id: 'share-owner', workflow_id: 'workflow-1', user_id: 'owner-1', role: 'owner' },
        { id: 'share-ada', workflow_id: 'workflow-1', user_id: 'user-2', role: 'viewer' },
      ],
    });

    render(
      <UserList
        users={[
          {
            session_id: 'session-owner',
            user_id: 'owner-1',
            name: 'Mika',
            color: '#0d9488',
            role: 'owner',
            workflow_id: 'workflow-1',
          },
          {
            session_id: 'session-ada',
            user_id: 'user-2',
            name: 'Ada',
            color: '#7c3aed',
            role: 'viewer',
            workflow_id: 'workflow-1',
          },
        ]}
        currentUserId="owner-1"
        currentSessionId="session-owner"
        currentWorkflowId="workflow-1"
        isOpen
        onClose={() => undefined}
      />,
    );

    await waitFor(() => expect(screen.getByText('Mika (Tu)')).toBeInTheDocument());

    expect(screen.getByText('Usuarios activos')).toBeInTheDocument();
    expect(screen.getByTitle('Cerrar')).toBeInTheDocument();
    expect(screen.getByText('Administrador')).toBeInTheDocument();
    expect(screen.getByText('Lector')).toBeInTheDocument();
    expect(screen.getAllByText('Flujo de trabajo workflow-1')).toHaveLength(2);
    expect(screen.queryByText('Workflow workflow-1')).not.toBeInTheDocument();
    const manageAccess = screen.getByTitle('Gestionar acceso');
    expect(manageAccess).toBeInTheDocument();

    fireEvent.click(manageAccess);

    expect(screen.getByRole('button', { name: 'Hacer editor' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Hacer comentarista' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Hacer lector' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Expulsar usuario' })).toBeInTheDocument();
  });

  it('logs swallowed user-list API failures with stable scopes', async () => {
    const { default: UserList } = await import('../collab/UserList');
    const users = [
      {
        session_id: 'session-owner',
        user_id: 'owner-1',
        name: 'Mika',
        color: '#0d9488',
        role: 'owner' as const,
        workflow_id: 'workflow-1',
      },
      {
        session_id: 'session-ada',
        user_id: 'user-2',
        name: 'Ada',
        color: '#7c3aed',
        role: 'viewer' as const,
        workflow_id: 'workflow-1',
      },
    ];
    const shares = [
      { id: 'share-owner', workflow_id: 'workflow-1', user_id: 'owner-1', role: 'owner' },
      { id: 'share-ada', workflow_id: 'workflow-1', user_id: 'user-2', role: 'viewer' },
    ];

    const refreshError = new Error('share refresh failed');
    apiMocks.apiGet.mockRejectedValueOnce(refreshError);
    const refreshView = render(
      <UserList
        users={users}
        currentUserId="owner-1"
        currentSessionId="session-owner"
        currentWorkflowId="workflow-1"
        isOpen
        onClose={() => undefined}
      />,
    );

    await waitFor(() => expect(loggingMock.logError).toHaveBeenCalledWith('collab.userList.refresh', refreshError));
    refreshView.unmount();

    const roleError = new Error('role change failed');
    apiMocks.apiGet.mockResolvedValueOnce({ shares });
    apiMocks.apiPost.mockRejectedValueOnce(roleError);
    const roleView = render(
      <UserList
        users={users}
        currentUserId="owner-1"
        currentSessionId="session-owner"
        currentWorkflowId="workflow-1"
        isOpen
        onClose={() => undefined}
      />,
    );

    await waitFor(() => expect(screen.getByTitle('Manage access')).toBeInTheDocument());
    fireEvent.click(screen.getByTitle('Manage access'));
    fireEvent.click(screen.getByRole('button', { name: 'Make editor' }));

    await waitFor(() => expect(loggingMock.logError).toHaveBeenCalledWith('collab.userList.roleChange', roleError));
    expect(screen.getByText("Could not change Ada's role.")).toBeInTheDocument();
    roleView.unmount();

    const removeError = new Error('remove failed');
    apiMocks.apiGet.mockResolvedValueOnce({ shares });
    apiMocks.apiDelete.mockRejectedValueOnce(removeError);
    const removeView = render(
      <UserList
        users={users}
        currentUserId="owner-1"
        currentSessionId="session-owner"
        currentWorkflowId="workflow-1"
        isOpen
        onClose={() => undefined}
      />,
    );

    await waitFor(() => expect(screen.getByTitle('Manage access')).toBeInTheDocument());
    fireEvent.click(screen.getByTitle('Manage access'));
    fireEvent.click(screen.getByRole('button', { name: 'Kick user' }));

    await waitFor(() => expect(loggingMock.logError).toHaveBeenCalledWith('collab.userList.remove', removeError));
    expect(screen.getByText('Could not remove Ada.')).toBeInTheDocument();
    removeView.unmount();
  });
});
