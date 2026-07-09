import { setCollabRemoteBase, resolveCollabUrl } from '../collab/remoteBase';

it('rewrites only collab paths when a remote base is set', () => {
  setCollabRemoteBase('https://x.trycloudflare.com');
  expect(resolveCollabUrl('/api/collab/rooms/join')).toBe('https://x.trycloudflare.com/api/collab/rooms/join');
  expect(resolveCollabUrl('/api/config')).toBe('/api/config'); // untouched
  setCollabRemoteBase(null);
  expect(resolveCollabUrl('/api/collab/rooms/join')).toBe('/api/collab/rooms/join');
});
