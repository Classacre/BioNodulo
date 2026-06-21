import { useEffect, useMemo, useRef, useState, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import * as Y from 'yjs';
import { WebsocketProvider } from 'y-websocket';
import { Awareness } from 'y-protocols/awareness';
import { createWorkflowDoc, workflowToDoc, docToWorkflow } from './yjsDoc';
import { useAwareness } from './useAwareness';
import { getToken } from './auth';
import { apiGet, apiPost } from '../api/client';
import { getCollabClientToken } from '../api/website';
import { logError } from '../state/logging';
import { appWebSocketUrl } from '../utils/appBase';
import type { CollabUser, AwarenessState } from './types';

const AUTH_CLOSE_CODES = new Set([4401, 4403]);

// Cloud editor collaboration: a Yjs WebSocket served by the Cloudflare
// Durable-Objects Worker (y-websocket protocol). Enabled at build time via
// VITE_COLLAB_PROVIDER=durable-objects; unset → local /ws/collab unchanged.
const CLOUD_COLLAB = (import.meta.env.VITE_COLLAB_PROVIDER || '').trim() === 'durable-objects';
const CLOUD_COLLAB_HOST = (import.meta.env.VITE_COLLAB_HOST || '').trim();

interface UseCollabReturn {
  doc: Y.Doc | null;
  localSessionId: string;
  connected: boolean;
  connecting: boolean;
  offline: boolean;
  activeUsers: AwarenessState[];
  localAwareness: AwarenessState;
  setCursor: (cursor: AwarenessState['cursor']) => void;
  setSelection: (selection: AwarenessState['selection']) => void;
  setViewport: (viewport: AwarenessState['viewport']) => void;
  setActivity: (activity: AwarenessState['activity']) => void;
  claimDrag: (nodeId: string) => void;
  releaseDrag: () => void;
  shareWorkflow: (userId: string, role: string) => Promise<void>;
  isShared: boolean;
  error: string | null;
  reconnectAttempt: number;
}

function wsServerUrl(): string {
  return appWebSocketUrl('/ws/collab');
}

function newSessionId(): string {
  if (typeof crypto !== 'undefined' && crypto.randomUUID) {
    return crypto.randomUUID();
  }
  return `session-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
}

export function useCollab(workflowId: string | null, currentUser: CollabUser): UseCollabReturn {
  const { t } = useTranslation();
  const tRef = useRef(t);
  const [doc, setDoc] = useState<Y.Doc | null>(null);
  const [awareness, setAwareness] = useState<Awareness | null>(null);
  const [connected, setConnected] = useState(false);
  const [connecting, setConnecting] = useState(false);
  const [offline, setOffline] = useState(() => !navigator.onLine);
  const [isShared, setIsShared] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [reconnectAttempt, setReconnectAttempt] = useState(0);
  const localSessionIdRef = useRef<string>(newSessionId());
  const providerRef = useRef<WebsocketProvider | null>(null);

  const awarenessUser = useMemo(() => ({
    ...currentUser,
    sessionId: localSessionIdRef.current,
    workflowId: workflowId || undefined,
  }), [currentUser.id, currentUser.name, currentUser.color, currentUser.role, workflowId]);

  const awarenessResult = useAwareness(doc, awarenessUser, awareness, connected);
  const activeUsers = useMemo(() => awarenessResult.others, [awarenessResult.others]);

  useEffect(() => {
    tRef.current = t;
  }, [t]);

  useEffect(() => {
    const handleOnline = () => setOffline(false);
    const handleOffline = () => setOffline(true);
    setOffline(!navigator.onLine);
    window.addEventListener('online', handleOnline);
    window.addEventListener('offline', handleOffline);
    return () => {
      window.removeEventListener('online', handleOnline);
      window.removeEventListener('offline', handleOffline);
    };
  }, []);

  useEffect(() => {
    if (!workflowId) {
      providerRef.current?.disconnect();
      (providerRef.current as (WebsocketProvider & { destroy?: () => void }) | null)?.destroy?.();
      providerRef.current = null;
      setDoc(null);
      setAwareness(null);
      setConnected(false);
      setConnecting(false);
      setError(null);
      setReconnectAttempt(0);
      return;
    }

    // In the cloud editor the WS auth is a per-room token fetched from the
    // website; locally it's the stored auth token. Bail early only in local mode
    // (cloud fetches its token below).
    if (!CLOUD_COLLAB && !getToken()) {
      setDoc(null);
      setAwareness(null);
      setConnected(false);
      setConnecting(false);
      setError(null);
      setReconnectAttempt(0);
      return;
    }

    const ydoc = createWorkflowDoc(workflowId);
    const aw = new Awareness(ydoc);
    setDoc(ydoc);
    setAwareness(aw);
    setConnected(false);
    setConnecting(true);
    setError(null);
    setReconnectAttempt(0);

    let cancelled = false;
    let myProvider: WebsocketProvider | null = null;
    let heartbeat: number | undefined;

    const buildProvider = (wsUrl: string, room: string, params: Record<string, string>) => {
      const provider = new WebsocketProvider(wsUrl, room, ydoc, {
        awareness: aw,
        disableBc: true,
        maxBackoffTime: 30000,
        resyncInterval: 10000,
        params,
      });
      myProvider = provider;
      providerRef.current = provider;

      const handleStatus = ({ status }: { status: 'connected' | 'disconnected' | 'connecting' }) => {
        if (providerRef.current !== provider) return;
        setConnected(status === 'connected');
        setConnecting(status === 'connecting');
        setReconnectAttempt(provider.wsUnsuccessfulReconnects);
        if (status === 'connected') {
          setError(null);
          setReconnectAttempt(0);
        }
      };

      const handleClose = (event: CloseEvent | null) => {
        if (providerRef.current !== provider) return;
        setConnected(false);
        setConnecting(provider.shouldConnect);
        setReconnectAttempt(provider.wsUnsuccessfulReconnects);
        if (event && AUTH_CLOSE_CODES.has(event.code)) {
          provider.shouldConnect = false;
          provider.disconnect();
          setConnecting(false);
          setError(event.reason || (event.code === 4403 ? tRef.current('collab.connectionForbidden') : tRef.current('collab.connectionUnauthorized')));
        }
      };

      const handleError = () => {
        if (providerRef.current !== provider) return;
        setError(tRef.current('collab.connectionError'));
        setReconnectAttempt(provider.wsUnsuccessfulReconnects);
      };

      provider.on('status', handleStatus);
      provider.on('connection-close', handleClose);
      provider.on('connection-error', handleError);

      heartbeat = window.setInterval(() => {
        if (providerRef.current !== provider) return;
        const state = aw.getLocalState() as AwarenessState | null;
        if (state) {
          aw.setLocalState({ ...state, timestamp: Date.now() });
        }
      }, 15000);
    };

    void (async () => {
      if (CLOUD_COLLAB) {
        // Fetch a room-scoped token (verifies team ownership of the workflow).
        const ct = await getCollabClientToken(workflowId).catch(err => {
          logError('collab.token', err);
          return null;
        });
        if (cancelled) return;
        if (!ct) {
          setConnecting(false);
          setError(tRef.current('collab.connectionUnauthorized'));
          return;
        }
        buildProvider(`wss://${ct.host || CLOUD_COLLAB_HOST}/editor`, ct.room, {
          token: ct.token,
          session_id: localSessionIdRef.current,
        });
      } else {
        const token = getToken();
        if (cancelled || !token) {
          setConnecting(false);
          return;
        }
        buildProvider(wsServerUrl(), workflowId, {
          client: 'y-websocket',
          token,
          session_id: localSessionIdRef.current,
        });
      }
    })();

    return () => {
      cancelled = true;
      if (heartbeat !== undefined) window.clearInterval(heartbeat);
      if (myProvider) {
        myProvider.shouldConnect = false;
        myProvider.disconnect();
        (myProvider as WebsocketProvider & { destroy?: () => void }).destroy?.();
        if (providerRef.current === myProvider) providerRef.current = null;
      }
      aw.destroy();
      setDoc(current => (current === ydoc ? null : current));
      setAwareness(current => (current === aw ? null : current));
      setConnected(false);
      setConnecting(false);
    };
  }, [workflowId, currentUser.id]);

  useEffect(() => {
    // Cloud collab shares == team membership (no per-workflow share list); the
    // /api/collab/shares endpoint only exists on the local FastAPI backend.
    if (CLOUD_COLLAB) {
      setIsShared(false);
      return;
    }
    if (!workflowId) {
      setIsShared(false);
      return;
    }
    const token = getToken();
    if (!token) {
      setIsShared(false);
      return;
    }
    apiGet<{ shares?: unknown[] }>(`/api/collab/shares/${workflowId}`)
      .then(data => {
        setIsShared(Array.isArray(data?.shares) && data.shares.length > 0);
      })
      .catch(err => {
        logError('collab.useCollab.shares', err);
        setIsShared(false);
      });
  }, [workflowId]);

  const shareWorkflow = useCallback(async (userId: string, role: string) => {
    if (!workflowId) return;
    const token = getToken();
    if (!token) throw new Error(tRef.current('collab.shareSignInRequired'));
    try {
      await apiPost('/api/collab/share', { workflow_id: workflowId, user_id: userId, role });
      setIsShared(true);
    } catch (err) {
      logError('collab.useCollab.share', err);
      throw new Error(tRef.current('collab.shareWorkflowError'));
    }
  }, [workflowId]);

  return {
    doc,
    localSessionId: localSessionIdRef.current,
    connected,
    connecting,
    offline,
    activeUsers,
    localAwareness: awarenessResult.localState,
    setCursor: awarenessResult.setCursor,
    setSelection: awarenessResult.setSelection,
    setViewport: awarenessResult.setViewport,
    setActivity: awarenessResult.setActivity,
    claimDrag: awarenessResult.claimDrag,
    releaseDrag: awarenessResult.releaseDrag,
    shareWorkflow,
    isShared,
    error,
    reconnectAttempt,
  };
}

export { useAwareness, docToWorkflow, workflowToDoc };
