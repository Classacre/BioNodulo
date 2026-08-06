import { beforeEach, describe, expect, it, vi } from 'vitest';

const notify = vi.fn();
vi.mock('../state/notifications', () => ({ notify: (o: unknown) => notify(o) }));

import { checkForUpdate, isDesktopApp, offerUpdateOnStartup } from '../utils/appUpdate';

/** Pretend to be the desktop shell, with a scripted `invoke`. */
function withShell(handler: ((cmd: string) => Promise<unknown>) | null) {
  (window as unknown as { __TAURI__?: unknown }).__TAURI__ = handler
    ? { core: { invoke: handler } }
    : undefined;
}

// Mirrors i18next's {{var}} interpolation so the assertions test the real
// message the user sees, not the untouched template.
const t = (key: string, opts?: Record<string, unknown>) =>
  String(opts?.defaultValue ?? key).replace(
    /\{\{(\w+)\}\}/g,
    (_match, name: string) => String(opts?.[name] ?? ''),
  );

beforeEach(() => {
  notify.mockClear();
  withShell(null);
});

/**
 * The updater plugin, its signing key and a signed release feed were configured
 * long ago, but nothing ever called check() — so the app shipped with a working
 * auto-updater that never updated anything.
 */
describe('startup update offer', () => {
  it('offers an update when one is published', async () => {
    withShell(async () => ({ available: true, version: '0.1.0-alpha.7' }));

    await offerUpdateOnStartup(t);

    expect(notify).toHaveBeenCalledOnce();
    const options = notify.mock.calls[0][0] as { title: string; duration: number };
    expect(options.title).toContain('0.1.0-alpha.7');
    // A toast about restarting must not expire before it is read.
    expect(options.duration).toBe(0);
  });

  it('warns that installing restarts the app', async () => {
    // A running workflow would be lost, so the user has to be told before
    // clicking, not after.
    withShell(async () => ({ available: true, version: '9.9.9' }));

    await offerUpdateOnStartup(t);

    const { message } = notify.mock.calls[0][0] as { message: string };
    expect(message).toMatch(/restart/i);
  });

  it('installs only when the user asks', async () => {
    const invoke = vi.fn(async (cmd: string) =>
      cmd === 'check_for_update' ? { available: true, version: '9.9.9' } : undefined
    );
    withShell(invoke);

    await offerUpdateOnStartup(t);
    expect(invoke).not.toHaveBeenCalledWith('install_update');

    const { actions } = notify.mock.calls[0][0] as { actions: { onClick: () => void }[] };
    actions[0].onClick();
    expect(invoke).toHaveBeenCalledWith('install_update');
  });

  it('says nothing when the app is current', async () => {
    withShell(async () => ({ available: false }));

    await offerUpdateOnStartup(t);

    expect(notify).not.toHaveBeenCalled();
  });

  it('says nothing in the browser', async () => {
    withShell(null);

    await offerUpdateOnStartup(t);

    expect(notify).not.toHaveBeenCalled();
    expect(isDesktopApp()).toBe(false);
  });

  it('stays silent when the check itself fails', async () => {
    // Offline, or a proxy blocking the release feed: the user cannot act on it
    // and would otherwise see an error on every launch.
    withShell(async () => { throw new Error('network down'); });

    await expect(checkForUpdate()).resolves.toEqual({ available: false });
    await offerUpdateOnStartup(t);
    expect(notify).not.toHaveBeenCalled();
  });

  it('ignores an available update with no version', async () => {
    withShell(async () => ({ available: true }));

    await offerUpdateOnStartup(t);

    expect(notify).not.toHaveBeenCalled();
  });
});
