import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, it, expect, afterEach } from 'vitest';
import {
  ALL_PALETTE_TOKENS,
  applyPalette,
  completePalette,
  BUILT_IN_PALETTES,
  getResolvedPaletteMode,
  paletteThemeMode,
} from '../state/palettes';
import type { ThemePalette } from '../state/palettes';

describe('palettes.completePalette', () => {
  it('fills missing tokens from the base palette in both modes', () => {
    const partial: ThemePalette = {
      id: 'partial',
      name: 'Partial',
      description: 'sparse',
      preview: ['#000'],
      light: { accent: '#abc123' },
      dark: { canvas: '#0a0a0a' },
    };
    const completed = completePalette(partial);
    expect(completed.light.accent).toBe('#abc123');
    expect(completed.dark.canvas).toBe('#0a0a0a');
    // Tokens NOT specified should fall back to the first built-in
    const base = BUILT_IN_PALETTES[0]!;
    expect(completed.light.canvas).toBe(base.light.canvas);
    expect(completed.dark.accent).toBe(base.dark.accent);
  });

  it('returns the input unchanged when there is no base palette', () => {
    const palette: ThemePalette = {
      id: 'x', name: 'X', description: '', preview: [], light: {}, dark: {},
    };
    const completed = completePalette(palette);
    expect(completed.id).toBe('x');
  });
});

describe('palettes.getResolvedPaletteMode', () => {
  it('returns the explicit mode when provided', () => {
    expect(getResolvedPaletteMode('dark')).toBe('dark');
    expect(getResolvedPaletteMode('light')).toBe('light');
  });

  it('falls back to light when document.documentElement has no dark marker', () => {
    document.documentElement.classList.remove('dark');
    document.documentElement.removeAttribute('data-theme');
    expect(getResolvedPaletteMode()).toBe('light');
  });

  it('reads dark from data-theme', () => {
    document.documentElement.setAttribute('data-theme', 'dark');
    expect(getResolvedPaletteMode()).toBe('dark');
    document.documentElement.removeAttribute('data-theme');
  });
});

describe('palette theme modes', () => {
  it('exposes light and dark as selectable palettes with explicit modes', () => {
    expect(BUILT_IN_PALETTES.map(palette => palette.id)).toEqual(expect.arrayContaining(['light', 'dark']));
    expect(paletteThemeMode('light')).toBe('light');
    expect(paletteThemeMode('dark')).toBe('dark');
    // Every palette is now self-describing — light/dark are not special. A
    // themed palette reports its own mode rather than `null`.
    expect(paletteThemeMode('bionodulo')).toBe('light');
    for (const palette of BUILT_IN_PALETTES) {
      expect(palette.mode === 'light' || palette.mode === 'dark', `${palette.id} mode`).toBe(true);
    }
  });
});

describe('palettes.applyPalette', () => {
  afterEach(() => {
    document.documentElement.className = '';
    document.documentElement.removeAttribute('data-theme');
    document.documentElement.removeAttribute('data-palette');
  });

  it("drives the .dark class and canvas token from each palette's own mode", () => {
    const root = document.documentElement;

    applyPalette('dark');
    expect(root.classList.contains('dark')).toBe(true);
    expect(root.dataset.theme).toBe('dark');
    expect(root.dataset.palette).toBe('dark');
    const darkCanvas = root.style.getPropertyValue('--canvas');

    // Switching from dark to a themed (light-mode) palette must fully switch:
    // the .dark class clears and the tokens become the themed palette's own —
    // this reproduces the bug where dark -> other palette did not change.
    applyPalette('clinical');
    expect(root.dataset.palette).toBe('clinical');
    expect(root.classList.contains('dark')).toBe(false);
    expect(root.dataset.theme).toBe('light');
    expect(root.style.getPropertyValue('--canvas')).not.toBe(darkCanvas);

    // And back to a dark palette re-applies the dark class.
    applyPalette('dark');
    expect(root.classList.contains('dark')).toBe(true);
  });
});

describe('design token documentation', () => {
  it('documents every CSS token and built-in canvas pattern', () => {
    const docs = readFileSync(resolve(process.cwd(), '..', 'docs/DESIGN_TOKENS.md'), 'utf8');

    for (const token of ALL_PALETTE_TOKENS) {
      expect(docs, `missing --${token}`).toContain(`--${token}`);
    }

    for (const palette of BUILT_IN_PALETTES) {
      const expectedRow = `| ${palette.name} (\`${palette.id}\`) | \`${palette.canvasPattern ?? 'none'}\` |`;
      expect(docs, `missing pattern row for ${palette.id}`).toContain(expectedRow);
    }
  });
});
