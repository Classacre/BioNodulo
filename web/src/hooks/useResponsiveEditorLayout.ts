import { useLayoutEffect, useRef, useState } from 'react';

interface DrawerState {
  ai: boolean;
  runs: boolean;
  comments: boolean;
}

export function useResponsiveEditorLayout(
  drawers: DrawerState,
  close: { ai: (open: boolean) => void; runs: (open: boolean) => void; comments: (open: boolean) => void },
) {
  const { ai, runs, comments } = drawers;
  const closeRef = useRef(close);
  closeRef.current = close;
  const [bounds, setBounds] = useState({ width: Math.max(0, window.innerWidth - 56), height: window.innerHeight - 76, top: 76 });
  const [aiWidth, setAiWidth] = useState(380);
  const previous = useRef<DrawerState>({ ai: false, runs: false, comments: false });
  const priority = useRef<(keyof DrawerState)[]>([]);

  useLayoutEffect(() => {
    const canvas = document.querySelector('.main-canvas');
    const ai = document.querySelector('.ai-drawer');
    if (!canvas) return;
    const measure = () => {
      const rect = canvas.getBoundingClientRect();
      setBounds(value => value.width === rect.width && value.height === rect.height && value.top === rect.top
        ? value : { width: rect.width, height: rect.height, top: rect.top });
      if (ai) setAiWidth(ai.getBoundingClientRect().width);
    };
    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(canvas);
    if (ai) observer.observe(ai);
    window.addEventListener('resize', measure);
    return () => { observer.disconnect(); window.removeEventListener('resize', measure); };
  }, [ai]);

  useLayoutEffect(() => {
    const current = { ai, runs, comments };
    for (const key of ['ai', 'runs', 'comments'] as const) {
      if (current[key] && !previous.current[key]) priority.current = [...priority.current.filter(item => item !== key), key];
    }
    previous.current = current;
    priority.current = priority.current.filter(key => current[key]);
    const widths = { ai: Math.min(aiWidth, bounds.width), runs: Math.min(380, bounds.width), comments: Math.min(320, bounds.width) };
    let used = 0;
    for (const key of [...priority.current].reverse()) {
      if (used && used + widths[key] + 240 > bounds.width) closeRef.current[key](false);
      else used += widths[key];
    }
  }, [ai, runs, comments, bounds.width, aiWidth]);

  return { ...bounds, aiWidth };
}
