import { atom } from 'jotai';
import type { HostStatus, LogEntry } from '../types';

export interface NodeRunProgress {
  current: number;
  total: number;
  startedAt: number;
}

export const isRunningAtom = atom(false);
export const batchCountAtom = atom(1);
export const logsAtom = atom<LogEntry[]>([]);
export const hostStatusAtom = atom<HostStatus | null>(null);
export const nodeRunProgressAtom = atom<Record<string, NodeRunProgress>>({});


/**
 * Per-node download progress, keyed by node id.
 *
 * Fetching a remote input used to be invisible on the canvas -- the only signal
 * was a toast in the corner, far from the node actually doing the work. Toasts
 * are for the user's own uploads; a node pulling a file from the web shows it
 * on the node.
 *
 * `total` is 0 when the server sent no Content-Length, which the node renders
 * as an indeterminate bar rather than a made-up percentage.
 */
export interface NodeDownloadProgress {
  downloaded: number;
  total: number;
  url?: string;
}

export const nodeDownloadProgressAtom = atom<Record<string, NodeDownloadProgress>>({});
