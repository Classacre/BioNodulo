import { useCallback, useEffect, useMemo } from 'react';
import { useSyncExternalStore } from 'react';
import {
  applyPalette,
  clearPaletteOverrides,
  getActivePaletteId,
  getBuiltInPalettes,
  getPaletteRevision,
  getPaletteDefinition,
  setActivePaletteId,
  subscribePalettes,
  systemDefaultPaletteId,
  type PaletteMode,
} from '../state/palettes';

export interface UsePaletteThemeOptions {
  paletteId?: string;
  mode?: PaletteMode;
}

export function usePaletteTheme(options: UsePaletteThemeOptions = {}) {
  const activePaletteId = useSyncExternalStore(
    subscribePalettes,
    getActivePaletteId,
    getActivePaletteId,
  );
  const paletteRevision = useSyncExternalStore(
    subscribePalettes,
    getPaletteRevision,
    getPaletteRevision,
  );
  const paletteId = options.paletteId ?? activePaletteId;
  const palettes = useMemo(() => getBuiltInPalettes(), [paletteRevision]);
  const activePalette = getPaletteDefinition(paletteId) ?? palettes[0];

  // A palette is fully self-describing: applying it sets the CSS variables AND
  // the light/dark class from the palette's own mode. Nothing else manages the
  // theme, so a single apply on change is enough — no class observer needed.
  useEffect(() => {
    applyPalette(paletteId, options.mode);
  }, [options.mode, paletteId]);

  const setPalette = useCallback((id: string) => {
    setActivePaletteId(id);
    applyPalette(id);
  }, []);

  const resetPalette = useCallback(() => {
    const id = systemDefaultPaletteId();
    setActivePaletteId(id);
    applyPalette(id);
  }, []);

  return {
    paletteId,
    activePalette,
    palettes,
    setPalette,
    resetPalette,
    applyPalette: (id?: string, mode?: PaletteMode) => applyPalette(id ?? paletteId, mode ?? options.mode),
    clearPaletteOverrides,
  };
}
