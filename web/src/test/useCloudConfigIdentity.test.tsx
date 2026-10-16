import { act, renderHook, waitFor } from '@testing-library/react';
import { Provider, createStore } from 'jotai';
import type { ReactNode } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { useCloudConfig } from '../hooks/cloud/useCloudConfig';
import { useClerkAuth } from '../hooks/cloud/useClerkAuth';
import { authUserAtom, cloudConfigAtom, type CloudConfig } from '../state/appAtoms';
import { resolveBrowserStorageScope } from '../utils/browserStorageScope';

const mocks = vi.hoisted(() => {
  const getToken = vi.fn();
  const session = { id: 'session-a', getToken };
  const user = { id: 'user-a', fullName: 'Ada', primaryEmailAddress: null, username: null };
  const clerk = {
    session: session as typeof session | null,
    user: user as typeof user | null,
    organization: { id: 'org-a' } as { id: string } | null,
    load: vi.fn(), addListener: vi.fn(), openSignIn: vi.fn(), signOut: vi.fn(),
  };
  return {
    clerk, getToken, apiGet: vi.fn(), getCurrentUser: vi.fn(), configureWebsiteApi: vi.fn(),
    clearToken: vi.fn(), setAuthUser: vi.fn(), setToken: vi.fn(), registerTokenRefresher: vi.fn(),
    initDesktopOAuth: vi.fn(), setSettingsEditorMode: vi.fn(),
    Clerk: vi.fn(function Clerk() { return clerk; }),
  };
});
vi.mock('@clerk/clerk-js', () => ({ Clerk: mocks.Clerk }));
vi.mock('../api/client', () => ({ apiGet: mocks.apiGet }));
vi.mock('../api/website', () => ({
  getCurrentUser: mocks.getCurrentUser, configureWebsiteApi: mocks.configureWebsiteApi,
}));
vi.mock('../collab', () => ({ getUserColor: () => '#123456' }));
vi.mock('../collab/authStorage', () => ({
  clearToken: mocks.clearToken, setAuthUser: mocks.setAuthUser, setToken: mocks.setToken,
  registerTokenRefresher: mocks.registerTokenRefresher,
}));
vi.mock('../hooks/settings/useSettings', () => ({ setSettingsEditorMode: mocks.setSettingsEditorMode }));
vi.mock('../hooks/cloud/desktopOAuth', () => ({ initDesktopOAuth: mocks.initDesktopOAuth }));
vi.mock('../state/logging', () => ({ logError: vi.fn() }));

const config: CloudConfig = {
  cloudMode: false, editorMode: true, user: null, team: null, plan: null, credits: null,
  accountUrl: null, clerkPublishableKey: 'pk_test_example', oauth: null,
};
const me = (user = 'a', org = user) => ({
  id: `db-${user}`, clerkUserId: `user-${user}`, name: user.toUpperCase(), email: `${user}@example.test`,
  team: { id: `db-team-${org}`, name: org.toUpperCase(), clerkOrgId: `org-${org}` },
});
function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason: unknown) => void;
  const promise = new Promise<T>((res, rej) => { resolve = res; reject = rej; });
  return { promise, resolve, reject };
}
let listener: (() => void) | undefined;
function mount() {
  const store = createStore();
  const wrapper = ({ children }: { children: ReactNode }) => <Provider store={store}>{children}</Provider>;
  const hook = renderHook(() => {
    const cloud = useCloudConfig();
    const clerk = useClerkAuth(cloud.syncClerkIdentity);
    return { cloud, clerk };
  }, { wrapper });
  return { ...hook, store };
}
async function changeSession(user: string, org = user, session = user, token = Promise.resolve(`token-${user}`)) {
  await act(async () => {
    mocks.clerk.session = { id: `session-${session}`, getToken: vi.fn().mockReturnValue(token) };
    mocks.clerk.user = { id: `user-${user}`, fullName: user.toUpperCase(), primaryEmailAddress: null, username: null };
    mocks.clerk.organization = { id: `org-${org}` };
    listener?.();
  });
}

describe('cloud identity recovery after Clerk readiness', () => {
  beforeEach(() => {
    vi.resetAllMocks();
    mocks.apiGet.mockResolvedValue({ ...config });
    mocks.clerk.load.mockResolvedValue(undefined);
    mocks.getToken.mockResolvedValue('token-a');
    mocks.clerk.session = { id: 'session-a', getToken: mocks.getToken };
    mocks.clerk.user = { id: 'user-a', fullName: 'Ada', primaryEmailAddress: null, username: null };
    mocks.clerk.organization = { id: 'org-a' };
    listener = undefined;
    mocks.clerk.addListener.mockImplementation(callback => { listener = callback; return vi.fn(); });
  });
  afterEach(() => vi.useRealTimers());

  it('recovers initial cookie 401 after real Clerk sync without changing DB-owned storage keys', async () => {
    const clerkLoaded = deferred<void>();
    mocks.clerk.load.mockReturnValue(clerkLoaded.promise);
    mocks.getCurrentUser.mockRejectedValueOnce(new Error('Unauthorized')).mockResolvedValueOnce(me());
    const { result, store, unmount } = mount();
    await waitFor(() => expect(mocks.getCurrentUser).toHaveBeenCalledOnce());
    expect(store.get(cloudConfigAtom)?.user).toBeNull();
    await act(async () => { clerkLoaded.resolve(); });
    await waitFor(() => expect(result.current.cloud.cloudConfig?.user?.id).toBe('db-a'));
    expect(result.current.cloud.cloudConfig?.user?.clerkUserId).toBe('user-a');
    expect(store.get(authUserAtom)?.id).toBe('user-a');
    expect(resolveBrowserStorageScope(result.current.cloud.cloudConfig).storageSuffix)
      .toBe('.cloud.db-a.db-team-a');
    expect(mocks.getCurrentUser).toHaveBeenCalledTimes(2);
    await act(async () => { listener?.(); });
    expect(mocks.getCurrentUser).toHaveBeenCalledTimes(2);
    unmount();
  });

  it('invalidates the bootstrap read before token await and ignores its late cookie identity', async () => {
    const initial = deferred<ReturnType<typeof me>>();
    const token = deferred<string>();
    mocks.getCurrentUser.mockReturnValueOnce(initial.promise).mockResolvedValueOnce(me());
    mocks.getToken.mockReturnValue(token.promise);
    const { store, unmount } = mount();
    await waitFor(() => expect(mocks.getToken).toHaveBeenCalled());
    expect(mocks.getCurrentUser.mock.calls[0][0].aborted).toBe(true);
    await act(async () => { initial.resolve(me('foreign')); });
    expect(store.get(cloudConfigAtom)?.user).toBeNull();
    await act(async () => { token.resolve('token-a'); });
    await waitFor(() => expect(store.get(cloudConfigAtom)?.user?.id).toBe('db-a'));
    unmount();
  });

  it('clears a changed organization before token await, then rejects the previous organization cookie', async () => {
    mocks.getCurrentUser.mockRejectedValueOnce(new Error('Unauthorized')).mockResolvedValue(me());
    const { store, unmount } = mount();
    await waitFor(() => expect(store.get(cloudConfigAtom)?.user?.id).toBe('db-a'));
    const token = deferred<string>();
    await changeSession('a', 'b', 'b', token.promise);
    expect(store.get(cloudConfigAtom)?.user).toBeNull();
    expect(store.get(cloudConfigAtom)?.team).toBeNull();
    expect(store.get(authUserAtom)).toBeNull();
    await act(async () => { token.resolve('token-b'); });
    await waitFor(() => expect(mocks.getCurrentUser).toHaveBeenCalledTimes(3));
    expect(store.get(cloudConfigAtom)?.user).toBeNull();
    mocks.getCurrentUser.mockResolvedValue(me('a', 'b'));
    await act(async () => { listener?.(); });
    await waitFor(() => expect(store.get(cloudConfigAtom)?.team?.id).toBe('db-team-b'));
    unmount();
  });

  it('rejects delayed identities across A→B→A, including the first A request', async () => {
    const firstA = deferred<ReturnType<typeof me>>();
    const b = deferred<ReturnType<typeof me>>();
    const secondA = deferred<ReturnType<typeof me>>();
    mocks.getCurrentUser.mockRejectedValueOnce(new Error('Unauthorized'))
      .mockReturnValueOnce(firstA.promise).mockReturnValueOnce(b.promise).mockReturnValueOnce(secondA.promise);
    const { store, unmount } = mount();
    await waitFor(() => expect(mocks.getCurrentUser).toHaveBeenCalledTimes(2));
    await changeSession('b');
    await waitFor(() => expect(mocks.getCurrentUser).toHaveBeenCalledTimes(3));
    await changeSession('a', 'a', 'a-returned');
    await waitFor(() => expect(mocks.getCurrentUser).toHaveBeenCalledTimes(4));
    await act(async () => { firstA.resolve(me()); b.resolve(me('b')); });
    expect(store.get(cloudConfigAtom)?.user).toBeNull();
    expect(mocks.getCurrentUser.mock.calls[1][0].aborted).toBe(true);
    expect(mocks.getCurrentUser.mock.calls[2][0].aborted).toBe(true);
    await act(async () => { secondA.resolve({ ...me(), name: 'Returned A' }); });
    await waitFor(() => expect(store.get(cloudConfigAtom)?.user?.name).toBe('Returned A'));
    expect(store.get(authUserAtom)?.id).toBe('user-a');
    unmount();
  });

  it.each([
    ['different canonical user', { ...me(), clerkUserId: 'user-other' }],
    ['legacy DB id with no canonical user', { ...me(), clerkUserId: undefined }],
    ['different canonical organization', me('a', 'other')],
  ])('fails closed for %s after Clerk sync', async (_label, response) => {
    mocks.getCurrentUser.mockRejectedValueOnce(new Error('Unauthorized')).mockResolvedValue(response);
    const { store, unmount } = mount();
    await waitFor(() => expect(mocks.getCurrentUser).toHaveBeenCalledTimes(2));
    expect(store.get(cloudConfigAtom)?.user).toBeNull();
    expect(store.get(cloudConfigAtom)?.team).toBeNull();
    unmount();
  });

  it('allows the authoritative server fallback team when Clerk has no active organization', async () => {
    mocks.clerk.organization = null;
    mocks.getCurrentUser.mockRejectedValueOnce(new Error('Unauthorized')).mockResolvedValue(me('a', 'fallback'));
    const { store, unmount } = mount();
    await waitFor(() => expect(store.get(cloudConfigAtom)?.team?.id).toBe('db-team-fallback'));
    unmount();
  });

  it('blocks the previous organization while org→null waits for its authoritative fallback team', async () => {
    const fallback = deferred<ReturnType<typeof me>>();
    mocks.getCurrentUser.mockRejectedValueOnce(new Error('Unauthorized'))
      .mockResolvedValueOnce(me()).mockReturnValueOnce(fallback.promise);
    const { store, unmount } = mount();
    await waitFor(() => expect(store.get(cloudConfigAtom)?.team?.id).toBe('db-team-a'));
    await act(async () => { mocks.clerk.organization = null; listener?.(); });
    expect(store.get(cloudConfigAtom)?.user).toBeNull();
    expect(store.get(cloudConfigAtom)?.team).toBeNull();
    expect(resolveBrowserStorageScope(store.get(cloudConfigAtom)).mode).toBe('blocked');
    await act(async () => { fallback.resolve(me('a', 'fallback')); });
    await waitFor(() => expect(store.get(cloudConfigAtom)?.team?.id).toBe('db-team-fallback'));
    unmount();
  });

  it('clears identity when Clerk retains a user resource after removing its session', async () => {
    mocks.getCurrentUser.mockRejectedValueOnce(new Error('Unauthorized')).mockResolvedValue(me());
    const { store, unmount } = mount();
    await waitFor(() => expect(store.get(cloudConfigAtom)?.user?.id).toBe('db-a'));
    await act(async () => { mocks.clerk.session = null; listener?.(); });
    expect(store.get(cloudConfigAtom)?.user).toBeNull();
    expect(store.get(cloudConfigAtom)?.team).toBeNull();
    expect(store.get(authUserAtom)).toBeNull();
    expect(mocks.getCurrentUser).toHaveBeenCalledTimes(2);
    unmount();
  });

  it('blocks a previously ready identity on a same-session null token and recovers on the next valid sync', async () => {
    mocks.getCurrentUser.mockRejectedValueOnce(new Error('Unauthorized')).mockResolvedValue(me());
    const { store, unmount } = mount();
    await waitFor(() => expect(store.get(cloudConfigAtom)?.user?.id).toBe('db-a'));
    mocks.getToken.mockResolvedValueOnce(null);
    await act(async () => { listener?.(); });
    expect(store.get(cloudConfigAtom)?.user).toBeNull();
    expect(store.get(cloudConfigAtom)?.team).toBeNull();
    expect(store.get(authUserAtom)).toBeNull();
    expect(resolveBrowserStorageScope(store.get(cloudConfigAtom)).mode).toBe('blocked');
    expect(mocks.getCurrentUser).toHaveBeenCalledTimes(2);
    await act(async () => { listener?.(); });
    await waitFor(() => expect(store.get(cloudConfigAtom)?.user?.id).toBe('db-a'));
    expect(mocks.getCurrentUser).toHaveBeenCalledTimes(3);
    unmount();
  });

  it('revalidates a new session for the same user/org and ignores superseded token completion', async () => {
    const oldToken = deferred<string>();
    mocks.getToken.mockReturnValue(oldToken.promise);
    mocks.getCurrentUser.mockRejectedValueOnce(new Error('Unauthorized')).mockResolvedValue(me('b'));
    const { store, unmount } = mount();
    await waitFor(() => expect(mocks.getToken).toHaveBeenCalled());
    expect(mocks.getCurrentUser).toHaveBeenCalledTimes(1);
    await changeSession('b');
    await waitFor(() => expect(mocks.getCurrentUser).toHaveBeenCalledTimes(2));
    await waitFor(() => expect(store.get(cloudConfigAtom)?.user?.id).toBe('db-b'));
    await act(async () => { oldToken.resolve('old-token-a'); });
    expect(mocks.setToken).not.toHaveBeenCalledWith('old-token-a');
    expect(store.get(authUserAtom)?.id).toBe('user-b');
    await changeSession('b', 'b', 'b-renewed');
    await waitFor(() => expect(mocks.getCurrentUser).toHaveBeenCalledTimes(3));
    unmount();
  });

  it('does not revive identity after sign-out while /me is pending', async () => {
    const pending = deferred<ReturnType<typeof me>>();
    mocks.getCurrentUser.mockRejectedValueOnce(new Error('Unauthorized')).mockReturnValueOnce(pending.promise);
    const { result, store, unmount } = mount();
    await waitFor(() => expect(mocks.getCurrentUser).toHaveBeenCalledTimes(2));
    await act(async () => { result.current.clerk.signOut(); });
    await act(async () => {
      pending.resolve(me());
      // Clerk may replace a resource object while sign-out is still pending.
      mocks.clerk.session = { id: 'session-a', getToken: vi.fn().mockResolvedValue('resurrected-token') };
      listener?.();
    });
    expect(store.get(cloudConfigAtom)?.user).toBeNull();
    expect(store.get(authUserAtom)).toBeNull();
    expect(mocks.getCurrentUser).toHaveBeenCalledTimes(2);
    expect(mocks.setToken).not.toHaveBeenCalledWith('resurrected-token');
    unmount();
  });

  it('ignores retained callbacks and pending identity reads after unmount', async () => {
    const pending = deferred<ReturnType<typeof me>>();
    mocks.getCurrentUser.mockRejectedValueOnce(new Error('Unauthorized')).mockReturnValueOnce(pending.promise);
    const { store, unmount } = mount();
    await waitFor(() => expect(mocks.getCurrentUser).toHaveBeenCalledTimes(2));
    const retained = listener;
    unmount();
    await act(async () => { pending.resolve(me()); retained?.(); });
    expect(store.get(cloudConfigAtom)?.user).toBeNull();
    expect(mocks.getCurrentUser).toHaveBeenCalledTimes(2);
  });

  it.each(['local', 'injected'] as const)('preserves %s mode without Clerk or shared-editor identity reads', async mode => {
    mocks.apiGet.mockResolvedValue({ ...config, editorMode: false,
      cloudMode: mode === 'injected', clerkPublishableKey: mode === 'injected' ? 'pk_test_example' : null,
      user: mode === 'injected' ? { id: 'injected-user', name: 'Injected', email: '' } : null,
      team: mode === 'injected' ? { id: 'injected-team', name: 'Team' } : null });
    const { store, unmount } = mount();
    await waitFor(() => expect(store.get(cloudConfigAtom)).not.toBeNull());
    expect(mocks.Clerk).not.toHaveBeenCalled();
    expect(mocks.getCurrentUser).not.toHaveBeenCalled();
    expect(store.get(authUserAtom)?.id ?? null).toBe(mode === 'injected' ? 'injected-user' : null);
    unmount();
  });
});
