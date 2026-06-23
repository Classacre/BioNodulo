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
// Cloud editor: pick a saved workflow to open as a tab (or create a new one).
export const showOpenWorkflowAtom = atom(false);

// Collab overlay flags
export const showInviteDialogAtom = atom(false);
export const showShareDialogAtom = atom(false);
export const showCommentsAtom = atom(false);
export const showVersionsAtom = atom(false);
export const showAuditAtom = atom(false);

// UI selection / shell state
export const selectedNodeIdAtom = atom<string | null>(null);
export const consoleVisibleAtom = atom(false);

const FOCUS_MODE_KEY = 'bionodulo.focus_mode';
const LEGACY_FOCUS_MODE_KEY = 'bionodulo.focusMode';

function parseStoredBool(raw: string | null, fallback: boolean): boolean {
  if (raw === null) return fallback;
  if (raw === '1' || raw === 'true') return true;
  if (raw === '0' || raw === 'false') return false;
  try {
    return Boolean(JSON.parse(raw));
  } catch {
    return fallback;
  }
}

// Focus mode is now stored under bionodulo.focus_mode, but older builds used
// bionodulo.focusMode with "1"/"0" values. Read both so existing sessions keep
// their preference, then write both while the transition is active.
export const focusModeAtom = atomWithStorage<boolean>(FOCUS_MODE_KEY, false, {
  getItem: (_key, initialValue) => {
    try {
      const raw = localStorage.getItem(FOCUS_MODE_KEY);
      if (raw !== null) return parseStoredBool(raw, initialValue);
      const legacyRaw = localStorage.getItem(LEGACY_FOCUS_MODE_KEY);
      const migrated = parseStoredBool(legacyRaw, initialValue);
      if (legacyRaw !== null) localStorage.setItem(FOCUS_MODE_KEY, String(migrated));
      return migrated;
    } catch {
      return initialValue;
    }
  },
  setItem: (_key, value) => {
    localStorage.setItem(FOCUS_MODE_KEY, String(value));
    localStorage.setItem(LEGACY_FOCUS_MODE_KEY, value ? '1' : '0');
  },
  removeItem: () => {
    localStorage.removeItem(FOCUS_MODE_KEY);
    localStorage.removeItem(LEGACY_FOCUS_MODE_KEY);
  },
});
