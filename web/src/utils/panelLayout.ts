export interface DockedPanelRequest {
  id: string;
  width: number;
  side: 'left' | 'right';
}

export interface DockedPanelPlacement extends DockedPanelRequest {
  offset: number;
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
