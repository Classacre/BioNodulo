// Fetches the backend `/api/config` once on boot and exposes the cloud-launch
// runtime config. When the app was launched by the cloud orchestrator
// (`cloudMode`), the injected user identity is treated as logged-in: the
// authUser atom is populated directly and the guest AuthDialog is skipped (see
// useAuth's `cloudMode` short-circuit).
//
// In local / self-host mode `/api/config` reports `cloudMode: false` with null
// identity, so this hook is a no-op beyond recording that config loaded.

import { useCallback, useEffect, useRef } from 'react';
import { useAtom, useSetAtom } from 'jotai';
import { apiGet } from '../../api/client';
import { getUserColor } from '../../collab';
import { setAuthUser } from '../../collab/authStorage';
import { configureWebsiteApi, getCurrentUser } from '../../api/website';
import { authUserAtom, cloudConfigAtom, type CloudConfig } from '../../state/appAtoms';
import { setSettingsEditorMode } from '../settings/useSettings';
import { initDesktopOAuth } from './desktopOAuth';
import { logError } from '../../state/logging';
import type { ClerkIdentitySync } from './useClerkAuth';

export interface UseCloudConfigResult {
  /** Fetched config, or null until the first /api/config response. */
  cloudConfig: CloudConfig | null;
  /** True once cloud mode is confirmed active with an injected identity. */
  cloudMode: boolean;
  /** True when served by the shared stateless editor backend (DB persistence). */
  editorMode: boolean;
  syncClerkIdentity: (event: ClerkIdentitySync) => Promise<boolean>;
}

export function useCloudConfig(): UseCloudConfigResult {
  const [cloudConfig, setCloudConfig] = useAtom(cloudConfigAtom);
  const setAuthUserAtom = useSetAtom(authUserAtom);
  const configRef = useRef(cloudConfig);
  configRef.current = cloudConfig;
  const mounted = useRef(true);
  const identityOwner = useRef<object | null>(null);
  const identityRequest = useRef(0);
  const identityAbort = useRef<AbortController | null>(null);

  const readIdentity = useCallback(async (expected?: ClerkIdentitySync): Promise<boolean> => {
    const config = configRef.current;
    if (!mounted.current || !config || (!config.editorMode && !config.cloudMode)) return false;
    const epoch = ++identityRequest.current;
    identityAbort.current?.abort();
    const controller = new AbortController();
    identityAbort.current = controller;
    const current = () => mounted.current && identityRequest.current === epoch
      && (!expected || identityOwner.current === expected.owner)
      && configRef.current?.editorMode === config.editorMode
      && configRef.current?.cloudMode === config.cloudMode
      && configRef.current?.clerkPublishableKey === config.clerkPublishableKey
      && configRef.current?.accountUrl === config.accountUrl;
    try {
      const u = await getCurrentUser(controller.signal);
      if (!current() || !u?.id || !u.team?.id) return false;
      const clerkUserId = u.clerkUserId || u.id;
      if (expected && (clerkUserId !== expected.userId
        || (expected.orgId && u.team?.clerkOrgId !== expected.orgId))) return false;
      let applied = false;
      setCloudConfig(previous => {
        if (!current() || !previous || previous.editorMode !== config.editorMode
          || previous.cloudMode !== config.cloudMode || previous.clerkPublishableKey !== config.clerkPublishableKey
          || previous.accountUrl !== config.accountUrl) return previous;
        const next = { ...previous,
          user: { id: u.id, clerkUserId, name: u.name || u.email || u.id, email: u.email || '' },
          team: u.team };
        configRef.current = next;
        applied = true;
        return next;
      });
      if (!applied || !current()) return false;
      const user = { id: clerkUserId, name: u.name || u.email || u.id,
        color: getUserColor(clerkUserId), kind: 'account' as const };
      setAuthUser(user);
      setAuthUserAtom(previous => previous?.id === user.id && previous.name === user.name
        && previous.kind === user.kind ? previous : user);
      return true;
    } catch (err) {
      if (current()) logError('cloud.config.me', err);
      return false;
    } finally {
      if (current()) identityAbort.current = null;
    }
  }, [setCloudConfig, setAuthUserAtom]);

  const syncClerkIdentity = useCallback(async (event: ClerkIdentitySync): Promise<boolean> => {
    const cfg = configRef.current;
    if (!mounted.current || !cfg?.editorMode || cfg.cloudMode) return false;
    if (identityOwner.current !== event.owner) {
      identityOwner.current = event.owner;
      identityRequest.current += 1;
      identityAbort.current?.abort();
      identityAbort.current = null;
      // Even org→null can select a different server fallback team. Private
      // state stays blocked until that owner has a new authoritative /me.
      setCloudConfig(previous => {
        if (!previous) return previous;
        const next = { ...previous, user: null, team: null };
        configRef.current = next;
        return next;
      });
      setAuthUserAtom(null);
    }
    if (!event.ready || !event.userId) return false;
    return readIdentity(event);
  }, [readIdentity, setCloudConfig, setAuthUserAtom]);

  useEffect(() => {
    mounted.current = true;
    let cancelled = false;
    apiGet<CloudConfig>('/api/config', { anonymous: true })
      .then(cfg => {
        if (cancelled || !cfg) return;
        configRef.current = cfg;
        setCloudConfig(cfg);
        // Desktop OAuth: if we hold a stored refresh token, restore the session
        // (and keep the access token fresh) without re-opening the browser.
        if (cfg.oauth?.clientId) void initDesktopOAuth(cfg.oauth);
        // Confirm settings persistence mode now that runtime config is known.
        setSettingsEditorMode(Boolean(cfg.editorMode));
        // Local/self-host app talking to the cloud account: point website API
        // calls (credits, invites) at the absolute cloud API base + bearer auth.
        // The cloud editor itself is same-origin (editorMode) → keep '/api'.
        if (!cfg.editorMode && cfg.accountUrl) {
          configureWebsiteApi(`${cfg.accountUrl.replace(/\/+$/, '')}/api`);
        }
        // Auto-login: adopt the injected identity as the current user.
        if (cfg.cloudMode && cfg.user?.id) {
          const user = {
            id: cfg.user.id,
            name: cfg.user.name || cfg.user.email || cfg.user.id,
            color: getUserColor(cfg.user.id),
            kind: 'account' as const,
          };
          setAuthUser(user);
          setAuthUserAtom(user);
        } else if (cfg.editorMode || cfg.cloudMode) {
          // The stateless editor backend's /api/config carries no user identity,
          // so fetch the signed-in user from the website (cookie/bearer) to seed
          // the collaboration identity. Without this, collab can't start.
          void readIdentity();
        }
      })
      .catch(err => {
        // /api/config is optional in older backends — degrade to local mode.
        logError('cloud.config.fetch', err);
        if (!cancelled) {
          setCloudConfig({
            cloudMode: false,
            editorMode: false,
            user: null,
            team: null,
            plan: null,
            credits: null,
            accountUrl: null,
            clerkPublishableKey: null,
            oauth: null,
          });
        }
      });
    return () => {
      cancelled = true;
      mounted.current = false;
      identityRequest.current += 1;
      identityAbort.current?.abort();
    };
    // Run once on mount.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return {
    cloudConfig,
    cloudMode: Boolean(cloudConfig?.cloudMode && cloudConfig.user?.id),
    editorMode: Boolean(cloudConfig?.editorMode),
    syncClerkIdentity,
  };
}
