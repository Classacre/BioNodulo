// Desktop OAuth 2.0 (Authorization Code + PKCE) token machinery for the
// locally-run app. Clerk is the OAuth provider; the app is a public client. The
// browser sign-in yields an authorization code (captured by the local backend
// loopback callback); we exchange it — and later refresh it — through the local
// backend's /api/desktop/token proxy (avoids browser↔Clerk CORS). Access tokens
// are short-lived; the refresh token (persisted locally) keeps the session alive
// without re-opening the browser. This is the correct native-app pattern, and it
// replaces the earlier short-lived-JWT hand-off.
import { apiPost } from '../../api/client';
import { getUserColor } from '../../collab';
import { setToken, setAuthUser, clearToken } from '../../collab/authStorage';
import { getDefaultStore } from 'jotai';
import { authUserAtom } from '../../state/appAtoms';

export interface OAuthConfig { clientId: string; authorizeUrl: string; tokenUrl: string; }
export const OAUTH_SCOPES = 'openid profile email offline_access user:org:read';

const REFRESH_KEY = 'bionodulo_oauth_refresh';
const EXP_KEY = 'bionodulo_oauth_exp';       // access-token expiry (ms epoch)
const REFRESH_SKEW_MS = 60_000;               // refresh a minute before expiry

const store = getDefaultStore();
let refreshTimer: ReturnType<typeof setTimeout> | null = null;

interface TokenResponse {
  access_token?: string;
  refresh_token?: string;
  id_token?: string;
  expires_in?: number;
  error?: string;
  error_description?: string;
}

// --- PKCE helpers ------------------------------------------------------------
function b64url(bytes: ArrayBuffer | Uint8Array): string {
  const arr = bytes instanceof Uint8Array ? bytes : new Uint8Array(bytes);
  let s = '';
  for (const b of arr) s += String.fromCharCode(b);
  return btoa(s).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}
export function genState(): string {
  return b64url(crypto.getRandomValues(new Uint8Array(16)));
}
export function genVerifier(): string {
  return b64url(crypto.getRandomValues(new Uint8Array(32)));
}
export async function challengeFor(verifier: string): Promise<string> {
  const digest = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(verifier));
  return b64url(digest);
}

/** The loopback redirect URI. Always 127.0.0.1 (RFC 8252 §7.3 port-flexible). */
export function redirectUri(): string {
  const port = window.location.port || (window.location.protocol === 'https:' ? '443' : '80');
  return `http://127.0.0.1:${port}/api/desktop/callback`;
}

function decodeJwt(token: string): { sub?: string; name?: string; email?: string } {
  try {
    const json = atob(token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/'));
    return JSON.parse(json);
  } catch {
    return {};
  }
}

/** Persist tokens, publish the bearer + identity, and schedule the next refresh. */
export function applyTokens(oauth: OAuthConfig, tokens: TokenResponse): boolean {
  if (!tokens.access_token) return false;
  setToken(tokens.access_token);
  const expMs = Date.now() + Math.max(30, tokens.expires_in ?? 3600) * 1000;
  try {
    localStorage.setItem(EXP_KEY, String(expMs));
    if (tokens.refresh_token) localStorage.setItem(REFRESH_KEY, tokens.refresh_token);
  } catch { /* ignore */ }

  // Identity for display comes from the id_token (openid scope). The opaque
  // access token can't be decoded.
  if (tokens.id_token) {
    const claims = decodeJwt(tokens.id_token);
    const id = claims.sub || 'me';
    const user = { id, name: claims.name || claims.email || id, color: getUserColor(id) };
    setAuthUser(user);
    store.set(authUserAtom, user);
  }
  scheduleRefresh(oauth);
  return true;
}

/** Exchange an authorization code for tokens via the local backend proxy. */
export async function exchangeCode(oauth: OAuthConfig, code: string, verifier: string): Promise<TokenResponse> {
  return apiPost<TokenResponse>('/desktop/token', {
    token_url: oauth.tokenUrl,
    client_id: oauth.clientId,
    grant_type: 'authorization_code',
    code,
    redirect_uri: redirectUri(),
    code_verifier: verifier,
  });
}

async function refreshOnce(oauth: OAuthConfig): Promise<boolean> {
  let refresh: string | null = null;
  try { refresh = localStorage.getItem(REFRESH_KEY); } catch { /* ignore */ }
  if (!refresh) return false;
  try {
    const tokens = await apiPost<TokenResponse>('/desktop/token', {
      token_url: oauth.tokenUrl,
      client_id: oauth.clientId,
      grant_type: 'refresh_token',
      refresh_token: refresh,
    });
    if (tokens.error || !tokens.access_token) { signOutOAuth(); return false; }
    return applyTokens(oauth, tokens);
  } catch {
    return false;
  }
}

/** Schedule a refresh shortly before the access token expires. */
export function scheduleRefresh(oauth: OAuthConfig): void {
  if (refreshTimer) { clearTimeout(refreshTimer); refreshTimer = null; }
  let expMs = 0;
  try { expMs = Number(localStorage.getItem(EXP_KEY) || 0); } catch { /* ignore */ }
  const delay = Math.max(5_000, expMs - Date.now() - REFRESH_SKEW_MS);
  refreshTimer = setTimeout(() => { void refreshOnce(oauth); }, delay);
}

/** On boot: if we hold a refresh token, restore the session (refresh if stale). */
export async function initDesktopOAuth(oauth: OAuthConfig): Promise<void> {
  let refresh: string | null = null;
  let expMs = 0;
  try {
    refresh = localStorage.getItem(REFRESH_KEY);
    expMs = Number(localStorage.getItem(EXP_KEY) || 0);
  } catch { /* ignore */ }
  if (!refresh) return;
  if (expMs - Date.now() < REFRESH_SKEW_MS) {
    await refreshOnce(oauth);
  } else {
    scheduleRefresh(oauth);
  }
}

/** Clear the OAuth session (bearer + refresh token + timer). */
export function signOutOAuth(): void {
  if (refreshTimer) { clearTimeout(refreshTimer); refreshTimer = null; }
  try {
    localStorage.removeItem(REFRESH_KEY);
    localStorage.removeItem(EXP_KEY);
  } catch { /* ignore */ }
  clearToken();
  store.set(authUserAtom, null);
}
