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
  /** Clerk OAuth application (public client) for desktop Authorization Code +
   *  PKCE sign-in. Null when the local instance isn't configured for it. */
  oauth: { clientId: string; authorizeUrl: string; tokenUrl: string } | null;
}

/** null = not yet fetched. Populated once on boot by useCloudConfig. */
export const cloudConfigAtom = atom<CloudConfig | null>(null);

// Selected cloud compute spec for the next run (set in the Compute panel).
// Persisted to localStorage so it survives reloads. Defaults to a small custom
// size (2 vCPU / 16 GB) within the Free-plan cap; the Compute panel clamps to
// the plan's limits.
const COMPUTE_SPEC_KEY = 'bionodulo.cloud.computeSpec';

function loadComputeSpec(): ComputeSpec {
  try {
    const raw = localStorage.getItem(COMPUTE_SPEC_KEY);
    if (raw) {
      const parsed = JSON.parse(raw) as ComputeSpec;
      if (parsed && (parsed.kind === 'profile' || parsed.kind === 'custom' || parsed.kind === 'gpu')) {
        return parsed;
      }
    }
  } catch { /* ignore */ }
  return { kind: 'custom', vcpu: 2, ramGb: 16 };
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

// Workflow auto-sizing: while true, the Compute panel keeps the spec matched to
// the active workflow (threads demand + GPU need). Any manual slider edit turns
// it off; the panel offers a one-click re-enable. Defaults to on.
const COMPUTE_AUTO_KEY = 'bionodulo.cloud.computeAuto';

function loadComputeAuto(): boolean {
  try {
    const raw = localStorage.getItem(COMPUTE_AUTO_KEY);
    if (raw === 'false') return false;
  } catch { /* ignore */ }
  return true;
}

const baseComputeAutoAtom = atom<boolean>(loadComputeAuto());

/** Whether compute auto-sizing is active; persisted alongside the spec. */
export const computeAutoAtom = atom(
  (get) => get(baseComputeAutoAtom),
  (_get, set, next: boolean) => {
    set(baseComputeAutoAtom, next);
    try { localStorage.setItem(COMPUTE_AUTO_KEY, JSON.stringify(next)); } catch { /* ignore */ }
  },
);
