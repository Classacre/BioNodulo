import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { NodeMetadata, ObjectInfo, Workflow } from '../../types';
import { collectRegistryNodeIds } from '../../utils/registryNodes';
import { logError } from '../../state/logging';

const MAX_ATTEMPTS = 3;

export function useRegistryNodeHydration(
  workflows: readonly Workflow[],
  objectInfo: ObjectInfo,
  registerNode: (nodeId: string) => Promise<NodeMetadata>,
  retryDelayMs = 1500,
) {
  const [failures, setFailures] = useState<Record<string, string>>({});
  const [retryKey, setRetryKey] = useState(0);
  const attempted = useRef(new Set<string>());
  const epochs = useRef(new Map<string, number>());
  const timers = useRef(new Map<string, number>());
  const desired = useRef(new Set<string>());
  const infoRef = useRef(objectInfo);
  infoRef.current = objectInfo;
  const ids = useMemo(() => collectRegistryNodeIds(workflows), [workflows]);

  const runAttempt: (id: string, attempt: number, epoch: number) => void = useCallback((id, attempt, epoch) => {
    if (!desired.current.has(id) || infoRef.current[id] || epochs.current.get(id) !== epoch) return;
    void registerNode(id).then(() => {
      if (epochs.current.get(id) !== epoch) return;
      setFailures(previous => {
        if (!(id in previous)) return previous;
        const next = { ...previous };
        delete next[id];
        return next;
      });
    }).catch(error => {
      if (!desired.current.has(id) || infoRef.current[id] || epochs.current.get(id) !== epoch) return;
      logError('registry.restoreNode', error);
      setFailures(previous => ({ ...previous, [id]: error instanceof Error ? error.message : String(error) }));
      if (attempt < MAX_ATTEMPTS) {
        const timer = window.setTimeout(() => {
          timers.current.delete(id);
          runAttempt(id, attempt + 1, epoch);
        }, retryDelayMs * 2 ** (attempt - 1));
        timers.current.set(id, timer);
      }
    });
  }, [registerNode, retryDelayMs]);

  useEffect(() => {
    desired.current = new Set(ids);
    for (const id of attempted.current) {
      if (!desired.current.has(id)) {
        attempted.current.delete(id);
        epochs.current.set(id, (epochs.current.get(id) ?? 0) + 1);
      }
    }
    for (const [id, timer] of timers.current) {
      if (!desired.current.has(id) || objectInfo[id]) {
        window.clearTimeout(timer);
        timers.current.delete(id);
      }
    }
    setFailures(previous => {
      const retained = Object.entries(previous).filter(([id]) => desired.current.has(id) && !objectInfo[id]);
      return retained.length === Object.keys(previous).length ? previous : Object.fromEntries(retained);
    });
    for (const id of ids) {
      if (objectInfo[id] || attempted.current.has(id)) continue;
      attempted.current.add(id);
      const epoch = (epochs.current.get(id) ?? 0) + 1;
      epochs.current.set(id, epoch);
      runAttempt(id, 1, epoch);
    }
  }, [ids, objectInfo, retryKey, runAttempt]);

  useEffect(() => () => {
    desired.current.clear();
    for (const timer of timers.current.values()) window.clearTimeout(timer);
    timers.current.clear();
  }, []);

  const retry = useCallback(() => {
    for (const id of Object.keys(failures)) {
      const timer = timers.current.get(id);
      if (timer !== undefined) window.clearTimeout(timer);
      timers.current.delete(id);
      attempted.current.delete(id);
      epochs.current.set(id, (epochs.current.get(id) ?? 0) + 1);
    }
    setFailures({});
    setRetryKey(value => value + 1);
  }, [failures]);

  return { failures, retry };
}
