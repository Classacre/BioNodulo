import { useEffect, useRef, useState } from 'react';
import type { ReactNode } from 'react';
import { useAtom, useAtomValue, useSetAtom } from 'jotai';
import { useTranslation } from 'react-i18next';
import Icon from '../ui/Icon';
import { useKeybindings } from '../../hooks/ui';
import { batchCountAtom, isRunningAtom } from '../../state/runAtoms';
import { showAIAtom, showBatchSheetAtom, showExportAtom } from '../../state/uiAtoms';

export type HPCStatus = 'off' | 'error' | 'on';
export type QueueMode = 'manual' | 'change' | 'instant';

function withShortcut(label: string, binding?: string | null): string {
  return binding ? `${label} (${binding})` : label;
}

interface TopBarProps {
  validationValid: boolean;
  validationErrors: string[];
  onRun: () => void;
  hpcStatus: HPCStatus;
  /** When false, the HPC badge is hidden entirely (settings.hpc.enabled is off). */
  hpcEnabled?: boolean;
  queueCount: number;
  queueMode?: QueueMode;
  onQueueModeChange?: (mode: QueueMode) => void;
  dryRunPreview?: boolean;
  onDryRunPreviewChange?: (enabled: boolean) => void;
  resumeCheckpointLabel?: string | null;
  onOpenRuntimeArtifacts?: () => void;
  onResumeCheckpointClear?: () => void;
  onToggleQueue: () => void;
  /**
   * When defined, rendered to the right of the validation badge — usually the
   * `<CollabBadge />`. When collab is disabled in settings the caller should
   * pass `null` so nothing is rendered (instead of a hollow placeholder).
   */
  collabControls?: ReactNode;
}

function BrandMark() {
  return (
    <svg className="mark" viewBox="0 0 64 64" aria-hidden="true">
      <rect width="64" height="64" rx="18" fill="#111314" />
      <circle cx="19" cy="22" r="7" fill="#7ee6b4" />
      <circle cx="45" cy="20" r="7" fill="#d7f36b" />
      <circle cx="32" cy="44" r="8" fill="#8fb7ff" />
      <path d="M25 22h13M23 28l6 10M41 27l-6 11" stroke="#f5f1e8" strokeWidth="4" strokeLinecap="round" />
    </svg>
  );
}

const QUEUE_MODE_KEYS: Record<QueueMode, string> = {
  manual: 'topbar.queueModeManual',
  change: 'topbar.queueModeChange',
  instant: 'topbar.queueModeInstant',
};

export default function TopBar({
  validationValid, validationErrors, onRun, hpcStatus, hpcEnabled = false,
  queueCount,
  queueMode = 'manual', onQueueModeChange,
  dryRunPreview = false, onDryRunPreviewChange,
  resumeCheckpointLabel = null, onOpenRuntimeArtifacts, onResumeCheckpointClear,
  onToggleQueue, collabControls,
}: TopBarProps) {
  const isRunning = useAtomValue(isRunningAtom);
  const [batchCount, setBatchCount] = useAtom(batchCountAtom);
  const setShowExport = useSetAtom(showExportAtom);
  const setShowAI = useSetAtom(showAIAtom);
  const setShowBatchSheet = useSetAtom(showBatchSheetAtom);
  const { t } = useTranslation();
  const { getBinding } = useKeybindings();
  const runShortcut = getBinding('workflow.run');
  const exportShortcut = getBinding('workflow.export');
  const aiShortcut = getBinding('ai.open');
  const queueModeLabel = t(QUEUE_MODE_KEYS[queueMode]);

  // Split-button menu next to Run: queue mode radios + sheet action.
  const [runMenuOpen, setRunMenuOpen] = useState(false);
  const runMenuRef = useRef<HTMLDivElement | null>(null);
  useEffect(() => {
    if (!runMenuOpen) return;
    const onDocClick = (event: MouseEvent) => {
      if (!runMenuRef.current) return;
      if (!runMenuRef.current.contains(event.target as Node)) setRunMenuOpen(false);
    };
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setRunMenuOpen(false);
    };
    document.addEventListener('mousedown', onDocClick);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('mousedown', onDocClick);
      document.removeEventListener('keydown', onKey);
    };
  }, [runMenuOpen]);

  const hpcBadgeClass =
    hpcStatus === 'on' ? 'hpc-badge hpc-on' :
    hpcStatus === 'error' ? 'hpc-badge hpc-error' :
    'hpc-badge hpc-off';

  const hpcLabel =
    hpcStatus === 'on' ? t('topbar.hpcOn') :
    hpcStatus === 'error' ? t('topbar.hpcError') :
    t('topbar.hpcOff');

  const clampedCount = Math.max(1, Math.min(99, batchCount));
  const updateBatchCount = (count: number) => {
    setBatchCount(Math.max(1, Math.min(99, count)));
  };

  return (
    <header className="topbar">
      <div className="brand">
        <BrandMark />
        <strong>BioNodulo</strong>
        <small>2.0</small>
      </div>

      <div className="validation-badge" style={{ visibility: validationErrors.length ? 'visible' : 'hidden' }}>
        {validationValid
          ? <span className="ok"><Icon name="circle" size={12} /> {t('topbar.validationValid')}</span>
          : <span className="err"><Icon name="circle" size={12} /> {t('topbar.validationIssues', { count: validationErrors.length })}</span>
        }
      </div>

      <div className="topbar-spacer" />

      {hpcEnabled && (
        <span className={hpcBadgeClass} title={hpcLabel}>
          <Icon name="server" size={14} /> {hpcLabel}
        </span>
      )}

      {collabControls}

      <div className="run-cluster">
        <button className="btn btn-sm" onClick={onToggleQueue} title={t('topbar.showQueue')}>
          {queueCount > 0 && <span className="pulse-dot" />}
          {t('topbar.queueCount', { count: queueCount })}
        </button>

        {/* Split-button: primary Run on the left, chevron dropdown on the
            right (batch stepper + queue mode + sheet). The two halves share
            a single border / background so they read as one control with a
            thin `|` separator. Batch count lives inside the menu now so it
            doesn't crowd the top bar. */}
        <div className="run-split-button" ref={runMenuRef}>
          <button
            className="btn btn-primary btn-sm run-split-main"
            onClick={onRun}
            disabled={isRunning}
            title={withShortcut(isRunning ? t('topbar.running') : t('topbar.runWorkflow'), runShortcut)}
            aria-label={withShortcut(isRunning ? t('topbar.running') : t('topbar.runWorkflow'), runShortcut)}
          >
            {isRunning
              ? <><Icon name="stop" size={14} /> {t('topbar.runningEllipsis')}</>
              : <><Icon name="play" size={14} /> {t('topbar.run')}</>}
          </button>
          <button
            type="button"
            className={`btn btn-primary btn-sm run-split-toggle ${runMenuOpen ? 'is-open' : ''}`}
            onClick={() => setRunMenuOpen(open => !open)}
            aria-haspopup="menu"
            aria-expanded={runMenuOpen}
            aria-label={t('topbar.runOptions')}
            title={t('topbar.runOptionsTitle', { count: clampedCount, mode: queueModeLabel })}
          >
            <Icon name="chevronDown" size={12} />
          </button>

          {runMenuOpen && (
            <div className="run-split-menu" role="menu">
              <div className="run-split-menu-header">{t('topbar.batchCount')}</div>
              <div className="run-split-menu-batch">
                <button
                  type="button"
                  className="run-split-menu-batch-btn"
                  aria-label={t('topbar.decreaseBatchCount')}
                  title={t('topbar.decreaseBatchCount')}
                  disabled={clampedCount <= 1 || isRunning}
                  onClick={() => updateBatchCount(clampedCount - 1)}
                >
                  <Icon name="minus" size={12} />
                </button>
                <span className="run-split-menu-batch-value" aria-label={t('topbar.batchCount')}>
                  {clampedCount}
                </span>
                <button
                  type="button"
                  className="run-split-menu-batch-btn"
                  aria-label={t('topbar.increaseBatchCount')}
                  title={t('topbar.increaseBatchCount')}
                  disabled={clampedCount >= 99 || isRunning}
                  onClick={() => updateBatchCount(clampedCount + 1)}
                >
                  <Icon name="plus" size={12} />
                </button>
                <span className="run-split-menu-batch-suffix">
                  {t('topbar.batchRuns', { count: clampedCount })}
                </span>
              </div>
              <div className="run-split-menu-divider" />
              <div className="run-split-menu-header">{t('topbar.preview')}</div>
              <button
                type="button"
                role="menuitemcheckbox"
                aria-checked={dryRunPreview}
                className={`run-split-menu-item ${dryRunPreview ? 'is-active' : ''}`}
                onClick={() => onDryRunPreviewChange?.(!dryRunPreview)}
                disabled={isRunning || !onDryRunPreviewChange}
              >
                <span className="run-split-menu-radio">{dryRunPreview ? '●' : '○'}</span>
                {t('topbar.dryRunPreview')}
              </button>
              <div className="run-split-menu-checkpoint">
                <span className="run-split-menu-checkpoint-label">{t('topbar.resumeCheckpoint')}</span>
                <span
                  className="run-split-menu-checkpoint-value"
                  title={resumeCheckpointLabel ?? t('topbar.noResumeCheckpoint')}
                >
                  {resumeCheckpointLabel ?? t('topbar.noResumeCheckpoint')}
                </span>
              </div>
              <button
                type="button"
                role="menuitem"
                className="run-split-menu-item"
                onClick={() => {
                  onOpenRuntimeArtifacts?.();
                  setRunMenuOpen(false);
                }}
                disabled={isRunning || !onOpenRuntimeArtifacts}
              >
                <Icon name="template" size={12} /> {t('topbar.chooseCheckpoint')}
              </button>
              {resumeCheckpointLabel && (
                <button
                  type="button"
                  role="menuitem"
                  className="run-split-menu-item"
                  onClick={() => {
                    onResumeCheckpointClear?.();
                    setRunMenuOpen(false);
                  }}
                  disabled={isRunning || !onResumeCheckpointClear}
                >
                  <Icon name="close" size={12} /> {t('topbar.clearResumeCheckpoint')}
                </button>
              )}
              <div className="run-split-menu-divider" />
              <div className="run-split-menu-header">{t('topbar.queueMode')}</div>
              {(['manual', 'change', 'instant'] as QueueMode[]).map(mode => (
                <button
                  key={mode}
                  type="button"
                  role="menuitemradio"
                  aria-checked={queueMode === mode}
                  className={`run-split-menu-item ${queueMode === mode ? 'is-active' : ''}`}
                  onClick={() => {
                    onQueueModeChange?.(mode);
                    setRunMenuOpen(false);
                  }}
                >
                  <span className="run-split-menu-radio">{queueMode === mode ? '●' : '○'}</span>
                  {t(QUEUE_MODE_KEYS[mode])}
                </button>
              ))}
              <div className="run-split-menu-divider" />
              <button
                type="button"
                role="menuitem"
                className="run-split-menu-item"
                onClick={() => {
                  setShowBatchSheet(true);
                  setRunMenuOpen(false);
                }}
                disabled={isRunning}
              >
                <Icon name="template" size={12} /> {t('topbar.batchFromSheet')}
              </button>
            </div>
          )}
        </div>

        {/* Drag-and-drop into the canvas already covers import, so the
            standalone Import button has been removed. Export icon swapped to
            visually match its action (out-of-app). */}
        <button
          className="btn btn-sm"
          onClick={() => setShowExport(true)}
          title={withShortcut(t('topbar.exportWorkflow'), exportShortcut)}
          aria-label={withShortcut(t('topbar.exportWorkflow'), exportShortcut)}
        >
          <Icon name="import" size={14} />
        </button>
        <button
          className="btn btn-ai btn-sm"
          onClick={() => setShowAI(true)}
          title={withShortcut(t('topbar.aiAssistant'), aiShortcut)}
          aria-label={withShortcut(t('topbar.openAiAssistant'), aiShortcut)}
        >
          <Icon name="wand" size={14} />
        </button>
      </div>
    </header>
  );
}
