import { useState, useEffect, useCallback } from 'react';

const DEFAULT_SETTINGS: Record<string, unknown> = {
  'bionodulo.theme': 'system',
  'bionodulo.snapToGrid': false,
  'bionodulo.showMinimap': true,
  'bionodulo.linksHidden': false,
  'bionodulo.viewportLocked': false,
  'bionodulo.autoSave': 'off',
  'bionodulo.queueHistorySize': 100,
  'bionodulo.fileExplorerDepth': 4,
  'bionodulo.showHiddenFiles': false,
  'bionodulo.strongHashing': false,
  'bionodulo.tooltipsEnabled': true,
  'bionodulo.confirmFileDelete': true,
  'bionodulo.preserveView': true,
  'bionodulo.llm.provider': 'openai',
  'bionodulo.llm.model': 'gpt-4.1-mini',
  'bionodulo.llm.baseUrl': '',
  'bionodulo.llm.apiKey': '',
  'bionodulo.llm.temperature': 0.2,
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

// Global shared state so all components see the same settings
let globalSettings = loadLocal();
let globalHydrated = false;
let globalFetchStarted = false;
const listeners = new Set<() => void>();

function emit() {
  listeners.forEach(fn => fn());
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
    globalSettings = { ...globalSettings, [key]: value };
    saveLocal(globalSettings);
    emit();
  }, []);

  const setAll = useCallback((newSettings: Record<string, unknown>) => {
    globalSettings = { ...globalSettings, ...newSettings };
    saveLocal(globalSettings);
    emit();
  }, []);

  // Sync with backend when available
  useEffect(() => {
    if (globalFetchStarted) return;
    globalFetchStarted = true;
    fetch('/api/settings')
      .then(r => r.ok ? r.json() : null)
      .then(data => {
        if (data) {
          globalSettings = { ...globalSettings, ...data };
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
