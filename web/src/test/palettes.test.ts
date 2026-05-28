import { describe, it, expect } from 'vitest';
import {
  completePalette,
  BUILT_IN_PALETTES,
  getResolvedPaletteMode,
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
