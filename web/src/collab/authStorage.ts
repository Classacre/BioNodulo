import type { AuthUser } from './types';
import { getUserColor } from './utils';

const TOKEN_KEY = 'bionodulo_auth_token';
const USER_KEY = 'bionodulo_auth_user';

export interface AuthSession {
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

export function tokenExpired(token: string): boolean {
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
      kind: parsed.kind === 'account' ? 'account' : 'guest',
    };
  } catch {
    return null;
  }
}

export function isGuestUser(user: { kind?: 'guest' | 'account' } | null): boolean {
  return !!user && user.kind !== 'account';
}


// --- token refresh hook -------------------------------------------------
//
// getToken() deliberately clears an expired token and returns null, so a request
// made a second past the TTL goes out with NO Authorization header and is
// rejected as Unauthorized. Clerk's session token lives ~60s and is re-pulled on
// a 45s interval, but browsers throttle timers in background tabs, so that
// window is missed routinely -- the user sees "Unauthorized" for a run that is
// actually fine.
//
// The auth layer registers a refresher here; the API client calls it once
// before retrying a 401 rather than surfacing a transient failure.
type TokenRefresher = () => Promise<string | null>;

let tokenRefresher: TokenRefresher | null = null;

export function registerTokenRefresher(refresher: TokenRefresher | null): void {
  tokenRefresher = refresher;
}

/** Force a fresh token. Returns null when no refresher is registered. */
export async function refreshToken(): Promise<string | null> {
  if (!tokenRefresher) return null;
  try {
    return await tokenRefresher();
  } catch {
    return null;
  }
}
