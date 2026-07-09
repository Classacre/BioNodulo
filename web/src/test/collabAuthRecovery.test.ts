// web/src/test/collabAuthRecovery.test.ts
import { isAuthRejection, recoverAndReprompt } from '../collab/collabAuthRecovery';
import { ApiError } from '../api/client';

it('detects 401/403 as auth rejections', () => {
  expect(isAuthRejection(new ApiError('x', 401, 'Unauthorized', null))).toBe(true);
  expect(isAuthRejection(new ApiError('x', 403, 'Forbidden', null))).toBe(true);
  expect(isAuthRejection(new ApiError('x', 500, 'Server', null))).toBe(false);
  expect(isAuthRejection(new Error('net'))).toBe(false);
});

it('clears token and reprompts on auth rejection', () => {
  const calls: string[] = [];
  const handled = recoverAndReprompt(new ApiError('x', 401, 'Unauthorized', null), {
    clearToken: () => calls.push('clear'),
    setAuthUser: () => calls.push('null'),
    requestCollabAuth: () => calls.push('reprompt'),
    action: { type: 'create' },
  });
  expect(handled).toBe(true);
  expect(calls).toEqual(['clear', 'null', 'reprompt']);
});
