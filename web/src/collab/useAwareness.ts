import { useCallback, useEffect, useRef, useState } from 'react';
import * as Y from 'yjs';
import {
  Awareness,
  encodeAwarenessUpdate,
  applyAwarenessUpdate,
  removeAwarenessStates,
} from 'y-protocols/awareness';
import type { CollabUser, AwarenessState } from './types';

const AWARENESS_TIMEOUT = 30000; // 30s before considering a user offline

interface UseAwarenessReturn {
  localState: AwarenessState;
  others: AwarenessState[];
  setCursor: (cursor: AwarenessState['cursor']) => void;
  setSelection: (selection: AwarenessState['selection']) => void;
  setViewport: (viewport: AwarenessState['viewport']) => void;
  setActivity: (activity: AwarenessState['activity']) => void;
  claimDrag: (nodeId: string) => void;
  releaseDrag: () => void;
}

/** Build the local awareness state object from user + overrides */
function buildLocalState(
  user: CollabUser,
  cursor: AwarenessState['cursor'],
  selection: AwarenessState['selection'],
  viewport: AwarenessState['viewport'],
  activity: AwarenessState['activity'],
  dragOwnership: AwarenessState['dragOwnership'],
): AwarenessState {
  return {
    user,
    cursor,
    selection,
    viewport,
    activity,
    dragOwnership,
    timestamp: Date.now(),
  };
}

/**
 * Hook that manages y-protocols Awareness state for a Yjs document.
 *
 * @param doc        - The Yjs document (null when not connected)
 * @param user       - The current user's identity
 * @param awareness  - Awareness instance managed by useCollab (shared WebSocket)
 * @param connected  - Whether the WebSocket is connected
 */
export function useAwareness(
  doc: Y.Doc | null,
  user: CollabUser,
  awareness: Awareness | null,
  connected: boolean,
): UseAwarenessReturn {
  const [others, setOthers] = useState<AwarenessState[]>([]);
  const [localState, setLocalState] = useState<AwarenessState>({
    user,
    cursor: null,
    selection: { nodeIds: [] },
    viewport: undefined,
    activity: 'active',
    dragOwnership: null,
    timestamp: Date.now(),
  });

  const localStateRef = useRef(localState);
  localStateRef.current = localState;

  const userRef = useRef(user);
  userRef.current = user;

  const othersRef = useRef<Map<number, AwarenessState & { _receivedAt: number }>>(new Map());
  const cleanupTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Update local awareness state in the y-protocols Awareness instance
  useEffect(() => {
    if (!awareness) return;

    const state = buildLocalState(
      userRef.current,
      localStateRef.current.cursor,
      localStateRef.current.selection,
      localStateRef.current.viewport,
      localStateRef.current.activity,
      localStateRef.current.dragOwnership,
    );
    awareness.setLocalState(state);
  }, [awareness, localState.cursor, localState.selection, localState.viewport, localState.activity, localState.dragOwnership, localState.user]);

  // Listen for remote awareness changes
  useEffect(() => {
    if (!awareness) return;

    const handler = ({
      added,
      updated,
      removed,
    }: {
      added: number[];
      updated: number[];
      removed: number[];
    }) => {
      const now = Date.now();
      const localClientId = awareness.doc.clientID;

      // Process removed clients
      for (const clientId of removed) {
        othersRef.current.delete(clientId);
      }

      // Process added/updated clients
      const changed = [...added, ...updated];
      for (const clientId of changed) {
        if (clientId === localClientId) continue; // skip self
        const state = awareness.getStates().get(clientId);
        if (!state) {
          othersRef.current.delete(clientId);
          continue;
        }
        try {
          const awarenessState = state as unknown as AwarenessState;
          othersRef.current.set(clientId, {
            ...awarenessState,
            _receivedAt: now,
          });
        } catch {
          // ignore malformed state
        }
      }

      // Update React state from the ref map (filter stale entries)
      const list = Array.from(othersRef.current.values())
        .filter(o => now - (o as AwarenessState & { _receivedAt: number })._receivedAt < AWARENESS_TIMEOUT)
        .map(({ _receivedAt, ...rest }) => rest as AwarenessState);
      setOthers(list);
    };

    awareness.on('change', handler);
    return () => {
      awareness.off('change', handler);
    };
  }, [awareness]);

  // Periodically clean up stale awareness entries
  useEffect(() => {
    cleanupTimerRef.current = setInterval(() => {
      const now = Date.now();
      let changed = false;
      othersRef.current.forEach((state, key) => {
        if (now - state._receivedAt > AWARENESS_TIMEOUT) {
          othersRef.current.delete(key);
          changed = true;
        }
      });
      if (changed) {
        const list = Array.from(othersRef.current.values()).map(
          ({ _receivedAt, ...rest }) => rest as AwarenessState,
        );
        setOthers(list);
      }
    }, 5000);
    return () => {
      if (cleanupTimerRef.current) clearInterval(cleanupTimerRef.current);
    };
  }, []);

  // Reset local state when user changes
  useEffect(() => {
    setLocalState(prev => ({
      ...prev,
      user,
      timestamp: Date.now(),
    }));
  }, [user.id, user.name, user.color]);

  const setCursor = useCallback((cursor: AwarenessState['cursor']) => {
    setLocalState(prev => ({ ...prev, cursor, timestamp: Date.now() }));
  }, []);

  const setSelection = useCallback((selection: AwarenessState['selection']) => {
    setLocalState(prev => ({ ...prev, selection, timestamp: Date.now() }));
  }, []);

  const setViewport = useCallback((viewport: AwarenessState['viewport']) => {
    setLocalState(prev => ({ ...prev, viewport, timestamp: Date.now() }));
  }, []);

  const setActivity = useCallback((activity: AwarenessState['activity']) => {
    setLocalState(prev => ({ ...prev, activity, timestamp: Date.now() }));
  }, []);

  const claimDrag = useCallback((nodeId: string) => {
    setLocalState(prev => ({
      ...prev,
      dragOwnership: { nodeId, startedAt: Date.now() },
      activity: 'dragging',
      timestamp: Date.now(),
    }));
  }, []);

  const releaseDrag = useCallback(() => {
    setLocalState(prev => ({
      ...prev,
      dragOwnership: null,
      activity: 'active',
      timestamp: Date.now(),
    }));
  }, []);

  return { localState, others, setCursor, setSelection, setViewport, setActivity, claimDrag, releaseDrag };
}

export { Awareness, encodeAwarenessUpdate, applyAwarenessUpdate, removeAwarenessStates };
