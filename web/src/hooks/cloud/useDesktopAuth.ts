// Desktop / locally-run app sign-in via OAuth 2.0 Authorization Code + PKCE.
//
// The local app runs on http://127.0.0.1:PORT where Clerk's SDK won't load
// (domain-locked). So it authenticates as a public OAuth client (RFC 8252):
// open the system browser to Clerk's /oauth/authorize with a PKCE challenge;
// after sign-in + consent Clerk redirects to the app's loopback callback with an
// authorization code; the local backend captures it; we poll for it, then
// exchange it (with the PKCE verifier) for access + refresh tokens via the
// backend proxy. Tokens are stored + auto-refreshed by desktopOAuth.ts.
import { useCallback, useRef, useState } from 'react';
import { useAtomValue } from 'jotai';
import { cloudConfigAtom } from '../../state/appAtoms';
import { apiGet } from '../../api/client';
import { logError } from '../../state/logging';
import {
  genState, genVerifier, challengeFor, redirectUri, exchangeCode, applyTokens,
  OAUTH_SCOPES, type OAuthConfig,
} from './desktopOAuth';

const POLL_MS = 1500;
const TIMEOUT_MS = 5 * 60_000;

export interface UseDesktopAuthResult {
  pending: boolean;
  /** Whether the local instance is configured for OAuth sign-in. */
  available: boolean;
  signInViaBrowser: () => void;
  cancel: () => void;
}

export function useDesktopAuth(): UseDesktopAuthResult {
  const cloudConfig = useAtomValue(cloudConfigAtom);
  const oauth = cloudConfig?.oauth ?? null;
  const [pending, setPending] = useState(false);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const deadlineRef = useRef(0);

  const stop = useCallback(() => {
    if (timerRef.current) { clearInterval(timerRef.current); timerRef.current = null; }
    setPending(false);
  }, []);

  const signInViaBrowser = useCallback(() => {
    if (!oauth?.clientId || !oauth.authorizeUrl || !oauth.tokenUrl) return;
    const cfg: OAuthConfig = oauth;
    setPending(true);
    (async () => {
      const state = genState();
      const verifier = genVerifier();
      const challenge = await challengeFor(verifier);
      const authorize = new URL(cfg.authorizeUrl);
      authorize.searchParams.set('response_type', 'code');
      authorize.searchParams.set('client_id', cfg.clientId);
      authorize.searchParams.set('redirect_uri', redirectUri());
      authorize.searchParams.set('scope', OAUTH_SCOPES);
      authorize.searchParams.set('state', state);
      authorize.searchParams.set('code_challenge', challenge);
      authorize.searchParams.set('code_challenge_method', 'S256');
      // A browser tab / Electron child window on the Clerk origin (SDK works there).
      window.open(authorize.toString(), '_blank', 'noopener,noreferrer');

      deadlineRef.current = Date.now() + TIMEOUT_MS;
      if (timerRef.current) clearInterval(timerRef.current);
      timerRef.current = setInterval(async () => {
        if (Date.now() > deadlineRef.current) { stop(); return; }
        try {
          const res = await apiGet<{ code: string | null; error: string | null }>(
            `/desktop/session?state=${state}`, { anonymous: true });
          if (res.error) { logError('desktop.oauth', new Error(res.error)); stop(); return; }
          if (res.code) {
            stop();
            const tokens = await exchangeCode(cfg, res.code, verifier);
            if (!applyTokens(cfg, tokens)) {
              logError('desktop.oauth.exchange', new Error(tokens.error || 'no access_token'));
            }
          }
        } catch (err) {
          logError('desktop.oauth.poll', err);
        }
      }, POLL_MS);
    })();
  }, [oauth, stop]);

  return { pending, available: Boolean(oauth?.clientId), signInViaBrowser, cancel: stop };
}
