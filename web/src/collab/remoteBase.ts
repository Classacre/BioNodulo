import { atom, getDefaultStore } from 'jotai';

export const collabRemoteBaseAtom = atom<string | null>(null);
const store = getDefaultStore();

let remoteBase: string | null = null;

export function setCollabRemoteBase(base: string | null): void {
  remoteBase = base ? base.replace(/\/+$/, '') : null;
  store.set(collabRemoteBaseAtom, remoteBase);
}

export function getCollabRemoteBase(): string | null {
  return remoteBase;
}

const COLLAB_RE = /^\/?api\/collab\//;

export function resolveCollabUrl(path: string): string {
  if (!remoteBase) return path;
  const clean = path.replace(/^\/+/, '');
  return COLLAB_RE.test('/' + clean) ? `${remoteBase}/${clean}` : path;
}
