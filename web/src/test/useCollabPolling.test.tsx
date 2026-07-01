import { act, renderHook } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { apiGet } from '../api/client';
import { useCollabPolling } from '../hooks/collab/useCollabPolling';
import { COLLAB_PRESENCE_POLL_VISIBLE_MS } from '../utils/pollingPolicy';

const apiMocks = vi.hoisted(() => ({
  apiGet: vi.fn(),
}));

const authMocks = vi.hoisted(() => ({
  getToken: vi.fn(),
}));

vi.mock('../api/client', () => apiMocks);
vi.mock('../collab', () => authMocks);
vi.mock('../state/logging', () => ({ logError: vi.fn() }));

describe('useCollabPolling', () => {
  let hiddenSpy: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    vi.useFakeTimers();
    apiMocks.apiGet.mockReset();
    authMocks.getToken.mockReturnValue('token');
    hiddenSpy = vi.spyOn(document, 'hidden', 'get').mockReturnValue(false);
  });

  afterEach(() => {
    hiddenSpy.mockRestore();
    vi.useRealTimers();
  });

  it('polls live presence on the resource-safe foreground cadence', async () => {
    apiMocks.apiGet.mockResolvedValue({ users: [] });
    const setLivePresenceUsers = vi.fn();

    renderHook(() => useCollabPolling({ collabEnabled: true, setLivePresenceUsers }));

    await act(async () => {
      await Promise.resolve();
    });
    expect(apiGet).toHaveBeenCalledTimes(1);
    apiMocks.apiGet.mockClear();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(COLLAB_PRESENCE_POLL_VISIBLE_MS - 1);
    });
    expect(apiGet).not.toHaveBeenCalled();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(1);
    });
    expect(apiGet).toHaveBeenCalledTimes(1);
  });

  it('does not hit the presence endpoint while the tab is hidden', async () => {
    hiddenSpy.mockReturnValue(true);
    apiMocks.apiGet.mockResolvedValue({ users: [] });

    renderHook(() => useCollabPolling({ collabEnabled: true, setLivePresenceUsers: vi.fn() }));

    await act(async () => {
      await vi.advanceTimersByTimeAsync(COLLAB_PRESENCE_POLL_VISIBLE_MS * 2);
    });

    expect(apiGet).not.toHaveBeenCalled();
  });
});
