/**
 * Cloud share-link invites (editor SPA side).
 *
 * A link like /build?workflow=<id>&invite=bni_<token> redeems through the
 * website's PUBLIC /api/collab/join. Guests receive the workflow definition,
 * a pre-minted collab room token (injected into useCollab instead of the
 * team mint), a display-name identity, and — for editor-role invites — a
 * runToken (the invite itself) accepted as a bearer by POST /api/runs.
 *
 * Logged-in members of the owning team get member:true and the SPA uses its
 * normal team path instead.
 */
import { atom } from 'jotai';
import { call } from '../api/website';

export interface CloudInviteSession {
  workflowId: string;
  member: boolean;
  role: 'viewer' | 'editor';
  identity: { name: string; kind: 'guest' | 'member' };
  /** Pre-minted room access (guests). Null for members. */
  room: string | null;
  roomToken: string | null;
  roomHost: string | null;
  roomExpiresAt: number | null;
  /** The invite token; editor-role guests send it as the run bearer. */
  runToken: string | null;
  name: string;
}

/** The active guest/member session redeemed from a share link (null = none). */
export const cloudInviteSessionAtom = atom<CloudInviteSession | null>(null);

/** Last guest display name used, so a returning guest keeps their identity. */
const GUEST_NAME_KEY = 'bionodulo.collab.guestName';

export function storedGuestName(): string | null {
  try {
    return localStorage.getItem(GUEST_NAME_KEY);
  } catch {
    return null;
  }
}

export function storeGuestName(name: string): void {
  try {
    localStorage.setItem(GUEST_NAME_KEY, name);
  } catch {
    /* ignore */
  }
}

interface JoinResponse {
  member: boolean;
  role: 'viewer' | 'editor';
  identity?: { name: string; kind: 'guest' | 'member' };
  workflow: { id: string; name: string; definition: unknown };
  room: string;
  token: string;
  host: string;
  expiresAt: number;
  runToken?: string | null;
}

/** Redeem an invite. Throws on invalid/expired/revoked tokens (404). */
export async function joinCloudInvite(
  inviteToken: string,
  name?: string | null,
): Promise<{ session: CloudInviteSession; workflow: JoinResponse['workflow'] }> {
  const data = await call<JoinResponse>('/collab/join', {
    method: 'POST',
    body: JSON.stringify({ invite: inviteToken, ...(name ? { name } : {}) }),
  });
  const guestName = data.identity?.name ?? name ?? 'Guest';
  if (!data.member && data.identity?.name) storeGuestName(data.identity.name);
  return {
    session: {
      workflowId: data.workflow.id,
      member: data.member,
      role: data.role,
      identity: data.identity ?? { name: guestName, kind: data.member ? 'member' : 'guest' },
      room: data.member ? null : data.room,
      roomToken: data.member ? null : data.token,
      roomHost: data.member ? null : data.host,
      roomExpiresAt: data.member ? null : data.expiresAt,
      runToken: data.runToken ?? null,
      name: guestName,
    },
    workflow: data.workflow,
  };
}

/** Create a share link (team members only — the website enforces ownership). */
export async function createCloudInvite(
  workflowId: string,
  role: 'viewer' | 'editor',
): Promise<{ link: string; token: string }> {
  return call<{ link: string; token: string }>('/collab/invites', {
    method: 'POST',
    body: JSON.stringify({ workflowId, role }),
  });
}
