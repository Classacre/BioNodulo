/**
 * Offer a new desktop version on startup.
 *
 * The updater plugin, its minisign key and a signed `latest.json` feed have
 * been configured since the Tauri migration, and every release publishes signed
 * artifacts — but nothing ever called `check()`, so the app shipped with a
 * working auto-updater that never updated anything.
 *
 * Installing is the user's decision, not ours: a workflow may be mid-run, and
 * restarting under someone would lose it. So this offers, once per launch, and
 * never blocks.
 */
import { notify } from '../state/notifications';

export interface UpdateStatus {
  available: boolean;
  version?: string;
  notes?: string;
  currentVersion?: string;
}

interface TauriBridge {
  core?: { invoke?: (cmd: string) => Promise<unknown> };
}

function invoker(): ((cmd: string) => Promise<unknown>) | null {
  const tauri = (window as unknown as { __TAURI__?: TauriBridge }).__TAURI__;
  return tauri?.core?.invoke ?? null;
}

/** Whether we are running inside the desktop shell at all. */
export function isDesktopApp(): boolean {
  return invoker() !== null;
}

/** Ask the shell whether a newer release exists. Never throws. */
export async function checkForUpdate(): Promise<UpdateStatus> {
  const invoke = invoker();
  if (!invoke) return { available: false };
  try {
    return (await invoke('check_for_update')) as UpdateStatus;
  } catch {
    // Offline, or a proxy blocking the release feed. Not worth reporting: the
    // user cannot act on it and would see it every launch.
    return { available: false };
  }
}

/**
 * Show the offer, if there is one.
 *
 * Returns the status so a caller can test the decision without a toast.
 */
export async function offerUpdateOnStartup(
  t: (key: string, opts?: Record<string, unknown>) => string,
): Promise<UpdateStatus> {
  const status = await checkForUpdate();
  if (!status.available || !status.version) return status;

  notify({
    id: 'app-update-available',
    title: t('update.availableTitle', {
      version: status.version,
      defaultValue: 'BioNodulo {{version}} is available',
    }),
    message: t('update.availableMessage', {
      defaultValue:
        'Installing restarts the app, so finish or stop any running workflow first.',
    }),
    tone: 'info',
    // Stays until dismissed: a five-second toast about a restart is a toast
    // nobody reads in time.
    duration: 0,
    actions: [
      {
        label: t('update.installNow', { defaultValue: 'Install and restart' }),
        onClick: () => {
          const invoke = invoker();
          if (!invoke) return;
          void invoke('install_update').catch((error: unknown) => {
            notify({
              title: t('update.failedTitle', { defaultValue: 'Update failed' }),
              message: String(
                (error as { message?: string })?.message ?? error ?? '',
              ),
              tone: 'error',
            });
          });
        },
      },
    ],
  });
  return status;
}
