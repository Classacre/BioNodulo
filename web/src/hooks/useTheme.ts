import { useEffect } from 'react';
import { useSettings } from './settings';
import { getActivePaletteId, paletteThemeMode } from '../state/palettes';

export function useTheme() {
  const { get, settings } = useSettings();

  useEffect(() => {
    const theme = get('bionodulo.theme') as string;
    const paletteMode = paletteThemeMode(getActivePaletteId());
    const root = document.documentElement;
    const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
    const useDark = paletteMode === 'dark' || (!paletteMode && (theme === 'dark' || (theme === 'system' && prefersDark)));
    root.classList.toggle('dark', useDark);
    document.body.classList.toggle('dark', useDark);
    root.dataset.theme = useDark ? 'dark' : 'light';
    root.style.colorScheme = useDark ? 'dark' : 'light';
  }, [get, settings]);

  // Also listen for system preference changes
  useEffect(() => {
    if (paletteThemeMode(getActivePaletteId())) return;
    const theme = get('bionodulo.theme') as string;
    if (theme !== 'system') return;
    const mq = window.matchMedia('(prefers-color-scheme: dark)');
    const handler = (e: MediaQueryListEvent) => {
      const root = document.documentElement;
      if (e.matches) root.classList.add('dark');
      else root.classList.remove('dark');
    };
    mq.addEventListener('change', handler);
    return () => mq.removeEventListener('change', handler);
  }, [get, settings]);

  const paletteMode = paletteThemeMode(getActivePaletteId());
  const theme = get('bionodulo.theme') as string;
  const isDark = paletteMode === 'dark'
    || (!paletteMode && (
      theme === 'dark'
      || (theme === 'system' && window.matchMedia('(prefers-color-scheme: dark)').matches)
    ));

  return { isDark };
}
