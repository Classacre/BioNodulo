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

import { closedIds, forgetClosed, isClosed, rememberClosed } from '../state/closedWorkflows';

beforeEach(() => {
  storage.clear();
  vi.stubGlobal('localStorage', localStorageStub);
  Object.defineProperty(window, 'localStorage', { value: localStorageStub, configurable: true });
});

/**
 * The cloud editor restores tabs from the team's most recent workflows. Closing
 * a tab only dropped it from React state, so the next visit opened it again —
 * a user with many workflows was handed back a wall of tabs they had already
 * dismissed.
 */
describe('closed workflows', () => {
  it('remembers a closed workflow', () => {
    rememberClosed('wf-1');

    expect(isClosed('wf-1')).toBe(true);
    expect(closedIds().has('wf-1')).toBe(true);
  });

  it('leaves other workflows alone', () => {
    rememberClosed('wf-1');

    expect(isClosed('wf-2')).toBe(false);
  });

  it('forgets when the user deliberately reopens it', () => {
    // Otherwise reopening works for the session and silently vanishes next
    // visit, which reads as the editor losing work.
    rememberClosed('wf-1');
    forgetClosed('wf-1');

    expect(isClosed('wf-1')).toBe(false);
  });

  it('does not accumulate duplicates', () => {
    rememberClosed('wf-1');
    rememberClosed('wf-1');

    expect([...closedIds()]).toEqual(['wf-1']);
  });

  it('bounds what it remembers', () => {
    // A long-lived browser must not grow this without limit.
    for (let i = 0; i < 260; i += 1) rememberClosed(`wf-${i}`);

    expect(closedIds().size).toBeLessThanOrEqual(200);
    // The most recent dismissals are the ones that matter.
    expect(isClosed('wf-259')).toBe(true);
  });

  it('ignores an empty id rather than storing one', () => {
    rememberClosed('');

    expect(closedIds().size).toBe(0);
  });

  it('treats unusable storage as nothing closed', () => {
    // Showing too many tabs is recoverable; hiding a workflow the user wants
    // is not.
    const broken = { ...localStorageStub, getItem: () => { throw new Error('denied'); } } as Storage;
    Object.defineProperty(window, 'localStorage', { value: broken, configurable: true });

    expect(closedIds().size).toBe(0);
    expect(isClosed('wf-1')).toBe(false);
  });

  it('survives corrupt stored data', () => {
    storage.set('bionodulo.workflows.closed', '{not json');

    expect(() => closedIds()).not.toThrow();
    expect(closedIds().size).toBe(0);
  });
});
