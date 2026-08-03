// Suggest the cloud to Windows users running locally -- once, dismissibly.
//
// Local execution is the default on Windows: the installer enables WSL2 while
// elevated, and workflows run in a private Linux distribution on the user's own
// machine. That is the right default (no credits, no upload, works offline),
// but the cloud is genuinely better for large jobs, and a laptop running a
// multi-hour alignment is a bad experience nobody warned them about.
//
// So: a suggestion, not a gate. Shown at most once, and never again after it is
// dismissed or acted on.

import { notify } from '../state/notifications';

const STORAGE_KEY = 'bionodulo.cloudSuggestion.dismissed';

interface LocalExecutionStatus {
  requiresWsl?: boolean;
  enabled?: boolean;
  state?: string;
}

/** Read the desktop shell's view of local execution, if we are in it. */
async function localExecutionStatus(): Promise<LocalExecutionStatus | null> {
  const tauri = (window as unknown as {
    __TAURI__?: { core?: { invoke?: (cmd: string) => Promise<unknown> } };
  }).__TAURI__;
  const invoke = tauri?.core?.invoke;
  if (!invoke) return null; // Browser or cloud editor: nothing to suggest.
  try {
    return (await invoke('get_local_execution_status')) as LocalExecutionStatus;
  } catch {
    return null;
  }
}

function alreadyDismissed(): boolean {
  try {
    return window.localStorage.getItem(STORAGE_KEY) === '1';
  } catch {
    // Private mode or a locked-down profile: treat as not dismissed rather
    // than suppressing the suggestion entirely.
    return false;
  }
}

function rememberDismissal(): void {
  try {
    window.localStorage.setItem(STORAGE_KEY, '1');
  } catch {
    /* Nothing to do; the suggestion simply appears again next session. */
  }
}

/**
 * Offer the cloud once, when a workflow is about to run locally on Windows.
 *
 * Resolves immediately and never blocks the run: the workflow starts either
 * way, which is what makes this a suggestion rather than a prompt.
 */
export async function maybeSuggestCloud(onSwitchToCloud?: () => void): Promise<void> {
  if (alreadyDismissed()) return;

  const status = await localExecutionStatus();
  // Only meaningful where local execution is the WSL2 path and it is actually
  // in use. On Linux and macOS local execution is simply native.
  if (!status?.requiresWsl || !status.enabled || status.state !== 'ready') return;

  rememberDismissal();
  notify({
    title: 'Running on this PC',
    message:
      'Large workflows finish faster on the cloud, and leave your machine free. ' +
      'Local runs use no credits and work offline.',
    tone: 'info',
    duration: 12000,
    actions: onSwitchToCloud
      ? [{ label: 'Run on cloud instead', onClick: onSwitchToCloud }]
      : [],
  });
}

/** Test seam: forget that the suggestion was shown. */
export function resetCloudSuggestion(): void {
  try {
    window.localStorage.removeItem(STORAGE_KEY);
  } catch {
    /* ignore */
  }
}
