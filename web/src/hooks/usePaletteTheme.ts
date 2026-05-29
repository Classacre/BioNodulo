import { useCallback, useEffect, useMemo, useSyncExternalStore } from 'react';
import {
  applyPalette,
  clearPaletteOverrides,
  getActivePaletteId,
  getBuiltInPalettes,
  getPaletteRevision,
  getPaletteDefinition,
  setActivePaletteId,
  subscribePalettes,
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

  useEffect(() => {
    const root = document.documentElement;
    const reapply = () => applyPalette(paletteId, options.mode);
    reapply();

    const observer = new MutationObserver(reapply);
    observer.observe(root, { attributes: true, attributeFilter: ['class', 'data-theme'] });
    return () => observer.disconnect();
  }, [options.mode, paletteId]);

  const setPalette = useCallback((id: string) => {
    setActivePaletteId(id);
    applyPalette(id, options.mode);
  }, [options.mode]);

  const resetPalette = useCallback(() => {
    setActivePaletteId('bionodulo');
    applyPalette('bionodulo', options.mode);
  }, [options.mode]);

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
