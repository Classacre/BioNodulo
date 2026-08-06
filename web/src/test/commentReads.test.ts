import { beforeEach, describe, expect, it, vi } from 'vitest';

// jsdom here ships no working localStorage; the suites stub it.
const storage = new Map<string, string>();
const localStorageStub: Storage = {
  get length() { return storage.size; },
  clear: () => storage.clear(),
  getItem: (key: string) => storage.get(key) ?? null,
  key: (index: number) => Array.from(storage.keys())[index] ?? null,
  removeItem: (key: string) => { storage.delete(key); },
  setItem: (key: string, value: string) => { storage.set(key, String(value)); },
};

import { lastSeenAt, markThreadRead, threadHasUnread } from '../collab/commentReads';
import type { Comment } from '../collab/types';

const ME = 'user-me';
const THEM = 'user-them';

function comment(over: Partial<Comment> & { created_at: string; user_id: string }): Comment {
  return {
    id: Math.random().toString(36).slice(2),
    workflow_id: 'w',
    node_id: 'node-1',
    user_name: 'Someone',
    user_color: '#fff',
    content: 'hello',
    parent_id: null,
    resolved: false,
    updated_at: over.created_at,
    replies: [],
    ...over,
  } as Comment;
}

beforeEach(() => {
  storage.clear();
  vi.stubGlobal('localStorage', localStorageStub);
  Object.defineProperty(window, 'localStorage', { value: localStorageStub, configurable: true });
});

/**
 * "Unread" is a property of the reader, not the thread. `resolved` cannot
 * answer it: a resolved thread may still hold something you never saw, and an
 * unresolved one may be entirely your own writing.
 */
describe('unread comments', () => {
  it('counts a never-opened thread from someone else as unread', () => {
    const thread = [comment({ created_at: '2026-08-06T10:00:00Z', user_id: THEM })];

    expect(threadHasUnread('node-1', thread, ME)).toBe(true);
  });

  it('never counts your own comments as unread', () => {
    // Writing something is not a reason to be nagged about it.
    const thread = [comment({ created_at: '2026-08-06T10:00:00Z', user_id: ME })];

    expect(threadHasUnread('node-1', thread, ME)).toBe(false);
  });

  it('goes quiet once the thread has been opened', () => {
    const thread = [comment({ created_at: '2026-08-06T10:00:00Z', user_id: THEM })];
    markThreadRead('node-1', Date.parse('2026-08-06T11:00:00Z'));

    expect(threadHasUnread('node-1', thread, ME)).toBe(false);
  });

  it('speaks up again when a newer reply arrives', () => {
    markThreadRead('node-1', Date.parse('2026-08-06T11:00:00Z'));
    const thread = [comment({ created_at: '2026-08-06T12:00:00Z', user_id: THEM })];

    expect(threadHasUnread('node-1', thread, ME)).toBe(true);
  });

  it('looks inside replies, not just the top-level comment', () => {
    // The parent may be old and read while the reply is new.
    markThreadRead('node-1', Date.parse('2026-08-06T11:00:00Z'));
    const thread = [
      comment({
        created_at: '2026-08-06T09:00:00Z',
        user_id: ME,
        replies: [comment({ created_at: '2026-08-06T12:00:00Z', user_id: THEM })],
      }),
    ];

    expect(threadHasUnread('node-1', thread, ME)).toBe(true);
  });

  it('is unaffected by whether the thread is resolved', () => {
    const thread = [
      comment({ created_at: '2026-08-06T10:00:00Z', user_id: THEM, resolved: true }),
    ];

    expect(threadHasUnread('node-1', thread, ME)).toBe(true);
  });

  it('treats an unparseable timestamp as read', () => {
    // Bad data must not leave a pin bouncing forever.
    const thread = [comment({ created_at: 'not a date', user_id: THEM })];

    expect(threadHasUnread('node-1', thread, ME)).toBe(false);
  });

  it('tracks threads independently', () => {
    markThreadRead('node-1');

    expect(lastSeenAt('node-1')).toBeGreaterThan(0);
    expect(lastSeenAt('node-2')).toBe(0);
  });

  it('survives storage being unavailable', () => {
    // Private mode: everything reads as unread rather than the badge vanishing.
    const broken = { ...localStorageStub, getItem: () => { throw new Error('denied'); },
      setItem: () => { throw new Error('denied'); } } as Storage;
    Object.defineProperty(window, 'localStorage', { value: broken, configurable: true });

    expect(() => markThreadRead('node-1')).not.toThrow();
    const thread = [comment({ created_at: '2026-08-06T10:00:00Z', user_id: THEM })];
    expect(threadHasUnread('node-1', thread, ME)).toBe(true);
  });
});
