import { atom } from 'jotai';
import type { getAuthUser } from '../collab';

export const authReadyAtom = atom(false);
export const authUserAtom = atom<ReturnType<typeof getAuthUser>>(null);
export const requestedWorkflowIdAtom = atom<string | null>(null);
export const showAuthDialogAtom = atom(false);
