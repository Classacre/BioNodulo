import { ApiError, apiGet, apiPost } from '../api/client';
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

/** Fetch a new JWT token from the auth endpoint */
export async function fetchToken(name: string): Promise<AuthSession> {
  let data: AuthTokenResponse;
  try {
    data = await apiPost<AuthTokenResponse>('/auth/token', { name }, { anonymous: true });
  } catch (err) {
    if (err instanceof ApiError) {
      const body = typeof err.body === 'string' ? err.body : JSON.stringify(err.body ?? 'Unknown error');
      throw new Error(`Auth failed (${err.status}): ${body}`);
    }
    throw err;
  }
  if (!data.token || !data.user_id) {
    throw new Error('Auth response missing token');
  }
  return {
    token: data.token,
    user: {
      id: data.user_id,
      name: data.name || name,
      color: getUserColor(data.user_id),
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
      name: data.name || 'Anonymous',
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
  const adjectives = ['Azure', 'Crimson', 'Emerald', 'Golden', 'Violet', 'Silver', 'Ruby', 'Sapphire', 'Amber', 'Coral'];
  const nouns = ['Phoenix', 'Falcon', 'Tiger', 'Wolf', 'Dragon', 'Bear', 'Eagle', 'Shark', 'Lion', 'Hawk'];
  const adj = adjectives[Math.floor(Math.random() * adjectives.length)];
  const noun = nouns[Math.floor(Math.random() * nouns.length)];
  const num = Math.floor(Math.random() * 9000) + 1000;
  return `Guest ${adj}${noun}${num}`;
}
