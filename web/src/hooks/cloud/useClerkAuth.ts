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
import { clearToken, registerTokenRefresher, setAuthUser, setToken } from '../../collab/authStorage';
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

/** Opaque owner changes on every session/user/org transition, including A→B→A. */
export interface ClerkIdentitySync {
  owner: object;
  userId: string | null;
  orgId: string | null;
  ready: boolean;
}

export function useClerkAuth(
  onIdentitySync?: (event: ClerkIdentitySync) => Promise<boolean>,
): UseClerkAuthResult {
  const cloudConfig = useAtomValue(cloudConfigAtom);
  const setAuthUserAtom = useSetAtom(authUserAtom);
  const clerkRef = useRef<Clerk | null>(null);
  const identitySyncRef = useRef(onIdentitySync);
  identitySyncRef.current = onIdentitySync;
  const invalidateRef = useRef<(() => void) | null>(null);
  const [clerkEnabled, setClerkEnabled] = useState(false);
  const [clerkSignedIn, setClerkSignedIn] = useState(false);

  const publishableKey = cloudConfig?.clerkPublishableKey ?? null;
  // cloudMode auto-login is handled elsewhere; never run Clerk there.
  const active = Boolean(publishableKey) && !cloudConfig?.cloudMode;

  useEffect(() => {
    if (!active || !publishableKey) return;
    let cancelled = false;
    let refreshTimer: ReturnType<typeof setInterval> | null = null;
    let unsubscribe: (() => void) | null = null;
    let tokenEpoch = 0;
    let scope: { sessionKey: unknown; userId: string | null; orgId: string | null; owner: object } | null = null;
    let identityReady = false;
    let identityPending: object | null = null;
    let signedOutSessionKey: unknown;

    const notify = (event: ClerkIdentitySync) => {
      const callback = identitySyncRef.current;
      return callback ? callback(event).catch(err => {
        if (!cancelled) logError('clerk.identity.sync', err);
        return false;
      }) : Promise.resolve(false);
    };
    const invalidateSharedIdentity = () => {
      tokenEpoch += 1;
      scope = { sessionKey: scope?.sessionKey ?? null,
        userId: scope?.userId ?? null, orgId: scope?.orgId ?? null, owner: {} };
      identityReady = false;
      identityPending = null;
      void notify({ owner: scope.owner, userId: null, orgId: null, ready: false });
    };
    const invalidate = () => {
      const session = clerkRef.current?.session;
      signedOutSessionKey = session?.id ?? session;
      invalidateSharedIdentity();
    };
    invalidateRef.current = invalidate;

    // Pull the current session JWT and mirror the Clerk user into the app's
    // token store + authUser atom. Clearing happens when no session is active.
    const sync = async (clerk: Clerk, skipCache = false) => {
      if (cancelled) return;
      try {
        const session = clerk.session;
        const userSnapshot = clerk.user;
        const sessionKey = session?.id ?? session;
        const blockedSession = Boolean(session && signedOutSessionKey === sessionKey);
        const userId = session && !blockedSession ? userSnapshot?.id ?? null : null;
        const orgId = userId ? clerk.organization?.id ?? null : null;
        if (!scope || scope.sessionKey !== sessionKey || scope.userId !== userId || scope.orgId !== orgId) {
          scope = { sessionKey, userId, orgId, owner: {} };
          identityReady = false;
          identityPending = null;
          clearToken();
          // Invalidate older /me responses before awaiting a new token.
          void notify({ ...scope, ready: false });
        }
        const expected = scope;
        const epoch = ++tokenEpoch;
        const current = () => !cancelled && tokenEpoch === epoch && scope === expected
          && (clerk.session?.id ?? clerk.session) === sessionKey
          && (clerk.user?.id ?? null) === userId && (clerk.organization?.id ?? null) === orgId;
        if (!session) signedOutSessionKey = undefined;
        if (!session || !userSnapshot || blockedSession) {
          clearToken();
          setAuthUserAtom(null);
          setClerkSignedIn(false);
          return;
        }
        let token: string | null = null;
        try {
          token = await session.getToken({
            template: CLERK_JWT_TEMPLATE,
            ...(skipCache ? { skipCache: true } : {}),
          });
        } catch {
          // No such template configured — fall back to the default session JWT.
          if (!current()) return;
          token = await session.getToken(skipCache ? { skipCache: true } : undefined);
        }
        if (!current()) return;
        if (!token) {
          invalidateSharedIdentity();
          clearToken();
          setAuthUserAtom(null);
          setClerkSignedIn(false);
          return;
        }
        const u = userSnapshot;
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
          kind: 'account' as const,
        };
        setToken(token);
        setAuthUser(user);
        setAuthUserAtom(user);
        setClerkSignedIn(true);
        // A failed initial cookie read can recover once Clerk has established
        // its session. Do not refetch on every token refresh after success.
        if (!identityReady && !identityPending && identitySyncRef.current) {
          const pending = {};
          identityPending = pending;
          void notify({ ...expected, ready: true }).then(ready => {
            if (!cancelled && scope === expected && identityPending === pending) {
              identityPending = null;
              identityReady = ready;
            }
          });
        }
        return token;
      } catch (err) {
        if (!cancelled) logError('clerk.session.sync', err);
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
        // React to sign-in / sign-out / session changes.
        unsubscribe = clerk.addListener(() => {
          void sync(clerk);
        });
        await sync(clerk);
        if (cancelled) return;
        // Force a server token read before the mirrored bearer expires. A plain
        // getToken() may legally return Clerk's cached JWT within its TTL.
        refreshTimer = setInterval(() => {
          void sync(clerk, true);
        }, TOKEN_REFRESH_MS);
        // The API client calls this when a request comes back 401, so a token
        // that lapsed between refreshes costs one retry instead of surfacing as
        // a failed run. The timer above is throttled in background tabs, which
        // is exactly when the lapse happens.
        registerTokenRefresher(async () => (await sync(clerk, true)) ?? null);
      } catch (err) {
        logError('clerk.load', err);
      }
    })();

    const onFocus = () => {
      const clerk = clerkRef.current;
      if (clerk) void sync(clerk, true);
    };
    window.addEventListener('focus', onFocus);

    return () => {
      invalidate();
      cancelled = true;
      window.removeEventListener('focus', onFocus);
      if (refreshTimer) clearInterval(refreshTimer);
      registerTokenRefresher(null);
      unsubscribe?.();
      clerkRef.current = null;
      if (invalidateRef.current === invalidate) invalidateRef.current = null;
    };
    // publishableKey/active fully determine the effect.
  }, [active, publishableKey, setAuthUserAtom]);

  const openSignIn = () => {
    clerkRef.current?.openSignIn();
  };

  // openUserProfile/openOrganizationProfile used to live here. They could
  // never run: this SPA bundles clerk-js itself and the UI chunks are absent,
  // so both threw "Clerk was not loaded with Ui components", and the desktop
  // CSP blocked them regardless. The account panel links to the website, which
  // renders those same screens properly.

  const signOut = () => {
    const clerk = clerkRef.current;
    invalidateRef.current?.();
    clearToken();
    setAuthUserAtom(null);
    setClerkSignedIn(false);
    if (clerk) void clerk.signOut();
  };

  return { clerkEnabled, clerkSignedIn, openSignIn, signOut };
}
