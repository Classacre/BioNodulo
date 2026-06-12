import { useCallback, useEffect, useMemo, useSyncExternalStore } from 'react';
import {
  applyPalette,
  clearPaletteOverrides,
  getActivePaletteId,
  getBuiltInPalettes,
  getPaletteRevision,
  getPaletteDefinition,
  paletteThemeMode,
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
    const forcedMode = paletteThemeMode(id);
    if (forcedMode) {
      document.documentElement.classList.toggle('dark', forcedMode === 'dark');
      document.body.classList.toggle('dark', forcedMode === 'dark');
      document.documentElement.dataset.theme = forcedMode;
      document.documentElement.style.colorScheme = forcedMode;
      try { localStorage.setItem('bionodulo.theme', forcedMode); } catch { /* ignore */ }
    }
    setActivePaletteId(id);
    applyPalette(id, forcedMode ?? options.mode);
  }, [options.mode]);

  const resetPalette = useCallback(() => {
    setActivePaletteId('light');
    applyPalette('light', 'light');
    try { localStorage.setItem('bionodulo.theme', 'light'); } catch { /* ignore */ }
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
