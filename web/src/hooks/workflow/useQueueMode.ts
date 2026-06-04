// Queue-mode persistence + auto-run timers.
//
// Three modes:
//   - 'manual'  — user clicks Run. No auto-run.
//   - 'change'  — re-runs 1.5s after the workflow becomes dirty (debounced).
//   - 'instant' — re-runs 250ms after the most recent run completes successfully.
//
// Extracted from App.tsx so the auto-queue side effects live next to the state
// that drives them.

import { useState, useEffect, useRef, useCallback } from 'react';
import type { WorkflowNode, RunRecord } from '../../types';

export type QueueMode = 'manual' | 'change' | 'instant';

const QUEUE_MODE_KEY = 'bionodulo.queueMode';

export interface UseQueueModeArgs {
  dirty: boolean;
  isRunning: boolean;
  activeNodes: WorkflowNode[];
  runs: RunRecord[];
  triggerRun: () => Promise<void> | void;
}

export interface UseQueueModeResult {
  queueMode: QueueMode;
  setQueueMode: (mode: QueueMode) => void;
}

export function useQueueMode({
  dirty,
  isRunning,
  activeNodes,
  runs,
  triggerRun,
}: UseQueueModeArgs): UseQueueModeResult {
  const [queueMode, setQueueModeState] = useState<QueueMode>(() => {
    try {
      const stored = localStorage.getItem(QUEUE_MODE_KEY);
      if (stored === 'change' || stored === 'instant' || stored === 'manual') return stored;
    } catch {
      /* ignore */
    }
    return 'manual';
  });

  const setQueueMode = useCallback((mode: QueueMode) => {
    setQueueModeState(mode);
    try {
      localStorage.setItem(QUEUE_MODE_KEY, mode);
    } catch {
      /* quota */
    }
  }, []);

  // Keep a ref to the latest triggerRun so the effects don't re-bind on every
  // render of the parent (handleRun's identity changes whenever the workflow
  // is edited).
  const triggerRunRef = useRef(triggerRun);
  useEffect(() => {
    triggerRunRef.current = triggerRun;
  }, [triggerRun]);

  // 'change' mode: debounce a run when the workflow becomes dirty. Skip if
  // the workflow has no executable nodes — notes/reroutes alone shouldn't
  // trigger a backend run.
  useEffect(() => {
    if (queueMode !== 'change') return;
    if (!dirty || isRunning) return;
    const realNodes = (activeNodes || []).filter(
      n => n.type !== 'note' && n.type !== 'reroute',
    );
    if (realNodes.length === 0) return;
    const timer = setTimeout(() => {
      void triggerRunRef.current();
    }, 1500);
    return () => clearTimeout(timer);
  }, [queueMode, dirty, isRunning, activeNodes]);

  // 'instant' mode: re-fire as soon as the most recent run finishes
  // successfully. Tracking the last run id ensures we don't double-fire.
  const lastInstantRunRef = useRef<string | null>(null);
  useEffect(() => {
    if (queueMode !== 'instant') return;
    if (isRunning) return;
    const latest = runs[0];
    if (!latest) return;
    if (latest.status !== 'completed') return;
    if (lastInstantRunRef.current === latest.run_id) return;
    lastInstantRunRef.current = latest.run_id;
    // Tiny delay so the UI can settle and the user can still cancel
    // the auto-queue by switching mode before the next run fires.
    const timer = setTimeout(() => {
      void triggerRunRef.current();
    }, 250);
    return () => clearTimeout(timer);
  }, [queueMode, isRunning, runs]);

  return { queueMode, setQueueMode };
}
