import type { TFunction } from 'i18next';

export type PaletteMode = 'light' | 'dark';

// 66-token design system. Tokens are organised into semantic groups so a
// palette author can override a base value (e.g. `accent`) and the derived
// states (`accent-hover`, `accent-active`, `accent-soft`) get filled in by
// `completePalette()` without requiring per-state hand-tuning. Authors who
// want fine control can still set any derived token explicitly.
export type PaletteToken =
  // Surfaces (8)
  | 'canvas'
  | 'surface'
  | 'surface-2'
  | 'surface-3'
  | 'surface-overlay'
  | 'surface-elevated'
  | 'surface-sunken'
  | 'surface-disabled'
  // Text (6)
  | 'text'
  | 'text-2'
  | 'text-3'
  | 'text-muted'
  | 'text-inverse'
  | 'text-link'
  // Borders / dividers (5)
  | 'border'
  | 'border-2'
  | 'border-strong'
  | 'border-subtle'
  | 'divider'
  // Accent (5)
  | 'accent'
  | 'accent-light'
  | 'accent-dark'
  | 'accent-hover'
  | 'accent-active'
  // Accent soft tints (3)
  | 'accent-soft'
  | 'accent-soft-2'
  | 'accent-contrast'
  // Status base (4)
  | 'danger'
  | 'warning'
  | 'success'
  | 'info'
  // Status soft tints (4)
  | 'danger-soft'
  | 'warning-soft'
  | 'success-soft'
  | 'info-soft'
  // Status borders (4)
  | 'danger-border'
  | 'warning-border'
  | 'success-border'
  | 'info-border'
  // Focus / interaction (5)
  | 'focus-ring'
  | 'focus-ring-soft'
  | 'selection-bg'
  | 'selection-fg'
  | 'highlight'
  // Canvas / graph (8)
  | 'minimap-bg'
  | 'minimap-fg'
  | 'minimap-mask'
  | 'edge-default'
  | 'edge-hover'
  | 'edge-selected'
  | 'grid-line'
  | 'grid-dot'
  // Code / mono (4)
  | 'code-bg'
  | 'code-fg'
  | 'code-comment'
  | 'code-keyword'
  // Backdrop / scrim (3)
  | 'backdrop'
  | 'scrim'
  | 'tooltip-bg'
  // Shadows / elevation (3)
  | 'shadow-color'
  | 'shadow-color-strong'
  | 'ring-color'
  // Misc (4)
  | 'badge-bg'
  | 'badge-fg'
  | 'kbd-bg'
  | 'kbd-fg';

export type PaletteTokens = Partial<Record<PaletteToken, string>>;

export const ALL_PALETTE_TOKENS: PaletteToken[] = [
  'canvas', 'surface', 'surface-2', 'surface-3', 'surface-overlay',
  'surface-elevated', 'surface-sunken', 'surface-disabled',
  'text', 'text-2', 'text-3', 'text-muted', 'text-inverse', 'text-link',
  'border', 'border-2', 'border-strong', 'border-subtle', 'divider',
  'accent', 'accent-light', 'accent-dark', 'accent-hover', 'accent-active',
  'accent-soft', 'accent-soft-2', 'accent-contrast',
  'danger', 'warning', 'success', 'info',
  'danger-soft', 'warning-soft', 'success-soft', 'info-soft',
  'danger-border', 'warning-border', 'success-border', 'info-border',
  'focus-ring', 'focus-ring-soft', 'selection-bg', 'selection-fg', 'highlight',
  'minimap-bg', 'minimap-fg', 'minimap-mask',
  'edge-default', 'edge-hover', 'edge-selected', 'grid-line', 'grid-dot',
  'code-bg', 'code-fg', 'code-comment', 'code-keyword',
  'backdrop', 'scrim', 'tooltip-bg',
  'shadow-color', 'shadow-color-strong', 'ring-color',
  'badge-bg', 'badge-fg', 'kbd-bg', 'kbd-fg',
];

export type CanvasPattern = 'none' | 'dots' | 'grid' | 'mesh';

export interface ThemePalette {
  id: string;
  name: string;
  description: string;
  descriptionKey?: string;
  preview: string[];
  light: PaletteTokens;
  dark: PaletteTokens;
  canvasPattern?: CanvasPattern;
}

const STORAGE_KEY = 'bionodulo.palette';
const CUSTOM_STORAGE_KEY = 'bionodulo.customPalettes';
const listeners = new Set<() => void>();
let paletteRevision = 0;

export const BUILT_IN_PALETTES: ThemePalette[] = [
  {
    id: 'bionodulo',
    name: 'BioNodulo',
    description: 'Default teal workbench palette.',
    descriptionKey: 'palettes.descriptions.bionodulo',
    canvasPattern: 'dots',
    preview: ['#0d9488', '#eef3f4', '#1d2930'],
    light: {
      canvas: '#eef3f4', surface: '#ffffff', 'surface-2': '#f3f6f7', 'surface-3': '#e8edef',
      text: '#1d2930', 'text-2': '#334155',
      border: '#d9e1e5', 'border-2': '#c4cdd3',
      accent: '#0d9488', 'accent-light': '#ccfbf1', 'accent-dark': '#0f766e',
      danger: '#dc2626', warning: '#f59e0b', success: '#16a34a', info: '#2563eb',
      'minimap-bg': 'rgba(255,255,255,0.9)',
    },
    dark: {
      canvas: '#0f172a', surface: '#1e293b', 'surface-2': '#334155', 'surface-3': '#475569',
      text: '#f1f5f9', 'text-2': '#cbd5e1',
      border: '#475569', 'border-2': '#64748b',
      accent: '#2dd4bf', 'accent-light': '#134e4a', 'accent-dark': '#5eead4',
      danger: '#f87171', warning: '#fbbf24', success: '#4ade80', info: '#60a5fa',
      'minimap-bg': 'rgba(15,23,42,0.9)',
    },
  },
  {
    id: 'clinical',
    name: 'Clinical',
    description: 'High-contrast clinical workstation theme.',
    descriptionKey: 'palettes.descriptions.clinical',
    canvasPattern: 'grid',
    preview: ['#0369a1', '#f8fafc', '#0f172a'],
    light: {
      canvas: '#f8fafc', surface: '#ffffff', 'surface-2': '#f1f5f9', 'surface-3': '#e2e8f0',
      text: '#0f172a', 'text-2': '#1e293b',
      border: '#cbd5e1', 'border-2': '#94a3b8',
      accent: '#0369a1', 'accent-light': '#bae6fd', 'accent-dark': '#075985',
      danger: '#b91c1c', warning: '#b45309', success: '#15803d', info: '#1d4ed8',
      'minimap-bg': 'rgba(248,250,252,0.92)',
    },
    dark: {
      canvas: '#020617', surface: '#0f172a', 'surface-2': '#1e293b', 'surface-3': '#334155',
      text: '#f1f5f9', 'text-2': '#cbd5e1',
      border: '#334155', 'border-2': '#475569',
      accent: '#38bdf8', 'accent-light': '#0c4a6e', 'accent-dark': '#7dd3fc',
      danger: '#f87171', warning: '#fbbf24', success: '#4ade80', info: '#60a5fa',
      'minimap-bg': 'rgba(2,6,23,0.92)',
    },
  },
  {
    id: 'field',
    name: 'Field Station',
    description: 'Outdoor / field-research green palette.',
    descriptionKey: 'palettes.descriptions.field',
    canvasPattern: 'mesh',
    preview: ['#15803d', '#fefce8', '#1c1917'],
    light: {
      canvas: '#fefce8', surface: '#ffffff', 'surface-2': '#fef9c3', 'surface-3': '#fef08a',
      text: '#1c1917', 'text-2': '#44403c',
      border: '#d6d3d1', 'border-2': '#a8a29e',
      accent: '#15803d', 'accent-light': '#bbf7d0', 'accent-dark': '#166534',
      danger: '#b91c1c', warning: '#a16207', success: '#15803d', info: '#1d4ed8',
      'minimap-bg': 'rgba(254,252,232,0.9)',
    },
    dark: {
      canvas: '#1c1917', surface: '#292524', 'surface-2': '#44403c', 'surface-3': '#57534e',
      text: '#fafaf9', 'text-2': '#e7e5e4',
      border: '#57534e', 'border-2': '#78716c',
      accent: '#4ade80', 'accent-light': '#14532d', 'accent-dark': '#86efac',
      danger: '#f87171', warning: '#fbbf24', success: '#4ade80', info: '#60a5fa',
      'minimap-bg': 'rgba(28,25,23,0.9)',
    },
  },
  {
    id: 'contrast',
    name: 'High Contrast',
    description: 'Maximum-contrast accessibility theme.',
    descriptionKey: 'palettes.descriptions.contrast',
    canvasPattern: 'grid',
    preview: ['#facc15', '#000000', '#ffffff'],
    light: {
      canvas: '#ffffff', surface: '#ffffff', 'surface-2': '#f5f5f5', 'surface-3': '#e5e5e5',
      text: '#000000', 'text-2': '#171717',
      border: '#000000', 'border-2': '#404040',
      accent: '#0000ff', 'accent-light': '#dbeafe', 'accent-dark': '#1e3a8a',
      danger: '#dc0000', warning: '#aa6600', success: '#006600', info: '#0000aa',
      'minimap-bg': 'rgba(255,255,255,1)',
    },
    dark: {
      canvas: '#000000', surface: '#0a0a0a', 'surface-2': '#171717', 'surface-3': '#262626',
      text: '#ffffff', 'text-2': '#fafafa',
      border: '#ffffff', 'border-2': '#d4d4d4',
      accent: '#facc15', 'accent-light': '#451a03', 'accent-dark': '#fde047',
      danger: '#ff6b6b', warning: '#ffd93d', success: '#6bff6b', info: '#6b9bff',
      'minimap-bg': 'rgba(0,0,0,1)',
    },
  },
];

function getPaletteStorage(): Storage | undefined {
  try {
    const storage = globalThis.localStorage;
    return storage &&
      typeof storage.getItem === 'function' &&
      typeof storage.setItem === 'function'
      ? storage
      : undefined;
  } catch {
    return undefined;
  }
}

function getStoredPaletteId(): string | null {
  const storage = getPaletteStorage();
  if (!storage) return null;
  try {
    return storage.getItem(STORAGE_KEY);
  } catch {
    return null;
  }
}

let activePaletteId: string = getStoredPaletteId() || BUILT_IN_PALETTES[0].id;
let customPalettes: ThemePalette[] = loadCustomPalettes();

function loadCustomPalettes(): ThemePalette[] {
  const storage = getPaletteStorage();
  if (!storage) return [];
  try {
    const raw = storage.getItem(CUSTOM_STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function persistCustomPalettes() {
  const storage = getPaletteStorage();
  if (!storage) return;
  try {
    storage.setItem(CUSTOM_STORAGE_KEY, JSON.stringify(customPalettes));
  } catch {
    /* quota — ignore */
  }
}

function notify() {
  paletteRevision++;
  listeners.forEach(fn => { try { fn(); } catch { /* listener error */ } });
}

export function getPaletteRevision(): number {
  return paletteRevision;
}

export function subscribePalette(fn: () => void): () => void {
  listeners.add(fn);
  return () => listeners.delete(fn);
}

export function getActivePaletteId(): string {
  return activePaletteId;
}

export function setActivePaletteId(id: string): void {
  activePaletteId = id;
  const storage = getPaletteStorage();
  if (storage) {
    try { storage.setItem(STORAGE_KEY, id); } catch { /* quota */ }
  }
  notify();
}

export function listPalettes(): ThemePalette[] {
  return [...BUILT_IN_PALETTES, ...customPalettes];
}

export function paletteDisplayName(palette: Pick<ThemePalette, 'id' | 'name'>, t: TFunction): string {
  const name = t(`palettes.${palette.id}`, { defaultValue: palette.name });
  return typeof name === 'string' && name ? name : palette.name;
}

export function getPaletteDefinition(id: string): ThemePalette | undefined {
  return listPalettes().find(p => p.id === id);
}

export function upsertCustomPalette(palette: ThemePalette): void {
  const idx = customPalettes.findIndex(p => p.id === palette.id);
  if (idx >= 0) customPalettes[idx] = palette;
  else customPalettes = [...customPalettes, palette];
  persistCustomPalettes();
  notify();
}

export function removeCustomPalette(id: string): void {
  customPalettes = customPalettes.filter(p => p.id !== id);
  persistCustomPalettes();
  notify();
}

export const subscribePalettes = subscribePalette;
export const addCustomPalette = upsertCustomPalette;
export function getBuiltInPalettes(): ThemePalette[] {
  return listPalettes();
}

// Derive missing tokens from base values. The mapping intentionally sticks to
// CSS color-mix() / rgba() so palette authors don't need to carry 66 hex
// values per mode — only the ~16 semantic anchors. Anything explicitly set on
// the palette wins.
function deriveTokens(base: PaletteTokens, mode: PaletteMode, fallback?: PaletteTokens): Record<PaletteToken, string> {
  const fb = fallback ?? {};
  const accent = base.accent ?? fb.accent ?? '#0d9488';
  const danger = base.danger ?? fb.danger ?? '#dc2626';
  const warning = base.warning ?? fb.warning ?? '#f59e0b';
  const success = base.success ?? fb.success ?? '#16a34a';
  const info = base.info ?? fb.info ?? '#2563eb';
  const text = base.text ?? fb.text ?? (mode === 'dark' ? '#f1f5f9' : '#1d2930');
  const surface = base.surface ?? fb.surface ?? (mode === 'dark' ? '#1e293b' : '#ffffff');
  const canvas = base.canvas ?? fb.canvas ?? (mode === 'dark' ? '#0f172a' : '#eef3f4');
  const isDark = mode === 'dark';
  const mix = (c: string, pct: number, with_ = isDark ? 'black' : 'white') =>
    `color-mix(in srgb, ${c} ${100 - pct}%, ${with_})`;
  const alpha = (c: string, a: number) =>
    `color-mix(in srgb, ${c} ${Math.round(a * 100)}%, transparent)`;

  const out: Record<PaletteToken, string> = {
    canvas,
    surface,
    'surface-2': base['surface-2'] ?? fb['surface-2'] ?? mix(surface, 5),
    'surface-3': base['surface-3'] ?? fb['surface-3'] ?? mix(surface, 12),
    'surface-overlay': base['surface-overlay'] ?? alpha(surface, 0.92),
    'surface-elevated': base['surface-elevated'] ?? mix(surface, 3, 'white'),
    'surface-sunken': base['surface-sunken'] ?? mix(surface, 6, 'black'),
    'surface-disabled': base['surface-disabled'] ?? alpha(surface, 0.6),
    text,
    'text-2': base['text-2'] ?? mix(text, 18),
    'text-3': base['text-3'] ?? mix(text, 32),
    'text-muted': base['text-muted'] ?? mix(text, 50),
    'text-inverse': base['text-inverse'] ?? (isDark ? '#0f172a' : '#ffffff'),
    'text-link': base['text-link'] ?? accent,
    border: base.border ?? (isDark ? '#475569' : '#d9e1e5'),
    'border-2': base['border-2'] ?? (isDark ? '#64748b' : '#c4cdd3'),
    'border-strong': base['border-strong'] ?? mix(text, 70),
    'border-subtle': base['border-subtle'] ?? alpha(text, 0.08),
    divider: base.divider ?? alpha(text, 0.12),
    accent,
    'accent-light': base['accent-light'] ?? mix(accent, 60, 'white'),
    'accent-dark': base['accent-dark'] ?? mix(accent, 25, 'black'),
    'accent-hover': base['accent-hover'] ?? mix(accent, 12, isDark ? 'white' : 'black'),
    'accent-active': base['accent-active'] ?? mix(accent, 24, 'black'),
    'accent-soft': base['accent-soft'] ?? alpha(accent, 0.16),
    'accent-soft-2': base['accent-soft-2'] ?? alpha(accent, 0.08),
    'accent-contrast': base['accent-contrast'] ?? '#ffffff',
    danger,
    warning,
    success,
    info,
    'danger-soft': base['danger-soft'] ?? alpha(danger, 0.16),
    'warning-soft': base['warning-soft'] ?? alpha(warning, 0.16),
    'success-soft': base['success-soft'] ?? alpha(success, 0.16),
    'info-soft': base['info-soft'] ?? alpha(info, 0.16),
    'danger-border': base['danger-border'] ?? alpha(danger, 0.4),
    'warning-border': base['warning-border'] ?? alpha(warning, 0.4),
    'success-border': base['success-border'] ?? alpha(success, 0.4),
    'info-border': base['info-border'] ?? alpha(info, 0.4),
    'focus-ring': base['focus-ring'] ?? alpha(accent, 0.5),
    'focus-ring-soft': base['focus-ring-soft'] ?? alpha(accent, 0.25),
    'selection-bg': base['selection-bg'] ?? alpha(accent, 0.3),
    'selection-fg': base['selection-fg'] ?? text,
    highlight: base.highlight ?? alpha(warning, 0.35),
    'minimap-bg': base['minimap-bg'] ?? (isDark ? 'rgba(15,23,42,0.9)' : 'rgba(255,255,255,0.9)'),
    'minimap-fg': base['minimap-fg'] ?? alpha(text, 0.6),
    'minimap-mask': base['minimap-mask'] ?? alpha(accent, 0.2),
    'edge-default': base['edge-default'] ?? mix(text, 50),
    'edge-hover': base['edge-hover'] ?? accent,
    'edge-selected': base['edge-selected'] ?? accent,
    'grid-line': base['grid-line'] ?? alpha(text, 0.06),
    'grid-dot': base['grid-dot'] ?? alpha(text, 0.18),
    'code-bg': base['code-bg'] ?? (isDark ? '#0a0e1a' : '#f8fafc'),
    'code-fg': base['code-fg'] ?? text,
    'code-comment': base['code-comment'] ?? mix(text, 50),
    'code-keyword': base['code-keyword'] ?? accent,
    backdrop: base.backdrop ?? alpha(isDark ? '#000000' : '#000000', 0.55),
    scrim: base.scrim ?? alpha(isDark ? '#000000' : '#0f172a', 0.35),
    'tooltip-bg': base['tooltip-bg'] ?? (isDark ? '#0a0e1a' : '#1d2930'),
    'shadow-color': base['shadow-color'] ?? alpha('#000000', isDark ? 0.4 : 0.12),
    'shadow-color-strong': base['shadow-color-strong'] ?? alpha('#000000', isDark ? 0.6 : 0.22),
    'ring-color': base['ring-color'] ?? alpha(accent, 0.4),
    'badge-bg': base['badge-bg'] ?? alpha(accent, 0.18),
    'badge-fg': base['badge-fg'] ?? accent,
    'kbd-bg': base['kbd-bg'] ?? mix(surface, 8),
    'kbd-fg': base['kbd-fg'] ?? text,
  };
  return out;
}

export function completePalette(palette: ThemePalette): { id: string; name: string; description: string; descriptionKey?: string; preview: string[]; light: Record<PaletteToken, string>; dark: Record<PaletteToken, string>; canvasPattern: CanvasPattern } {
  const base = BUILT_IN_PALETTES[0];
  return {
    id: palette.id,
    name: palette.name,
    description: palette.description,
    descriptionKey: palette.descriptionKey,
    preview: palette.preview,
    light: deriveTokens(palette.light, 'light', base?.light),
    dark: deriveTokens(palette.dark, 'dark', base?.dark),
    canvasPattern: palette.canvasPattern ?? 'none',
  };
}

export function getResolvedPaletteMode(mode?: PaletteMode): PaletteMode {
  if (mode) return mode;
  if (typeof document === 'undefined') return 'light';
  const root = document.documentElement;
  return root.dataset.theme === 'dark' || root.classList.contains('dark') ? 'dark' : 'light';
}

export function applyPalette(id = activePaletteId, mode?: PaletteMode, target?: HTMLElement): ThemePalette | null {
  if (typeof document === 'undefined') return null;
  const raw = getPaletteDefinition(id) ?? BUILT_IN_PALETTES[0];
  const palette = completePalette(raw);
  const resolvedMode = getResolvedPaletteMode(mode);
  const root = target ?? document.documentElement;
  const tokens = palette[resolvedMode];

  Object.entries(tokens).forEach(([token, value]) => {
    if (value) root.style.setProperty(`--${token}`, value, 'important');
  });

  root.dataset.palette = palette.id;
  root.dataset.canvasPattern = palette.canvasPattern || 'none';
  return raw;
}

export function clearPaletteOverrides(target?: HTMLElement): void {
  if (typeof document === 'undefined') return;
  const root = target ?? document.documentElement;
  ALL_PALETTE_TOKENS.forEach(token => root.style.removeProperty(`--${token}`));
  delete root.dataset.palette;
}
