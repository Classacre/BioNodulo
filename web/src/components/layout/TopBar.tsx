import Icon from '../ui/Icon';
import type { ReactNode } from 'react';

export type HPCStatus = 'off' | 'error' | 'on';

interface TopBarProps {
  validationValid: boolean;
  validationErrors: string[];
  onRun: () => void;
  onExport: () => void;
  onImport: () => void;
  onAI: () => void;
  onBatchSheet?: () => void;
  hpcStatus: HPCStatus;
  isRunning: boolean;
  queueCount: number;
  batchCount: number;
  queueMode?: 'manual' | 'change' | 'instant';
  onQueueModeChange?: (mode: 'manual' | 'change' | 'instant') => void;
  onToggleQueue: () => void;
  onBatchCountChange: (count: number) => void;
  collabControls?: ReactNode;
  autoSaveLabel?: string;
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

export default function TopBar({
  validationValid, validationErrors, onRun, onExport, onImport,
  onAI, onBatchSheet, hpcStatus, isRunning, queueCount, batchCount,
  queueMode = 'manual', onQueueModeChange,
  onToggleQueue, onBatchCountChange, collabControls, autoSaveLabel,
}: TopBarProps) {
  const hpcBadgeClass =
    hpcStatus === 'on' ? 'hpc-badge hpc-on' :
    hpcStatus === 'error' ? 'hpc-badge hpc-error' :
    'hpc-badge hpc-off';

  const hpcLabel =
    hpcStatus === 'on' ? 'HPC ON' :
    hpcStatus === 'error' ? 'HPC ERROR' :
    'HPC OFF';

  return (
    <header className="topbar">
      <div className="brand">
        <BrandMark />
        <strong>BioNodulo</strong>
        <small>2.0</small>
      </div>

      <div className="validation-badge" style={{ visibility: validationErrors.length ? 'visible' : 'hidden' }}>
        {validationValid
          ? <span className="ok"><Icon name="circle" size={12} /> Valid</span>
          : <span className="err"><Icon name="circle" size={12} /> {validationErrors.length} issues</span>
        }
      </div>

      <div className="topbar-spacer" />

      <span className={hpcBadgeClass} title={`HPC ${hpcStatus.toUpperCase()}`}>
        <Icon name="server" size={14} /> {hpcLabel}
      </span>

      {collabControls}

      {autoSaveLabel && (
        <span className="autosave-badge" title={autoSaveLabel}>
          <Icon name="check" size={12} /> {autoSaveLabel}
        </span>
      )}

      <div className="run-cluster">
        <button className="btn btn-sm" onClick={onToggleQueue} title="Show queue">
          {queueCount > 0 && <span className="pulse-dot" />}
          Queue: {queueCount}
        </button>
        <div className="batch-stepper" title="Batch count">
          <button
            className="btn btn-icon btn-sm"
            disabled={batchCount <= 1 || isRunning}
            onClick={() => onBatchCountChange(batchCount - 1)}
            type="button"
            aria-label="Decrease batch count"
            title="Decrease batch count"
          >
            <Icon name="minus" size={12} />
          </button>
          <input
            aria-label="Batch count"
            disabled={isRunning}
            max={99}
            min={1}
            onChange={(event) => {
              const next = Number.parseInt(event.target.value, 10);
              onBatchCountChange(Number.isFinite(next) ? next : 1);
            }}
            type="number"
            value={batchCount}
          />
          <button
            className="btn btn-icon btn-sm"
            disabled={batchCount >= 99 || isRunning}
            onClick={() => onBatchCountChange(batchCount + 1)}
            type="button"
            aria-label="Increase batch count"
            title="Increase batch count"
          >
            <Icon name="plus" size={12} />
          </button>
        </div>
        {onBatchSheet && (
          <button
            className="btn btn-sm"
            onClick={onBatchSheet}
            disabled={isRunning}
            title="Batch from sample sheet (CSV/TSV)"
            type="button"
          >
            <Icon name="template" size={12} /> Sheet
          </button>
        )}
        <button className="btn btn-primary btn-sm" onClick={onRun} disabled={isRunning}>
          {isRunning ? <><Icon name="stop" size={14} /> Running...</> : <><Icon name="play" size={14} /> Run</>}
        </button>
        {onQueueModeChange && (
          <select
            value={queueMode}
            onChange={event => onQueueModeChange(event.target.value as 'manual' | 'change' | 'instant')}
            title="Auto-queue mode"
            style={{
              padding: '4px 8px',
              fontSize: 11,
              borderRadius: 6,
              border: '1px solid var(--border)',
              background: queueMode === 'manual' ? 'var(--surface-2)' : 'color-mix(in srgb, var(--accent) 18%, var(--surface-2))',
              color: 'var(--text)',
            }}
          >
            <option value="manual">Manual</option>
            <option value="change">On change</option>
            <option value="instant">Instant</option>
          </select>
        )}
        <button className="btn btn-sm" onClick={onExport} title="Export workflow" aria-label="Export workflow">
          <Icon name="export" size={14} />
        </button>
        <button className="btn btn-sm" onClick={onImport} title="Import workflow" aria-label="Import workflow">
          <Icon name="import" size={14} />
        </button>
        <button className="btn btn-ai btn-sm" onClick={onAI} title="AI Assistant" aria-label="Open AI assistant">
          <Icon name="wand" size={14} />
        </button>
      </div>
    </header>
  );
}
