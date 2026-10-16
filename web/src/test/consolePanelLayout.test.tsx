import { act, fireEvent, render, screen } from '@testing-library/react';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { useEffect, useState } from 'react';
import { describe, expect, it, vi } from 'vitest';
import ConsolePanelSlot from '../components/layout/ConsolePanelSlot';
import { activateConsolePanel, consoleChromeFits, consoleHidesRailPanel, consolePanelLayout, fitDockedPanels } from '../utils/panelLayout';

describe('console allocation and retained panel presentation', () => {
  it.each([false, true])('reveals explicit panel intent without toggling retained state off (%s)', previous => {
    const close = vi.fn(); const setOpen = vi.fn();
    activateConsolePanel(true, setOpen, close, true);
    expect(close).toHaveBeenCalledOnce();
    expect(setOpen.mock.calls[0][0](previous)).toBe(true);
    setOpen.mockClear(); close.mockClear();
    activateConsolePanel(false, setOpen, close, true);
    expect(close).not.toHaveBeenCalled();
    expect(setOpen.mock.calls[0][0](previous)).toBe(!previous);
    setOpen.mockClear();
    activateConsolePanel(false, setOpen, close);
    expect(setOpen.mock.calls[0][0](previous)).toBe(true);
  });

  it('uses explicit intent callbacks for real AI, history, comments and a retained active rail button', async () => {
    const { Provider } = await import('jotai');
    const { default: TopBar } = await import('../components/layout/TopBar');
    const { default: LeftRail } = await import('../components/layout/LeftRail');
    const { default: CollabBadge } = await import('../collab/CollabBadge');
    const { setLanguage } = await import('../i18n'); await setLanguage('en');
    const onAI = vi.fn(); const onRuns = vi.fn(); const onComments = vi.fn(); const onRail = vi.fn();
    render(<Provider>
      <TopBar validationValid validationErrors={[]} onRun={() => undefined} hpcStatus="off" queueCount={0}
        onToggleQueue={onRuns} onOpenAI={onAI} />
      <LeftRail active="data" panelsSuspended onChange={onRail} />
      <CollabBadge enabled connected connecting={false} activeUsers={[]} currentWorkflowId="audit" followingUserId={null}
        isShared={false} onFollow={() => undefined} onOpenSettings={() => undefined} onCreateSession={() => undefined}
        onJoinSession={() => undefined} onLeaveSession={() => undefined} onToggleComments={onComments} />
    </Provider>);
    fireEvent.click(screen.getByRole('button', { name: /Open AI assistant/ })); expect(onAI).toHaveBeenCalledOnce();
    fireEvent.click(screen.getByRole('button', { name: 'Queue: 0' })); expect(onRuns).toHaveBeenCalledOnce();
    fireEvent.click(screen.getByRole('button', { name: 'Workspace (Ctrl+1)' })); expect(onRail).toHaveBeenCalledWith('data');
    fireEvent.click(screen.getByTitle('Collaboration: Connected'));
    fireEvent.click(screen.getByRole('button', { name: 'Comments' })); expect(onComments).toHaveBeenCalledOnce();
  });
  it.each([
    [1224, 372, 0, false, 852], [1224, 0, 372, false, 852],
    [1224, 372, 380, false, 472], [612, 372, 0, false, 240],
    [611, 372, 0, true, 611], [334, 312, 0, true, 334],
    [334, 0, 334, true, 334],
  ])('uses actual allocation at %ipx (%i left, %i right)', (width, left, right, exclusive, available) => {
    const result = consolePanelLayout(true, false, width as number, left as number, right as number);
    expect(result.exclusive).toBe(exclusive);
    expect(result.width).toBe(available);
    expect(result.leftInset).toBe(exclusive ? 0 : left);
    expect(result.rightInset).toBe(exclusive ? 0 : right);
  });

  it('preserves requested fitted allocations and restores them on close or focus mode', () => {
    const requests = [{ id: 'workspace', width: 340, side: 'left' as const }];
    const before = structuredClone(requests);
    const fitted = fitDockedPanels(requests, 334);
    const left = fitted[0].width + 32;
    expect(consolePanelLayout(true, false, 334, left, 0).exclusive).toBe(true);
    expect(consolePanelLayout(false, false, 334, left, 0).leftInset).toBe(left);
    expect(consolePanelLayout(true, true, 334, left, 0).exclusive).toBe(false);
    expect(requests).toEqual(before);
    expect(fitDockedPanels(requests, 334)).toEqual(fitted);
  });

  it('reveals an explicitly selected suspended desktop float even with ample normal console width', () => {
    const layout = consolePanelLayout(true, false, 1224, 0, 0);
    expect(layout.exclusive).toBe(false);
    const hidden = consoleHidesRailPanel(layout.exclusive, true, false, true);
    expect(hidden).toBe(true);
    const close = vi.fn(); const setOpen = vi.fn();
    activateConsolePanel(hidden, setOpen, close, true);
    expect(close).toHaveBeenCalledOnce(); expect(setOpen.mock.calls[0][0](true)).toBe(true);
    expect(consoleHidesRailPanel(false, true, false, false)).toBe(false);
    expect(consoleHidesRailPanel(false, false, false, true)).toBe(false);
    expect(consoleHidesRailPanel(false, true, true, true)).toBe(false);
  });

  it('keeps mounted unsent work and moves hidden focus to the console until the panel returns', () => {
    const mounted = vi.fn(); const unmounted = vi.fn();
    function Draft() {
      const [draft, setDraft] = useState('');
      useEffect(() => { mounted(); return unmounted; }, []);
      return <textarea aria-label="unsent draft" value={draft} onChange={event => setDraft(event.target.value)} />;
    }
    function Harness({ open, width }: { open: boolean; width: number }) {
      const policy = consolePanelLayout(open, false, width, 372, 0);
      return <><div className="bottom-console" tabIndex={-1}>Console</div>
        <ConsolePanelSlot suspended={policy.exclusive}><Draft /></ConsolePanelSlot></>;
    }
    const view = render(<Harness open width={1224} />);
    const draft = screen.getByRole('textbox', { name: 'unsent draft' });
    fireEvent.change(draft, { target: { value: 'keep unsent work' } }); draft.focus();
    expect(draft).toHaveFocus();
    act(() => view.rerender(<Harness open width={334} />));
    const slot = view.container.querySelector('.console-panel-slot')!;
    expect(slot).toHaveAttribute('inert'); expect(slot).toHaveAttribute('aria-hidden', 'true');
    expect(screen.queryByRole('textbox', { name: 'unsent draft' })).toBeNull();
    expect(draft).toHaveValue('keep unsent work');
    expect(view.container.querySelector('.bottom-console')).toHaveFocus();
    act(() => view.rerender(<Harness open={false} width={334} />));
    expect(screen.getByRole('textbox', { name: 'unsent draft' })).toBe(draft);
    expect(draft).toHaveValue('keep unsent work');
    expect(mounted).toHaveBeenCalledOnce(); expect(unmounted).not.toHaveBeenCalled();
  });

  it('hides unfittable bottom chrome when a tall console leaves too little canvas, and restores after resize', () => {
    expect(consoleChromeFits(644, 280, 150)).toBe(true);
    expect(consoleChromeFits(644, 510, 150)).toBe(false);
    expect(consoleChromeFits(360, 360, 150)).toBe(false);
    expect(consoleChromeFits(644, 280, 400)).toBe(false);
    expect(consoleChromeFits(644, 200, 400)).toBe(true);
  });

  it('keeps real console/chrome CSS bounded without overriding current height or focus hiding', () => {
    const css = readFileSync(resolve(__dirname, '../index.css'), 'utf8');
    const rule = (selector: string) => css.slice(css.indexOf(`\n${selector} {`) + 1).split('}')[0];
    expect(rule('.bottom-console')).toContain('left: var(--left-panel-inset, 0px)');
    expect(rule('.bottom-console')).toContain('right: var(--right-panel-inset, 0px)');
    expect(rule('.bottom-console')).toContain('max-height: 100%');
    expect(rule('.console-tabs')).toContain('flex-wrap: wrap');
    expect(rule('.console-tabs')).toContain('overflow: auto');
    expect(rule('.console-tabs')).toContain('max-height: 100%');
    expect(rule('.console-tabs > *')).toContain('flex-shrink: 0');
    expect(rule('.console-panel-slot.is-suspended')).toContain('visibility: hidden');
    for (const selector of ['.app-shell.console-open .react-flow__controls', '.app-shell.console-open .react-flow__minimap']) {
      expect(rule(selector)).toContain('var(--console-height, 280px)');
    }
    expect(css).toMatch(/\.app-shell\.focus-mode \.bottom-console\s*\{\s*display: none !important/);
  });
});
