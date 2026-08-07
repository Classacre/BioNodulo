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

import { readOpenWorkflows, writeOpenWorkflows } from '../state/openWorkflows';

beforeEach(() => {
  storage.clear();
  vi.stubGlobal('localStorage', localStorageStub);
  Object.defineProperty(window, 'localStorage', { value: localStorageStub, configurable: true });
});

/**
 * Reopening the editor kept restoring tabs the user had closed. The first
 * attempt recorded dismissals, which could never be authoritative: anything
 * closed before that shipped was never recorded, so it came back regardless.
 * Recording what is OPEN inverts it — a tab closed at any point is simply
 * absent from the set.
 */
describe('open workflow tabs', () => {
  it('restores exactly what was open', () => {
    writeOpenWorkflows(['a', 'b']);

    expect(readOpenWorkflows()).toEqual(['a', 'b']);
  });

  it('distinguishes "never recorded" from "everything closed"', () => {
    // The difference decides whether the editor falls back to recent work or
    // honours an empty desk. Conflating them is what resurrected closed tabs.
    expect(readOpenWorkflows()).toBeNull();

    writeOpenWorkflows([]);
    expect(readOpenWorkflows()).toEqual([]);
  });

  it('forgets a tab once it is no longer in the set', () => {
    writeOpenWorkflows(['a', 'b']);
    writeOpenWorkflows(['a']);

    expect(readOpenWorkflows()).toEqual(['a']);
  });

  it('does not store duplicates', () => {
    writeOpenWorkflows(['a', 'a', 'b']);

    expect(readOpenWorkflows()).toEqual(['a', 'b']);
  });

  it('drops empty ids rather than restoring a phantom tab', () => {
    writeOpenWorkflows(['a', '', 'b']);

    expect(readOpenWorkflows()).toEqual(['a', 'b']);
  });

  it('caps what it restores', () => {
    writeOpenWorkflows(Array.from({ length: 20 }, (_, i) => `w${i}`));

    expect(readOpenWorkflows()!.length).toBeLessThanOrEqual(8);
  });

  it('falls back to recent work when storage is unusable', () => {
    // Returning [] here would show an empty editor and read as lost work.
    const broken = { ...localStorageStub, getItem: () => { throw new Error('denied'); } } as Storage;
    Object.defineProperty(window, 'localStorage', { value: broken, configurable: true });

    expect(readOpenWorkflows()).toBeNull();
  });

  it('falls back when the stored value is corrupt', () => {
    storage.set('bionodulo.workflows.open', '{not json');

    expect(readOpenWorkflows()).toBeNull();
  });

  it('survives a write failing', () => {
    const broken = { ...localStorageStub, setItem: () => { throw new Error('denied'); } } as Storage;
    Object.defineProperty(window, 'localStorage', { value: broken, configurable: true });

    expect(() => writeOpenWorkflows(['a'])).not.toThrow();
  });
});
