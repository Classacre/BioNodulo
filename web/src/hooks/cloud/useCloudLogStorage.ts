import { useEffect, useLayoutEffect, useRef, type Dispatch, type SetStateAction } from 'react';
import type { LogEntry } from '../../types';

const PREFIX = 'bionodulo.cloud.logs';

export function cloudLogStorageKey(userId?: string | null, teamId?: string | null): string | null {
  const encode = (value: string) => encodeURIComponent(value).replace(/\./g, '%2E');
  return userId && teamId ? `${PREFIX}.${encode(userId)}.${encode(teamId)}` : null;
}

/** Clear volatile cloud records before a changed/unknown owner can paint them. */
export function useCloudScopeReset(scope: string | null | undefined, reset: () => void): void {
  const previous = useRef<string | null | undefined>(undefined);
  useLayoutEffect(() => {
    if (previous.current === scope) return;
    previous.current = scope;
    reset();
  }, [scope, reset]);
}

/** Restore only a proven owner, before a changed identity can paint old logs. */
export function useCloudLogStorage(
  editorMode: boolean,
  key: string | null,
  logs: LogEntry[],
  setLogs: Dispatch<SetStateAction<LogEntry[]>>,
): void {
  const restoredScope = useRef<string | null | undefined>(undefined);
  useLayoutEffect(() => {
    if (!editorMode || restoredScope.current === key) return;
    restoredScope.current = key;
    let restored: LogEntry[] = [];
    try {
      // The legacy unscoped cache has no provable owner. Never restore it.
      const raw = key ? localStorage.getItem(key) : null;
      if (raw) {
        const entries = JSON.parse(raw) as LogEntry[];
        if (Array.isArray(entries)) restored = entries.slice(-1000);
      }
    } catch { /* corrupt/unavailable storage */ }
    setLogs(restored);
  }, [editorMode, key, setLogs]);

  useEffect(() => {
    if (!editorMode || !key || restoredScope.current !== key) return;
    const timer = setTimeout(() => {
      try { localStorage.setItem(key, JSON.stringify(logs.slice(-1000))); } catch { /* quota */ }
    }, 800);
    return () => clearTimeout(timer);
  }, [editorMode, key, logs]);
}
