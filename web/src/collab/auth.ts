import type { AuthUser } from './types';
import { getUserColor } from './utils';

const TOKEN_KEY = 'bionodulo_auth_token';

/** Decode a Base64Url-encoded string (JWT-safe variant of Base64) */
function base64UrlDecode(str: string): string {
  // Replace Base64Url chars with standard Base64
  let normalized = str.replace(/-/g, '+').replace(/_/g, '/');
  // Add padding if needed
  while (normalized.length % 4) {
    normalized += '=';
  }
  try {
    return atob(normalized);
  } catch {
    return '{}';
  }
}

/** Extract the JWT payload without verifying the signature */
function decodeJwtPayload(token: string): Record<string, unknown> | null {
  const parts = token.split('.');
  if (parts.length !== 3) return null;
  try {
    const payloadJson = base64UrlDecode(parts[1]);
    return JSON.parse(payloadJson) as Record<string, unknown>;
  } catch {
    return null;
  }
}

/** Get the stored JWT token from localStorage */
export function getToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEY);
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

/** Remove the stored JWT token */
export function clearToken(): void {
  try {
    localStorage.removeItem(TOKEN_KEY);
  } catch {
    // Storage may be disabled
  }
}

/** Extract auth user info from the JWT payload (no signature verification) */
export function getAuthUser(): AuthUser | null {
  const token = getToken();
  if (!token) return null;
  const payload = decodeJwtPayload(token);
  if (!payload) return null;
  const id = String(payload.sub || payload.id || payload.user_id || '');
  const name = String(payload.name || payload.display_name || 'Anonymous');
  const color = String(payload.color || getUserColor(id));
  if (!id) return null;
  return { id, name, color };
}

/** Fetch a new JWT token from the auth endpoint */
export async function fetchToken(name: string): Promise<string> {
  const res = await fetch('/api/auth/token', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name }),
  });
  if (!res.ok) {
    const errText = await res.text().catch(() => 'Unknown error');
    throw new Error(`Auth failed (${res.status}): ${errText}`);
  }
  const data = (await res.json()) as { token?: string };
  if (!data.token) {
    throw new Error('Auth response missing token');
  }
  return data.token;
}

/** Validate the existing token by calling /api/auth/me */
export async function initAuth(): Promise<boolean> {
  const token = getToken();
  if (!token) return false;

  try {
    const res = await fetch('/api/auth/me', {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    });
    if (res.ok) {
      return true;
    }
    // Token is invalid — clear it
    clearToken();
    return false;
  } catch {
    // Network error — keep token for retry later
    return true;
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
