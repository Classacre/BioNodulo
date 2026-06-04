import { Children, isValidElement, useEffect, useMemo, useRef, useState } from 'react';
import type { ReactElement, ReactNode } from 'react';
import { useTranslation } from 'react-i18next';
import { useSettings } from '../../hooks/useSettings';
import { usePaletteTheme } from '../../hooks/usePaletteTheme';
import { addCustomPalette, type ThemePalette } from '../../state/palettes';
import { toast } from '../ui';
import Dialog from '../ui/Dialog';
import { listFeatureFlags, useFeatureFlag, setFeatureFlag } from '../../state/featureFlags';
import {
  isTelemetryEnabled,
  setTelemetryEnabled,
  getTelemetryEvents,
  clearTelemetry,
  exportTelemetryAsText,
  subscribeTelemetry,
} from '../../state/telemetry';
import { ApiError, apiPost } from '../../api/client';

interface SettingsPanelProps {
  onClose: () => void;
  collabEnabled?: boolean;
  collabConnected?: boolean;
  collabConnecting?: boolean;
  collabShareLink?: string;
  hasJoinLink?: boolean;
  onCreateCollabSession?: () => void;
  onJoinCollabSession?: () => void;
  onLeaveCollabSession?: () => void;
}

type SettingsSectionId =
  | 'appearance'
  | 'canvas'
  | 'collaboration'
  | 'cache'
  | 'execution'
  | 'files'
  | 'ai'
  | 'feature_flags'
  | 'telemetry';

const SETTINGS_SECTIONS: Array<{ id: SettingsSectionId }> = [
  { id: 'appearance' },
  { id: 'canvas' },
  { id: 'collaboration' },
  { id: 'cache' },
  { id: 'execution' },
  { id: 'files' },
  { id: 'ai' },
  { id: 'feature_flags' },
  { id: 'telemetry' },
];

const SETTINGS_SECTION_TITLE_KEYS: Record<SettingsSectionId, string> = {
  appearance: 'settings.section.appearance',
  canvas: 'settings.section.canvas',
  collaboration: 'settings.section.collaboration',
  cache: 'settings.section.cache',
  execution: 'settings.section.execution',
  files: 'settings.section.files',
  ai: 'settings.section.aiAssistant',
  feature_flags: 'settings.section.featureFlags',
  telemetry: 'settings.section.telemetry',
};

const AI_PROVIDER_OPTIONS = [
  { value: 'openai', label: 'OpenAI' },
  { value: 'anthropic', label: 'Anthropic' },
  { value: 'openrouter', label: 'OpenRouter' },
  { value: 'litellm', label: 'LiteLLM Proxy' },
  { value: 'custom', label: 'Custom OpenAI-compatible' },
];

function matchesQuery(query: string, ...needles: Array<string | undefined>): boolean {
  if (!query) return true;
  const trimmed = query.trim().toLowerCase();
  if (!trimmed) return true;
  const tokens = trimmed.split(/\s+/);
  const haystack = needles.filter(Boolean).join(' ').toLowerCase();
  return tokens.every(token => haystack.includes(token));
}

export default function SettingsPanel({
  onClose,
  collabEnabled = false,
  collabConnected = false,
  collabConnecting = false,
  collabShareLink = '',
  hasJoinLink = false,
  onCreateCollabSession,
  onJoinCollabSession,
  onLeaveCollabSession,
}: SettingsPanelProps) {
  const { t } = useTranslation();
  const { get, getBool, set } = useSettings();
  const { paletteId, palettes, setPalette, resetPalette } = usePaletteTheme();
  const [query, setQuery] = useState('');
  const [activeSection, setActiveSection] = useState<SettingsSectionId>('appearance');

  const toggle = (key: string) => set(key, !getBool(key));

  const exportPalette = () => {
    const palette = palettes.find(item => item.id === paletteId);
    if (!palette) return;
    const blob = new Blob([JSON.stringify(palette, null, 2)], { type: 'application/json' });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = `${palette.id}.palette.json`;
    link.click();
    URL.revokeObjectURL(link.href);
    toast.success('Palette exported', { message: link.download });
  };

  const importPalette = async (file: File) => {
    try {
      const palette = JSON.parse(await file.text()) as ThemePalette;
      if (!palette.id || !palette.name || !palette.light || !palette.dark) throw new Error('Invalid palette file');
      addCustomPalette(palette);
      setPalette(palette.id);
      toast.success('Palette imported', { message: palette.name });
    } catch (err) {
      toast.error('Could not import palette', { message: err instanceof Error ? err.message : String(err) });
    }
  };

  const bodyRef = useRef<HTMLDivElement>(null);
  const trimmedQuery = query.trim();
  const isSectionVisible = (id: SettingsSectionId) => Boolean(trimmedQuery) || activeSection === id;
  const sectionTitle = (id: SettingsSectionId) => t(SETTINGS_SECTION_TITLE_KEYS[id]);

  // Recount visible rows after each render so the toolbar can show "X matches"
  // and a "no matches" hint when the query rules everything out. We sample the
  // DOM (rather than rebuilding the filter graph in JS) because the visibility
  // logic already lives in SettingsGroup/SettingRow.
  const [matchCount, setMatchCount] = useState<number | null>(null);
  useEffect(() => {
    if (!trimmedQuery) {
      setMatchCount(null);
      return;
    }
    const node = bodyRef.current;
    if (!node) return;
    setMatchCount(node.querySelectorAll('.setting-row').length);
  }, [trimmedQuery, query, activeSection]);

  return (
    <Dialog
      title={t('settings.title')}
      onClose={onClose}
      width={920}
      maxHeight="84vh"
      className="settings-menu-dialog"
    >
      <div className="settings-menu-layout">
        <nav className="settings-section-tabs" aria-label={t('settings.sectionsNav')}>
          {SETTINGS_SECTIONS.map(section => (
            <button
              key={section.id}
              type="button"
              className={`settings-section-tab ${activeSection === section.id ? 'active' : ''}`}
              onClick={() => setActiveSection(section.id)}
              aria-current={activeSection === section.id ? 'page' : undefined}
            >
              {sectionTitle(section.id)}
            </button>
          ))}
        </nav>
        <div className="settings-section-content" ref={bodyRef}>
          <div className="settings-search-bar">
          <input
            type="search"
            placeholder={t('settings.searchPlaceholder')}
            value={query}
            onChange={event => setQuery(event.target.value)}
            aria-label={t('settings.searchAria')}
            style={{
              width: '100%',
              padding: '6px 10px',
              borderRadius: 6,
              border: '1px solid var(--border)',
              background: 'var(--surface-2)',
              color: 'var(--text)',
              fontSize: 12,
            }}
          />
          {trimmedQuery && (
            <div className="settings-search-summary">
              {matchCount === 0
                ? <span className="settings-search-empty">{t('settings.searchNoMatch', { query: trimmedQuery })}</span>
                : <span>{matchCount === null ? t('settings.searchCounting') : t('settings.searchMatchCount', { count: matchCount })}</span>}
              <button type="button" className="settings-search-clear" onClick={() => setQuery('')}>{t('common.clear')}</button>
            </div>
          )}
        </div>
        {/* Appearance */}
        <SettingsGroup active={isSectionVisible('appearance')} query={query} title={sectionTitle('appearance')}>
          <SettingRow query={query} label="Theme" desc="Select app theme" keywords="dark light system mode">
            <select className="select-input" value={String(get('bionodulo.theme'))} onChange={e => set('bionodulo.theme', e.target.value)}>
              <option value="system">System</option>
              <option value="light">Light</option>
              <option value="dark">Dark</option>
            </select>
          </SettingRow>
          <SettingRow query={query} label="Tooltips" desc="Show tooltips on hover" keywords="hint hover help">
            <div className={`toggle ${get('bionodulo.tooltipsEnabled') ? 'on' : ''}`} onClick={() => toggle('bionodulo.tooltipsEnabled')} />
          </SettingRow>
          <SettingRow query={query} label="Palette" desc="Switch color palette" keywords="theme color swatch">
            <div className="palette-setting">
              <select className="select-input" value={paletteId} onChange={event => setPalette(event.target.value)}>
                {palettes.map(palette => (
                  <option key={palette.id} value={palette.id}>{palette.name}</option>
                ))}
              </select>
              <button className="btn btn-sm" onClick={resetPalette} type="button">Reset</button>
            </div>
          </SettingRow>
          <div className="palette-actions">
            <button className="btn btn-sm" onClick={exportPalette} type="button">Export Palette</button>
            <label className="btn btn-sm">
              Import Palette
              <input accept=".json,application/json" onChange={event => event.target.files?.[0] && void importPalette(event.target.files[0])} type="file" />
            </label>
          </div>
          <div className="palette-preview-list">
            {palettes.map(palette => (
              <button
                className={`palette-preview-card ${paletteId === palette.id ? 'active' : ''}`}
                key={palette.id}
                onClick={() => setPalette(palette.id)}
                title={palette.description}
                type="button"
              >
                <span>{palette.name}</span>
                <span className="palette-swatches">
                  {palette.preview.map(color => <i key={color} style={{ background: color }} />)}
                </span>
              </button>
            ))}
          </div>
        </SettingsGroup>

        {/* Canvas */}
        <SettingsGroup active={isSectionVisible('canvas')} query={query} title={sectionTitle('canvas')}>
          <SettingRow query={query} label="Snap to Grid" desc="Align nodes to grid" keywords="grid alignment">
            <div className={`toggle ${get('bionodulo.snapToGrid') ? 'on' : ''}`} onClick={() => toggle('bionodulo.snapToGrid')} />
          </SettingRow>
          <SettingRow query={query} label="Lock Viewport" desc="Prevent canvas pan/zoom" keywords="zoom pan camera">
            <div className={`toggle ${get('bionodulo.viewportLocked') ? 'on' : ''}`} onClick={() => toggle('bionodulo.viewportLocked')} />
          </SettingRow>
          <SettingRow query={query} label="Preserve View" desc="Remember canvas position" keywords="zoom pan persist">
            <div className={`toggle ${get('bionodulo.preserveView') ? 'on' : ''}`} onClick={() => toggle('bionodulo.preserveView')} />
          </SettingRow>
          <SettingRow query={query} label="Auto Save" desc="Automatically save workflows" keywords="autosave persist localstorage">
            <select className="select-input" value={String(get('bionodulo.autoSave'))} onChange={e => set('bionodulo.autoSave', e.target.value)}>
              <option value="off">Off</option>
              <option value="30s">Every 30s</option>
              <option value="60s">Every minute</option>
            </select>
          </SettingRow>
          <SettingRow query={query} label="Render Quality" desc="Visual fidelity vs. performance on large graphs" keywords="quality performance shadows smoothing antialias fps">
            <select
              className="select-input"
              value={String(get('bionodulo.canvas.quality') || 'auto')}
              onChange={e => set('bionodulo.canvas.quality', e.target.value)}
            >
              <option value="auto">Auto (recommended)</option>
              <option value="high">High (always)</option>
              <option value="low">Low (fast)</option>
            </select>
          </SettingRow>
          <SettingRow query={query} label="Node Shadows" desc="Draw drop shadows behind nodes" keywords="shadow depth performance">
            <div className={`toggle ${getBool('bionodulo.canvas.shadows', true) ? 'on' : ''}`} onClick={() => set('bionodulo.canvas.shadows', !getBool('bionodulo.canvas.shadows', true))} />
          </SettingRow>
          <SettingRow query={query} label="Smooth Links" desc="Anti-alias bezier connections" keywords="antialias smoothing links edges">
            <div className={`toggle ${getBool('bionodulo.canvas.smoothLinks', true) ? 'on' : ''}`} onClick={() => set('bionodulo.canvas.smoothLinks', !getBool('bionodulo.canvas.smoothLinks', true))} />
          </SettingRow>
          <SettingRow query={query} label="Color by Status" desc="Tint node headers by last run status (completed/error/cached)" keywords="color status run completed error cached tint">
            <div className={`toggle ${getBool('bionodulo.canvas.colorByStatus') ? 'on' : ''}`} onClick={() => set('bionodulo.canvas.colorByStatus', !getBool('bionodulo.canvas.colorByStatus'))} />
          </SettingRow>
          <SettingRow query={query} label="Link Color" desc="How connection lines are colored" keywords="color edge link data type gradient">
            <select
              className="select-input"
              value={String(get('bionodulo.canvas.linkColorMode') || 'type')}
              onChange={e => set('bionodulo.canvas.linkColorMode', e.target.value)}
            >
              <option value="type">By data type</option>
              <option value="gradient">Gradient (mismatch highlight)</option>
              <option value="uniform">Uniform</option>
            </select>
          </SettingRow>
        </SettingsGroup>

        {/* Collaboration */}
        <SettingsGroup active={isSectionVisible('collaboration')} query={query} title={sectionTitle('collaboration')}>
          <SettingRow query={query} label="Mode" desc="BioNodulo starts offline. Create or join a temporary room when you want shared editing." keywords="yjs collab share multi-user offline">
            <span className={`collab-mode-pill ${collabEnabled ? 'online' : 'offline'}`}>
              {collabEnabled
                ? collabConnected
                  ? 'Live'
                  : collabConnecting
                    ? 'Connecting'
                    : 'Enabled'
                : hasJoinLink
                  ? 'Link ready'
                  : 'Offline'}
            </span>
          </SettingRow>
          <SettingRow query={query} label="Create Link" desc="Start a temporary room and copy a link for other users." keywords="server create host link invite">
            <button className="btn btn-primary btn-sm" type="button" onClick={onCreateCollabSession} disabled={!onCreateCollabSession}>
              Create
            </button>
          </SettingRow>
          <SettingRow query={query} label="Join Link" desc="Paste a BioNodulo collaboration link or room ID." keywords="server join link invite">
            <button className="btn btn-sm" type="button" onClick={onJoinCollabSession} disabled={!onJoinCollabSession}>
              Join
            </button>
          </SettingRow>
          {collabEnabled && collabShareLink && (
            <SettingRow query={query} label="Current Link" desc="Temporary link for this running BioNodulo server." keywords="server share copy link">
              <div className="collab-settings-link" title={collabShareLink}>{collabShareLink}</div>
            </SettingRow>
          )}
          {collabEnabled && (
            <SettingRow query={query} label="Stop Collaboration" desc="Return this browser to offline mode." keywords="server stop leave disconnect offline">
              <button className="btn btn-sm" type="button" onClick={onLeaveCollabSession} disabled={!onLeaveCollabSession}>
                Stop
              </button>
            </SettingRow>
          )}
          <SettingRow query={query} label="Presence Cursors" desc="Show collaborators on the canvas" keywords="cursors awareness yjs">
            <div className={`toggle ${getBool('bionodulo.collab.presence') ? 'on' : ''}`} onClick={() => toggle('bionodulo.collab.presence')} />
          </SettingRow>
        </SettingsGroup>

        {/* Cache */}
        <SettingsGroup active={isSectionVisible('cache')} query={query} title={sectionTitle('cache')}>
          <SettingRow query={query} label="Enable Cache" desc="Cache workflow node results between runs" keywords="cache memoize">
            <div className={`toggle ${get('bionodulo.cacheEnabled') ? 'on' : ''}`} onClick={() => toggle('bionodulo.cacheEnabled')} />
          </SettingRow>
          <SettingRow query={query} label="Clear Cache" desc="Delete all cached execution results" keywords="delete clear purge">
            <button
              className="btn btn-secondary"
              style={{ padding: '4px 12px', fontSize: 12 }}
              onClick={async () => {
                try {
                  const data = await apiPost<{ entries_deleted?: number }>('/cache/clear');
                  toast.success('Cache cleared', { message: `${data?.entries_deleted || 0} entries deleted` });
                } catch (err) {
                  toast.error('Failed to clear cache', {
                    message: err instanceof ApiError ? undefined : 'Server unreachable',
                  });
                }
              }}
            >
              Clear
            </button>
          </SettingRow>
        </SettingsGroup>

        {/* Execution */}
        <SettingsGroup active={isSectionVisible('execution')} query={query} title={sectionTitle('execution')}>
          <SettingRow query={query} label="Queue History Size" desc="Maximum history entries" keywords="queue history">
            <input type="number" className="text-input" style={{ width: 60 }} value={Number(get('bionodulo.queueHistorySize'))} onChange={e => set('bionodulo.queueHistorySize', parseInt(e.target.value))} />
          </SettingRow>
          <SettingRow query={query} label="Strong Hashing" desc="Use stronger cache keys" keywords="hash cache key">
            <div className={`toggle ${get('bionodulo.strongHashing') ? 'on' : ''}`} onClick={() => toggle('bionodulo.strongHashing')} />
          </SettingRow>
        </SettingsGroup>

        {/* Files */}
        <SettingsGroup active={isSectionVisible('files')} query={query} title={sectionTitle('files')}>
          <SettingRow query={query} label="Explorer Depth" desc="File tree nesting limit" keywords="workspace file tree">
            <input type="number" className="text-input" style={{ width: 60 }} value={Number(get('bionodulo.fileExplorerDepth'))} onChange={e => set('bionodulo.fileExplorerDepth', parseInt(e.target.value))} />
          </SettingRow>
          <SettingRow query={query} label="Show Hidden Files" desc="Display dotfiles" keywords="dotfiles hidden">
            <div className={`toggle ${get('bionodulo.showHiddenFiles') ? 'on' : ''}`} onClick={() => toggle('bionodulo.showHiddenFiles')} />
          </SettingRow>
          <SettingRow query={query} label="Confirm Delete" desc="Prompt before file deletion" keywords="confirm delete safety">
            <div className={`toggle ${get('bionodulo.confirmFileDelete') ? 'on' : ''}`} onClick={() => toggle('bionodulo.confirmFileDelete')} />
          </SettingRow>
        </SettingsGroup>

        {/* LLM */}
        <SettingsGroup active={isSectionVisible('ai')} query={query} title={sectionTitle('ai')}>
          <SettingRow query={query} label="Provider" desc="LLM API provider" keywords="openai anthropic claude openrouter litellm proxy custom llm ai">
            <select className="select-input" value={String(get('bionodulo.llm.provider'))} onChange={e => set('bionodulo.llm.provider', e.target.value)}>
              {AI_PROVIDER_OPTIONS.map(option => (
                <option key={option.value} value={option.value}>{option.label}</option>
              ))}
            </select>
          </SettingRow>
          <SettingRow query={query} label="Model" desc="Model name or LiteLLM model string" keywords="model gpt claude gemini groq mistral ollama openrouter litellm">
            <input type="text" className="text-input" value={String(get('bionodulo.llm.model'))} onChange={e => set('bionodulo.llm.model', e.target.value)} />
          </SettingRow>
          <SettingRow query={query} label="Base URL" desc="API base URL for proxy or custom endpoint" keywords="endpoint url proxy litellm openai compatible">
            <input type="text" className="text-input" value={String(get('bionodulo.llm.baseUrl') || '')} onChange={e => set('bionodulo.llm.baseUrl', e.target.value)} placeholder="http://localhost:4000/v1" />
          </SettingRow>
          <SettingRow query={query} label="API Key" desc="Your API key" keywords="secret token api">
            <input type="password" className="text-input" value={String(get('bionodulo.llm.apiKey') || '')} onChange={e => set('bionodulo.llm.apiKey', e.target.value)} placeholder="sk-..." />
          </SettingRow>
          <SettingRow query={query} label="Temperature" desc="Sampling temperature" keywords="temperature creativity">
            <input type="number" className="text-input" style={{ width: 60 }} min={0} max={2} step={0.1} value={Number(get('bionodulo.llm.temperature'))} onChange={e => set('bionodulo.llm.temperature', parseFloat(e.target.value))} />
          </SettingRow>
          <SettingRow query={query} label="Max Tokens" desc="Maximum response tokens" keywords="max tokens context output limit">
            <input type="number" className="text-input" style={{ width: 84 }} min={256} max={32768} step={256} value={Number(get('bionodulo.llm.maxTokens') || 4096)} onChange={e => set('bionodulo.llm.maxTokens', parseInt(e.target.value, 10))} />
          </SettingRow>
        </SettingsGroup>

        <FeatureFlagsGroup active={isSectionVisible('feature_flags')} query={query} title={sectionTitle('feature_flags')} />
        <TelemetryGroup active={isSectionVisible('telemetry')} query={query} title={sectionTitle('telemetry')} />
        </div>
      </div>
    </Dialog>
  );
}

function TelemetryGroup({ active, query, title }: { active: boolean; query: string; title: string }) {
  const [enabled, setEnabled] = useState(() => isTelemetryEnabled());
  const [eventCount, setEventCount] = useState(() => getTelemetryEvents().length);
  useEffect(() => subscribeTelemetry(events => setEventCount(events.length)), []);

  const handleToggle = () => {
    const next = !enabled;
    setEnabled(next);
    setTelemetryEnabled(next);
  };

  const handleExport = () => {
    const text = exportTelemetryAsText();
    if (!text) {
      toast.info('No telemetry events recorded yet');
      return;
    }
    const blob = new Blob([text], { type: 'text/plain' });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = `bionodulo-telemetry-${Date.now()}.log`;
    link.click();
    URL.revokeObjectURL(link.href);
    toast.success('Telemetry exported', { message: link.download });
  };

  return (
    <SettingsGroup active={active} query={query} title={title}>
      <SettingRow query={query} label="Record diagnostic events" desc="Capture a local ring buffer of UI events for debugging. Never leaves your machine." keywords="telemetry diagnostics analytics debug">
        <div className={`toggle ${enabled ? 'on' : ''}`} onClick={handleToggle} />
      </SettingRow>
      <SettingRow query={query} label="Buffer" desc={`${eventCount} events stored (capped at 200)`} keywords="telemetry buffer">
        <div style={{ display: 'flex', gap: 6 }}>
          <button type="button" className="btn btn-sm" onClick={handleExport} disabled={eventCount === 0}>Export</button>
          <button type="button" className="btn btn-sm btn-ghost" onClick={() => clearTelemetry()} disabled={eventCount === 0}>Clear</button>
        </div>
      </SettingRow>
    </SettingsGroup>
  );
}

function FeatureFlagsGroup({ active, query, title }: { active: boolean; query: string; title: string }) {
  // Subscribe via useFeatureFlag for the first flag (forces re-render) — the
  // hook below handles the rest. We re-read the definitions list every render
  // since registerFlag() is cheap and is the source of truth.
  const flags = listFeatureFlags();
  if (flags.length === 0) return null;
  return (
    <SettingsGroup active={active} query={query} title={title}>
      {flags.map(flag => (
        <FeatureFlagRow key={flag.key} query={query} flag={flag} />
      ))}
    </SettingsGroup>
  );
}

function FeatureFlagRow({ query, flag }: { query: string; flag: { key: string; label: string; description?: string } }) {
  const enabled = useFeatureFlag(flag as never);
  return (
    <SettingRow query={query} label={flag.label} desc={flag.description || flag.key} keywords={`flag experimental ${flag.key}`}>
      <div className={`toggle ${enabled ? 'on' : ''}`} onClick={() => setFeatureFlag(flag as never, !enabled)} />
    </SettingRow>
  );
}

function SettingsGroup({ active = true, query, title, children }: { active?: boolean; query: string; title: string; children: ReactNode }) {
  const visible = useMemo(() => {
    if (!active) return false;
    if (!query.trim()) return true;
    let any = false;
    Children.forEach(children, child => {
      if (!isValidElement(child)) return;
      const props = (child as ReactElement<{ label?: string; desc?: string; keywords?: string }>).props;
      if (matchesQuery(query, props.label, props.desc, props.keywords, title)) any = true;
    });
    return any;
  }, [active, query, title, children]);
  if (!visible) return null;
  return (
    <div className="settings-group">
      <div className="settings-group-title">{title}</div>
      {children}
    </div>
  );
}

function SettingRow({ query, label, desc, keywords, children }: { query?: string; label: string; desc: string; keywords?: string; children: ReactNode }) {
  if (query && !matchesQuery(query, label, desc, keywords)) return null;
  return (
    <div className="setting-row">
      <div>
        <div className="setting-label">{label}</div>
        <div className="setting-desc">{desc}</div>
      </div>
      <div className="setting-control">{children}</div>
    </div>
  );
}
