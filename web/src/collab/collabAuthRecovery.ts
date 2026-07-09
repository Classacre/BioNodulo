import { ApiError } from '../api/client';
import type { CollabLinkTarget } from './shareLinks';

export type CollabAuthAction = { type: 'create' } | { type: 'join'; target: CollabLinkTarget };

export function isAuthRejection(err: unknown): boolean {
  return err instanceof ApiError && (err.status === 401 || err.status === 403);
}

export function recoverAndReprompt(
  err: unknown,
  deps: {
    clearToken: () => void;
    setAuthUser: (u: null) => void;
    requestCollabAuth: (action: CollabAuthAction) => void;
    action: CollabAuthAction;
  },
): boolean {
  if (!isAuthRejection(err)) return false;
  deps.clearToken();
  deps.setAuthUser(null);
  deps.requestCollabAuth(deps.action);
  return true;
}
