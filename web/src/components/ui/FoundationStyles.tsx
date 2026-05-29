import { useEffect } from 'react';

const STYLE_ID = 'bionodulo-ui-foundation-styles';

const FOUNDATION_CSS = `
.bn-ui-toast-viewport {
  position: fixed;
  top: 56px;
  right: 12px;
  z-index: 900;
  display: flex;
  flex-direction: column;
  gap: 8px;
  width: min(380px, calc(100vw - 24px));
  pointer-events: none;
}
.bn-ui-toast {
  pointer-events: auto;
  overflow: hidden;
  border: 1px solid var(--border);
  border-left: 4px solid var(--accent);
  border-radius: 8px;
  background: var(--surface);
  color: var(--text);
  box-shadow: var(--shadow-lg);
  animation: bnUiToastIn 160ms ease;
}
.bn-ui-toast[data-tone="success"] { border-left-color: var(--success); }
.bn-ui-toast[data-tone="warning"] { border-left-color: var(--warning); }
.bn-ui-toast[data-tone="error"] { border-left-color: var(--danger); }
.bn-ui-toast[data-tone="loading"] { border-left-color: var(--accent); }
.bn-ui-toast-row {
  display: grid;
  grid-template-columns: 20px minmax(0, 1fr) auto;
  gap: 10px;
  padding: 10px 12px;
}
.bn-ui-toast-icon {
  width: 20px;
  height: 20px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  color: var(--accent-dark);
}
.bn-ui-toast[data-tone="success"] .bn-ui-toast-icon { color: var(--success); }
.bn-ui-toast[data-tone="warning"] .bn-ui-toast-icon { color: var(--warning); }
.bn-ui-toast[data-tone="error"] .bn-ui-toast-icon { color: var(--danger); }
.bn-ui-toast-title {
  font-size: 12px;
  font-weight: 700;
  line-height: 1.35;
}
.bn-ui-toast-message {
  margin-top: 2px;
  color: var(--text-2);
  font-size: 12px;
  line-height: 1.45;
}
.bn-ui-toast-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 8px;
}
.bn-ui-toast-progress {
  height: 3px;
  background: var(--surface-3);
}
.bn-ui-toast-progress > span {
  display: block;
  height: 100%;
  width: 0;
  background: currentColor;
  color: var(--accent);
  transition: width 120ms linear;
}
.bn-ui-toast[data-tone="success"] .bn-ui-toast-progress > span { color: var(--success); }
.bn-ui-toast[data-tone="warning"] .bn-ui-toast-progress > span { color: var(--warning); }
.bn-ui-toast[data-tone="error"] .bn-ui-toast-progress > span { color: var(--danger); }
.bn-ui-icon-button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border: 0;
  border-radius: 6px;
  background: transparent;
  color: var(--muted);
  cursor: pointer;
}
.bn-ui-icon-button:hover {
  background: var(--surface-2);
  color: var(--text);
}
.bn-ui-button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  min-height: 30px;
  padding: 6px 12px;
  border: 1px solid var(--border-2);
  border-radius: 6px;
  background: var(--surface);
  color: var(--text);
  font: inherit;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
}
.bn-ui-button:hover { background: var(--surface-2); }
.bn-ui-button-primary {
  background: var(--accent);
  border-color: var(--accent-dark);
  color: #fff;
}
.bn-ui-button-primary:hover { background: var(--accent-dark); }
.bn-ui-button-danger {
  background: var(--danger);
  border-color: var(--danger);
  color: #fff;
}
.bn-ui-button-ghost {
  background: transparent;
  border-color: transparent;
  color: var(--muted);
}
.bn-ui-button-ghost:hover {
  background: var(--surface-2);
  color: var(--text);
}
.bn-ui-overlay {
  position: fixed;
  inset: 0;
  z-index: 850;
  display: flex;
  align-items: flex-start;
  justify-content: center;
  padding: 10vh 16px 16px;
  background: rgba(0,0,0,0.42);
}
.bn-ui-dialog,
.bn-ui-command,
.bn-ui-shortcuts {
  width: min(560px, 100%);
  max-height: 82vh;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--surface);
  color: var(--text);
  box-shadow: var(--shadow-lg);
  animation: bnUiDialogIn 140ms ease;
}
.bn-ui-dialog { max-width: 440px; }
.bn-ui-command { max-width: 680px; }
.bn-ui-shortcuts { max-width: 820px; }
.bn-ui-dialog-header,
.bn-ui-shortcuts-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 14px 16px;
  border-bottom: 1px solid var(--border);
}
.bn-ui-dialog-title,
.bn-ui-shortcuts-title {
  font-size: 14px;
  font-weight: 700;
}
.bn-ui-dialog-body,
.bn-ui-shortcuts-body {
  padding: 16px;
  overflow: auto;
}
.bn-ui-dialog-body {
  color: var(--text-2);
  font-size: 13px;
  line-height: 1.5;
}
.bn-ui-dialog-field {
  display: grid;
  gap: 6px;
  margin-top: 14px;
  color: var(--muted);
  font-size: 12px;
}
.bn-ui-dialog-input {
  width: 100%;
  min-height: 34px;
  border: 1px solid var(--border-2);
  border-radius: 6px;
  background: var(--surface-2);
  color: var(--text);
  font: inherit;
  font-size: 13px;
  padding: 7px 9px;
  outline: none;
}
.bn-ui-dialog-input:focus {
  border-color: var(--accent);
  box-shadow: 0 0 0 2px var(--accent-light);
}
.bn-ui-dialog-footer,
.bn-ui-shortcuts-footer {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 8px;
  padding: 12px 16px;
  border-top: 1px solid var(--border);
}
.bn-ui-tooltip-trigger {
  display: inline-flex;
}
.bn-ui-tooltip {
  position: fixed;
  z-index: 950;
  max-width: 260px;
  padding: 6px 8px;
  border: 1px solid var(--border);
  border-radius: 6px;
  background: var(--text);
  color: var(--surface);
  box-shadow: var(--shadow);
  font-size: 11px;
  line-height: 1.35;
  pointer-events: none;
}
.bn-ui-command-input-wrap {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 14px;
  border-bottom: 1px solid var(--border);
}
.bn-ui-command-input,
.bn-ui-shortcuts-search,
.bn-ui-shortcut-input {
  width: 100%;
  min-width: 0;
  border: 1px solid var(--border);
  border-radius: 6px;
  background: var(--surface-2);
  color: var(--text);
  font: inherit;
  font-size: 13px;
  outline: none;
}
.bn-ui-command-input {
  border: 0;
  background: transparent;
  font-size: 14px;
}
.bn-ui-command-input:focus,
.bn-ui-shortcuts-search:focus,
.bn-ui-shortcut-input:focus {
  border-color: var(--accent);
}
.bn-ui-command-list {
  max-height: min(58vh, 520px);
  overflow: auto;
  padding: 8px;
}
.bn-ui-command-group {
  margin: 8px 0 4px;
  padding: 0 8px;
  color: var(--muted);
  font-size: 10px;
  font-weight: 800;
  letter-spacing: 0.06em;
  text-transform: uppercase;
}
.bn-ui-command-item {
  width: 100%;
  display: grid;
  grid-template-columns: 22px minmax(0, 1fr) auto;
  align-items: center;
  gap: 10px;
  padding: 9px 10px;
  border: 0;
  border-radius: 6px;
  background: transparent;
  color: var(--text);
  text-align: left;
  cursor: pointer;
}
.bn-ui-command-item[aria-selected="true"] {
  background: var(--accent-light);
  color: var(--accent-dark);
}
.bn-ui-command-item:disabled {
  cursor: not-allowed;
  opacity: 0.45;
}
.bn-ui-command-label {
  font-size: 13px;
  font-weight: 650;
}
.bn-ui-command-description {
  margin-top: 1px;
  color: var(--muted);
  font-size: 11px;
}
.bn-ui-empty {
  padding: 24px 16px;
  color: var(--muted);
  text-align: center;
  font-size: 12px;
}
.bn-ui-kbd-list {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  white-space: nowrap;
}
.bn-ui-shortcuts-tools {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
}
.bn-ui-shortcuts-search {
  padding: 7px 10px;
}
.bn-ui-shortcut-section {
  margin-top: 14px;
}
.bn-ui-shortcut-section:first-child {
  margin-top: 0;
}
.bn-ui-shortcut-section-title {
  margin-bottom: 6px;
  color: var(--muted);
  font-size: 10px;
  font-weight: 800;
  letter-spacing: 0.06em;
  text-transform: uppercase;
}
.bn-ui-shortcut-row {
  display: grid;
  grid-template-columns: minmax(180px, 1fr) minmax(160px, 220px) auto;
  align-items: center;
  gap: 10px;
  padding: 8px 0;
  border-top: 1px solid var(--border);
}
.bn-ui-shortcut-label {
  font-size: 12px;
  font-weight: 650;
}
.bn-ui-shortcut-desc {
  margin-top: 2px;
  color: var(--muted);
  font-size: 11px;
}
.bn-ui-shortcut-input {
  padding: 6px 8px;
  text-align: center;
  cursor: pointer;
}
.bn-ui-shortcut-input[data-recording="true"] {
  border-color: var(--accent);
  color: var(--accent-dark);
}
.bn-ui-shortcut-conflict {
  color: var(--danger);
  font-size: 10px;
  font-weight: 700;
}
@keyframes bnUiToastIn {
  from { opacity: 0; transform: translateY(-6px); }
  to { opacity: 1; transform: translateY(0); }
}
@keyframes bnUiDialogIn {
  from { opacity: 0; transform: translateY(-6px) scale(0.98); }
  to { opacity: 1; transform: translateY(0) scale(1); }
}
@media (max-width: 720px) {
  .bn-ui-toast-viewport { top: 8px; right: 8px; width: calc(100vw - 16px); }
  .bn-ui-overlay { padding-top: 8px; align-items: flex-start; }
  .bn-ui-shortcut-row {
    grid-template-columns: 1fr;
    gap: 6px;
  }
}
`;

export function ensureFoundationStyles() {
  if (typeof document === 'undefined' || document.getElementById(STYLE_ID)) return;
  const style = document.createElement('style');
  style.id = STYLE_ID;
  style.textContent = FOUNDATION_CSS;
  document.head.appendChild(style);
}

export function useFoundationStyles() {
  useEffect(() => {
    ensureFoundationStyles();
  }, []);
}

export function FoundationStyles() {
  useFoundationStyles();
  return null;
}
