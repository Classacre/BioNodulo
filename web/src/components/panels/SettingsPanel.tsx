import { Children, isValidElement, useEffect, useMemo, useRef, useState } from 'react';
import type { ReactElement, ReactNode } from 'react';
import { useTranslation } from 'react-i18next';
import { useSettings } from '../../hooks/settings';
import { usePaletteTheme } from '../../hooks/usePaletteTheme';
import { addCustomPalette, paletteDisplayName, type ThemePalette } from '../../state/palettes';
import { toast } from '../ui';
import Dialog from '../ui/Dialog';
import { listFeatureFlags, useFeatureFlag, setFeatureFlag } from '../../state/featureFlags';
import type { FeatureFlagDef } from '../../state/featureFlags';
import {
  isTelemetryEnabled,
  setTelemetryEnabled,
  getTelemetryEvents,
  clearTelemetry,
  exportTelemetryAsText,
  subscribeTelemetry,
} from '../../state/telemetry';
import { ApiError, apiPost } from '../../api/client';
import { logError } from '../../state/logging';

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
  { value: 'litellm', labelKey: 'settings.ai.providerOptions.litellm' },
  { value: 'custom', labelKey: 'settings.ai.providerOptions.custom' },
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
    toast.success(t('settings.appearance.paletteExported'), { message: link.download });
  };

  const importPalette = async (file: File) => {
    try {
      const palette = JSON.parse(await file.text()) as ThemePalette;
      if (!palette.id || !palette.name || !palette.light || !palette.dark) throw new Error(t('settings.appearance.invalidPaletteFile'));
      addCustomPalette(palette);
      setPalette(palette.id);
      toast.success(t('settings.appearance.paletteImported'), { message: palette.name });
    } catch (err) {
      toast.error(t('settings.appearance.paletteImportFailed'), { message: err instanceof Error ? err.message : String(err) });
    }
  };

  const bodyRef = useRef<HTMLDivElement>(null);
  const trimmedQuery = query.trim();
  const isSectionVisible = (id: SettingsSectionId) => Boolean(trimmedQuery) || activeSection === id;
  const sectionTitle = (id: SettingsSectionId) => t(SETTINGS_SECTION_TITLE_KEYS[id]);
  const st = (key: string) => t(`settings.${key}`);
  const paletteDescription = (palette: ThemePalette) => palette.descriptionKey
    ? t(palette.descriptionKey, { defaultValue: palette.description })
    : palette.description;
  const paletteName = (palette: ThemePalette) => paletteDisplayName(palette, t);
  const collabStatusLabel = collabEnabled
    ? collabConnected
      ? st('collaboration.statusLive')
      : collabConnecting
        ? st('collaboration.statusConnecting')
        : st('collaboration.statusEnabled')
    : hasJoinLink
      ? st('collaboration.statusLinkReady')
      : st('collaboration.statusOffline');

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
          <SettingRow query={query} label={st('theme')} desc={st('appearance.themeDescription')} keywords="dark light system mode tema claro oscuro sistema">
            <select className="select-input" value={String(get('bionodulo.theme'))} onChange={e => set('bionodulo.theme', e.target.value)}>
              <option value="system">{st('appearance.themeSystem')}</option>
              <option value="light">{st('appearance.themeLight')}</option>
              <option value="dark">{st('appearance.themeDark')}</option>
            </select>
          </SettingRow>
          <SettingRow query={query} label={st('appearance.tooltips')} desc={st('appearance.tooltipsDescription')} keywords="hint hover help tooltip cursor ayuda">
            <div className={`toggle ${get('bionodulo.tooltipsEnabled') ? 'on' : ''}`} onClick={() => toggle('bionodulo.tooltipsEnabled')} />
          </SettingRow>
          <SettingRow query={query} label={st('palette')} desc={st('appearance.paletteDescription')} keywords="theme color swatch paleta colores">
            <div className="palette-setting">
              <select className="select-input" value={paletteId} onChange={event => setPalette(event.target.value)}>
                {palettes.map(palette => (
                  <option key={palette.id} value={palette.id}>{paletteName(palette)}</option>
                ))}
              </select>
              <button className="btn btn-sm" onClick={resetPalette} type="button">{t('common.reset')}</button>
            </div>
          </SettingRow>
          <div className="palette-actions">
            <button className="btn btn-sm" onClick={exportPalette} type="button">{st('appearance.exportPalette')}</button>
            <label className="btn btn-sm">
              {st('appearance.importPalette')}
              <input accept=".json,application/json" onChange={event => event.target.files?.[0] && void importPalette(event.target.files[0])} type="file" />
            </label>
          </div>
          <div className="palette-preview-list">
            {palettes.map(palette => (
              <button
                className={`palette-preview-card ${paletteId === palette.id ? 'active' : ''}`}
                key={palette.id}
                onClick={() => setPalette(palette.id)}
                title={paletteDescription(palette)}
                type="button"
              >
                <span>{paletteName(palette)}</span>
                <span className="palette-swatches">
                  {palette.preview.map(color => <i key={color} style={{ background: color }} />)}
                </span>
              </button>
            ))}
          </div>
        </SettingsGroup>

        {/* Canvas */}
        <SettingsGroup active={isSectionVisible('canvas')} query={query} title={sectionTitle('canvas')}>
          <SettingRow query={query} label={st('snapToGrid')} desc={st('canvas.snapToGridDescription')} keywords="grid alignment cuadricula alineacion">
            <div className={`toggle ${get('bionodulo.snapToGrid') ? 'on' : ''}`} onClick={() => toggle('bionodulo.snapToGrid')} />
          </SettingRow>
          <SettingRow query={query} label={st('canvas.lockViewport')} desc={st('canvas.lockViewportDescription')} keywords="zoom pan camera bloquear vista lienzo">
            <div className={`toggle ${get('bionodulo.viewportLocked') ? 'on' : ''}`} onClick={() => toggle('bionodulo.viewportLocked')} />
          </SettingRow>
          <SettingRow query={query} label={st('canvas.preserveView')} desc={st('canvas.preserveViewDescription')} keywords="zoom pan persist conservar posicion">
            <div className={`toggle ${get('bionodulo.preserveView') ? 'on' : ''}`} onClick={() => toggle('bionodulo.preserveView')} />
          </SettingRow>
          <SettingRow query={query} label={st('autoSave')} desc={st('canvas.autoSaveDescription')} keywords="autosave persist localstorage guardado automatico">
            <select className="select-input" value={String(get('bionodulo.autoSave'))} onChange={e => set('bionodulo.autoSave', e.target.value)}>
              <option value="off">{st('canvas.autoSaveOff')}</option>
              <option value="30s">{st('canvas.autoSaveEvery30s')}</option>
              <option value="60s">{st('canvas.autoSaveEveryMinute')}</option>
            </select>
          </SettingRow>
          <SettingRow query={query} label={st('canvas.renderQuality')} desc={st('canvas.renderQualityDescription')} keywords="quality performance shadows smoothing antialias fps calidad rendimiento">
            <select
              className="select-input"
              value={String(get('bionodulo.canvas.quality') || 'auto')}
              onChange={e => set('bionodulo.canvas.quality', e.target.value)}
            >
              <option value="auto">{st('canvas.renderQualityAuto')}</option>
              <option value="high">{st('canvas.renderQualityHigh')}</option>
              <option value="low">{st('canvas.renderQualityLow')}</option>
            </select>
          </SettingRow>
          <SettingRow query={query} label={st('canvas.nodeShadows')} desc={st('canvas.nodeShadowsDescription')} keywords="shadow depth performance sombra nodos">
            <div className={`toggle ${getBool('bionodulo.canvas.shadows', true) ? 'on' : ''}`} onClick={() => set('bionodulo.canvas.shadows', !getBool('bionodulo.canvas.shadows', true))} />
          </SettingRow>
          <SettingRow query={query} label={st('canvas.smoothLinks')} desc={st('canvas.smoothLinksDescription')} keywords="antialias smoothing links edges enlaces suavizado">
            <div className={`toggle ${getBool('bionodulo.canvas.smoothLinks', true) ? 'on' : ''}`} onClick={() => set('bionodulo.canvas.smoothLinks', !getBool('bionodulo.canvas.smoothLinks', true))} />
          </SettingRow>
          <SettingRow query={query} label={st('canvas.colorByStatus')} desc={st('canvas.colorByStatusDescription')} keywords="color status run completed error cached tint estado">
            <div className={`toggle ${getBool('bionodulo.canvas.colorByStatus') ? 'on' : ''}`} onClick={() => set('bionodulo.canvas.colorByStatus', !getBool('bionodulo.canvas.colorByStatus'))} />
          </SettingRow>
          <SettingRow query={query} label={st('canvas.linkColor')} desc={st('canvas.linkColorDescription')} keywords="color edge link data type gradient enlace dato">
            <select
              className="select-input"
              value={String(get('bionodulo.canvas.linkColorMode') || 'type')}
              onChange={e => set('bionodulo.canvas.linkColorMode', e.target.value)}
            >
              <option value="type">{st('canvas.linkColorByType')}</option>
              <option value="gradient">{st('canvas.linkColorGradient')}</option>
              <option value="uniform">{st('canvas.linkColorUniform')}</option>
            </select>
          </SettingRow>
        </SettingsGroup>

        {/* Collaboration */}
        <SettingsGroup active={isSectionVisible('collaboration')} query={query} title={sectionTitle('collaboration')}>
          <SettingRow query={query} label={st('collaboration.mode')} desc={st('collaboration.modeDescription')} keywords="yjs collab share multi-user offline colaboracion sala enlace sin conexion">
            <span className={`collab-mode-pill ${collabEnabled ? 'online' : 'offline'}`}>
              {collabStatusLabel}
            </span>
          </SettingRow>
          <SettingRow query={query} label={st('collaboration.createLink')} desc={st('collaboration.createLinkDescription')} keywords="server create host link invite crear enlace sala invitar">
            <button className="btn btn-primary btn-sm" type="button" onClick={onCreateCollabSession} disabled={!onCreateCollabSession}>
              {t('common.create')}
            </button>
          </SettingRow>
          <SettingRow query={query} label={st('collaboration.joinLink')} desc={st('collaboration.joinLinkDescription')} keywords="server join link invite unirse enlace sala">
            <button className="btn btn-sm" type="button" onClick={onJoinCollabSession} disabled={!onJoinCollabSession}>
              {st('collaboration.joinAction')}
            </button>
          </SettingRow>
          {collabEnabled && collabShareLink && (
            <SettingRow query={query} label={st('collaboration.currentLink')} desc={st('collaboration.currentLinkDescription')} keywords="server share copy link enlace actual compartir">
              <div className="collab-settings-link" title={collabShareLink}>{collabShareLink}</div>
            </SettingRow>
          )}
          {collabEnabled && (
            <SettingRow query={query} label={st('collaboration.stopCollaboration')} desc={st('collaboration.stopCollaborationDescription')} keywords="server stop leave disconnect offline detener salir sin conexion">
              <button className="btn btn-sm" type="button" onClick={onLeaveCollabSession} disabled={!onLeaveCollabSession}>
                {st('collaboration.stopAction')}
              </button>
            </SettingRow>
          )}
          <SettingRow query={query} label={st('collaboration.presenceCursors')} desc={st('collaboration.presenceCursorsDescription')} keywords="cursors awareness yjs cursores presencia colaboradores">
            <div className={`toggle ${getBool('bionodulo.collab.presence') ? 'on' : ''}`} onClick={() => toggle('bionodulo.collab.presence')} />
          </SettingRow>
        </SettingsGroup>

        {/* Cache */}
        <SettingsGroup active={isSectionVisible('cache')} query={query} title={sectionTitle('cache')}>
          <SettingRow query={query} label={st('cache.enableCache')} desc={st('cache.enableCacheDescription')} keywords="cache memoize resultados ejecuciones">
            <div className={`toggle ${get('bionodulo.cacheEnabled') ? 'on' : ''}`} onClick={() => toggle('bionodulo.cacheEnabled')} />
          </SettingRow>
          <SettingRow query={query} label={st('clearCache')} desc={st('cache.clearCacheDescription')} keywords="delete clear purge limpiar eliminar cache">
            <button
              className="btn btn-secondary"
              style={{ padding: '4px 12px', fontSize: 12 }}
              onClick={async () => {
                try {
                  const data = await apiPost<{ entries_deleted?: number }>('/cache/clear');
                  const count = data?.entries_deleted || 0;
                  toast.success(st('cache.clearedTitle'), { message: t('settings.cache.entriesDeleted', { count }) });
                } catch (err) {
                  logError('settings.cache.clear', err);
                  toast.error(st('cache.clearFailed'), {
                    message: err instanceof ApiError ? undefined : st('cache.serverUnreachable'),
                  });
                }
              }}
            >
              {t('common.clear')}
            </button>
          </SettingRow>
        </SettingsGroup>

        {/* Execution */}
        <SettingsGroup active={isSectionVisible('execution')} query={query} title={sectionTitle('execution')}>
          <SettingRow query={query} label={st('execution.queueHistorySize')} desc={st('execution.queueHistorySizeDescription')} keywords="queue history cola historial">
            <input type="number" className="text-input" style={{ width: 60 }} value={Number(get('bionodulo.queueHistorySize'))} onChange={e => set('bionodulo.queueHistorySize', parseInt(e.target.value))} />
          </SettingRow>
          <SettingRow query={query} label={st('execution.strongHashing')} desc={st('execution.strongHashingDescription')} keywords="hash cache key claves fuerte">
            <div className={`toggle ${get('bionodulo.strongHashing') ? 'on' : ''}`} onClick={() => toggle('bionodulo.strongHashing')} />
          </SettingRow>
        </SettingsGroup>

        {/* Files */}
        <SettingsGroup active={isSectionVisible('files')} query={query} title={sectionTitle('files')}>
          <SettingRow query={query} label={st('files.explorerDepth')} desc={st('files.explorerDepthDescription')} keywords="workspace file tree archivos arbol profundidad">
            <input type="number" className="text-input" style={{ width: 60 }} value={Number(get('bionodulo.fileExplorerDepth'))} onChange={e => set('bionodulo.fileExplorerDepth', parseInt(e.target.value))} />
          </SettingRow>
          <SettingRow query={query} label={st('files.showHiddenFiles')} desc={st('files.showHiddenFilesDescription')} keywords="dotfiles hidden ocultos archivos">
            <div className={`toggle ${get('bionodulo.showHiddenFiles') ? 'on' : ''}`} onClick={() => toggle('bionodulo.showHiddenFiles')} />
          </SettingRow>
          <SettingRow query={query} label={st('files.confirmDelete')} desc={st('files.confirmDeleteDescription')} keywords="confirm delete safety confirmar eliminar seguridad">
            <div className={`toggle ${get('bionodulo.confirmFileDelete') ? 'on' : ''}`} onClick={() => toggle('bionodulo.confirmFileDelete')} />
          </SettingRow>
        </SettingsGroup>

        {/* LLM */}
        <SettingsGroup active={isSectionVisible('ai')} query={query} title={sectionTitle('ai')}>
          <SettingRow query={query} label={st('ai.provider')} desc={st('ai.providerDescription')} keywords="openai anthropic claude openrouter litellm proxy custom llm ai proveedor modelo">
            <select className="select-input" value={String(get('bionodulo.llm.provider'))} onChange={e => set('bionodulo.llm.provider', e.target.value)}>
              {AI_PROVIDER_OPTIONS.map(option => (
                <option key={option.value} value={option.value}>{option.labelKey ? t(option.labelKey) : option.label}</option>
              ))}
            </select>
          </SettingRow>
          <SettingRow query={query} label={st('ai.model')} desc={st('ai.modelDescription')} keywords="model gpt claude gemini groq mistral ollama openrouter litellm modelo">
            <input type="text" className="text-input" value={String(get('bionodulo.llm.model'))} onChange={e => set('bionodulo.llm.model', e.target.value)} />
          </SettingRow>
          <SettingRow query={query} label={st('ai.baseUrl')} desc={st('ai.baseUrlDescription')} keywords="endpoint url proxy litellm openai compatible base">
            <input type="text" className="text-input" value={String(get('bionodulo.llm.baseUrl') || '')} onChange={e => set('bionodulo.llm.baseUrl', e.target.value)} placeholder="http://localhost:4000/v1" />
          </SettingRow>
          <SettingRow query={query} label={st('ai.apiKey')} desc={st('ai.apiKeyDescription')} keywords="secret token api clave">
            <input type="password" className="text-input" value={String(get('bionodulo.llm.apiKey') || '')} onChange={e => set('bionodulo.llm.apiKey', e.target.value)} placeholder="sk-..." />
          </SettingRow>
          <SettingRow query={query} label={st('ai.temperature')} desc={st('ai.temperatureDescription')} keywords="temperature creativity temperatura">
            <input type="number" className="text-input" style={{ width: 60 }} min={0} max={2} step={0.1} value={Number(get('bionodulo.llm.temperature'))} onChange={e => set('bionodulo.llm.temperature', parseFloat(e.target.value))} />
          </SettingRow>
          <SettingRow query={query} label={st('ai.maxTokens')} desc={st('ai.maxTokensDescription')} keywords="max tokens context output limit maximos">
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
  const { t } = useTranslation();
  const [enabled, setEnabled] = useState(() => isTelemetryEnabled());
  const [eventCount, setEventCount] = useState(() => getTelemetryEvents().length);
  const tt = (key: string, options?: Record<string, unknown>) => t(`settings.telemetryPanel.${key}`, options);
  const bufferDescriptionKey = eventCount === 1 ? 'bufferDescription' : 'bufferDescriptionPlural';
  useEffect(() => subscribeTelemetry(events => setEventCount(events.length)), []);

  const handleToggle = () => {
    const next = !enabled;
    setEnabled(next);
    setTelemetryEnabled(next);
  };

  const handleExport = () => {
    const text = exportTelemetryAsText();
    if (!text) {
      toast.info(tt('noEventsToast'));
      return;
    }
    const blob = new Blob([text], { type: 'text/plain' });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = `bionodulo-telemetry-${Date.now()}.log`;
    link.click();
    URL.revokeObjectURL(link.href);
    toast.success(tt('exportedToast'), { message: link.download });
  };

  return (
    <SettingsGroup active={active} query={query} title={title}>
      <SettingRow query={query} label={tt('recordDiagnosticEvents')} desc={tt('recordDiagnosticEventsDescription')} keywords="telemetry diagnostics analytics debug diagnostico eventos">
        <div className={`toggle ${enabled ? 'on' : ''}`} onClick={handleToggle} />
      </SettingRow>
      <SettingRow query={query} label={tt('buffer')} desc={tt(bufferDescriptionKey, { count: eventCount, limit: 200 })} keywords="telemetry buffer eventos">
        <div style={{ display: 'flex', gap: 6 }}>
          <button type="button" className="btn btn-sm" onClick={handleExport} disabled={eventCount === 0}>{t('common.export')}</button>
          <button type="button" className="btn btn-sm btn-ghost" onClick={() => clearTelemetry()} disabled={eventCount === 0}>{t('common.clear')}</button>
        </div>
      </SettingRow>
    </SettingsGroup>
  );
}

function FeatureFlagsGroup({ active, query, title }: { active: boolean; query: string; title: string }) {
  const { t } = useTranslation();
  // Subscribe via useFeatureFlag for the first flag (forces re-render) — the
  // hook below handles the rest. We re-read the definitions list every render
  // since registerFlag() is cheap and is the source of truth.
  const flags = listFeatureFlags();
  if (flags.length === 0) return null;
  return (
    <SettingsGroup active={active} query={query} title={title}>
      {flags.map(flag => {
        const label = flag.labelKey ? t(flag.labelKey, { defaultValue: flag.label }) : flag.label;
        const desc = flag.descriptionKey ? t(flag.descriptionKey, { defaultValue: flag.description || flag.key }) : (flag.description || flag.key);
        const keywords = `flag experimental ${flag.key} ${flag.label} ${flag.description || ''}`;
        return (
          <FeatureFlagRow
            desc={desc}
            flag={flag}
            key={flag.key}
            keywords={keywords}
            label={label}
            query={query}
          />
        );
      })}
    </SettingsGroup>
  );
}

function FeatureFlagRow({
  query,
  flag,
  label,
  desc,
  keywords,
}: {
  query: string;
  flag: FeatureFlagDef;
  label: string;
  desc: string;
  keywords: string;
}) {
  const enabled = useFeatureFlag(flag as never);
  return (
    <SettingRow query={query} label={label} desc={desc} keywords={keywords}>
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
