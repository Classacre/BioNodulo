import { useEffect } from 'react';
import { setCollabRemoteBase } from '../../collab/remoteBase';
import type { CollabLinkTarget } from '../../collab/shareLinks';

interface DeepLinkPayload {
  host: string;
  path: string;
  params: Record<string, string>;
}

export function deepLinkToJoin(payload: DeepLinkPayload): { remoteBase: string; target: CollabLinkTarget } | null {
  if (payload.host !== 'open') return null;
  const { h, w, i } = payload.params;
  if (!w) return null;
  return {
    remoteBase: h,
    target: { workflowId: w, inviteToken: i ?? null },
  };
}

export function isValidRemoteBase(base: string | null): boolean {
  if (!base) return false;
  try {
    const url = new URL(base);
    return url.protocol === 'https:' && url.hostname.endsWith('.trycloudflare.com');
  } catch {
    return false;
  }
}

export function useDeepLinkJoin(opts: { onJoin: (target: CollabLinkTarget) => void }): void {
  const { onJoin } = opts;
  useEffect(() => {
    const tauri = (window as unknown as {
      __TAURI__?: {
        event?: {
          listen?: (
            e: string,
            cb: (ev: { payload: DeepLinkPayload }) => void
          ) => Promise<() => void>;
        };
      };
    }).__TAURI__;
    const listenFn = tauri?.event?.listen;
    if (!listenFn) return;

    let cancelled = false;
    let unlisten: (() => void) | null = null;

    void listenFn('app:deep-link', (ev) => {
      const result = deepLinkToJoin(ev.payload);
      if (!result) return;
      const { remoteBase, target } = result;
      // Only adopt the tunnel host as the collab transport when it passes the
      // https + *.trycloudflare.com allowlist; a link with any other base joins
      // same-origin instead. Note this proves the base IS a trycloudflare quick
      // tunnel, not that it's the *legitimate* host — trycloudflare tunnels are
      // open to anyone, so opening an untrusted bionodulo://open link is a trust
      // decision (matching trycloudflare's ephemeral-tunnel model). onJoin fires
      // regardless; the workflow id is re-validated server-side against the invite.
      if (isValidRemoteBase(remoteBase)) {
        setCollabRemoteBase(remoteBase);
      }
      onJoin(target);
    }).then((fn) => {
      if (cancelled) {
        fn();
      } else {
        unlisten = fn;
      }
    });

    return () => {
      cancelled = true;
      unlisten?.();
    };
  }, [onJoin]);
}
