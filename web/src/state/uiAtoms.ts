import { atom } from 'jotai';
import { atomWithStorage } from 'jotai/utils';

// Modal open flags — boolean atoms, default false.
// Children use useSetAtom/useAtomValue to open/close without prop-drilling.
export const showExportAtom = atom(false);
export const showImportAtom = atom(false);
export const showOutputDiffAtom = atom(false);
export const showBulkParamAtom = atom(false);
export const showDoctorAtom = atom(false);
export const showAIAtom = atom(false);
export const showBatchSheetAtom = atom(false);
export const showGettingStartedAtom = atom(false);
export const showShortcutsAtom = atom(false);

// Collab overlay flags
export const showShareDialogAtom = atom(false);
export const showCommentsAtom = atom(false);
export const showVersionsAtom = atom(false);
export const showAuditAtom = atom(false);

// UI selection / shell state
export const selectedNodeIdAtom = atom<string | null>(null);
export const consoleVisibleAtom = atom(false);
/** Focus mode — persisted across sessions. */
export const focusModeAtom = atomWithStorage<boolean>('bionodulo.focus_mode', false);
