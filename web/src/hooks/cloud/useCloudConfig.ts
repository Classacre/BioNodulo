// Fetches the backend `/api/config` once on boot and exposes the cloud-launch
// runtime config. When the app was launched by the cloud orchestrator
// (`cloudMode`), the injected user identity is treated as logged-in: the
// authUser atom is populated directly and the guest AuthDialog is skipped (see
// useAuth's `cloudMode` short-circuit).
//
// In local / self-host mode `/api/config` reports `cloudMode: false` with null
// identity, so this hook is a no-op beyond recording that config loaded.

import { useEffect } from 'react';
import { useAtom, useSetAtom } from 'jotai';
import { apiGet } from '../../api/client';
import { getUserColor } from '../../collab';
import { setAuthUser } from '../../collab/authStorage';
import { configureWebsiteApi } from '../../api/website';
import { authUserAtom, cloudConfigAtom, type CloudConfig } from '../../state/appAtoms';
import { logError } from '../../state/logging';

export interface UseCloudConfigResult {
  /** Fetched config, or null until the first /api/config response. */
  cloudConfig: CloudConfig | null;
  /** True once cloud mode is confirmed active with an injected identity. */
  cloudMode: boolean;
  /** True when served by the shared stateless editor backend (DB persistence). */
  editorMode: boolean;
}

export function useCloudConfig(): UseCloudConfigResult {
  const [cloudConfig, setCloudConfig] = useAtom(cloudConfigAtom);
  const setAuthUserAtom = useSetAtom(authUserAtom);

  useEffect(() => {
    let cancelled = false;
    apiGet<CloudConfig>('/api/config', { anonymous: true })
      .then(cfg => {
        if (cancelled || !cfg) return;
        setCloudConfig(cfg);
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
          };
          setAuthUser(user);
          setAuthUserAtom(user);
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
          });
        }
      });
    return () => { cancelled = true; };
    // Run once on mount.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return {
    cloudConfig,
    cloudMode: Boolean(cloudConfig?.cloudMode && cloudConfig.user?.id),
    editorMode: Boolean(cloudConfig?.editorMode),
  };
}
