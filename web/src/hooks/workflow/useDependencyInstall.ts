import { useState, useCallback, useEffect, useRef } from 'react';
import type { InstallJobStatus, Workflow } from '../../types';
import { apiGet, apiPost } from '../../api/client';
import { logError } from '../../state/logging';

const INSTALL_PROGRESS_MESSAGE_KEYS: Record<string, string> = {
  'Generating pixi.toml manifest...': 'resolveReport.installMessages.generatingManifest',
  'Locking dependencies with pixi (this may take a moment)...': 'resolveReport.installMessages.lockingDependencies',
  'Installing packages into environment...': 'resolveReport.installMessages.installingPackages',
  'Installation cancelled': 'resolveReport.installMessages.installationCancelled',
};

/** Translate a raw install-progress message from the backend into a localized
 * string. Exported so both the banner and the auto-install toast render the
 * same human-readable progress text. */
export function installProgressMessage(
  message: string,
  t: (key: string, values?: Record<string, unknown>) => string,
): string {
  const trimmed = message.trim();
  if (!trimmed) return '';
  const resolvedMatch = /^Resolved (\d+) packages for env (.+)$/.exec(trimmed);
  if (resolvedMatch) {
    return t('resolveReport.installMessages.resolvedPackages', {
      count: Number(resolvedMatch[1]),
      env: resolvedMatch[2],
    });
  }
  const knownMessageKey = INSTALL_PROGRESS_MESSAGE_KEYS[trimmed];
  if (knownMessageKey) return t(knownMessageKey);
  const readyMatch = /^Environment (.+) ready with (\d+) packages$/.exec(trimmed);
  if (readyMatch) {
    return t('resolveReport.installMessages.environmentReady', {
      env: readyMatch[1],
      count: Number(readyMatch[2]),
    });
  }
  return trimmed;
}

export interface UseDependencyInstall {
  /** Start an environment install for the workflow and resolve once the job
   * finishes. Resolves `true` on completion, `false` on failure/cancellation. */
  install: (workflow: Workflow) => Promise<boolean>;
  installing: boolean;
  /** Latest job status (current_step, message, percent), or null when idle. */
  status: InstallJobStatus | null;
  step: string;
  percent: number;
}

const POLL_INTERVAL_MS = 1500;

/**
 * Encapsulates the "ensure workflow env" install flow: POST the job, poll its
 * status until it finishes, and surface live progress. Shared between the
 * MissingDependenciesBanner (manual install) and the Run auto-install path so
 * both drive the exact same backend interaction.
 *
 * @param onProgress optional callback fired on every status poll, useful for
 *   updating a progress toast.
 */
export function useDependencyInstall(onProgress?: (status: InstallJobStatus) => void): UseDependencyInstall {
  const [installing, setInstalling] = useState(false);
  const [status, setStatus] = useState<InstallJobStatus | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const statusPollErrorLoggedRef = useRef(false);
  const onProgressRef = useRef(onProgress);
  onProgressRef.current = onProgress;

  const clearPoll = useCallback(() => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }, []);

  const install = useCallback((workflow: Workflow): Promise<boolean> => {
    return new Promise<boolean>((resolve) => {
      clearPoll();
      setInstalling(true);
      setStatus(null);

      void (async () => {
        let jobId: string | undefined;
        try {
          const data = await apiPost<{ job_id?: string }>('/manager/ensure-workflow-env', { workflow });
          jobId = data.job_id;
        } catch (err) {
          logError('dependencies.install.start', err);
          setInstalling(false);
          resolve(false);
          return;
        }
        if (!jobId) {
          // No job means the env is already satisfied / nothing to install.
          setInstalling(false);
          resolve(true);
          return;
        }
        statusPollErrorLoggedRef.current = false;
        pollRef.current = setInterval(async () => {
          try {
            const next = await apiGet<InstallJobStatus>(`/manager/status/${jobId}`);
            setStatus(next);
            onProgressRef.current?.(next);
            if (next.status === 'completed' || next.status === 'failed' || next.status === 'cancelled') {
              clearPoll();
              setInstalling(false);
              resolve(next.status === 'completed');
            }
          } catch (err) {
            if (!statusPollErrorLoggedRef.current) {
              logError('dependencies.install.status', err);
              statusPollErrorLoggedRef.current = true;
            }
            /* ignore transient poll errors */
          }
        }, POLL_INTERVAL_MS);
      })();
    });
  }, [clearPoll]);

  useEffect(() => () => clearPoll(), [clearPoll]);

  return {
    install,
    installing,
    status,
    step: status?.current_step ?? '',
    percent: typeof status?.percent === 'number' ? status.percent : 0,
  };
}
