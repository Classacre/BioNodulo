import { afterEach, beforeEach, it, expect } from 'vitest';
import { clearToken, setAuthUser, getAuthUser, isGuestUser } from '../collab/authStorage';

const storage = new Map<string, string>();
const fakeStorage: Storage = {
  get length() { return storage.size; },
  clear: () => storage.clear(),
  getItem: (key: string) => storage.get(key) ?? null,
  key: (index: number) => Array.from(storage.keys())[index] ?? null,
  removeItem: (key: string) => { storage.delete(key); },
  setItem: (key: string, value: string) => { storage.set(key, String(value)); },
};

beforeEach(() => {
  globalThis.localStorage = fakeStorage;
  storage.clear();
  clearToken();
});

afterEach(() => {
  clearToken();
  storage.clear();
});

it('round-trips the identity kind and defaults to guest', () => {
  setAuthUser({ id: 'u1', name: 'Ada', color: '#fff', kind: 'guest' });
  expect(getAuthUser()?.kind).toBe('guest');
  expect(isGuestUser(getAuthUser())).toBe(true);

  setAuthUser({ id: 'u2', name: 'Cloud', color: '#000', kind: 'account' });
  expect(isGuestUser(getAuthUser())).toBe(false);
});
