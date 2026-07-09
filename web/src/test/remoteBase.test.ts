import { getDefaultStore } from 'jotai';
import { setCollabRemoteBase, resolveCollabUrl, collabRemoteBaseAtom } from '../collab/remoteBase';

afterEach(() => {
  setCollabRemoteBase(null);
});

it('rewrites only collab paths when a remote base is set', () => {
  setCollabRemoteBase('https://x.trycloudflare.com');
  expect(resolveCollabUrl('/api/collab/rooms/join')).toBe('https://x.trycloudflare.com/api/collab/rooms/join');
  expect(resolveCollabUrl('/api/config')).toBe('/api/config'); // untouched
  setCollabRemoteBase(null);
  expect(resolveCollabUrl('/api/collab/rooms/join')).toBe('/api/collab/rooms/join');
});

it('strips trailing slashes from the remote base', () => {
  setCollabRemoteBase('https://x.trycloudflare.com/');
  expect(resolveCollabUrl('/api/collab/rooms')).toBe('https://x.trycloudflare.com/api/collab/rooms');
});

it('keeps collabRemoteBaseAtom in sync with the module var', () => {
  const store = getDefaultStore();
  setCollabRemoteBase('https://x.trycloudflare.com');
  expect(store.get(collabRemoteBaseAtom)).toBe('https://x.trycloudflare.com');
  setCollabRemoteBase(null);
  expect(store.get(collabRemoteBaseAtom)).toBeNull();
});
