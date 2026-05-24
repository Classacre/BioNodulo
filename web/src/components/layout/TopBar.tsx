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
  hpcStatus: HPCStatus;
  isRunning: boolean;
  queueCount: number;
  onToggleQueue: () => void;
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

export default function TopBar({
  validationValid, validationErrors, onRun, onExport, onImport,
  onAI, hpcStatus, isRunning, queueCount, onToggleQueue, collabControls,
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
        <small>Alpha 1.5</small>
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

      <div className="run-cluster">
        <button className="btn btn-sm" onClick={onToggleQueue} title="Show queue">
          {queueCount > 0 && <span className="pulse-dot" />}
          Queue: {queueCount}
        </button>
        <button className="btn btn-primary btn-sm" onClick={onRun} disabled={isRunning}>
          {isRunning ? <><Icon name="stop" size={14} /> Running...</> : <><Icon name="play" size={14} /> Run</>}
        </button>
        <button className="btn btn-sm" onClick={onExport} title="Export workflow">
          <Icon name="export" size={14} />
        </button>
        <button className="btn btn-sm" onClick={onImport} title="Import workflow">
          <Icon name="import" size={14} />
        </button>
        <button className="btn btn-ai btn-sm" onClick={onAI} title="AI Assistant">
          <Icon name="wand" size={14} />
        </button>
      </div>
    </header>
  );
}
