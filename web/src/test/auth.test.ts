import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { ApiError, apiGet, apiPost } from '../api/client';
import { clearToken, fetchToken, generateGuestName, getAuthUser, initAuth, isAuthTokenError, setAuthSession } from '../collab/auth';

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

  afterEach(async () => {
    const { setLanguage } = await import('../i18n');
    await setLanguage('en');
    clearToken();
    storage.clear();
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
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

    await expect(fetchToken('Mika')).rejects.toMatchObject({ code: 'missing_token' });
  });

  it('rejects API token failures with structured auth error context', async () => {
    vi.mocked(apiPost).mockRejectedValueOnce(new ApiError('unauthorized', 401, 'Unauthorized', 'invalid'));

    await expect(fetchToken('Mika')).rejects.toMatchObject({
      code: 'api_failed',
      status: 401,
      body: 'invalid',
    });
  });

  it('detects structured auth token failures', () => {
    expect(isAuthTokenError({ code: 'missing_token' })).toBe(true);
    expect(isAuthTokenError({ code: 'api_failed', status: 401 })).toBe(true);
    expect(isAuthTokenError(new Error('Auth failed'))).toBe(false);
  });

  it('keeps auth token fallback errors out of low-level English messages', () => {
    const source = readFileSync(resolve(__dirname, '../collab/auth.ts'), 'utf8');

    [
      'Auth failed',
      'Auth response missing token',
      "'Anonymous'",
      '`Guest ',
      "'Azure'",
      "'Phoenix'",
    ].forEach(text => {
      expect(source).not.toContain(text);
    });
  });

  it('uses locale copy for missing authenticated user names', async () => {
    const { default: i18n, setLanguage } = await import('../i18n');
    await setLanguage('es');
    setAuthSession({
      token: jwtWithExp(Math.floor(Date.now() / 1000) + 60),
      user: { id: 'user-1', name: 'Mika', color: '#123456' },
    });
    vi.mocked(apiGet).mockResolvedValueOnce({ user_id: 'user-2' });

    await expect(initAuth()).resolves.toBe(true);

    expect(i18n.t('collab.authAnonymousName')).toBe('Anonimo');
    expect(getAuthUser()).toEqual(expect.objectContaining({ id: 'user-2', name: 'Anonimo' }));
  });

  it('generates guest names from the active locale', async () => {
    const { default: i18n, setLanguage } = await import('../i18n');
    await setLanguage('es');
    vi.spyOn(Math, 'random').mockReturnValue(0);

    expect(i18n.t('collab.guestName', {
      adjective: i18n.t('collab.guestAdjectives.azure'),
      noun: i18n.t('collab.guestNouns.phoenix'),
      number: 1000,
    })).toBe('Invitado AzulFenix1000');
    expect(generateGuestName()).toBe('Invitado AzulFenix1000');
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
