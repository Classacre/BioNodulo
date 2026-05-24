import { useEffect, useMemo, useRef, useState, useCallback } from 'react';
import * as Y from 'yjs';
import * as decoding from 'lib0/decoding';
import * as encoding from 'lib0/encoding';
import { Awareness, encodeAwarenessUpdate, applyAwarenessUpdate } from 'y-protocols/awareness';
import * as syncProtocol from 'y-protocols/sync';
import { createWorkflowDoc, workflowToDoc, docToWorkflow } from './yjsDoc';
import { useAwareness } from './useAwareness';
import { getToken } from './auth';
import type { CollabUser, AwarenessState } from './types';

const RECONNECT_BASE_DELAY = 1000;
const MAX_RECONNECT_DELAY = 30000;
const MAX_RECONNECT_ATTEMPTS = 10;
const UPDATE_RATE_LIMIT = 30;

// y-websocket protocol constants (matching pycrdt-websocket)
const MSG_SYNC = 0;
const MSG_AWARENESS = 1;

interface RoomPresenceUser {
  session_id: string;
  user_id: string;
  name: string;
  color: string;
  role?: AwarenessState['user']['role'];
  workflow_id?: string;
}

interface RoomPresenceMessage {
  type: 'room.presence';
  workflow_id: string;
  users: RoomPresenceUser[];
}

interface UseCollabReturn {
  doc: Y.Doc | null;
  localSessionId: string;
  connected: boolean;
  connecting: boolean;
  offline: boolean; // true when browser is offline
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

export function useCollab(workflowId: string | null, currentUser: CollabUser): UseCollabReturn {
  const [doc, setDoc] = useState<Y.Doc | null>(null);
  const [connected, setConnected] = useState(false);
  const [connecting, setConnecting] = useState(false);
  const [offline, setOffline] = useState(false);
  const [isShared, setIsShared] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [reconnectAttempt, setReconnectAttempt] = useState(0);
  const [roomUsers, setRoomUsers] = useState<AwarenessState[]>([]);
  const localSessionIdRef = useRef<string>(
    typeof crypto !== 'undefined' && crypto.randomUUID
      ? crypto.randomUUID()
      : `session-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`,
  );

  const wsRef = useRef<WebSocket | null>(null);
  const docRef = useRef<Y.Doc | null>(null);
  const reconnectAttemptRef = useRef(0);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const shouldReconnectRef = useRef(true);
  const [awareness, setAwareness] = useState<Awareness | null>(null);
  const awarenessRef = useRef<Awareness | null>(null);

  useEffect(() => {
    awarenessRef.current = awareness;
  }, [awareness]);

  const updateCountRef = useRef(0);
  const updateWindowStartRef = useRef(Date.now());
  const skippedUpdateRef = useRef(false);

  const awarenessUser = useMemo(() => ({
    ...currentUser,
    sessionId: localSessionIdRef.current,
    workflowId: workflowId || undefined,
  }), [currentUser.id, currentUser.name, currentUser.color, workflowId]);
  const awarenessResult = useAwareness(doc, awarenessUser, awareness, connected);
  const activeUsers = useMemo(() => {
    const awarenessByUserId = new Map(
      awarenessResult.others.map(state => [state.user.sessionId || state.user.id, state]),
    );
    for (const roomUser of roomUsers) {
      const key = roomUser.user.sessionId || roomUser.user.id;
      if (!awarenessByUserId.has(key)) {
        awarenessByUserId.set(key, roomUser);
      }
    }
    return Array.from(awarenessByUserId.values());
  }, [awarenessResult.others, roomUsers]);

  const buildWsUrl = useCallback((wfId: string) => {
    const proto = window.location.protocol === 'https:' ? 'wss' : 'ws';
    const token = getToken();
    const tokenParam = token ? `&token=${encodeURIComponent(token)}` : '';
    const sessionParam = `&session_id=${encodeURIComponent(localSessionIdRef.current)}`;
    return `${proto}://${window.location.host}/ws/collab/${wfId}?client=web${tokenParam}${sessionParam}`;
  }, []);

  const applyBinaryAwareness = useCallback((awarenessBytes: Uint8Array) => {
    const aw = awarenessRef.current;
    if (!aw) return;
    try {
      applyAwarenessUpdate(aw, new Uint8Array(awarenessBytes), 'remote');
    } catch (err) {
      console.warn('[collab] Failed to apply awareness update:', err);
    }
  }, []);

  const handleMessage = useCallback((ev: MessageEvent) => {
    if (!(ev.data instanceof ArrayBuffer)) {
      if (typeof ev.data === 'string') {
        try {
          const message = JSON.parse(ev.data) as RoomPresenceMessage;
          if (message.type === 'room.presence' && Array.isArray(message.users)) {
            const users = message.users
              .filter(user => user.user_id && user.session_id !== localSessionIdRef.current)
              .map(user => ({
                user: {
                  id: user.user_id,
                  name: user.name || user.user_id,
                  color: user.color || '#3b82f6',
                  role: user.role,
                  workflowId: user.workflow_id || message.workflow_id,
                  sessionId: user.session_id,
                },
                cursor: null,
                selection: { nodeIds: [] },
                activity: 'active' as const,
                timestamp: Date.now(),
              }));
            setRoomUsers(users);
            return;
          }
        } catch {
          // Non-JSON text does not belong to the native collab protocol.
        }
      }
      console.warn('[collab] Received unsupported message, ignoring');
      return;
    }
    const data = new Uint8Array(ev.data);
    if (data.length < 1) return;

    const decoder = decoding.createDecoder(data);
    const msgType = decoding.readVarUint(decoder);

    // Sync message: [0] [sync_type] [varUint8Array(payload)]
    if (msgType === MSG_SYNC) {
      const currentDoc = docRef.current;
      if (!currentDoc) return;
      try {
        const encoder = encoding.createEncoder();
        encoding.writeVarUint(encoder, MSG_SYNC);
        const syncType = syncProtocol.readSyncMessage(decoder, encoder, currentDoc, 'remote', err => {
          console.warn('[collab] Failed to apply sync message:', err);
        });
        if (syncType === syncProtocol.messageYjsSyncStep2) {
          setConnecting(false);
        }
        const ws = wsRef.current;
        if (encoding.length(encoder) > 1 && ws?.readyState === WebSocket.OPEN) {
          ws.send(encoding.toUint8Array(encoder));
        }
      } catch (err) {
        console.warn('[collab] Failed to read sync message:', err);
      }
    }
    // Awareness message: [1] [varUint8Array(awareness_bytes)]
    else if (msgType === MSG_AWARENESS) {
      try {
        applyBinaryAwareness(decoding.readVarUint8Array(decoder));
      } catch (err) {
        console.warn('[collab] Failed to read awareness message:', err);
      }
    }
    else {
      console.warn('[collab] Unknown message type:', msgType);
    }
  }, [applyBinaryAwareness]);

  // Listen for local Yjs changes and send as native Yjs updates
  useEffect(() => {
    if (!doc) return;

    const handler = (update: Uint8Array, origin: unknown) => {
      if (origin === 'remote') return;

      // Rate limiting
      const now = Date.now();
      if (now - updateWindowStartRef.current >= 1000) {
        updateCountRef.current = 0;
        updateWindowStartRef.current = now;
        skippedUpdateRef.current = false;
      }
      updateCountRef.current++;
      if (updateCountRef.current > UPDATE_RATE_LIMIT) {
        if (!skippedUpdateRef.current) {
          skippedUpdateRef.current = true;
          console.warn('[collab] Update rate limit exceeded');
        }
        return;
      }

      const ws = wsRef.current;
      if (!ws || ws.readyState !== WebSocket.OPEN) return;

      try {
        const encoder = encoding.createEncoder();
        encoding.writeVarUint(encoder, MSG_SYNC);
        syncProtocol.writeUpdate(encoder, update);
        ws.send(encoding.toUint8Array(encoder));
      } catch (err) {
        console.warn('[collab] Failed to send update:', err);
      }
    };

    doc.on('update', handler);
    return () => {
      doc.off('update', handler);
    };
  }, [doc]);

  // Broadcast awareness changes
  useEffect(() => {
    if (!awareness || !connected) return;

    const sendAwareness = (changedClients: number[]) => {
      const ws = wsRef.current;
      if (!ws || ws.readyState !== WebSocket.OPEN) return;

      if (changedClients.length === 0) return;

      try {
        const update = encodeAwarenessUpdate(awareness, changedClients);
        const encoder = encoding.createEncoder();
        encoding.writeVarUint(encoder, MSG_AWARENESS);
        encoding.writeVarUint8Array(encoder, update);
        ws.send(encoding.toUint8Array(encoder));
      } catch (err) {
        console.warn('[collab] Failed to send awareness:', err);
      }
    };

    const handler = ({ added, updated, removed }: {
      added: number[]; updated: number[]; removed: number[];
    }, origin: unknown) => {
      if (origin === 'remote' && added.length > 0) {
        // A newcomer advertises itself before the relay has any awareness
        // snapshot for the room. Answer immediately with our own state.
        sendAwareness([awareness.doc.clientID]);
        return;
      }
      if (origin === 'remote') return;
      sendAwareness([...added, ...updated, ...removed]);
    };

    awareness.on('change', handler);
    // The local awareness state can be prepared before the socket connects.
    // Announce it again after the sender is attached so new tabs appear in
    // the collaborator list without waiting for cursor movement.
    sendAwareness([awareness.doc.clientID]);
    // The native relay does not replay awareness already sent before a later
    // collaborator joins. Refresh the local announcement periodically so a
    // new browser sees existing users even while everyone is idle.
    const heartbeat = setInterval(() => sendAwareness([awareness.doc.clientID]), 3000);
    return () => {
      clearInterval(heartbeat);
      awareness.off('change', handler);
    };
  }, [awareness, connected]);

  // Main connection manager
  useEffect(() => {
    if (!workflowId) {
      docRef.current = null;
      setDoc(null);
      setConnected(false);
      setConnecting(false);
      setError(null);
      setRoomUsers([]);
      setReconnectAttempt(0);
      reconnectAttemptRef.current = 0;
      if (awareness) {
        awareness.destroy();
        setAwareness(null);
      }
      return;
    }

    const ydoc = createWorkflowDoc(workflowId);
    docRef.current = ydoc;
    setDoc(ydoc);
    setError(null);
    setRoomUsers([]);
    reconnectAttemptRef.current = 0;
    setReconnectAttempt(0);
    shouldReconnectRef.current = true;

    // Track browser online/offline state
    const handleOnline = () => setOffline(false);
    const handleOffline = () => setOffline(true);
    setOffline(!navigator.onLine);
    window.addEventListener('online', handleOnline);
    window.addEventListener('offline', handleOffline);

    const aw = new Awareness(ydoc);
    setAwareness(aw);
    const token = getToken();

    const connect = () => {
      if (wsRef.current?.readyState === WebSocket.OPEN) return;

      try {
        const url = buildWsUrl(workflowId);
        const ws = new WebSocket(url);
        ws.binaryType = 'arraybuffer';
        wsRef.current = ws;
        setConnecting(true);

        ws.onopen = () => {
          setConnected(true);
          setError(null);
          reconnectAttemptRef.current = 0;
          setReconnectAttempt(0);

          // Send SyncStep1: our state vector
          try {
            const encoder = encoding.createEncoder();
            encoding.writeVarUint(encoder, MSG_SYNC);
            syncProtocol.writeSyncStep1(encoder, ydoc);
            ws.send(encoding.toUint8Array(encoder));
          } catch (err) {
            console.warn('[collab] Failed to send SyncStep1:', err);
          }

          // Send initial awareness
          try {
            const awUpdate = encodeAwarenessUpdate(aw, [ydoc.clientID]);
            const encoder = encoding.createEncoder();
            encoding.writeVarUint(encoder, MSG_AWARENESS);
            encoding.writeVarUint8Array(encoder, awUpdate);
            ws.send(encoding.toUint8Array(encoder));
          } catch (err) {
            console.warn('[collab] Failed to send initial awareness:', err);
          }
        };

        ws.onmessage = handleMessage;

        ws.onclose = () => {
          setConnected(false);
          setConnecting(false);
          setRoomUsers([]);
          if (shouldReconnectRef.current) {
            const attempt = reconnectAttemptRef.current;
            if (attempt >= MAX_RECONNECT_ATTEMPTS) {
              setError('Disconnected: max reconnection attempts reached');
              return;
            }
            const delay = Math.min(RECONNECT_BASE_DELAY * Math.pow(2, attempt), MAX_RECONNECT_DELAY);
            reconnectAttemptRef.current = attempt + 1;
            setReconnectAttempt(attempt + 1);
            reconnectTimerRef.current = setTimeout(connect, delay);
          }
        };

        ws.onerror = () => {
          setError('WebSocket connection error');
          ws.close();
        };
      } catch (err) {
        setConnecting(false);
        setError(err instanceof Error ? err.message : 'Failed to connect');
      }
    };

    if (token) {
      connect();
    } else {
      setConnected(false);
      setConnecting(false);
      setError(null);
    }

    return () => {
      shouldReconnectRef.current = false;
      if (reconnectTimerRef.current) clearTimeout(reconnectTimerRef.current);
      wsRef.current?.close();
      wsRef.current = null;
      if (docRef.current === ydoc) {
        docRef.current = null;
      }
      aw.destroy();
      setAwareness(null);
      window.removeEventListener('online', handleOnline);
      window.removeEventListener('offline', handleOffline);
    };
  }, [workflowId, currentUser.id, buildWsUrl, handleMessage]);

  // Check if workflow is shared
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
    fetch(`/api/collab/shares/${workflowId}`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then(r => (r.ok ? r.json() : null))
      .then(data => {
        setIsShared(data?.shares?.length > 0);
      })
      .catch(() => setIsShared(false));
  }, [workflowId]);

  const shareWorkflow = useCallback(async (userId: string, role: string) => {
    if (!workflowId) return;
    const token = getToken();
    if (!token) throw new Error('Sign in before sharing workflows');
    const r = await fetch('/api/collab/share', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({ workflow_id: workflowId, user_id: userId, role }),
    });
    if (!r.ok) throw new Error('Failed to share workflow');
    setIsShared(true);
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
