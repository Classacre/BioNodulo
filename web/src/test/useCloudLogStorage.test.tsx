import { useState } from 'react';
import { act, renderHook } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cloudLogStorageKey, useCloudLogStorage, useCloudScopeReset } from '../hooks/cloud/useCloudLogStorage';
import type { LogEntry } from '../types';

const entry = (message: string): LogEntry => ({ run_id: 'run', node_id: 'node', level: 'info', timestamp: '2026-10-16T00:00:00Z', message });

describe('cloud console ownership', () => {
  beforeEach(() => { localStorage.clear(); vi.useFakeTimers(); });
  afterEach(() => { vi.useRealTimers(); });

  it('switches team and guest scopes in page without retaining or writing the previous scope', () => {
    const a = cloudLogStorageKey('user', 'team-a')!;
    const b = cloudLogStorageKey('user', 'team-b')!;
    localStorage.setItem(a, JSON.stringify([entry('team A')]));
    localStorage.setItem(b, JSON.stringify([entry('team B')]));
    localStorage.setItem('bionodulo.cloud.logs', JSON.stringify([entry('legacy secret')]));
    const { result, rerender } = renderHook(({ scope }: { scope: string | null }) => {
      const [logs, setLogs] = useState<LogEntry[]>([]);
      useCloudLogStorage(true, scope, logs, setLogs);
      return { logs, setLogs };
    }, { initialProps: { scope: a as string | null } });
    expect(result.current.logs.map(log => log.message)).toEqual(['team A']);
    act(() => result.current.setLogs([entry('unsaved team A')]));
    rerender({ scope: b });
    expect(result.current.logs.map(log => log.message)).toEqual(['team B']);
    act(() => vi.advanceTimersByTime(800));
    expect(JSON.parse(localStorage.getItem(a)!)[0].message).toBe('team A');
    expect(JSON.parse(localStorage.getItem(b)!)[0].message).toBe('team B');
    rerender({ scope: null });
    expect(result.current.logs).toEqual([]);
    act(() => vi.advanceTimersByTime(800));
    expect(JSON.parse(localStorage.getItem(b)!)[0].message).toBe('team B');
  });

  it('keeps local logs intact and tolerates corrupt cloud storage', () => {
    const key = cloudLogStorageKey('user', 'team')!;
    localStorage.setItem(key, 'invalid JSON');
    const { result, rerender } = renderHook(({ editorMode }) => {
      const [logs, setLogs] = useState([entry('local')]);
      useCloudLogStorage(editorMode, key, logs, setLogs);
      return logs;
    }, { initialProps: { editorMode: false } });
    expect(result.current[0].message).toBe('local');
    rerender({ editorMode: true });
    expect(result.current).toEqual([]);
  });

  it('requires both identities and encodes delimiters without collisions', () => {
    expect(cloudLogStorageKey(null, 'team')).toBeNull();
    expect(cloudLogStorageKey('user', null)).toBeNull();
    expect(cloudLogStorageKey('a.b', 'c')).not.toBe(cloudLogStorageKey('a', 'b.c'));
  });

  it('clears old run summaries and output metadata synchronously when the in-page owner changes', () => {
    const { result, rerender } = renderHook(({ scope }: { scope: string | null }) => {
      const [rows, setRows] = useState<string[]>([]);
      useCloudScopeReset(scope, () => setRows([]));
      return { rows, setRows };
    }, { initialProps: { scope: 'team-a' as string | null } });
    act(() => result.current.setRows(['team A run/output hash']));
    rerender({ scope: 'team-b' });
    expect(result.current.rows).toEqual([]);
    act(() => result.current.setRows(['team B run/output hash']));
    rerender({ scope: null });
    expect(result.current.rows).toEqual([]);
  });
});
