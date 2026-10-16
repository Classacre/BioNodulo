export interface DockedPanelRequest {
  id: string;
  width: number;
  side: 'left' | 'right';
}

export interface DockedPanelPlacement extends DockedPanelRequest {
  offset: number;
}

/** Console controls need usable width; retain normal allocations while hidden. */
export function consolePanelLayout(open: boolean, focusMode: boolean, width: number, left: number, right: number) {
  const availableWidth = Math.max(0, width - left - right);
  const exclusive = open && !focusMode && availableWidth < 240;
  return { exclusive, leftInset: exclusive ? 0 : left, rightInset: exclusive ? 0 : right,
    width: exclusive ? width : availableWidth };
}

export function consoleChromeFits(canvasHeight: number, consoleHeight: number, chromeHeight: number) {
  return canvasHeight >= consoleHeight + Math.max(176, chromeHeight) + 16;
}

export function consoleHidesRailPanel(exclusive: boolean, open: boolean, focusMode: boolean, floating: boolean) {
  return exclusive || (open && !focusMode && floating);
}

/** Explicit selection reveals retained panels instead of toggling hidden intent off. */
export function activateConsolePanel(exclusive: boolean, setOpen: (value: (previous: boolean) => boolean) => void,
  closeConsole: () => void, toggle = false) {
  if (exclusive) closeConsole();
  setOpen(previous => exclusive || !toggle || !previous);
}

/** Keep recent panels usable while retaining space to work on the canvas. */
export function fitDockedPanels(
  requests: DockedPanelRequest[], canvasWidth: number, reservedRight = 0,
): DockedPanelPlacement[] {
  const available = Math.max(0, canvasWidth - reservedRight);
  if (!available) return [];
  const toolbarSpace = Math.min(32, available);
  const minimum = Math.min(280, available - toolbarSpace);
  const budget = Math.max(minimum + toolbarSpace, available - 240);
  const count = Math.min(requests.length, Math.max(1, Math.floor(budget / (minimum + toolbarSpace))));
  const visible = requests.slice(-count);
  let extra = Math.max(0, budget - (minimum + toolbarSpace) * visible.length);
  const widths = new Map<string, number>();
  // Give the most recently used panel its preferred width first.
  for (const panel of [...visible].reverse()) {
    const preferred = Number.isFinite(panel.width) ? Math.max(minimum, Math.min(620, panel.width)) : 340;
    const width = minimum + Math.min(extra, Math.max(0, preferred - minimum));
    widths.set(panel.id, width);
    extra -= width - minimum;
  }
  let left = 0;
  let right = reservedRight;
  return visible.map(panel => {
    const width = widths.get(panel.id)!;
    const offset = panel.side === 'left' ? left : right;
    if (panel.side === 'left') left += width + toolbarSpace;
    else right += width + toolbarSpace;
    return { ...panel, width, offset };
  });
}
