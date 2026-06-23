import { atom } from 'jotai';
import type { getAuthUser } from '../collab';
import type { ComputeSpec } from '../utils/computeSpec';

export const authReadyAtom = atom(false);
export const authUserAtom = atom<ReturnType<typeof getAuthUser>>(null);
export const requestedWorkflowIdAtom = atom<string | null>(null);
export const showAuthDialogAtom = atom(false);

/** Runtime config served by the backend's `/api/config` (cloud-launch info). */
export interface CloudConfig {
  cloudMode: boolean;
  /** Shared stateless editor backend: persist workflows to the website DB and
   *  submit runs to the cloud Batch runner (no in-session execution). */
  editorMode: boolean;
  user: { id: string; name: string; email: string } | null;
  team: { id: string; name: string } | null;
  plan: string | null;
  credits: { remaining: number | null; total: number | null } | null;
  accountUrl: string | null;
  clerkPublishableKey: string | null;
}

/** null = not yet fetched. Populated once on boot by useCloudConfig. */
export const cloudConfigAtom = atom<CloudConfig | null>(null);

// Selected cloud compute spec for the next run (set in the Compute panel).
// Persisted to localStorage so it survives reloads. Defaults to the Small
// preset; the Compute panel coerces Free-plan users to micro/small.
const COMPUTE_SPEC_KEY = 'bionodulo.cloud.computeSpec';

function loadComputeSpec(): ComputeSpec {
  try {
    const raw = localStorage.getItem(COMPUTE_SPEC_KEY);
    if (raw) {
      const parsed = JSON.parse(raw) as ComputeSpec;
      if (parsed && (parsed.kind === 'profile' || parsed.kind === 'custom')) return parsed;
    }
  } catch { /* ignore */ }
  return { kind: 'profile', profile: 'small' };
}

const baseComputeSpecAtom = atom<ComputeSpec>(loadComputeSpec());

/** Selected compute spec; writing it also persists to localStorage. */
export const computeSpecAtom = atom(
  (get) => get(baseComputeSpecAtom),
  (_get, set, next: ComputeSpec) => {
    set(baseComputeSpecAtom, next);
    try { localStorage.setItem(COMPUTE_SPEC_KEY, JSON.stringify(next)); } catch { /* ignore */ }
  },
);
