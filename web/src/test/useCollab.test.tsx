import { renderHook, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { apiGet, apiPost } from '../api/client';
import { useCollab } from '../collab/useCollab';
import type { CollabUser } from '../collab/types';
import { logError } from '../state/logging';

const apiMocks = vi.hoisted(() => ({
  apiGet: vi.fn(),
  apiPost: vi.fn(),
}));

const loggingMocks = vi.hoisted(() => ({
  logError: vi.fn(),
}));

const authMocks = vi.hoisted(() => ({
  getToken: vi.fn(),
}));

const websocketMocks = vi.hoisted(() => ({
  WebsocketProvider: vi.fn(function WebsocketProvider() {
    return {
      shouldConnect: true,
      wsUnsuccessfulReconnects: 0,
      on: vi.fn(),
      off: vi.fn(),
      disconnect: vi.fn(),
      destroy: vi.fn(),
    };
  }),
}));

vi.mock('../api/client', () => apiMocks);
vi.mock('../state/logging', () => loggingMocks);
vi.mock('../collab/auth', () => authMocks);
vi.mock('y-websocket', () => websocketMocks);
vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string) => ({
      'collab.shareSignInRequired': 'Inicia sesion antes de compartir flujos de trabajo',
      'collab.shareWorkflowError': 'No se pudo compartir el flujo de trabajo',
    }[key] ?? key),
  }),
  // i18n/index.ts (pulled in transitively) calls i18n.use(initReactI18next),
  // so the mock must provide it or module init throws.
  initReactI18next: { type: '3rdParty', init: () => {} },
}));
vi.mock('../collab/useAwareness', () => ({
  useAwareness: () => ({
    others: [],
    localState: {
      user: {
        id: 'user-1',
        name: 'Ada',
        color: '#cc3366',
        role: 'owner',
      },
      cursor: null,
      selection: { nodeIds: [] },
      activity: 'active',
      dragOwnership: null,
      timestamp: 0,
    },
    setCursor: vi.fn(),
    setSelection: vi.fn(),
    setViewport: vi.fn(),
    setActivity: vi.fn(),
    claimDrag: vi.fn(),
    releaseDrag: vi.fn(),
  }),
}));

const currentUser: CollabUser = {
  id: 'user-1',
  name: 'Ada',
  color: '#cc3366',
  role: 'owner',
};

describe('useCollab', () => {
  beforeEach(() => {
    vi.mocked(apiGet).mockReset();
    vi.mocked(apiPost).mockReset();
    vi.mocked(logError).mockReset();
    authMocks.getToken.mockReturnValue('token');
  });

  it('logs share-state load failures and keeps the unshared fallback', async () => {
    const err = new Error('shares unavailable');
    vi.mocked(apiGet).mockRejectedValueOnce(err);

    const { result } = renderHook(() => useCollab('workflow-1', currentUser));

    await waitFor(() => {
      expect(logError).toHaveBeenCalledWith('collab.useCollab.shares', err);
    });
    expect(result.current.isShared).toBe(false);
  });

  it('throws localized shareWorkflow failure errors', async () => {
    const err = new Error('share failed upstream');
    vi.mocked(apiGet).mockResolvedValueOnce({ shares: [] });
    vi.mocked(apiPost).mockRejectedValueOnce(err);

    const { result } = renderHook(() => useCollab('workflow-1', currentUser));

    await expect(result.current.shareWorkflow('user-2', 'viewer')).rejects.toThrow(
      'No se pudo compartir el flujo de trabajo',
    );
    expect(logError).toHaveBeenCalledWith('collab.useCollab.share', err);
  });

  it('throws localized shareWorkflow sign-in errors', async () => {
    authMocks.getToken.mockReturnValue('');
    vi.mocked(apiGet).mockResolvedValueOnce({ shares: [] });

    const { result } = renderHook(() => useCollab('workflow-1', currentUser));

    await expect(result.current.shareWorkflow('user-2', 'viewer')).rejects.toThrow(
      'Inicia sesion antes de compartir flujos de trabajo',
    );
    expect(apiPost).not.toHaveBeenCalled();
  });
});
