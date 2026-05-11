import { useState, useCallback, useRef } from 'react';
import type { Workflow } from '../types';

const MAX_HISTORY = 50;

export function useHistory(workflow: Workflow, onChange: (w: Workflow) => void) {
  const [history, setHistory] = useState<Workflow[]>([workflow]);
  const [index, setIndex] = useState(0);
  const skip = useRef(false);

  const push = useCallback((w: Workflow) => {
    if (skip.current) { skip.current = false; return; }
    setHistory(prev => {
      const next = [...prev.slice(0, index + 1), JSON.parse(JSON.stringify(w))];
      if (next.length > MAX_HISTORY) next.shift();
      return next;
    });
    setIndex(prev => Math.min(prev + 1, MAX_HISTORY - 1));
  }, [index]);

  const undo = useCallback(() => {
    if (index > 0) {
      const newIndex = index - 1;
      setIndex(newIndex);
      skip.current = true;
      onChange(history[newIndex]);
    }
  }, [index, history, onChange]);

  const redo = useCallback(() => {
    if (index < history.length - 1) {
      const newIndex = index + 1;
      setIndex(newIndex);
      skip.current = true;
      onChange(history[newIndex]);
    }
  }, [index, history, onChange]);

  const canUndo = index > 0;
  const canRedo = index < history.length - 1;

  return { push, undo, redo, canUndo, canRedo };
}
