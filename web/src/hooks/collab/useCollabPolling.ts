// Collab REST polling: live presence (30s visible / 120s hidden).
//
// Comments now sync through the collab Yjs doc (see collab/yjsDoc + bridge), so
// this only polls the server-side global presence list (used by the user-list
// panel; real-time cursors come from y-protocols awareness).

import { useEffect, useCallback } from 'react';
import { apiGet } from '../../api/client';
import { logError } from '../../state/logging';
import { getToken } from '../../collab';
import type { LivePresenceUser } from '../../collab';
import {
  COLLAB_PRESENCE_POLL_HIDDEN_MS,
  COLLAB_PRESENCE_POLL_VISIBLE_MS,
  isBrowserDocumentHidden,
  startVisibilityAwarePolling,
} from '../../utils/pollingPolicy';

export interface UseCollabPollingArgs {
  collabEnabled: boolean;
  setLivePresenceUsers: (users: LivePresenceUser[]) => void;
}

export function useCollabPolling({
  collabEnabled,
  setLivePresenceUsers,
}: UseCollabPollingArgs): void {
  const fetchLivePresence = useCallback(async () => {
    if (!collabEnabled) return;
    if (isBrowserDocumentHidden()) return;
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
    if (!collabEnabled) return;
    const tick = async () => {
      await fetchLivePresence();
    };
    return startVisibilityAwarePolling(
      tick,
      COLLAB_PRESENCE_POLL_VISIBLE_MS,
      COLLAB_PRESENCE_POLL_HIDDEN_MS,
    );
  }, [collabEnabled, fetchLivePresence]);
}
