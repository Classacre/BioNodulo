import Icon from '../ui/Icon';

interface TopBarProps {
  validationValid: boolean;
  validationErrors: string[];
  onRun: () => void;
  onExport: () => void;
  onImport: () => void;
  onAI: () => void;
  hpcEnabled: boolean;
  onToggleHPC: () => void;
  isRunning: boolean;
  queueCount: number;
  onToggleQueue: () => void;
}

export default function TopBar({
  validationValid, validationErrors, onRun, onExport, onImport,
  onAI, hpcEnabled, onToggleHPC, isRunning, queueCount, onToggleQueue,
}: TopBarProps) {
  return (
    <header className="topbar">
      <div className="brand">
        <span className="mark">B</span>
        <strong>BioNodulo</strong>
        <small>Alpha 1.1</small>
      </div>

      <div className="validation-badge" style={{ visibility: validationErrors.length ? 'visible' : 'hidden' }}>
        {validationValid
          ? <span className="ok"><Icon name="circle" size={12} /> Valid</span>
          : <span className="err"><Icon name="circle" size={12} /> {validationErrors.length} issues</span>
        }
      </div>

      <div className="topbar-spacer" />

      <button
        className={`btn ${hpcEnabled ? 'btn-primary' : ''} btn-sm`}
        onClick={onToggleHPC}
        title={hpcEnabled ? 'HPC Enabled' : 'HPC Disabled'}
      >
        <Icon name="server" size={14} /> HPC {hpcEnabled ? 'ON' : 'OFF'}
      </button>

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
