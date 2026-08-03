import { beforeEach, describe, expect, it, vi } from 'vitest';

// jsdom in this project ships no working localStorage, so tests supply one --
// the same stub pattern the other suites use.
const storage = new Map<string, string>();
const localStorageStub: Storage = {
  get length() {
    return storage.size;
  },
  clear: () => storage.clear(),
  getItem: (key: string) => storage.get(key) ?? null,
  key: (index: number) => Array.from(storage.keys())[index] ?? null,
  removeItem: (key: string) => {
    storage.delete(key);
  },
  setItem: (key: string, value: string) => {
    storage.set(key, String(value));
  },
};

const notify = vi.fn();
vi.mock('../state/notifications', () => ({ notify: (o: unknown) => notify(o) }));

import { maybeSuggestCloud, resetCloudSuggestion } from '../utils/cloudSuggestion';

/** Pretend to be the desktop shell with a given local-execution status. */
function withDesktop(status: Record<string, unknown> | Error | null) {
  (window as unknown as { __TAURI__?: unknown }).__TAURI__ = status
    ? {
        core: {
          invoke: () =>
            status instanceof Error ? Promise.reject(status) : Promise.resolve(status),
        },
      }
    : undefined;
}

const RUNNING_LOCALLY = { requiresWsl: true, enabled: true, state: 'ready' };

describe('cloud suggestion', () => {
  beforeEach(() => {
    notify.mockClear();
    storage.clear();
    vi.stubGlobal('localStorage', localStorageStub);
    Object.defineProperty(window, 'localStorage', {
      value: localStorageStub,
      configurable: true,
    });
    resetCloudSuggestion();
    withDesktop(null);
  });

  it('suggests the cloud when a Windows machine runs locally', async () => {
    withDesktop(RUNNING_LOCALLY);

    await maybeSuggestCloud();

    expect(notify).toHaveBeenCalledOnce();
    const options = notify.mock.calls[0][0] as { message: string; tone: string };
    // It must read as a suggestion, so it says what local execution is good
    // for rather than only advertising the cloud.
    expect(options.message).toMatch(/offline/i);
    expect(options.tone).toBe('info');
  });

  it('offers a way to act on the suggestion', async () => {
    withDesktop(RUNNING_LOCALLY);
    const switchToCloud = vi.fn();

    await maybeSuggestCloud(switchToCloud);

    const { actions } = notify.mock.calls[0][0] as { actions: { onClick: () => void }[] };
    expect(actions).toHaveLength(1);
    actions[0].onClick();
    expect(switchToCloud).toHaveBeenCalled();
  });

  it('only ever appears once', async () => {
    withDesktop(RUNNING_LOCALLY);

    await maybeSuggestCloud();
    await maybeSuggestCloud();

    expect(notify).toHaveBeenCalledOnce();
  });

  it('stays quiet in the browser', async () => {
    // The cloud editor is already the cloud; suggesting it is nonsense.
    withDesktop(null);

    await maybeSuggestCloud();

    expect(notify).not.toHaveBeenCalled();
  });

  it('stays quiet on platforms that run workflows natively', async () => {
    // Linux and macOS need no WSL, so there is nothing to trade off.
    withDesktop({ requiresWsl: false, enabled: true, state: 'ready' });

    await maybeSuggestCloud();

    expect(notify).not.toHaveBeenCalled();
  });

  it('stays quiet when local execution is not actually running', async () => {
    // Already on the cloud because WSL is not set up: suggesting the cloud
    // would be telling the user to do what they are already doing.
    withDesktop({ requiresWsl: true, enabled: false, state: 'distro-missing' });

    await maybeSuggestCloud();

    expect(notify).not.toHaveBeenCalled();
  });

  it('stays quiet when the shell cannot answer', async () => {
    withDesktop(new Error('command unavailable'));

    await maybeSuggestCloud();

    expect(notify).not.toHaveBeenCalled();
  });

  it('does not block the run it is called from', async () => {
    // The workflow starts either way; this is what makes it a suggestion
    // rather than a prompt.
    withDesktop(RUNNING_LOCALLY);

    await expect(maybeSuggestCloud()).resolves.toBeUndefined();
  });
});
