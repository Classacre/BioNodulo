import { act, renderHook } from '@testing-library/react';
import { Provider, createStore } from 'jotai';
import type { ReactNode } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { useClerkAuth } from '../hooks/cloud/useClerkAuth';
import { cloudConfigAtom } from '../state/appAtoms';

const clerkMocks = vi.hoisted(() => {
  const getToken = vi.fn();
  const unsubscribe = vi.fn();
  const clerk = {
    load: vi.fn(),
    session: { getToken },
    user: {
      id: 'user-1',
      fullName: 'Ada Lovelace',
      primaryEmailAddress: null,
      username: null,
    },
    organization: null,
    addListener: vi.fn(),
    openSignIn: vi.fn(),
    openUserProfile: vi.fn(),
    openOrganizationProfile: vi.fn(),
    signOut: vi.fn(),
  };
  return {
    clerk,
    getToken,
    unsubscribe,
    Clerk: vi.fn(function Clerk() {
      return clerk;
    }),
  };
});

const authMocks = vi.hoisted(() => ({
  clearToken: vi.fn(),
  setAuthUser: vi.fn(),
  setToken: vi.fn(),
  // The hook registers a refresher so the API client can retry a 401 once
  // instead of surfacing a transient "Unauthorized" as a failed run.
  registerTokenRefresher: vi.fn(),
}));

vi.mock('@clerk/clerk-js', () => ({ Clerk: clerkMocks.Clerk }));
vi.mock('../collab', () => ({ getUserColor: () => '#123456' }));
vi.mock('../collab/authStorage', () => authMocks);
vi.mock('../state/logging', () => ({ logError: vi.fn() }));

describe('useClerkAuth token refresh', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.clearAllMocks();
    clerkMocks.clerk.load.mockResolvedValue(undefined);
    clerkMocks.clerk.addListener.mockReturnValue(clerkMocks.unsubscribe);
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('bypasses the Clerk token cache before the mirrored bearer expires', async () => {
    clerkMocks.getToken
      .mockResolvedValueOnce('initial-token')
      .mockResolvedValueOnce('refreshed-token');
    const store = createStore();
    store.set(cloudConfigAtom, {
      cloudMode: false,
      editorMode: false,
      user: null,
      team: null,
      plan: null,
      credits: null,
      accountUrl: null,
      clerkPublishableKey: 'pk_test_example',
      oauth: null,
    });
    const wrapper = ({ children }: { children: ReactNode }) => (
      <Provider store={store}>{children}</Provider>
    );

    const { unmount } = renderHook(() => useClerkAuth(), { wrapper });
    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });

    expect(clerkMocks.getToken).toHaveBeenNthCalledWith(1, {
      template: 'bionodulo',
    });
    expect(authMocks.setToken).toHaveBeenLastCalledWith('initial-token');

    await act(async () => {
      await vi.advanceTimersByTimeAsync(45_000);
    });

    expect(clerkMocks.getToken).toHaveBeenNthCalledWith(2, {
      template: 'bionodulo',
      skipCache: true,
    });
    expect(authMocks.setToken).toHaveBeenLastCalledWith('refreshed-token');

    unmount();
    expect(clerkMocks.unsubscribe).toHaveBeenCalledOnce();
  });

  it('does not install refresh work after unmounting during the initial token read', async () => {
    let resolveToken: ((token: string) => void) | undefined;
    clerkMocks.getToken.mockReturnValueOnce(new Promise<string>((resolve) => {
      resolveToken = resolve;
    }));
    const store = createStore();
    store.set(cloudConfigAtom, {
      cloudMode: false,
      editorMode: false,
      user: null,
      team: null,
      plan: null,
      credits: null,
      accountUrl: null,
      clerkPublishableKey: 'pk_test_example',
      oauth: null,
    });
    const wrapper = ({ children }: { children: ReactNode }) => (
      <Provider store={store}>{children}</Provider>
    );

    const { unmount } = renderHook(() => useClerkAuth(), { wrapper });
    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });
    expect(clerkMocks.getToken).toHaveBeenCalledOnce();

    unmount();
    await act(async () => {
      resolveToken?.('late-token');
      await Promise.resolve();
    });

    expect(clerkMocks.clerk.addListener).not.toHaveBeenCalled();
    expect(clerkMocks.unsubscribe).not.toHaveBeenCalled();
    expect(authMocks.setToken).not.toHaveBeenCalled();
    await act(async () => {
      await vi.advanceTimersByTimeAsync(45_000);
    });
    expect(clerkMocks.getToken).toHaveBeenCalledOnce();
  });
});
