// Auto-save timer that periodically snapshots the workflow to localStorage,
// publishes to collab (if enabled), and refreshes the recents thumbnail.
//
// Extracted from App.tsx to reduce the god-component footprint. Returns the
// last auto-save timestamp for display in the UI.

import { useEffect, useState, useRef } from 'react';
import type { Workflow } from '../../types';
import { renderRecentThumbnail } from '../../utils/workflowThumbnail';
import { refreshRecentThumbnail } from '../../state/recentWorkflows';

const AUTO_SAVE_LAST_KEY = 'bionodulo.autoSave.last';

export interface UseAutoSaveArgs {
  autoSaveSetting: string; // 'off' | '30s' | '60s'
  collabEnabled: boolean;
  latestWorkflow: Workflow;
  publishCollabWorkflowSnapshot: (workflow: Workflow) => Promise<void>;
  setDirty: (dirty: boolean) => void;
}

export interface UseAutoSaveResult {
  lastAutoSaveAt: string | null;
}

export function useAutoSave({
  autoSaveSetting,
  collabEnabled,
  latestWorkflow,
  publishCollabWorkflowSnapshot,
  setDirty,
}: UseAutoSaveArgs): UseAutoSaveResult {
  const [lastAutoSaveAt, setLastAutoSaveAt] = useState<string | null>(() => {
    try {
      return localStorage.getItem(AUTO_SAVE_LAST_KEY);
    } catch {
      return null;
    }
  });

  const latestWorkflowRef = useRef(latestWorkflow);
  useEffect(() => {
    latestWorkflowRef.current = latestWorkflow;
  }, [latestWorkflow]);

  useEffect(() => {
    if (autoSaveSetting === 'off') return;
    const seconds = parseInt(autoSaveSetting.replace('s', ''), 10);
    if (!Number.isFinite(seconds) || seconds <= 0) return;

    const timer = setInterval(() => {
      const workflow = latestWorkflowRef.current;
      try {
        localStorage.setItem(AUTO_SAVE_LAST_KEY, new Date().toISOString());
      } catch {
        /* quota — ignore */
      }
      if (collabEnabled) {
        void publishCollabWorkflowSnapshot(workflow);
      }
      // Keep the recents thumbnail current so reopening from Getting Started
      // reflects the current shape of the workflow, not the moment of import.
      if (workflow?.id && (workflow.nodes?.length ?? 0) > 0) {
        const thumbnail = renderRecentThumbnail(workflow);
        if (thumbnail) {
          refreshRecentThumbnail(workflow.id, thumbnail, {
            name: workflow.name,
            nodeCount: workflow.nodes?.length ?? 0,
          });
        }
      }
      const savedAt = new Date().toISOString();
      setLastAutoSaveAt(savedAt);
      setDirty(false);
    }, seconds * 1000);

    return () => clearInterval(timer);
  }, [autoSaveSetting, collabEnabled, publishCollabWorkflowSnapshot, setDirty]);

  return { lastAutoSaveAt };
}
