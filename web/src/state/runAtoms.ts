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
