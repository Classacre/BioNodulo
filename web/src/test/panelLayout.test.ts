import { describe, expect, it } from 'vitest';
import { fitDockedPanels } from '../utils/panelLayout';

const requests = [
  { id: 'workspace', width: 340, side: 'left' as const },
  { id: 'nodes', width: 340, side: 'left' as const },
  { id: 'environment', width: 340, side: 'right' as const },
];

describe('dock panel fitting', () => {
  it('keeps all panels side by side when the viewport has room', () => {
    expect(fitDockedPanels(requests, 1600)).toEqual([
      { ...requests[0], offset: 0 }, { ...requests[1], offset: 372 }, { ...requests[2], offset: 0 },
    ]);
  });
  it('collapses older panels while keeping the latest panels inside a laptop canvas', () => {
    const result = fitDockedPanels(requests, 968);
    expect(result.map(panel => panel.id)).toEqual(['nodes', 'environment']);
    expect(result.reduce((sum, panel) => sum + panel.width, 0)).toBeLessThanOrEqual(968 - 240);
  });
  it('reserves the drawer area before positioning a right dock', () => {
    const result = fitDockedPanels(requests, 1384, 760);
    expect(result).toEqual([{ ...requests[2], offset: 760 }]);
  });
  it.each([334, 200])('keeps the latest panel and its controls inside a narrow %spx canvas', width => {
    const result = fitDockedPanels(requests, width);
    expect(result).toHaveLength(1);
    expect(result[0].id).toBe('environment');
    expect(result[0].width + result[0].offset).toBeLessThanOrEqual(width);
  });
  it('collapses docks while a drawer fills the canvas', () => {
    expect(fitDockedPanels(requests, 334, 334)).toEqual([]);
  });
});
