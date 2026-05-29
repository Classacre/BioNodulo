import { describe, it, expect, vi, beforeEach } from 'vitest';
import { logError, subscribeErrors, recentErrors, clearRecentErrors } from '../state/logging';

describe('state/logging', () => {
  beforeEach(() => {
    clearRecentErrors();
    vi.spyOn(console, 'error').mockImplementation(() => {});
  });

  it('records the scope, message, name, and stack for an Error', () => {
    const err = new Error('boom');
    err.name = 'WhammyError';
    logError('test.scope', err);
    const entries = recentErrors();
    expect(entries).toHaveLength(1);
    expect(entries[0]).toMatchObject({
      scope: 'test.scope',
      message: 'boom',
      name: 'WhammyError',
    });
    expect(entries[0]!.stack).toBeDefined();
  });

  it('handles a non-Error value gracefully', () => {
    logError('test.scope', 'just a string');
    expect(recentErrors()[0]!.message).toBe('just a string');
    logError('test.scope', { reason: 'shape' });
    expect(recentErrors()[1]!.message).toContain('shape');
  });

  it('notifies subscribers and supports unsubscribe', () => {
    const onError = vi.fn();
    const unsub = subscribeErrors(onError);
    logError('a.b', new Error('one'));
    expect(onError).toHaveBeenCalledTimes(1);
    unsub();
    logError('a.b', new Error('two'));
    expect(onError).toHaveBeenCalledTimes(1);
  });

  it('caps the ring buffer at 200', () => {
    for (let i = 0; i < 250; i++) logError('rb', new Error(`e${i}`));
    expect(recentErrors().length).toBe(200);
    expect(recentErrors()[0]!.message).toBe('e50');
  });
});
