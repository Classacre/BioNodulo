import { Children, isValidElement, useMemo, useState } from 'react';
import type { ReactElement, ReactNode } from 'react';
import { useSettings } from '../../hooks/useSettings';
import { usePaletteTheme } from '../../hooks/usePaletteTheme';
import { addCustomPalette, type ThemePalette } from '../../state/palettes';
import { toast } from '../ui';

interface SettingsPanelProps {
  onClose: () => void;
}

function matchesQuery(query: string, ...needles: Array<string | undefined>): boolean {
  if (!query) return true;
  const trimmed = query.trim().toLowerCase();
  if (!trimmed) return true;
  const tokens = trimmed.split(/\s+/);
  const haystack = needles.filter(Boolean).join(' ').toLowerCase();
  return tokens.every(token => haystack.includes(token));
}

export default function SettingsPanel({ onClose: _onClose }: SettingsPanelProps) {
  const { get, getBool, set } = useSettings();
  const { paletteId, palettes, setPalette, resetPalette } = usePaletteTheme();
  const [query, setQuery] = useState('');

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

  return (
    <div className="rail-panel">
      <div className="rail-panel-header">Settings</div>
      <div className="rail-panel-body">
        <div style={{ position: 'sticky', top: 0, background: 'var(--surface)', zIndex: 2, paddingBottom: 8, marginBottom: 4 }}>
          <input
            type="search"
            placeholder="Search settings... (e.g. theme, cache, hpc)"
            value={query}
            onChange={event => setQuery(event.target.value)}
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
        </div>
        {/* Appearance */}
        <SettingsGroup query={query} title="Appearance">
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
        <SettingsGroup query={query} title="Canvas">
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
        </SettingsGroup>

        {/* Collaboration */}
        <SettingsGroup query={query} title="Collaboration">
          <SettingRow query={query} label="Real-Time Collaboration" desc="Enable shared editing and presence" keywords="yjs collab share multi-user">
            <div className={`toggle ${getBool('bionodulo.collab.enabled') ? 'on' : ''}`} onClick={() => toggle('bionodulo.collab.enabled')} />
          </SettingRow>
          <SettingRow query={query} label="Presence Cursors" desc="Show collaborators on the canvas" keywords="cursors awareness yjs">
            <div className={`toggle ${getBool('bionodulo.collab.presence') ? 'on' : ''}`} onClick={() => toggle('bionodulo.collab.presence')} />
          </SettingRow>
          <SettingRow query={query} label="Startup Choice" desc="Show collaboration choice on startup" keywords="getting started welcome">
            <div className={`toggle ${getBool('bionodulo.getting_started.show_on_startup') ? 'on' : ''}`} onClick={() => toggle('bionodulo.getting_started.show_on_startup')} />
          </SettingRow>
        </SettingsGroup>

        {/* Cache */}
        <SettingsGroup query={query} title="Cache">
          <SettingRow query={query} label="Enable Cache" desc="Cache workflow node results between runs" keywords="cache memoize">
            <div className={`toggle ${get('bionodulo.cacheEnabled') ? 'on' : ''}`} onClick={() => toggle('bionodulo.cacheEnabled')} />
          </SettingRow>
          <SettingRow query={query} label="Clear Cache" desc="Delete all cached execution results" keywords="delete clear purge">
            <button
              className="btn btn-secondary"
              style={{ padding: '4px 12px', fontSize: 12 }}
              onClick={async () => {
                try {
                  const r = await fetch('/api/cache/clear', { method: 'POST' });
                  if (r.ok) {
                    const data = await r.json();
                    toast.success('Cache cleared', { message: `${data.entries_deleted || 0} entries deleted` });
                  } else {
                    toast.error('Failed to clear cache');
                  }
                } catch {
                  toast.error('Failed to clear cache', { message: 'Server unreachable' });
                }
              }}
            >
              Clear
            </button>
          </SettingRow>
        </SettingsGroup>

        {/* Execution */}
        <SettingsGroup query={query} title="Execution">
          <SettingRow query={query} label="Queue History Size" desc="Maximum history entries" keywords="queue history">
            <input type="number" className="text-input" style={{ width: 60 }} value={Number(get('bionodulo.queueHistorySize'))} onChange={e => set('bionodulo.queueHistorySize', parseInt(e.target.value))} />
          </SettingRow>
          <SettingRow query={query} label="Strong Hashing" desc="Use stronger cache keys" keywords="hash cache key">
            <div className={`toggle ${get('bionodulo.strongHashing') ? 'on' : ''}`} onClick={() => toggle('bionodulo.strongHashing')} />
          </SettingRow>
        </SettingsGroup>

        {/* Files */}
        <SettingsGroup query={query} title="Files">
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
        <SettingsGroup query={query} title="AI Assistant">
          <SettingRow query={query} label="Provider" desc="LLM API provider" keywords="openai anthropic claude llm ai">
            <select className="select-input" value={String(get('bionodulo.llm.provider'))} onChange={e => set('bionodulo.llm.provider', e.target.value)}>
              <option value="openai">OpenAI</option>
              <option value="anthropic">Anthropic</option>
              <option value="custom">Custom</option>
            </select>
          </SettingRow>
          <SettingRow query={query} label="Model" desc="Model name" keywords="model gpt claude">
            <input type="text" className="text-input" value={String(get('bionodulo.llm.model'))} onChange={e => set('bionodulo.llm.model', e.target.value)} />
          </SettingRow>
          <SettingRow query={query} label="Base URL" desc="API base URL (optional)" keywords="endpoint url proxy">
            <input type="text" className="text-input" value={String(get('bionodulo.llm.baseUrl') || '')} onChange={e => set('bionodulo.llm.baseUrl', e.target.value)} placeholder="https://api.openai.com/v1" />
          </SettingRow>
          <SettingRow query={query} label="API Key" desc="Your API key" keywords="secret token api">
            <input type="password" className="text-input" value={String(get('bionodulo.llm.apiKey') || '')} onChange={e => set('bionodulo.llm.apiKey', e.target.value)} placeholder="sk-..." />
          </SettingRow>
          <SettingRow query={query} label="Temperature" desc="Sampling temperature" keywords="temperature creativity">
            <input type="number" className="text-input" style={{ width: 60 }} min={0} max={2} step={0.1} value={Number(get('bionodulo.llm.temperature'))} onChange={e => set('bionodulo.llm.temperature', parseFloat(e.target.value))} />
          </SettingRow>
        </SettingsGroup>
      </div>
    </div>
  );
}

function SettingsGroup({ query, title, children }: { query: string; title: string; children: ReactNode }) {
  const visible = useMemo(() => {
    if (!query.trim()) return true;
    let any = false;
    Children.forEach(children, child => {
      if (!isValidElement(child)) return;
      const props = (child as ReactElement<{ label?: string; desc?: string; keywords?: string }>).props;
      if (matchesQuery(query, props.label, props.desc, props.keywords, title)) any = true;
    });
    return any;
  }, [query, title, children]);
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
