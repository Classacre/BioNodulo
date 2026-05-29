// Panel layout state: open tabs, widths, floating positions, right-dock flags.
// Extracted from App.tsx to isolate the panel-management surface.
//
// Returns state + setters for the rail-panel system. Persists widths, floats,
// and right-dock flags to localStorage so the layout survives page refresh.

import { useState, useCallback } from 'react';
import type { RailTab } from '../components/layout/LeftRail';

type OpenPanelTab = Exclude<RailTab, null | 'console'>;
type FloatingPanelLayout = Record<string, { x: number; y: number }>;

const PANEL_WIDTHS_KEY = 'bionodulo.panel.widths';
const PANEL_FLOATS_KEY = 'bionodulo.panel.floats';
const PANEL_RIGHT_DOCKED_KEY = 'bionodulo.panel.rightDocked';

function loadPanelWidths(): Record<string, number> {
  try {
    const raw = localStorage.getItem(PANEL_WIDTHS_KEY);
    return raw ? (JSON.parse(raw) as Record<string, number>) : {};
  } catch {
    return {};
  }
}

function loadFloatingPanels(): FloatingPanelLayout {
  try {
    const raw = localStorage.getItem(PANEL_FLOATS_KEY);
    return raw ? (JSON.parse(raw) as FloatingPanelLayout) : {};
  } catch {
    return {};
  }
}

function loadRightDockedPanels(): Record<string, true> {
  try {
    const raw = localStorage.getItem(PANEL_RIGHT_DOCKED_KEY);
    const parsed = raw ? (JSON.parse(raw) as unknown) : null;
    if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) return {};
    const result: Record<string, true> = {};
    for (const key of Object.keys(parsed as Record<string, unknown>)) {
      if ((parsed as Record<string, unknown>)[key]) result[key] = true;
    }
    return result;
  } catch {
    return {};
  }
}

function clampPanelWidth(width: number): number {
  return Math.max(280, Math.min(620, Math.round(width)));
}

export interface UsePanelLayoutResult {
  openPanelTabs: OpenPanelTab[];
  setOpenPanelTabs: React.Dispatch<React.SetStateAction<OpenPanelTab[]>>;
  panelWidths: Record<string, number>;
  setPanelWidth: (tab: OpenPanelTab, width: number) => void;
  floatingPanels: FloatingPanelLayout;
  setFloatingPanel: (tab: OpenPanelTab, layout: { x: number; y: number } | null) => void;
  toggleFloatingPanel: (tab: OpenPanelTab, index: number) => void;
  rightDockedPanels: Record<string, true>;
  toggleRightDocked: (tab: OpenPanelTab) => void;
}

export function usePanelLayout(): UsePanelLayoutResult {
  const [openPanelTabs, setOpenPanelTabs] = useState<OpenPanelTab[]>([]);
  const [panelWidths, setPanelWidths] = useState<Record<string, number>>(() => loadPanelWidths());
  const [floatingPanels, setFloatingPanels] = useState<FloatingPanelLayout>(() => loadFloatingPanels());
  const [rightDockedPanels, setRightDockedPanels] = useState<Record<string, true>>(() =>
    loadRightDockedPanels(),
  );

  const toggleRightDocked = useCallback((tab: OpenPanelTab) => {
    setRightDockedPanels(prev => {
      const next = { ...prev };
      if (next[tab]) {
        delete next[tab];
      } else {
        next[tab] = true;
      }
      try {
        localStorage.setItem(PANEL_RIGHT_DOCKED_KEY, JSON.stringify(next));
      } catch {
        /* quota */
      }
      return next;
    });
  }, []);

  const setPanelWidth = useCallback((tab: OpenPanelTab, width: number) => {
    setPanelWidths(prev => {
      const next = { ...prev, [tab]: clampPanelWidth(width) };
      try {
        localStorage.setItem(PANEL_WIDTHS_KEY, JSON.stringify(next));
      } catch {
        /* quota */
      }
      return next;
    });
  }, []);

  const setFloatingPanel = useCallback((tab: OpenPanelTab, layout: { x: number; y: number } | null) => {
    setFloatingPanels(prev => {
      const next = { ...prev };
      if (layout) {
        next[tab] = {
          x: Math.max(12, Math.min(window.innerWidth - 320, Math.round(layout.x))),
          y: Math.max(8, Math.min(window.innerHeight - 180, Math.round(layout.y))),
        };
      } else {
        delete next[tab];
      }
      try {
        localStorage.setItem(PANEL_FLOATS_KEY, JSON.stringify(next));
      } catch {
        /* quota */
      }
      return next;
    });
  }, []);

  const toggleFloatingPanel = useCallback(
    (tab: OpenPanelTab, index: number) => {
      if (floatingPanels[tab]) {
        setFloatingPanel(tab, null);
        return;
      }
      setFloatingPanel(tab, { x: 80 + index * 28, y: 72 + index * 24 });
    },
    [floatingPanels, setFloatingPanel],
  );

  return {
    openPanelTabs,
    setOpenPanelTabs,
    panelWidths,
    setPanelWidth,
    floatingPanels,
    setFloatingPanel,
    toggleFloatingPanel,
    rightDockedPanels,
    toggleRightDocked,
  };
}
