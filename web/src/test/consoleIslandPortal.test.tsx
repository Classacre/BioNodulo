import { act, fireEvent, render, screen } from '@testing-library/react';
import { Provider } from 'jotai';
import { useState } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import DynamicIsland, { EMPTY_DOI_TELEMETRY, type DoiTelemetry } from '../components/canvas/DynamicIsland';
import BottomConsole from '../components/layout/BottomConsole';
import { dismissAllNotifications, notify } from '../state/notifications';
import type { Workflow } from '../types';

vi.mock('../api/client', () => ({ apiGet: vi.fn(), apiGetText: vi.fn() }));
const storage = new Map<string, string>();
const storageStub: Storage = {
  get length() { return storage.size; },
  clear: () => storage.clear(), getItem: key => storage.get(key) ?? null,
  setItem: (key, value) => { storage.set(key, String(value)); },
  removeItem: key => { storage.delete(key); }, key: index => [...storage.keys()][index] ?? null,
};

const workflow: Workflow = { id: 'synthetic', name: 'Portal audit', app: 'bionodulo', version: '2.0',
  nodes: [{ id: 'source', type: 'string_format', position: [0, 0], params: { template: 'A' } }],
  edges: [], groups: [], outputs: {} };

function Harness({ open, doi = EMPTY_DOI_TELEMETRY, targetKey = 0, hidden = false }: {
  open: boolean; doi?: DoiTelemetry; targetKey?: number; hidden?: boolean;
}) {
  const [target, setTarget] = useState<HTMLDivElement | null>(null);
  return <Provider><div className={`app-shell${open ? ' console-open' : ''}`}><div className="main-canvas">
    <DynamicIsland workflow={workflow} systemStats={false} doi={doi} hidden={hidden} portalTarget={open ? target : null} />
    {open && <BottomConsole key={targetKey} queue={[]} history={[]} editorMode onClose={() => undefined} statusSlotRef={setTarget} />}
  </div></div></Provider>;
}

beforeEach(async () => {
  const { setLanguage } = await import('../i18n'); await setLanguage('en');
  vi.stubGlobal('localStorage', storageStub);
  localStorage.clear(); dismissAllNotifications();
});
afterEach(() => {
  act(() => dismissAllNotifications());
  vi.useRealTimers(); vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe('one stateful island, inline Console markup', () => {
  it('retains pinned full mode, DOI and actionable notifications across console attach, target replacement and close', () => {
    const doi = { ...EMPTY_DOI_TELEMETRY, active: true, result: 'running' as const,
      lines: ['Verified stage'], thinking: 'Retained reasoning', outputTokens: 17 };
    const action = vi.fn();
    const view = render(<Harness open={false} doi={doi} />);
    fireEvent.click(view.container.querySelector('.island-pill')!);
    act(() => { notify({ id: 'persistent', title: 'Review required', tone: 'error', duration: 0,
      actions: [{ label: 'Review output', onClick: action }] }); });
    expect(view.container.querySelector('.main-canvas > .island-full')).not.toBeNull();
    view.rerender(<Harness open doi={doi} />);
    const firstSlot = view.container.querySelector('.console-status-slot')!;
    expect(firstSlot.querySelector('.island-full')).not.toBeNull();
    expect(view.container.querySelector('.main-canvas > .island')).toBeNull();
    expect(firstSlot.textContent).toContain('Retained reasoning');
    fireEvent.click(screen.getByRole('button', { name: 'Review output' })); expect(action).toHaveBeenCalledWith('persistent');
    act(() => { notify({ id: 'new-inline', title: 'New error while Console is open', tone: 'error', duration: 0 }); });
    expect(firstSlot.textContent).toContain('New error while Console is open');
    view.rerender(<Harness open doi={doi} targetKey={1} />);
    const replacementSlot = view.container.querySelector('.console-status-slot')!;
    expect(replacementSlot).not.toBe(firstSlot); expect(firstSlot.isConnected).toBe(false);
    expect(replacementSlot.querySelector('.island-full')).not.toBeNull();
    expect(replacementSlot.textContent).toContain('New error while Console is open');
    expect(view.container.querySelector('.console-body')?.contains(replacementSlot)).toBe(false);
    expect(replacementSlot.previousElementSibling).toHaveClass('console-tabs');
    expect(replacementSlot.nextElementSibling).toHaveClass('console-body');
    expect(screen.getByRole('button', { name: 'Close console' })).toBeInTheDocument();
    view.rerender(<Harness open={false} doi={doi} />);
    expect(view.container.querySelector('.bottom-console')).toBeNull();
    expect(view.container.querySelector('.main-canvas > .island-full')).not.toBeNull();
    expect(screen.getByText('New error while Console is open')).toBeInTheDocument();
  });

  it('retains the original toast expiry and peek state instead of resetting timers when moved', () => {
    vi.useFakeTimers();
    const view = render(<Harness open={false} />);
    act(() => { notify({ id: 'timed', title: 'Visible timed notification', duration: 5000 }); });
    expect(view.container.querySelector('.island-peek')).not.toBeNull();
    act(() => vi.advanceTimersByTime(2000));
    view.rerender(<Harness open />);
    expect(view.container.querySelector('.console-status-slot .island-peek')).not.toBeNull();
    expect(screen.getByText(/Visible timed notification/)).toBeInTheDocument();
    act(() => vi.advanceTimersByTime(2999));
    expect(screen.getByText(/Visible timed notification/)).toBeInTheDocument();
    act(() => vi.advanceTimersByTime(1));
    expect(screen.queryByText(/Visible timed notification/)).toBeNull();
    expect(view.container.querySelector('.console-status-slot .island-min')).not.toBeNull();
    view.rerender(<Harness open={false} />);
    expect(view.container.querySelector('.main-canvas > .island-min')).not.toBeNull();
  });

  it('keeps focus hiding and restores the same pinned mode after focus mode', () => {
    const view = render(<Harness open />);
    fireEvent.click(view.container.querySelector('.island-pill')!);
    view.rerender(<Harness open hidden />);
    expect(view.container.querySelector('.island')).toBeNull();
    view.rerender(<Harness open />);
    expect(view.container.querySelector('.console-status-slot .island-full')).not.toBeNull();
  });

});
