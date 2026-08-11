import { act, fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { useRef, useState } from 'react';
import { useFocusTrap } from '../hooks/ui/useFocusTrap';

/**
 * Mirrors how Dialog uses the hook: a fresh `onEscape` closure on every render
 * (Dialog builds `handleEscape` inline) and a focusable element (the close
 * button) ahead of the input. Regression test for the invite dialog losing
 * focus on every keystroke: a state change re-rendered the dialog, the trap
 * effect re-ran on the new callback identity, and its cleanup restored focus
 * to whatever was focused before the dialog opened.
 */
function Harness({ onEscape = () => {} }: { onEscape?: () => void }) {
  const ref = useRef<HTMLDivElement>(null);
  const [value, setValue] = useState('');
  useFocusTrap(ref, true, () => onEscape());
  return (
    <div>
      <button type="button">outside</button>
      <div ref={ref}>
        <button type="button">close</button>
        <input
          aria-label="email"
          value={value}
          onChange={e => setValue(e.target.value)}
        />
      </div>
    </div>
  );
}

const flushTimers = () => act(async () => { await new Promise(r => setTimeout(r, 0)); });

describe('useFocusTrap', () => {
  it('keeps focus on the input across re-renders with a fresh escape callback', async () => {
    render(<Harness />);
    const input = screen.getByLabelText('email');
    await flushTimers();

    input.focus();
    fireEvent.change(input, { target: { value: 'a' } });
    await flushTimers();
    fireEvent.change(input, { target: { value: 'ab' } });
    await flushTimers();

    expect(document.activeElement).toBe(input);
    expect(input).toHaveValue('ab');
  });

  it('invokes the latest escape handler', async () => {
    const first = vi.fn();
    const second = vi.fn();
    const { rerender } = render(<Harness onEscape={first} />);
    await flushTimers();
    rerender(<Harness onEscape={second} />);
    await flushTimers();

    const input = screen.getByLabelText('email');
    fireEvent.keyDown(input, { key: 'Escape' });

    expect(first).not.toHaveBeenCalled();
    expect(second).toHaveBeenCalledTimes(1);
  });
});
