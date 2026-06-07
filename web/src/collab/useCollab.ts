import { useEffect, useMemo, useRef, useState, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import * as Y from 'yjs';
import { WebsocketProvider } from 'y-websocket';
import { Awareness } from 'y-protocols/awareness';
import { createWorkflowDoc, workflowToDoc, docToWorkflow } from './yjsDoc';
import { useAwareness } from './useAwareness';
import { getToken } from './auth';
import { apiGet, apiPost } from '../api/client';
import { logError } from '../state/logging';
import { appWebSocketUrl } from '../utils/appBase';
import type { CollabUser, AwarenessState } from './types';

const AUTH_CLOSE_CODES = new Set([4401, 4403]);

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

    const token = getToken();
    if (!token) {
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

    const provider = new WebsocketProvider(wsServerUrl(), workflowId, ydoc, {
      awareness: aw,
      disableBc: true,
      maxBackoffTime: 30000,
      resyncInterval: 10000,
      params: {
        client: 'y-websocket',
        token,
        session_id: localSessionIdRef.current,
      },
    });
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

    const heartbeat = window.setInterval(() => {
      if (providerRef.current !== provider) return;
      const state = aw.getLocalState() as AwarenessState | null;
      if (state) {
        aw.setLocalState({ ...state, timestamp: Date.now() });
      }
    }, 15000);

    return () => {
      window.clearInterval(heartbeat);
      provider.off('status', handleStatus);
      provider.off('connection-close', handleClose);
      provider.off('connection-error', handleError);
      provider.shouldConnect = false;
      provider.disconnect();
      (provider as WebsocketProvider & { destroy?: () => void }).destroy?.();
      if (providerRef.current === provider) {
        providerRef.current = null;
      }
      aw.destroy();
      setDoc(current => (current === ydoc ? null : current));
      setAwareness(current => (current === aw ? null : current));
      setConnected(false);
      setConnecting(false);
    };
  }, [workflowId, currentUser.id]);

  useEffect(() => {
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
    if (!token) throw new Error('Sign in before sharing workflows');
    try {
      await apiPost('/api/collab/share', { workflow_id: workflowId, user_id: userId, role });
      setIsShared(true);
    } catch (err) {
      logError('collab.useCollab.share', err);
      throw new Error('Failed to share workflow');
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
