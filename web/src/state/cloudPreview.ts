import { atom } from 'jotai';
import type { CloudPreviewOutput } from '../utils/cloudPreview';

export interface CloudPreviewSelection { runId: string; output: CloudPreviewOutput; scope: string }
export const cloudPreviewSelectionAtom = atom<CloudPreviewSelection | null>(null);
export const cloudNodeOutputsAtom = atom<Record<string, { runId: string; outputs: CloudPreviewOutput[] }>>({});
