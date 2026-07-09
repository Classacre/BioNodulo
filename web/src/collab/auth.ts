import { ApiError, apiGet, apiPost } from '../api/client';
import i18n from '../i18n';
import {
  clearToken,
  getAuthUser,
  getToken,
  setAuthSession,
  setAuthUser,
  setToken,
  tokenExpired,
  type AuthSession,
} from './authStorage';
import { getUserColor } from './utils';

export { clearToken, getAuthUser, getToken, setAuthSession, setAuthUser, setToken };

interface AuthTokenResponse {
  token?: string;
  user_id?: string;
  name?: string;
}

interface AuthMeResponse {
  user_id?: string;
  name?: string;
}

export type AuthTokenError =
  | { code: 'api_failed'; status: number; statusText: string; body: string }
  | { code: 'missing_token' };

export function isAuthTokenError(err: unknown): err is AuthTokenError {
  if (!err || typeof err !== 'object' || !('code' in err)) return false;
  const code = (err as { code?: unknown }).code;
  return code === 'api_failed' || code === 'missing_token';
}

/** Fetch a new JWT token from the auth endpoint */
export async function fetchToken(name: string): Promise<AuthSession> {
  let data: AuthTokenResponse;
  try {
    data = await apiPost<AuthTokenResponse>('/auth/token', { name }, { anonymous: true });
  } catch (err) {
    if (err instanceof ApiError) {
      const body = typeof err.body === 'string' ? err.body : JSON.stringify(err.body ?? null);
      throw { code: 'api_failed', status: err.status, statusText: err.statusText, body } satisfies AuthTokenError;
    }
    throw err;
  }
  if (!data.token || !data.user_id) {
    throw { code: 'missing_token' } satisfies AuthTokenError;
  }
  return {
    token: data.token,
    user: {
      id: data.user_id,
      name: data.name || name,
      color: getUserColor(data.user_id),
      kind: 'guest',
    },
  };
}

/** Validate the existing token by calling /api/auth/me */
export async function initAuth(): Promise<boolean> {
  const token = getToken();
  if (!token) return false;
  if (tokenExpired(token)) {
    clearToken();
    return false;
  }

  try {
    const data = await apiGet<AuthMeResponse>('/auth/me', {
      headers: { Authorization: `Bearer ${token}` },
      anonymous: true,
    });
    if (!data.user_id) {
      clearToken();
      return false;
    }
    setAuthUser({
      id: data.user_id,
      name: data.name || i18n.t('collab.authAnonymousName'),
      color: getUserColor(data.user_id),
    });
    return true;
  } catch (err) {
    if (err instanceof ApiError) {
      // Token is invalid — clear it
      clearToken();
      return false;
    }
    // Network error — keep token for retry later
    return getAuthUser() !== null;
  }
}

/** Generate a random guest user name */
export function generateGuestName(): string {
  const adjectiveKeys = ['azure', 'crimson', 'emerald', 'golden', 'violet', 'silver', 'ruby', 'sapphire', 'amber', 'coral'];
  const nounKeys = ['phoenix', 'falcon', 'tiger', 'wolf', 'dragon', 'bear', 'eagle', 'shark', 'lion', 'hawk'];
  const adjective = i18n.t(`collab.guestAdjectives.${adjectiveKeys[Math.floor(Math.random() * adjectiveKeys.length)]}`);
  const noun = i18n.t(`collab.guestNouns.${nounKeys[Math.floor(Math.random() * nounKeys.length)]}`);
  const number = Math.floor(Math.random() * 9000) + 1000;
  return i18n.t('collab.guestName', { adjective, noun, number });
}
