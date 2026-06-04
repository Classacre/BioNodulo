// Collab REST polling: workflow comments (5s) + live presence (3s).
//
// Extracted from App.tsx — these are independent of the y-websocket bridge,
// which still owns real-time edits and awareness. Polling exists because
// comments and the global presence list are stored server-side and don't
// flow through the y-doc.

import { useEffect, useCallback } from 'react';
import { apiGet } from '../../api/client';
import { logError } from '../../state/logging';
import { getToken } from '../../collab';
import type { Comment, LivePresenceUser } from '../../collab';

export interface UseCollabPollingArgs {
  collabEnabled: boolean;
  activeWorkflowId: string | undefined;
  setWorkflowComments: (comments: Comment[]) => void;
  setLivePresenceUsers: (users: LivePresenceUser[]) => void;
}

export interface UseCollabPollingResult {
  refetchComments: () => Promise<void>;
}

export function useCollabPolling({
  collabEnabled,
  activeWorkflowId,
  setWorkflowComments,
  setLivePresenceUsers,
}: UseCollabPollingArgs): UseCollabPollingResult {
  const fetchWorkflowComments = useCallback(async () => {
    if (!collabEnabled || !activeWorkflowId) return;
    const token = getToken();
    if (!token) return;
    try {
      const data = await apiGet<{ comments?: Comment[] }>(
        `/api/collab/workflows/${activeWorkflowId}/comments`,
      );
      setWorkflowComments(data.comments ?? []);
    } catch (err) {
      logError('collab.comments.fetch', err);
      // Node comment pins are optional when collaboration is unavailable.
    }
  }, [activeWorkflowId, collabEnabled, setWorkflowComments]);

  useEffect(() => {
    setWorkflowComments([]);
    void fetchWorkflowComments();
    if (!collabEnabled) return;
    const interval = setInterval(fetchWorkflowComments, 5000);
    return () => clearInterval(interval);
  }, [collabEnabled, fetchWorkflowComments, setWorkflowComments]);

  const fetchLivePresence = useCallback(async () => {
    if (!collabEnabled) return;
    const token = getToken();
    if (!token) return;
    try {
      const data = await apiGet<{ users?: LivePresenceUser[] }>('/api/collab/presence');
      setLivePresenceUsers(data.users ?? []);
    } catch (err) {
      logError('collab.presence.fetch', err);
      // Room-local awareness still drives collaborative cursor rendering.
    }
  }, [collabEnabled, setLivePresenceUsers]);

  useEffect(() => {
    void fetchLivePresence();
    if (!collabEnabled) return;
    const interval = setInterval(fetchLivePresence, 3000);
    return () => clearInterval(interval);
  }, [collabEnabled, fetchLivePresence]);

  return { refetchComments: fetchWorkflowComments };
}
