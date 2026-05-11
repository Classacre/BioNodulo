import { useEffect } from 'react';
import { useSettings } from './useSettings';

export function useTheme() {
  const { getBool, get, settings } = useSettings();

  useEffect(() => {
    const theme = get('bionodulo.theme') as string;
    const root = document.documentElement;
    if (theme === 'dark') {
      root.classList.add('dark');
    } else if (theme === 'light') {
      root.classList.remove('dark');
    } else {
      // system
      if (window.matchMedia('(prefers-color-scheme: dark)').matches) {
        root.classList.add('dark');
      } else {
        root.classList.remove('dark');
      }
    }
  }, [get, settings]);

  // Also listen for system preference changes
  useEffect(() => {
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

  const isDark = getBool('bionodulo.theme')
    ? get('bionodulo.theme') === 'dark'
    : window.matchMedia('(prefers-color-scheme: dark)').matches;

  return { isDark };
}
