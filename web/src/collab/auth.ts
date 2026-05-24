import type { AuthUser } from './types';
import { getUserColor } from './utils';

const TOKEN_KEY = 'bionodulo_auth_token';
const USER_KEY = 'bionodulo_auth_user';

interface AuthSession {
  token: string;
  user: AuthUser;
}

function decodeJwtPayload(token: string): Record<string, unknown> | null {
  try {
    const parts = token.split('.');
    if (parts.length < 2) return null;
    const normalized = parts[1].replace(/-/g, '+').replace(/_/g, '/');
    const padded = normalized.padEnd(Math.ceil(normalized.length / 4) * 4, '=');
    const json = decodeURIComponent(
      atob(padded).split('').map(char => `%${char.charCodeAt(0).toString(16).padStart(2, '0')}`).join(''),
    );
    return JSON.parse(json) as Record<string, unknown>;
  } catch {
    return null;
  }
}

function tokenExpired(token: string): boolean {
  const payload = decodeJwtPayload(token);
  const exp = typeof payload?.exp === 'number' ? payload.exp : null;
  return exp !== null && exp * 1000 <= Date.now();
}

/** Get the stored JWT token from localStorage */
export function getToken(): string | null {
  try {
    const token = localStorage.getItem(TOKEN_KEY);
    if (token && tokenExpired(token)) {
      clearToken();
      return null;
    }
    return token;
  } catch {
    return null;
  }
}

/** Store a JWT token in localStorage */
export function setToken(token: string): void {
  try {
    localStorage.setItem(TOKEN_KEY, token);
  } catch {
    // Storage may be disabled or full
  }
}

/** Store authenticated user details returned by the backend */
export function setAuthUser(user: AuthUser): void {
  try {
    localStorage.setItem(USER_KEY, JSON.stringify(user));
  } catch {
    // Storage may be disabled or full
  }
}

/** Store a complete authenticated session */
export function setAuthSession(session: AuthSession): void {
  setToken(session.token);
  setAuthUser(session.user);
}

/** Remove the stored JWT token */
export function clearToken(): void {
  try {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
  } catch {
    // Storage may be disabled
  }
}

/** Get stored auth user info returned by the server */
export function getAuthUser(): AuthUser | null {
  try {
    const raw = localStorage.getItem(USER_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as Partial<AuthUser>;
    if (!parsed.id || !parsed.name) return null;
    return {
      id: String(parsed.id),
      name: String(parsed.name),
      color: String(parsed.color || getUserColor(String(parsed.id))),
    };
  } catch {
    return null;
  }
}

/** Fetch a new JWT token from the auth endpoint */
export async function fetchToken(name: string): Promise<AuthSession> {
  const res = await fetch('/api/auth/token', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name }),
  });
  if (!res.ok) {
    const errText = await res.text().catch(() => 'Unknown error');
    throw new Error(`Auth failed (${res.status}): ${errText}`);
  }
  const data = (await res.json()) as { token?: string; user_id?: string; name?: string };
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
    const res = await fetch('/api/auth/me', {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    });
    if (res.ok) {
      const data = (await res.json()) as { user_id?: string; name?: string };
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
    }
    // Token is invalid — clear it
    clearToken();
    return false;
  } catch {
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
