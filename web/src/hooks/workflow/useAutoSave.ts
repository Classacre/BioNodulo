// Auto-save timer that periodically snapshots the workflow to localStorage,
// publishes to collab (if enabled), and refreshes the recents thumbnail.
//
// Extracted from App.tsx to reduce the god-component footprint. Returns the
// last auto-save timestamp for display in the UI.

import { useEffect, useState, useRef } from 'react';
import type { Workflow } from '../../types';
import { renderRecentThumbnail } from '../../utils/workflowThumbnail';
import { refreshRecentThumbnail } from '../../state/recentWorkflows';
import { logError } from '../../state/logging';
import { LOCAL_BROWSER_STORAGE_SCOPE, type BrowserStorageScope } from '../../utils/browserStorageScope';

const AUTO_SAVE_LAST_KEY = 'bionodulo.autoSave.last';

export interface UseAutoSaveArgs {
  autoSaveSetting: string; // 'off' | '30s' | '60s'
  collabEnabled: boolean;
  latestWorkflow: Workflow;
  publishCollabWorkflowSnapshot: (workflow: Workflow) => Promise<void>;
  setDirty: (dirty: boolean) => void;
  clearDirtyOnInterval?: boolean;
  storageScope?: BrowserStorageScope;
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
  clearDirtyOnInterval = true,
  storageScope = LOCAL_BROWSER_STORAGE_SCOPE,
}: UseAutoSaveArgs): UseAutoSaveResult {
  const [lastAutoSaveAt, setLastAutoSaveAt] = useState<string | null>(() => {
    try {
      return localStorage.getItem(AUTO_SAVE_LAST_KEY);
    } catch {
      return null;
    }
  });

  const latestWorkflowRef = useRef(latestWorkflow);
  const scopeRef = useRef({ identity: storageScope.identity });
  if (scopeRef.current.identity !== storageScope.identity) scopeRef.current = { identity: storageScope.identity };
  const scopeGeneration = scopeRef.current;
  useEffect(() => {
    latestWorkflowRef.current = latestWorkflow;
  }, [latestWorkflow]);

  useEffect(() => {
    if (autoSaveSetting === 'off') return;
    const seconds = parseInt(autoSaveSetting.replace('s', ''), 10);
    if (!Number.isFinite(seconds) || seconds <= 0) return;

    let cancelled = false;
    const timer = setInterval(async () => {
      if (cancelled || scopeRef.current !== scopeGeneration) return;
      const workflow = latestWorkflowRef.current;
      try {
        localStorage.setItem(AUTO_SAVE_LAST_KEY, new Date().toISOString());
      } catch {
        /* quota — ignore */
      }
      if (collabEnabled) {
        try {
          await publishCollabWorkflowSnapshot(workflow);
          if (cancelled || scopeRef.current !== scopeGeneration) return;
          if (clearDirtyOnInterval && latestWorkflowRef.current === workflow) setDirty(false);
        } catch (err) {
          if (cancelled || scopeRef.current !== scopeGeneration) return;
          logError('workflow.autoSave.collab', err);
        }
      }
      if (cancelled || scopeRef.current !== scopeGeneration) return;
      // Keep the recents thumbnail current so reopening from Getting Started
      // reflects the current shape of the workflow, not the moment of import.
      if (workflow?.id && (workflow.nodes?.length ?? 0) > 0) {
        const thumbnail = renderRecentThumbnail(workflow);
        if (thumbnail) {
          refreshRecentThumbnail(workflow.id, thumbnail, {
            name: workflow.name,
            nodeCount: workflow.nodes?.length ?? 0,
          }, storageScope);
        }
      }
      const savedAt = new Date().toISOString();
      setLastAutoSaveAt(savedAt);
      if (!collabEnabled && clearDirtyOnInterval) setDirty(false);
    }, seconds * 1000);

    return () => { cancelled = true; clearInterval(timer); };
  }, [autoSaveSetting, collabEnabled, publishCollabWorkflowSnapshot, setDirty, clearDirtyOnInterval, storageScope, scopeGeneration]);

  return { lastAutoSaveAt };
}
