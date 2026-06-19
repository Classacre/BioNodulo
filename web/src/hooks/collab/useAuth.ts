// Encapsulates the auth init flow + login/close handlers that App.tsx used to
// run inline. Returns a small object the host component can spread into
// `<AuthDialog>` and the rest of the auth-aware UI.
//
// Behaviour: if collab is disabled or settings haven't loaded yet, mark auth
// as ready and skip the dialog. Otherwise call `initAuth()`, populate the
// authUser atom on success, and prompt for login on failure.

import { useCallback, useEffect } from 'react';
import { useAtom } from 'jotai';
import { initAuth, getAuthUser } from '../../collab/auth';
import { authReadyAtom, authUserAtom, showAuthDialogAtom } from '../../state/appAtoms';

export interface UseAuthArgs {
  collabEnabled: boolean;
  settingsReady: boolean;
  /**
   * Cloud-launch mode: the user is auto-logged-in from the injected identity
   * (handled by useCloudConfig). When true we mark auth ready and never show
   * the guest AuthDialog.
   */
  cloudMode?: boolean;
}

export interface UseAuthResult {
  authUser: ReturnType<typeof getAuthUser> | null;
  authReady: boolean;
  showAuthDialog: boolean;
  setShowAuthDialog: (open: boolean) => void;
  handleAuthLogin: (name: string) => void;
  handleAuthClose: () => void;
}

export function useAuth({ collabEnabled, settingsReady, cloudMode = false }: UseAuthArgs): UseAuthResult {
  const [authUser, setAuthUser] = useAtom(authUserAtom);
  const [authReady, setAuthReady] = useAtom(authReadyAtom);
  const [showAuthDialog, setShowAuthDialog] = useAtom(showAuthDialogAtom);

  useEffect(() => {
    let cancelled = false;
    // Cloud mode: identity is injected + set by useCloudConfig. Treat the user
    // as logged in and never prompt the guest dialog.
    if (cloudMode) {
      setAuthReady(true);
      setShowAuthDialog(false);
      return;
    }
    if (!collabEnabled || !settingsReady) {
      setAuthReady(true);
      setShowAuthDialog(false);
      return;
    }
    setAuthReady(false);
    initAuth().then(valid => {
      if (cancelled) return;
      if (valid) {
        setAuthUser(getAuthUser());
        setShowAuthDialog(false);
      } else {
        setAuthUser(null);
        setShowAuthDialog(true);
      }
    }).finally(() => {
      if (!cancelled) setAuthReady(true);
    });
    return () => { cancelled = true; };
  }, [cloudMode, collabEnabled, settingsReady, setAuthReady, setAuthUser, setShowAuthDialog]);

  const handleAuthLogin = useCallback((_name: string) => {
    setAuthUser(getAuthUser());
    setAuthReady(true);
    setShowAuthDialog(false);
  }, [setAuthReady, setAuthUser, setShowAuthDialog]);

  const handleAuthClose = useCallback(() => {
    // Closing without logging in keeps the app usable — collab just won't
    // connect. Auth dialog can be reopened from the top-bar avatar.
    setShowAuthDialog(false);
  }, [setShowAuthDialog]);

  return {
    authUser,
    authReady,
    showAuthDialog,
    setShowAuthDialog,
    handleAuthLogin,
    handleAuthClose,
  };
}
