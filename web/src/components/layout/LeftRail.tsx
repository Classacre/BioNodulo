import Icon from '../ui/Icon';
import { Tooltip } from '../ui';
import { usePanelRegistry } from '../../state/panels';
import { useKeybindings } from '../../hooks/useKeybindings';

export type RailTab = 'data' | 'nodes' | 'templates' | 'environments' | 'help' | 'console' | 'settings' | 'hpc' | string | null;

interface LeftRailProps {
  active: RailTab;
  onChange: (tab: RailTab) => void;
}

interface RailButtonProps {
  active: boolean;
  icon: string;
  label: string;
  shortcut?: string;
  onClick: () => void;
}

function RailButton({ active, icon, label, shortcut, onClick }: RailButtonProps) {
  const titleText = shortcut ? `${label} (${shortcut})` : label;
  return (
    <Tooltip
      placement="right"
      content={
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}>
          <span>{label}</span>
          {shortcut && (
            <kbd
              style={{
                fontFamily: 'JetBrains Mono, ui-monospace, monospace',
                fontSize: 10,
                padding: '1px 5px',
                borderRadius: 3,
                background: 'rgba(148,163,184,0.18)',
                border: '1px solid rgba(148,163,184,0.35)',
              }}
            >
              {shortcut}
            </kbd>
          )}
        </span>
      }
    >
      <button
        className={`rail-btn ${active ? 'active' : ''}`}
        onClick={onClick}
        title={titleText}
        aria-label={titleText}
        type="button"
      >
        <Icon name={icon} size={18} />
      </button>
    </Tooltip>
  );
}

export default function LeftRail({ active, onChange }: LeftRailProps) {
  const toggle = (tab: RailTab) => onChange(active === tab ? null : tab);
  const registered = usePanelRegistry();
  const { getBinding } = useKeybindings();

  return (
    <nav className="left-rail">
      <RailButton active={active === 'data'} icon="folder" label="Data" shortcut={getBinding('rail.workspace') ?? undefined} onClick={() => toggle('data')} />
      <RailButton active={active === 'nodes'} icon="nodes" label="Nodes" shortcut={getBinding('rail.nodes') ?? undefined} onClick={() => toggle('nodes')} />
      <RailButton active={active === 'templates'} icon="template" label="Templates" shortcut={getBinding('rail.templates') ?? undefined} onClick={() => toggle('templates')} />
      <div className="rail-sep" />
      <RailButton active={active === 'environments'} icon="dna" label="Environments" shortcut={getBinding('rail.environment') ?? undefined} onClick={() => toggle('environments')} />
      <RailButton active={active === 'hpc'} icon="server" label="HPC" shortcut={getBinding('rail.hpc') ?? undefined} onClick={() => toggle('hpc')} />
      {registered.length > 0 && <div className="rail-sep" />}
      {registered.map(panel => (
        <RailButton
          key={panel.id}
          active={active === panel.id}
          icon={panel.icon}
          label={panel.title}
          shortcut={panel.shortcutTitle}
          onClick={() => toggle(panel.id)}
        />
      ))}
      <div className="rail-sep" />
      <RailButton active={active === 'help'} icon="help" label="Help / Wiki" shortcut={getBinding('rail.help') ?? undefined} onClick={() => toggle('help')} />
      <RailButton active={active === 'console'} icon="console" label="Console" shortcut={getBinding('rail.console') ?? undefined} onClick={() => toggle('console')} />
      <div className="rail-sep" />
      <RailButton active={active === 'settings'} icon="settings" label="Settings" shortcut={getBinding('settings.toggle') ?? undefined} onClick={() => toggle('settings')} />
    </nav>
  );
}
