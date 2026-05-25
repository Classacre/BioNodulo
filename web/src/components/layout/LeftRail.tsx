import Icon from '../ui/Icon';
import { usePanelRegistry } from '../../state/panels';

export type RailTab = 'data' | 'nodes' | 'templates' | 'environments' | 'help' | 'console' | 'settings' | 'hpc' | string | null;

interface LeftRailProps {
  active: RailTab;
  onChange: (tab: RailTab) => void;
}

export default function LeftRail({ active, onChange }: LeftRailProps) {
  const toggle = (tab: RailTab) => onChange(active === tab ? null : tab);
  const registered = usePanelRegistry();

  return (
    <nav className="left-rail">
      <button className={`rail-btn ${active === 'data' ? 'active' : ''}`} onClick={() => toggle('data')} title="Data (Ctrl+1)">
        <Icon name="folder" size={18} />
      </button>
      <button className={`rail-btn ${active === 'nodes' ? 'active' : ''}`} onClick={() => toggle('nodes')} title="Nodes (Ctrl+2)">
        <Icon name="nodes" size={18} />
      </button>
      <button className={`rail-btn ${active === 'templates' ? 'active' : ''}`} onClick={() => toggle('templates')} title="Templates (Ctrl+3)">
        <Icon name="template" size={18} />
      </button>
      <div className="rail-sep" />
      <button className={`rail-btn ${active === 'environments' ? 'active' : ''}`} onClick={() => toggle('environments')} title="Environments (Ctrl+4)">
        <Icon name="dna" size={18} />
      </button>
      <button className={`rail-btn ${active === 'hpc' ? 'active' : ''}`} onClick={() => toggle('hpc')} title="HPC (Ctrl+5)">
        <Icon name="server" size={18} />
      </button>
      {registered.length > 0 && <div className="rail-sep" />}
      {registered.map(panel => (
        <button
          key={panel.id}
          className={`rail-btn ${active === panel.id ? 'active' : ''}`}
          onClick={() => toggle(panel.id)}
          title={`${panel.title}${panel.shortcutTitle ? ` (${panel.shortcutTitle})` : ''}`}
        >
          <Icon name={panel.icon} size={18} />
        </button>
      ))}
      <div className="rail-sep" />
      <button className={`rail-btn ${active === 'help' ? 'active' : ''}`} onClick={() => toggle('help')} title="Help / Wiki (Ctrl+6)">
        <Icon name="help" size={18} />
      </button>
      <button className={`rail-btn ${active === 'console' ? 'active' : ''}`} onClick={() => toggle('console')} title="Console (Ctrl+7)">
        <Icon name="console" size={18} />
      </button>
      <div className="rail-sep" />
      <button className={`rail-btn ${active === 'settings' ? 'active' : ''}`} onClick={() => toggle('settings')} title="Settings (Ctrl+,)">
        <Icon name="settings" size={18} />
      </button>
    </nav>
  );
}
