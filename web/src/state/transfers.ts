// Cloud file transfer store (uploads + downloads) driving the minimizable
// transfer window. Transfers are started imperatively from api/cloudFiles.ts,
// so state lives in a jotai atom updated via the default store (no React needed
// to enqueue). Components read it with the usual hooks.
import { atom } from 'jotai';
import { getDefaultStore } from 'jotai';

export type TransferDirection = 'upload' | 'download';
export type TransferStatus = 'active' | 'done' | 'error' | 'canceled';

export interface Transfer {
  id: string;
  name: string;
  direction: TransferDirection;
  status: TransferStatus;
  loaded: number;
  total: number;
  /** Bytes/second, smoothed. 0 until the first progress tick. */
  speedBps: number;
  error?: string;
  /** Cloud object key once an upload finishes. */
  key?: string;
  /** Abort handle so the window's cancel button can stop an in-flight transfer. */
  abort?: () => void;
}

/** Active + recently finished transfers (newest last). */
export const transfersAtom = atom<Transfer[]>([]);
/** Whether the transfer window is collapsed to its background pill. */
export const transferMinimizedAtom = atom(false);

const store = getDefaultStore();

let seq = 0;
export function newTransferId(): string {
  seq += 1;
  return `xfer_${Date.now()}_${seq}`;
}

export function addTransfer(t: Transfer): void {
  store.set(transfersAtom, prev => [...prev, t]);
  // A new transfer un-minimizes so the user sees progress start.
  store.set(transferMinimizedAtom, false);
}

export function updateTransfer(id: string, patch: Partial<Transfer>): void {
  store.set(transfersAtom, prev => prev.map(t => (t.id === id ? { ...t, ...patch } : t)));
}

export function removeTransfer(id: string): void {
  store.set(transfersAtom, prev => prev.filter(t => t.id !== id));
}

/** Drop every finished (done/error/canceled) transfer from the list. */
export function clearFinishedTransfers(): void {
  store.set(transfersAtom, prev => prev.filter(t => t.status === 'active'));
}
