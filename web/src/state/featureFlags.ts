// Lightweight feature flag system.
//
// Designed for in-development surfaces that should ship dark by default and
// be toggleable per-user via the Settings panel (or via a URL query param
// like `?flag=experimentalReroutes`). Flag values live in localStorage so
// they survive reloads.
//
// Definition pattern:
//   const FLAG = registerFlag({ key: 'experimentalReroutes', defaultValue: false, label: '...' });
//
// Usage in React:
//   const enabled = useFeatureFlag(FLAG);
//
// The store deliberately stays in-process — no async fetch, no remote
// service — so the API stays simple and survives offline.

import { useEffect, useState } from 'react';

export interface FeatureFlagDef {
  /** Stable identifier used as the localStorage key suffix. */
  key: string;
  /** Default value applied when the user has never overridden the flag. */
  defaultValue: boolean;
  /** Human-readable label for the Settings UI. */
  label: string;
  /** Optional description shown beneath the toggle. */
  description?: string;
}

const STORAGE_PREFIX = 'bionodulo.flag.';
const definitions = new Map<string, FeatureFlagDef>();
const overrides = new Map<string, boolean>(); // explicit user overrides
const listeners = new Set<() => void>();

function emit(): void {
  listeners.forEach(listener => {
    try { listener(); } catch { /* ignore */ }
  });
}

function loadOverride(key: string): boolean | undefined {
  if (typeof localStorage === 'undefined') return undefined;
  try {
    const raw = localStorage.getItem(STORAGE_PREFIX + key);
    if (raw === '1' || raw === 'true') return true;
    if (raw === '0' || raw === 'false') return false;
  } catch {
    /* ignore */
  }
  return undefined;
}

function persistOverride(key: string, value: boolean | undefined): void {
  if (typeof localStorage === 'undefined') return;
  try {
    if (value === undefined) localStorage.removeItem(STORAGE_PREFIX + key);
    else localStorage.setItem(STORAGE_PREFIX + key, value ? '1' : '0');
  } catch {
    /* ignore */
  }
}

/**
 * Register a flag. Safe to call multiple times with the same key (subsequent
 * registrations are ignored). Returns the same definition object so callers
 * can keep a reference and pass it to `useFeatureFlag` / `getFeatureFlag`.
 */
export function registerFlag(def: FeatureFlagDef): FeatureFlagDef {
  const existing = definitions.get(def.key);
  if (existing) return existing;
  definitions.set(def.key, def);
  const initialOverride = loadOverride(def.key);
  if (initialOverride !== undefined) overrides.set(def.key, initialOverride);
  // One-shot URL bootstrapping: `?flag=foo,bar` flips the listed flags on
  // for this session so a teammate can preview a feature without poking
  // localStorage. Only runs once per page load.
  applyUrlBootstrapOnce();
  return def;
}

let urlBootstrapped = false;
function applyUrlBootstrapOnce(): void {
  if (urlBootstrapped) return;
  urlBootstrapped = true;
  if (typeof window === 'undefined') return;
  try {
    const params = new URLSearchParams(window.location.search);
    const enable = params.get('flag');
    if (enable) {
      for (const key of enable.split(',').map(k => k.trim()).filter(Boolean)) {
        overrides.set(key, true);
      }
    }
    const disable = params.get('flagOff');
    if (disable) {
      for (const key of disable.split(',').map(k => k.trim()).filter(Boolean)) {
        overrides.set(key, false);
      }
    }
  } catch {
    /* ignore */
  }
}

export function getFeatureFlag(def: FeatureFlagDef): boolean {
  const override = overrides.get(def.key);
  return override === undefined ? def.defaultValue : override;
}

export function setFeatureFlag(def: FeatureFlagDef, value: boolean | undefined): void {
  if (value === undefined) overrides.delete(def.key);
  else overrides.set(def.key, value);
  persistOverride(def.key, value);
  emit();
}

export function listFeatureFlags(): FeatureFlagDef[] {
  return Array.from(definitions.values()).sort((a, b) => a.label.localeCompare(b.label));
}

export function useFeatureFlag(def: FeatureFlagDef): boolean {
  const [value, setValue] = useState(() => getFeatureFlag(def));
  useEffect(() => {
    const listener = () => setValue(getFeatureFlag(def));
    listeners.add(listener);
    return () => { listeners.delete(listener); };
  }, [def]);
  return value;
}
