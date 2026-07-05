// Desktop / locally-run app sign-in via loopback OAuth.
//
// The local app runs on http://127.0.0.1:PORT where Clerk's production keys
// won't load (domain-locked). So we open the cloud's /desktop-auth page in a
// browser window (an allowed origin, where Clerk works). After the user signs
// in, that page mints a Clerk JWT and redirects the browser to our local
// backend's /api/desktop/callback?token=&state=, which stashes it. We poll
// /api/desktop/session?state= to pick the token up, then store it like any other
// bearer so api/client.ts + api/website.ts send it to the cloud.
import { useCallback, useRef, useState } from 'react';
import { useAtomValue, useSetAtom } from 'jotai';
import { getUserColor } from '../../collab';
import { setToken, setAuthUser } from '../../collab/authStorage';
import { authUserAtom, cloudConfigAtom } from '../../state/appAtoms';
import { apiGet } from '../../api/client';
import { logError } from '../../state/logging';

const POLL_MS = 1500;
const TIMEOUT_MS = 5 * 60_000;

/** Decode a JWT payload without verifying (id/name only, for display). */
function decodeJwt(token: string): { sub?: string; name?: string; email?: string } {
  try {
    const part = token.split('.')[1];
    const json = atob(part.replace(/-/g, '+').replace(/_/g, '/'));
    return JSON.parse(json);
  } catch {
    return {};
  }
}

function randomState(): string {
  const a = new Uint8Array(16);
  crypto.getRandomValues(a);
  return Array.from(a, b => b.toString(16).padStart(2, '0')).join('');
}

export interface UseDesktopAuthResult {
  /** True while waiting for the browser sign-in to complete. */
  pending: boolean;
  /** Open the cloud sign-in in a browser window and adopt the returned token. */
  signInViaBrowser: () => void;
  /** Cancel an in-progress wait. */
  cancel: () => void;
}

export function useDesktopAuth(): UseDesktopAuthResult {
  const cloudConfig = useAtomValue(cloudConfigAtom);
  const setAuthUserAtom = useSetAtom(authUserAtom);
  const [pending, setPending] = useState(false);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const deadlineRef = useRef(0);

  const stop = useCallback(() => {
    if (timerRef.current) { clearInterval(timerRef.current); timerRef.current = null; }
    setPending(false);
  }, []);

  const adopt = useCallback((token: string) => {
    const claims = decodeJwt(token);
    const id = claims.sub || 'me';
    const user = { id, name: claims.name || claims.email || id, color: getUserColor(id) };
    setToken(token);
    setAuthUser(user);
    setAuthUserAtom(user);
  }, [setAuthUserAtom]);

  const signInViaBrowser = useCallback(() => {
    const accountUrl = cloudConfig?.accountUrl?.replace(/\/+$/, '');
    if (!accountUrl) return;
    const state = randomState();
    const host = window.location.hostname === 'localhost' ? 'localhost' : '127.0.0.1';
    const port = window.location.port || (window.location.protocol === 'https:' ? '443' : '80');
    const url = `${accountUrl}/desktop-auth?host=${host}&port=${encodeURIComponent(port)}&state=${state}`;
    // A blank tab / Electron child window on the cloud origin (Clerk works there).
    window.open(url, '_blank', 'noopener,noreferrer');

    setPending(true);
    deadlineRef.current = Date.now() + TIMEOUT_MS;
    if (timerRef.current) clearInterval(timerRef.current);
    timerRef.current = setInterval(async () => {
      if (Date.now() > deadlineRef.current) { stop(); return; }
      try {
        const res = await apiGet<{ token: string | null }>(`/desktop/session?state=${state}`, { anonymous: true });
        if (res.token) { adopt(res.token); stop(); }
      } catch (err) {
        logError('desktop.auth.poll', err);
      }
    }, POLL_MS);
  }, [cloudConfig, adopt, stop]);

  return { pending, signInViaBrowser, cancel: stop };
}
