export type PaletteMode = 'light' | 'dark';

export type PaletteToken =
  | 'canvas'
  | 'surface'
  | 'surface-2'
  | 'surface-3'
  | 'text'
  | 'text-2'
  | 'muted'
  | 'border'
  | 'border-2'
  | 'accent'
  | 'accent-light'
  | 'accent-dark'
  | 'danger'
  | 'warning'
  | 'success'
  | 'minimap-bg';

export type PaletteTokens = Partial<Record<PaletteToken, string>>;

// Optional per-palette canvas decoration. Renders as a CSS background-image
// behind the canvas grid so each palette can have a subtly distinct feel
// without changing the actual node rendering.
export type CanvasPattern = 'none' | 'dots' | 'grid' | 'mesh';

export interface ThemePalette {
  id: string;
  name: string;
  description: string;
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
    canvasPattern: 'dots',
    preview: ['#0d9488', '#eef3f4', '#1d2930'],
    light: {
      canvas: '#eef3f4',
      surface: '#ffffff',
      'surface-2': '#f3f6f7',
      'surface-3': '#e8edef',
      text: '#1d2930',
      'text-2': '#334155',
      muted: '#64748b',
      border: '#d9e1e5',
      'border-2': '#c4cdd3',
      accent: '#0d9488',
      'accent-light': '#ccfbf1',
      'accent-dark': '#0f766e',
      danger: '#dc2626',
      warning: '#f59e0b',
      success: '#16a34a',
      'minimap-bg': 'rgba(255,255,255,0.9)',
    },
    dark: {
      canvas: '#0f172a',
      surface: '#1e293b',
      'surface-2': '#334155',
      'surface-3': '#475569',
      text: '#f1f5f9',
      'text-2': '#cbd5e1',
      muted: '#94a3b8',
      border: '#475569',
      'border-2': '#64748b',
      accent: '#2dd4bf',
      'accent-light': '#134e4a',
      'accent-dark': '#5eead4',
      danger: '#f87171',
      warning: '#fbbf24',
      success: '#4ade80',
      'minimap-bg': 'rgba(30,41,59,0.9)',
    },
  },
  {
    id: 'clinical',
    name: 'Clinical',
    description: 'Clean blue-green palette with high scan contrast.',
    canvasPattern: 'grid',
    preview: ['#2563eb', '#f7fafc', '#0f172a'],
    light: {
      canvas: '#f7fafc',
      surface: '#ffffff',
      'surface-2': '#eef6f8',
      'surface-3': '#dcebed',
      text: '#0f172a',
      'text-2': '#1f3a4a',
      muted: '#60717f',
      border: '#d3e0e5',
      'border-2': '#b7c8d1',
      accent: '#2563eb',
      'accent-light': '#dbeafe',
      'accent-dark': '#1d4ed8',
      danger: '#be123c',
      warning: '#b45309',
      success: '#047857',
      'minimap-bg': 'rgba(255,255,255,0.92)',
    },
    dark: {
      canvas: '#111827',
      surface: '#18212f',
      'surface-2': '#243244',
      'surface-3': '#33465c',
      text: '#f8fafc',
      'text-2': '#d8e2ef',
      muted: '#9caebf',
      border: '#35465b',
      'border-2': '#51647a',
      accent: '#60a5fa',
      'accent-light': '#17324f',
      'accent-dark': '#bfdbfe',
      danger: '#fb7185',
      warning: '#f59e0b',
      success: '#34d399',
      'minimap-bg': 'rgba(24,33,47,0.9)',
    },
  },
  {
    id: 'field',
    name: 'Field Station',
    description: 'Muted green and graphite palette for long sessions.',
    canvasPattern: 'mesh',
    preview: ['#15803d', '#f1f5f2', '#18231d'],
    light: {
      canvas: '#f1f5f2',
      surface: '#ffffff',
      'surface-2': '#edf3ef',
      'surface-3': '#dfe8e2',
      text: '#18231d',
      'text-2': '#2e4235',
      muted: '#647469',
      border: '#d5dfd8',
      'border-2': '#b8c7bd',
      accent: '#15803d',
      'accent-light': '#dcfce7',
      'accent-dark': '#166534',
      danger: '#b91c1c',
      warning: '#ca8a04',
      success: '#16a34a',
      'minimap-bg': 'rgba(255,255,255,0.9)',
    },
    dark: {
      canvas: '#111711',
      surface: '#1a241d',
      'surface-2': '#253329',
      'surface-3': '#33453a',
      text: '#eef7ef',
      'text-2': '#d1e4d4',
      muted: '#9ab0a0',
      border: '#38493d',
      'border-2': '#536758',
      accent: '#86efac',
      'accent-light': '#17452a',
      'accent-dark': '#bbf7d0',
      danger: '#f87171',
      warning: '#facc15',
      success: '#4ade80',
      'minimap-bg': 'rgba(26,36,29,0.9)',
    },
  },
  {
    id: 'contrast',
    name: 'High Contrast',
    description: 'Sharp contrast palette for dense review work.',
    canvasPattern: 'none',
    preview: ['#f97316', '#ffffff', '#0b0f19'],
    light: {
      canvas: '#f4f6f8',
      surface: '#ffffff',
      'surface-2': '#edf0f2',
      'surface-3': '#dde3e8',
      text: '#0b0f19',
      'text-2': '#1f2937',
      muted: '#4b5563',
      border: '#cdd5df',
      'border-2': '#9aa8b6',
      accent: '#f97316',
      'accent-light': '#ffedd5',
      'accent-dark': '#c2410c',
      danger: '#991b1b',
      warning: '#a16207',
      success: '#166534',
      'minimap-bg': 'rgba(255,255,255,0.94)',
    },
    dark: {
      canvas: '#06080d',
      surface: '#10151f',
      'surface-2': '#1c2533',
      'surface-3': '#2b3748',
      text: '#ffffff',
      'text-2': '#e5e7eb',
      muted: '#b6c2d1',
      border: '#465568',
      'border-2': '#718096',
      accent: '#fb923c',
      'accent-light': '#431c08',
      'accent-dark': '#fed7aa',
      danger: '#fca5a5',
      warning: '#fde68a',
      success: '#86efac',
      'minimap-bg': 'rgba(16,21,31,0.94)',
    },
  },
];

let activePaletteId = loadActivePaletteId();
let customPalettes = loadCustomPalettes();

function loadActivePaletteId() {
  if (typeof localStorage === 'undefined') return BUILT_IN_PALETTES[0].id;
  try {
    return localStorage.getItem(STORAGE_KEY) || BUILT_IN_PALETTES[0].id;
  } catch {
    return BUILT_IN_PALETTES[0].id;
  }
}

function loadCustomPalettes(): ThemePalette[] {
  if (typeof localStorage === 'undefined') return [];
  try {
    const raw = localStorage.getItem(CUSTOM_STORAGE_KEY);
    const parsed = raw ? JSON.parse(raw) : [];
    return Array.isArray(parsed) ? parsed.filter(isThemePalette) : [];
  } catch {
    return [];
  }
}

function saveCustomPalettes() {
  try {
    localStorage.setItem(CUSTOM_STORAGE_KEY, JSON.stringify(customPalettes));
  } catch {
    /* ignore */
  }
}

function isThemePalette(input: unknown): input is ThemePalette {
  const palette = input as ThemePalette;
  return Boolean(
    palette
    && typeof palette.id === 'string'
    && typeof palette.name === 'string'
    && typeof palette.description === 'string'
    && Array.isArray(palette.preview)
    && palette.light && typeof palette.light === 'object'
    && palette.dark && typeof palette.dark === 'object',
  );
}

function emit() {
  paletteRevision += 1;
  listeners.forEach(listener => listener());
}

export function subscribePalettes(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function getActivePaletteId(): string {
  return activePaletteId;
}

export function getPaletteRevision(): number {
  return paletteRevision;
}

export function setActivePaletteId(id: string): void {
  const palette = getPaletteDefinition(id);
  if (!palette || activePaletteId === palette.id) return;
  activePaletteId = palette.id;
  try {
    localStorage.setItem(STORAGE_KEY, activePaletteId);
  } catch {
    /* ignore */
  }
  emit();
}

export function getBuiltInPalettes(): ThemePalette[] {
  return [...BUILT_IN_PALETTES, ...customPalettes];
}

export function getPaletteDefinition(id: string): ThemePalette | undefined {
  return getBuiltInPalettes().find(palette => palette.id === id);
}

export function addCustomPalette(palette: ThemePalette): void {
  const normalized: ThemePalette = {
    ...palette,
    id: palette.id.trim() || `custom-${Date.now()}`,
    preview: palette.preview.length ? palette.preview.slice(0, 4) : ['#0d9488', '#ffffff', '#0f172a'],
  };
  customPalettes = [
    ...customPalettes.filter(item => item.id !== normalized.id),
    normalized,
  ];
  saveCustomPalettes();
  emit();
}

/**
 * Merge a custom palette with the first built-in palette's tokens so any
 * missing key falls back to a known-good default. Users authoring custom
 * palettes can ship just the tokens they want to override; everything else
 * stays consistent. Returns a fresh palette with both light and dark fully
 * populated.
 */
export function completePalette(palette: ThemePalette): ThemePalette {
  const base = BUILT_IN_PALETTES[0];
  if (!base) return palette;
  return {
    ...palette,
    light: { ...base.light, ...(palette.light || {}) },
    dark: { ...base.dark, ...(palette.dark || {}) },
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

  // Use `important` so palette tokens override dark/light theme CSS defaults
  // (e.g. `[data-theme="dark"] :root { --accent: ... }`) which otherwise win
  // the cascade against inline styles and make palette swaps look like no-ops
  // in dark mode.
  Object.entries(tokens).forEach(([token, value]) => {
    if (value) root.style.setProperty(`--${token}`, value, 'important');
  });

  root.dataset.palette = palette.id;
  root.dataset.canvasPattern = palette.canvasPattern || 'none';
  return palette;
}

export function clearPaletteOverrides(target?: HTMLElement): void {
  if (typeof document === 'undefined') return;
  const root = target ?? document.documentElement;
  const tokens: PaletteToken[] = [
    'canvas', 'surface', 'surface-2', 'surface-3', 'text', 'text-2', 'muted',
    'border', 'border-2', 'accent', 'accent-light', 'accent-dark',
    'danger', 'warning', 'success', 'minimap-bg',
  ];
  tokens.forEach(token => root.style.removeProperty(`--${token}`));
  delete root.dataset.palette;
}
