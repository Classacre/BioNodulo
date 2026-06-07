import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { Tooltip } from '../components/ui/Tooltip';

describe('Tooltip', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    cleanup();
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it('opens after the configured delay and closes when the trigger is left', () => {
    render(
      <Tooltip content="Start a workflow run" delay={200}>
        <button type="button">Run</button>
      </Tooltip>,
    );

    const trigger = screen.getByText('Run').parentElement;
    expect(trigger).not.toBeNull();

    fireEvent.mouseEnter(trigger!);
    act(() => {
      vi.advanceTimersByTime(199);
    });

    expect(screen.queryByRole('tooltip')).not.toBeInTheDocument();

    act(() => {
      vi.advanceTimersByTime(1);
    });

    expect(screen.getByRole('tooltip')).toHaveTextContent('Start a workflow run');

    fireEvent.mouseLeave(trigger!);

    expect(screen.queryByRole('tooltip')).not.toBeInTheDocument();
  });

  it('links the open tooltip to the trigger with aria-describedby', () => {
    render(
      <Tooltip content="Inspect sample metadata" delay={0}>
        <button type="button">Inspect</button>
      </Tooltip>,
    );

    const trigger = screen.getByText('Inspect').parentElement;
    expect(trigger).not.toBeNull();
    expect(trigger).not.toHaveAttribute('aria-describedby');

    fireEvent.focus(trigger!);
    act(() => {
      vi.runOnlyPendingTimers();
    });

    const tooltip = screen.getByRole('tooltip');
    expect(tooltip).toHaveTextContent('Inspect sample metadata');
    expect(trigger).toHaveAttribute('aria-describedby', tooltip.id);

    fireEvent.blur(trigger!);

    expect(trigger).not.toHaveAttribute('aria-describedby');
    expect(screen.queryByRole('tooltip')).not.toBeInTheDocument();
  });

  it('renders tooltip content through a document body portal', () => {
    const { container } = render(
      <Tooltip content={<span>Portal content</span>} delay={0}>
        <button type="button">Details</button>
      </Tooltip>,
    );

    const trigger = screen.getByText('Details').parentElement;
    expect(trigger).not.toBeNull();

    fireEvent.mouseEnter(trigger!);
    act(() => {
      vi.runOnlyPendingTimers();
    });

    const tooltip = screen.getByRole('tooltip');
    expect(tooltip).toHaveTextContent('Portal content');
    expect(document.body).toContainElement(tooltip);
    expect(container).not.toContainElement(tooltip);
  });

  it('does not open or describe the trigger when disabled', () => {
    render(
      <Tooltip content="Disabled hint" delay={0} disabled>
        <button type="button">Disabled action</button>
      </Tooltip>,
    );

    const trigger = screen.getByText('Disabled action').parentElement;
    expect(trigger).not.toBeNull();

    fireEvent.mouseEnter(trigger!);
    fireEvent.focus(trigger!);
    act(() => {
      vi.runOnlyPendingTimers();
    });

    expect(screen.queryByRole('tooltip')).not.toBeInTheDocument();
    expect(trigger).not.toHaveAttribute('aria-describedby');
  });

  it('repositions while open on scroll and resize events', () => {
    const firstRect = new DOMRect(10, 20, 100, 40);
    const scrolledRect = new DOMRect(30, 50, 100, 40);
    const resizedRect = new DOMRect(60, 80, 100, 40);
    const getBoundingClientRect = vi
      .spyOn(HTMLSpanElement.prototype, 'getBoundingClientRect')
      .mockReturnValueOnce(firstRect)
      .mockReturnValueOnce(scrolledRect)
      .mockReturnValueOnce(resizedRect);

    render(
      <Tooltip content="Positioned hint" delay={0} placement="bottom">
        <button type="button">Positioned</button>
      </Tooltip>,
    );

    const trigger = screen.getByText('Positioned').parentElement;
    expect(trigger).not.toBeNull();

    fireEvent.mouseEnter(trigger!);
    act(() => {
      vi.runOnlyPendingTimers();
    });

    const tooltip = screen.getByRole('tooltip');
    expect(tooltip).toHaveStyle({ left: '60px', top: '68px', transform: 'translateX(-50%)' });

    act(() => {
      window.dispatchEvent(new Event('scroll'));
    });

    expect(getBoundingClientRect).toHaveBeenCalledTimes(2);
    expect(tooltip).toHaveStyle({ left: '80px', top: '98px', transform: 'translateX(-50%)' });

    act(() => {
      window.dispatchEvent(new Event('resize'));
    });

    expect(getBoundingClientRect).toHaveBeenCalledTimes(3);
    expect(tooltip).toHaveStyle({ left: '110px', top: '128px', transform: 'translateX(-50%)' });
  });
});
