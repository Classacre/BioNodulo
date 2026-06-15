import { useState, useEffect, useCallback } from 'react';
import { apiGet, apiPost } from '../../api/client';

const DEFAULT_SETTINGS: Record<string, unknown> = {
  'bionodulo.snapToGrid': false,
  'bionodulo.showMinimap': true,
  'bionodulo.linksHidden': false,
  'bionodulo.viewportLocked': false,
  'bionodulo.autoSave': 'off',
  'bionodulo.queueHistorySize': 100,
  'bionodulo.showHiddenFiles': false,
  'bionodulo.tooltipsEnabled': true,
  'bionodulo.locale': 'system',
  'bionodulo.canvas.gridSize': 20,
  'bionodulo.canvas.showGrid': true,
  'bionodulo.notifications.toastDuration': 5000,
  'bionodulo.execution.maxWorkers': 4,
  'bionodulo.execution.contentHashing': 'fast',
  'bionodulo.execution.envIsolation': 'auto',
  'bionodulo.execution.timeoutSeconds': 3600,
  'bionodulo.llm.provider': 'openai',
  'bionodulo.llm.model': 'gpt-4.1-mini',
  'bionodulo.llm.baseUrl': '',
  'bionodulo.llm.apiKey': '',
  'bionodulo.llm.temperature': 0.2,
  'bionodulo.llm.maxTokens': 4096,
  'bionodulo.cacheEnabled': true,
  'bionodulo.hpc.enabled': false,
  'bionodulo.hpc.backend': 'slurm',
  'bionodulo.hpc.partition': '',
  'bionodulo.hpc.account': '',
  'bionodulo.hpc.modules': [],
  'bionodulo.hpc.container': '',
  'bionodulo.hpc.walltime': '01:00:00',
  'bionodulo.hpc.cpus_per_task': 4,
  'bionodulo.hpc.mem_per_cpu': '4G',
  'bionodulo.collab.enabled': false,
  'bionodulo.collab.presence': true,
  'bionodulo.getting_started.show_on_startup': true,
  'bionodulo.getting_started.dismissed': false,
};

const STORAGE_KEY = 'bionodulo.settings';

function loadLocal(): Record<string, unknown> {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) return { ...DEFAULT_SETTINGS, ...JSON.parse(raw) };
  } catch { /* ignore */ }
  return { ...DEFAULT_SETTINGS };
}

function saveLocal(settings: Record<string, unknown>) {
  try { localStorage.setItem(STORAGE_KEY, JSON.stringify(settings)); } catch { /* ignore */ }
}

// Persist changed keys to the backend so settings the server consumes (LLM
// credentials/model, execution + file options) actually take effect. localStorage
// alone never reaches the backend. Fire-and-forget: the UI already updated local
// state, and the app must keep working offline.
function persistRemote(partial: Record<string, unknown>): void {
  if (!partial || Object.keys(partial).length === 0) return;
  void apiPost('/api/settings', { settings: partial }).catch(() => { /* offline */ });
}

// Global shared state so all components see the same settings
let globalSettings = loadLocal();
let globalHydrated = false;
let globalFetchStarted = false;
const listeners = new Set<() => void>();

// Per-key change subscribers: lets feature code react to a specific setting
// without reading every render. Receives (newValue, oldValue, key) so a hook
// can ignore no-op flips and short-circuit when the new value matches state.
type SettingChangeListener = (newValue: unknown, oldValue: unknown, key: string) => void;
const keyListeners = new Map<string, Set<SettingChangeListener>>();

/** Non-reactive read of a single setting (no subscription/re-render). Use in
 * hot paths or non-component code; components that must update on change should
 * use `useSettings`. */
export function getSettingValue<T = unknown>(key: string, fallback?: T): T {
  const val = globalSettings[key];
  return (val === undefined ? fallback : val) as T;
}

export function subscribeSetting(key: string, listener: SettingChangeListener): () => void {
  let bucket = keyListeners.get(key);
  if (!bucket) {
    bucket = new Set();
    keyListeners.set(key, bucket);
  }
  bucket.add(listener);
  return () => {
    bucket?.delete(listener);
    if (bucket && bucket.size === 0) keyListeners.delete(key);
  };
}

function emit() {
  listeners.forEach(fn => fn());
}

function emitKeyChange(key: string, newValue: unknown, oldValue: unknown): void {
  const bucket = keyListeners.get(key);
  if (!bucket) return;
  bucket.forEach(listener => {
    try {
      listener(newValue, oldValue, key);
    } catch {
      // Side-effect hooks must not crash the settings system.
    }
  });
}

export function useSettings() {
  const [, forceUpdate] = useState(0);

  useEffect(() => {
    const cb = () => forceUpdate(n => n + 1);
    listeners.add(cb);
    return () => { listeners.delete(cb); };
  }, []);

  const get = useCallback((key: string) => globalSettings[key], []);

  const getBool = useCallback((key: string, fallback = false) => {
    const val = globalSettings[key];
    if (typeof val === 'boolean') return val;
    if (typeof val === 'string') return val === 'true' || val === '1';
    if (val === undefined || val === null) return fallback;
    return !!val;
  }, []);

  // Typed accessors: validate at the boundary instead of forcing every caller
  // to sprinkle `as string` casts. Each falls back to a sensible default when
  // the value isn't the expected shape.
  const getString = useCallback((key: string, fallback = ''): string => {
    const val = globalSettings[key];
    return typeof val === 'string' ? val : fallback;
  }, []);

  const getNumber = useCallback((key: string, fallback = 0): number => {
    const val = globalSettings[key];
    if (typeof val === 'number' && Number.isFinite(val)) return val;
    if (typeof val === 'string') {
      const parsed = Number(val);
      if (Number.isFinite(parsed)) return parsed;
    }
    return fallback;
  }, []);

  const getStringArray = useCallback((key: string, fallback: string[] = []): string[] => {
    const val = globalSettings[key];
    if (Array.isArray(val)) return val.filter((item): item is string => typeof item === 'string');
    return fallback;
  }, []);

  const getRecord = useCallback(<T = unknown>(key: string, fallback: Record<string, T> = {}): Record<string, T> => {
    const val = globalSettings[key];
    if (val && typeof val === 'object' && !Array.isArray(val)) return val as Record<string, T>;
    return fallback;
  }, []);

  const set = useCallback((key: string, value: unknown) => {
    const previous = globalSettings[key];
    globalSettings = { ...globalSettings, [key]: value };
    saveLocal(globalSettings);
    persistRemote({ [key]: value });
    emitKeyChange(key, value, previous);
    emit();
  }, []);

  const setAll = useCallback((newSettings: Record<string, unknown>) => {
    const previous = globalSettings;
    globalSettings = { ...globalSettings, ...newSettings };
    saveLocal(globalSettings);
    persistRemote(newSettings);
    for (const [key, value] of Object.entries(newSettings)) {
      emitKeyChange(key, value, previous[key]);
    }
    emit();
  }, []);

  // Sync with backend when available
  useEffect(() => {
    if (globalFetchStarted) return;
    globalFetchStarted = true;
    apiGet<Partial<typeof globalSettings>>('/api/settings')
      .then(data => {
        if (data) {
          // The backend redacts secrets (e.g. apiKey -> "***") on GET. Don't let
          // a redacted placeholder clobber the real local value.
          const clean: Record<string, unknown> = {};
          for (const [key, value] of Object.entries(data)) {
            if (typeof value === 'string' && /^\*+$/.test(value)) continue;
            clean[key] = value;
          }
          globalSettings = { ...globalSettings, ...clean };
          saveLocal(globalSettings);
        }
      })
      .catch(() => { /* offline */ })
      .finally(() => {
        globalHydrated = true;
        emit();
      });
  }, []);

  return { settings: globalSettings, ready: globalHydrated, get, getBool, getString, getNumber, getStringArray, getRecord, set, setAll };
}

/**
 * React-friendly subscription to a single setting key. The handler runs on
 * every change to `key`; pass a stable callback (useCallback) so the
 * subscription isn't torn down on every render.
 */
export function useSettingChange(key: string, handler: SettingChangeListener): void {
  useEffect(() => subscribeSetting(key, handler), [key, handler]);
}
