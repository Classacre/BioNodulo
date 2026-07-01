import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import {
  CLOUD_CREDITS_POLL_HIDDEN_MS,
  CLOUD_CREDITS_POLL_VISIBLE_MS,
  CLOUD_RUN_POLL_HIDDEN_MS,
  CLOUD_RUN_POLL_VISIBLE_MS,
  COLLAB_PRESENCE_POLL_HIDDEN_MS,
  COLLAB_PRESENCE_POLL_VISIBLE_MS,
  SYSTEM_STATS_POLL_HIDDEN_MS,
  SYSTEM_STATS_POLL_VISIBLE_MS,
  isBrowserDocumentHidden,
  pollingDelay,
  startVisibilityAwarePolling,
} from '../utils/pollingPolicy';

describe('pollingPolicy', () => {
  let hiddenSpy: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    vi.useFakeTimers();
    hiddenSpy = vi.spyOn(document, 'hidden', 'get').mockReturnValue(false);
  });

  afterEach(() => {
    hiddenSpy.mockRestore();
    vi.useRealTimers();
  });

  it('uses resource-safe foreground intervals for chatty app polls', () => {
    expect(SYSTEM_STATS_POLL_VISIBLE_MS).toBeGreaterThanOrEqual(15_000);
    expect(CLOUD_RUN_POLL_VISIBLE_MS).toBeGreaterThanOrEqual(10_000);
    expect(COLLAB_PRESENCE_POLL_VISIBLE_MS).toBeGreaterThanOrEqual(30_000);
    expect(CLOUD_CREDITS_POLL_VISIBLE_MS).toBeGreaterThanOrEqual(300_000);
  });

  it('backs off substantially when the tab is hidden', () => {
    expect(SYSTEM_STATS_POLL_HIDDEN_MS).toBeGreaterThanOrEqual(120_000);
    expect(CLOUD_RUN_POLL_HIDDEN_MS).toBeGreaterThanOrEqual(60_000);
    expect(COLLAB_PRESENCE_POLL_HIDDEN_MS).toBeGreaterThanOrEqual(120_000);
    expect(CLOUD_CREDITS_POLL_HIDDEN_MS).toBeGreaterThanOrEqual(600_000);
  });

  it('selects the hidden interval only when the browser reports a hidden document', () => {
    expect(pollingDelay(10, 20, { hidden: false })).toBe(10);
    expect(pollingDelay(10, 20, { hidden: true })).toBe(20);
    expect(isBrowserDocumentHidden(null)).toBe(false);
  });

  it('refreshes immediately when a hidden tab becomes visible', async () => {
    hiddenSpy.mockReturnValue(true);
    const callback = vi.fn().mockResolvedValue(undefined);

    const stop = startVisibilityAwarePolling(callback, 10, 100);
    await Promise.resolve();
    expect(callback).toHaveBeenCalledTimes(1);
    callback.mockClear();

    await vi.advanceTimersByTimeAsync(99);
    expect(callback).not.toHaveBeenCalled();

    hiddenSpy.mockReturnValue(false);
    document.dispatchEvent(new Event('visibilitychange'));
    await Promise.resolve();
    expect(callback).toHaveBeenCalledTimes(1);

    stop();
  });

  it('reschedules to the hidden delay when a visible tab is backgrounded', async () => {
    const callback = vi.fn().mockResolvedValue(undefined);

    const stop = startVisibilityAwarePolling(callback, 10, 100);
    await Promise.resolve();
    expect(callback).toHaveBeenCalledTimes(1);
    callback.mockClear();

    hiddenSpy.mockReturnValue(true);
    document.dispatchEvent(new Event('visibilitychange'));

    await vi.advanceTimersByTimeAsync(99);
    expect(callback).not.toHaveBeenCalled();

    await vi.advanceTimersByTimeAsync(1);
    expect(callback).toHaveBeenCalledTimes(1);

    stop();
  });
});
