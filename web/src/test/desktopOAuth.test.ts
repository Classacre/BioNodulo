import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { getDefaultStore } from 'jotai';
import { apiPost } from '../api/client';
import { authUserAtom } from '../state/appAtoms';
import { getToken } from '../collab/authStorage';
import { applyTokens, signOutOAuth, type OAuthConfig } from '../hooks/cloud/desktopOAuth';

vi.mock('../api/client', () => ({ apiPost: vi.fn() }));
vi.mock('../collab', () => ({ getUserColor: () => '#123456' }));

const oauth: OAuthConfig = {
  clientId: 'test-client',
  authorizeUrl: 'https://auth.example/oauth/authorize',
  tokenUrl: 'https://auth.example/oauth/token',
};

describe('desktop OAuth session lifecycle', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.resetAllMocks();
    localStorage.clear();
    signOutOAuth();
  });

  afterEach(() => {
    signOutOAuth();
    vi.useRealTimers();
  });

  it('retries refresh after a temporary network failure', async () => {
    vi.mocked(apiPost)
      .mockRejectedValueOnce(new TypeError('Failed to fetch'))
      .mockResolvedValueOnce({ access_token: 'renewed-access', expires_in: 3600 });
    applyTokens(oauth, { access_token: 'initial-access', refresh_token: 'refresh', expires_in: 65 });

    await vi.advanceTimersByTimeAsync(5_000);
    expect(apiPost).toHaveBeenCalledOnce();
    expect(getToken()).toBe('initial-access');
    await vi.advanceTimersByTimeAsync(30_000);

    expect(apiPost).toHaveBeenCalledTimes(2);
    expect(getToken()).toBe('renewed-access');
  });

  it('does not restore a session when an in-flight refresh finishes after sign-out', async () => {
    let finishRefresh!: (tokens: unknown) => void;
    vi.mocked(apiPost).mockReturnValueOnce(new Promise(resolve => { finishRefresh = resolve; }));
    applyTokens(oauth, { access_token: 'initial-access', refresh_token: 'refresh', expires_in: 65 });
    await vi.advanceTimersByTimeAsync(5_000);
    expect(apiPost).toHaveBeenCalledOnce();

    signOutOAuth();
    finishRefresh({ access_token: 'late-access', refresh_token: 'late-refresh', expires_in: 3600 });
    await vi.advanceTimersByTimeAsync(0);

    expect(getToken()).toBeNull();
    expect(localStorage.getItem('bionodulo_oauth_refresh')).toBeNull();
    expect(getDefaultStore().get(authUserAtom)).toBeNull();
    expect(vi.getTimerCount()).toBe(0);
  });

  it('does not schedule retries when a failed refresh finishes after sign-out', async () => {
    let failRefresh!: (error: Error) => void;
    vi.mocked(apiPost).mockReturnValueOnce(new Promise((_, reject) => { failRefresh = reject; }));
    applyTokens(oauth, { access_token: 'initial-access', refresh_token: 'refresh', expires_in: 65 });
    await vi.advanceTimersByTimeAsync(5_000);
    signOutOAuth();
    failRefresh(new TypeError('Failed to fetch'));
    await vi.advanceTimersByTimeAsync(30_000);

    expect(apiPost).toHaveBeenCalledOnce();
    expect(vi.getTimerCount()).toBe(0);
  });
});
