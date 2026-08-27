import Icon from '../ui/Icon';
import { Tooltip } from '../ui';
import { useAtomValue, useSetAtom } from 'jotai';
import { useTranslation } from 'react-i18next';
import { usePanelRegistry } from '../../state/panels';
import { useKeybindings } from '../../hooks/ui';
import { consoleVisibleAtom } from '../../state/uiAtoms';
import { authUserAtom, cloudConfigAtom } from '../../state/appAtoms';
import { openDocs } from '../../utils/links';

export type RailTab = 'data' | 'nodes' | 'templates' | 'environments' | 'runtimeArtifacts' | 'help' | 'console' | 'settings' | 'hpc' | 'user' | 'compute' | string | null;

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
  const { t } = useTranslation();
  const consoleVisible = useAtomValue(consoleVisibleAtom);
  const setConsoleVisible = useSetAtom(consoleVisibleAtom);
  const toggle = (tab: RailTab) => onChange(active === tab ? null : tab);
  const toggleConsole = () => {
    const isVisible = consoleVisible || active === 'console';
    setConsoleVisible(!isVisible);
    onChange(isVisible ? null : 'console');
  };
  const registered = usePanelRegistry();
  const { getBinding } = useKeybindings();
  // The cloud editor has no local host: workspace files, the conda/pixi
  // environment manager, runtime artifacts and the HPC/SLURM panel all depend
  // on machine-local state the Lambda doesn't have. Hide them in editor mode.
  const cloudConfig = useAtomValue(cloudConfigAtom);
  const authUser = useAtomValue(authUserAtom);
  const editorMode = cloudConfig?.editorMode ?? false;
  // Signed in either by cloud-launch identity (/api/config) or a local Clerk
  // sign-in (authUserAtom). Cloud-compute needs an account; the Account/user
  // button is ALWAYS shown — it's the local sign-in entry point.
  const signedIn = Boolean(cloudConfig?.user) || Boolean(authUser);

  return (
    <nav className="left-rail">
      {!editorMode && (
        <RailButton active={active === 'data'} icon="folder" label={t('panels.workspace')} shortcut={getBinding('rail.workspace') ?? undefined} onClick={() => toggle('data')} />
      )}
      <RailButton active={active === 'nodes'} icon="nodes" label={t('panels.nodes')} shortcut={getBinding('rail.nodes') ?? undefined} onClick={() => toggle('nodes')} />
      <RailButton active={active === 'templates'} icon="template" label={t('panels.templates')} shortcut={getBinding('rail.templates') ?? undefined} onClick={() => toggle('templates')} />
      {!editorMode && (
        <>
          <div className="rail-sep" />
          <RailButton active={active === 'environments'} icon="dna" label={t('panels.environment')} shortcut={getBinding('rail.environment') ?? undefined} onClick={() => toggle('environments')} />
          <RailButton active={active === 'runtimeArtifacts'} icon="activity" label={t('panels.runtimeArtifacts')} onClick={() => toggle('runtimeArtifacts')} />
          <RailButton active={active === 'hpc'} icon="server" label={t('panels.hpc')} shortcut={getBinding('rail.hpc') ?? undefined} onClick={() => toggle('hpc')} />
        </>
      )}
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
      {/* Help is the docs site, not an in-app panel — open in a new tab. */}
      <RailButton active={false} icon="help" label={t('panels.helpWiki')} shortcut={getBinding('rail.help') ?? undefined} onClick={() => openDocs()} />
      <RailButton active={active === 'console' || consoleVisible} icon="console" label={t('panels.console')} shortcut={getBinding('rail.console') ?? undefined} onClick={toggleConsole} />
      <div className="rail-sep" />
      {signedIn && (
        <RailButton active={active === 'compute'} icon="cpu" label={t('panels.compute', { defaultValue: 'Cloud compute' })} onClick={() => toggle('compute')} />
      )}
      {/* Account is always available — it's the local sign-in entry point. */}
      <RailButton active={active === 'user'} icon="user" label={t('panels.account', { defaultValue: 'Account' })} onClick={() => toggle('user')} />
      <RailButton active={active === 'settings'} icon="settings" label={t('panels.settings')} shortcut={getBinding('settings.toggle') ?? undefined} onClick={() => toggle('settings')} />
    </nav>
  );
}
