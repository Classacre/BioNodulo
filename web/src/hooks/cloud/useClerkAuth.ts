// Optional Clerk sign-in for self-host / local mode.
//
// Gating (all decided from `/api/config`, fetched by useCloudConfig):
//   - cloudMode === true            -> do nothing. The injected identity is
//                                      already adopted by useCloudConfig.
//   - clerkPublishableKey present   -> lazy-load @clerk/clerk-js, initialise it
//     and not cloudMode               with that key, and expose signIn/signOut.
//                                      On an active Clerk session the session
//                                      JWT is pulled and stored via the app's
//                                      setToken() so api/client.ts sends it; the
//                                      Clerk user populates authUserAtom.
//   - no key & not cloudMode        -> no-op. The app stays fully usable with no
//                                      login (this hook never touches Clerk).
//
// Clerk is only imported when a publishable key is present, so the SDK is never
// loaded — and never a runtime dependency — for the no-login path.
//
// The backend validates the Clerk session JWT as a generic OIDC token (see
// bionodulo/collab/auth.py). For that to work the deployer sets:
//   BIONODULO_OIDC_ISSUER   = https://clerk.<your-domain>   (Clerk Frontend API)
//   BIONODULO_OIDC_JWKS_URL = <issuer>/.well-known/jwks.json (optional; derived
//                             from the issuer when omitted)
//   BIONODULO_OIDC_AUDIENCE = the `aud` claim of the token. Clerk's default
//                             session token has no `aud`, so define a Clerk JWT
//                             template named `bionodulo` whose `aud` equals this
//                             value, and this hook requests that template below.

import { useEffect, useRef, useState } from 'react';
import { useAtomValue, useSetAtom } from 'jotai';
import type { Clerk } from '@clerk/clerk-js';
import { getUserColor } from '../../collab';
import { clearToken, setAuthUser, setToken } from '../../collab/authStorage';
import { authUserAtom, cloudConfigAtom } from '../../state/appAtoms';
import { logError } from '../../state/logging';

// JWT template (configured in the Clerk dashboard) used so the issued token's
// `aud` matches BIONODULO_OIDC_AUDIENCE. When the deployment validates the raw
// session token instead, Clerk falls back to the default token automatically.
const CLERK_JWT_TEMPLATE = 'bionodulo';
// Re-pull the session token a little before the default ~60s Clerk token TTL.
const TOKEN_REFRESH_MS = 45_000;

export interface UseClerkAuthResult {
  /** True once a publishable key is present and Clerk has finished loading. */
  clerkEnabled: boolean;
  /** True while Clerk reports an active, signed-in session. */
  clerkSignedIn: boolean;
  /** Open Clerk's hosted sign-in (modal). No-op until Clerk is ready. */
  openSignIn: () => void;
  /** Sign out of Clerk and clear the app token. */
  signOut: () => void;
}

export function useClerkAuth(): UseClerkAuthResult {
  const cloudConfig = useAtomValue(cloudConfigAtom);
  const setAuthUserAtom = useSetAtom(authUserAtom);
  const clerkRef = useRef<Clerk | null>(null);
  const [clerkEnabled, setClerkEnabled] = useState(false);
  const [clerkSignedIn, setClerkSignedIn] = useState(false);

  const publishableKey = cloudConfig?.clerkPublishableKey ?? null;
  // cloudMode auto-login is handled elsewhere; never run Clerk there.
  const active = Boolean(publishableKey) && !cloudConfig?.cloudMode;

  useEffect(() => {
    if (!active || !publishableKey) return;
    let cancelled = false;
    let refreshTimer: ReturnType<typeof setInterval> | null = null;

    // Pull the current session JWT and mirror the Clerk user into the app's
    // token store + authUser atom. Clearing happens when no session is active.
    const sync = async (clerk: Clerk) => {
      try {
        const session = clerk.session;
        if (!session || !clerk.user) {
          clearToken();
          setAuthUserAtom(null);
          setClerkSignedIn(false);
          return;
        }
        let token: string | null = null;
        try {
          token = await session.getToken({ template: CLERK_JWT_TEMPLATE });
        } catch {
          // No such template configured — fall back to the default session JWT.
          token = await session.getToken();
        }
        if (cancelled) return;
        if (!token) {
          clearToken();
          setAuthUserAtom(null);
          setClerkSignedIn(false);
          return;
        }
        const u = clerk.user;
        const id = u.id;
        const name =
          u.fullName ||
          u.primaryEmailAddress?.emailAddress ||
          u.username ||
          id;
        const user = {
          id,
          name,
          color: getUserColor(id),
        };
        setToken(token);
        setAuthUser(user);
        setAuthUserAtom(user);
        setClerkSignedIn(true);
      } catch (err) {
        logError('clerk.session.sync', err);
      }
    };

    (async () => {
      try {
        const { Clerk: ClerkCtor } = await import('@clerk/clerk-js');
        if (cancelled) return;
        const clerk = new ClerkCtor(publishableKey);
        await clerk.load();
        if (cancelled) return;
        clerkRef.current = clerk;
        setClerkEnabled(true);
        await sync(clerk);
        // React to sign-in / sign-out / session changes.
        clerk.addListener(() => { void sync(clerk); });
        // clerk-js refreshes the underlying session itself; we just re-pull the
        // short-lived JWT on a timer and when the tab regains focus.
        refreshTimer = setInterval(() => { void sync(clerk); }, TOKEN_REFRESH_MS);
      } catch (err) {
        logError('clerk.load', err);
      }
    })();

    const onFocus = () => {
      const clerk = clerkRef.current;
      if (clerk) void sync(clerk);
    };
    window.addEventListener('focus', onFocus);

    return () => {
      cancelled = true;
      window.removeEventListener('focus', onFocus);
      if (refreshTimer) clearInterval(refreshTimer);
    };
    // publishableKey/active fully determine the effect.
  }, [active, publishableKey, setAuthUserAtom]);

  const openSignIn = () => {
    clerkRef.current?.openSignIn();
  };

  const signOut = () => {
    const clerk = clerkRef.current;
    clearToken();
    setAuthUserAtom(null);
    setClerkSignedIn(false);
    if (clerk) void clerk.signOut();
  };

  return { clerkEnabled, clerkSignedIn, openSignIn, signOut };
}
