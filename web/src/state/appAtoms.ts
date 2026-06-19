import { atom } from 'jotai';
import type { getAuthUser } from '../collab';

export const authReadyAtom = atom(false);
export const authUserAtom = atom<ReturnType<typeof getAuthUser>>(null);
export const requestedWorkflowIdAtom = atom<string | null>(null);
export const showAuthDialogAtom = atom(false);

/** Runtime config served by the backend's `/api/config` (cloud-launch info). */
export interface CloudConfig {
  cloudMode: boolean;
  user: { id: string; name: string; email: string } | null;
  team: { id: string; name: string } | null;
  plan: string | null;
  credits: { remaining: number | null; total: number | null } | null;
  accountUrl: string | null;
  clerkPublishableKey: string | null;
}

/** null = not yet fetched. Populated once on boot by useCloudConfig. */
export const cloudConfigAtom = atom<CloudConfig | null>(null);
