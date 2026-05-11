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
  'bionodulo.hpc.enabled': false,
  'bionodulo.hpc.backend': 'slurm',
  'bionodulo.hpc.partition': '',
  'bionodulo.hpc.account': '',
  'bionodulo.hpc.modules': [],
  'bionodulo.hpc.container': '',
  'bionodulo.hpc.walltime': '01:00:00',
  'bionodulo.hpc.cpus_per_task': 4,
  'bionodulo.hpc.mem_per_cpu': '4G',
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

  const getBool = useCallback((key: string) => {
    const val = globalSettings[key];
    if (typeof val === 'boolean') return val;
    if (typeof val === 'string') return val === 'true' || val === '1';
    return !!val;
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
    fetch('/api/settings')
      .then(r => r.ok ? r.json() : null)
      .then(data => {
        if (data) {
          globalSettings = { ...globalSettings, ...data };
          saveLocal(globalSettings);
          emit();
        }
      })
      .catch(() => { /* offline */ });
  }, []);

  return { settings: globalSettings, get, getBool, set, setAll };
}
