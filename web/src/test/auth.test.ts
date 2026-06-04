import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiError, apiGet, apiPost } from '../api/client';
import { clearToken, fetchToken, getAuthUser, initAuth, setAuthSession } from '../collab/auth';

const apiMocks = vi.hoisted(() => {
  class MockApiError extends Error {
    readonly status: number;
    readonly statusText: string;
    readonly body: unknown;

    constructor(message: string, status: number, statusText: string, body: unknown) {
      super(message);
      this.name = 'ApiError';
      this.status = status;
      this.statusText = statusText;
      this.body = body;
    }
  }

  return {
    ApiError: MockApiError,
    apiGet: vi.fn(),
    apiPost: vi.fn(),
  };
});

vi.mock('../api/client', () => apiMocks);

const storage = new Map<string, string>();
const fakeStorage: Storage = {
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

function jwtWithExp(expSeconds: number): string {
  const payload = btoa(JSON.stringify({ exp: expSeconds })).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
  return `header.${payload}.signature`;
}

describe('collab/auth', () => {
  beforeEach(() => {
    vi.stubGlobal('localStorage', fakeStorage);
    storage.clear();
    clearToken();
    vi.mocked(apiGet).mockReset();
    vi.mocked(apiPost).mockReset();
  });

  afterEach(() => {
    clearToken();
    storage.clear();
    vi.unstubAllGlobals();
  });

  it('fetches a token through the API client and shapes the auth session', async () => {
    vi.mocked(apiPost).mockResolvedValueOnce({
      token: 'jwt-token',
      user_id: 'user-1',
      name: 'Mika',
    });

    const session = await fetchToken('Guest');

    expect(apiPost).toHaveBeenCalledWith('/auth/token', { name: 'Guest' }, { anonymous: true });
    expect(session).toEqual({
      token: 'jwt-token',
      user: expect.objectContaining({ id: 'user-1', name: 'Mika' }),
    });
  });

  it('rejects token responses missing required fields', async () => {
    vi.mocked(apiPost).mockResolvedValueOnce({ name: 'Mika' });

    await expect(fetchToken('Mika')).rejects.toThrow('Auth response missing token');
  });

  it('clears invalid stored tokens when auth validation returns an API error', async () => {
    setAuthSession({
      token: jwtWithExp(Math.floor(Date.now() / 1000) + 60),
      user: { id: 'user-1', name: 'Mika', color: '#123456' },
    });
    expect(getAuthUser()).toEqual({ id: 'user-1', name: 'Mika', color: '#123456' });
    vi.mocked(apiGet).mockRejectedValueOnce(new ApiError('unauthorized', 401, 'Unauthorized', 'invalid'));

    await expect(initAuth()).resolves.toBe(false);

    expect(getAuthUser()).toBeNull();
  });

  it('keeps the stored user when auth validation has a network failure', async () => {
    setAuthSession({
      token: jwtWithExp(Math.floor(Date.now() / 1000) + 60),
      user: { id: 'user-1', name: 'Mika', color: '#123456' },
    });
    expect(getAuthUser()).toEqual({ id: 'user-1', name: 'Mika', color: '#123456' });
    vi.mocked(apiGet).mockRejectedValueOnce(new TypeError('network down'));

    await expect(initAuth()).resolves.toBe(true);

    expect(getAuthUser()).toEqual({ id: 'user-1', name: 'Mika', color: '#123456' });
  });
});
