import { useState, useEffect } from 'react';
import { useSettings } from '../../hooks/useSettings';

interface SettingsPanelProps {
  onClose: () => void;
}

export default function SettingsPanel({ onClose: _onClose }: SettingsPanelProps) {
  const { get, set } = useSettings();
  const [workspaceRoot, setWorkspaceRoot] = useState('');
  const [workspaceLoading, setWorkspaceLoading] = useState(false);
  const [workspaceError, setWorkspaceError] = useState('');

  useEffect(() => {
    fetch('/api/workspace/root')
      .then(r => r.ok ? r.json() : null)
      .then(data => {
        if (data?.root) setWorkspaceRoot(data.root);
      })
      .catch(() => {});
  }, []);

  const toggle = (key: string) => set(key, !get(key));

  const handleChangeWorkspace = async () => {
    setWorkspaceError('');
    if (!workspaceRoot.trim()) return;
    setWorkspaceLoading(true);
    try {
      const r = await fetch('/api/workspace/root', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path: workspaceRoot.trim() }),
      });
      const data = await r.json();
      if (!r.ok) {
        setWorkspaceError(data.detail || 'Failed to change workspace');
      } else {
        setWorkspaceRoot(data.root);
      }
    } catch {
      setWorkspaceError('Network error');
    }
    setWorkspaceLoading(false);
  };

  return (
    <div className="rail-panel">
      <div className="rail-panel-header">Settings</div>
      <div className="rail-panel-body">
        {/* Appearance */}
        <div className="settings-group">
          <div className="settings-group-title">Appearance</div>
          <SettingRow label="Theme" desc="Select app theme">
            <select className="select-input" value={String(get('bionodulo.theme'))} onChange={e => set('bionodulo.theme', e.target.value)}>
              <option value="system">System</option>
              <option value="light">Light</option>
              <option value="dark">Dark</option>
            </select>
          </SettingRow>
          <SettingRow label="Tooltips" desc="Show tooltips on hover">
            <div className={`toggle ${get('bionodulo.tooltipsEnabled') ? 'on' : ''}`} onClick={() => toggle('bionodulo.tooltipsEnabled')} />
          </SettingRow>
        </div>

        {/* Workspace */}
        <div className="settings-group">
          <div className="settings-group-title">Workspace</div>
          <SettingRow label="Workspace Root" desc="Directory where runs, cache, and data are stored">
            <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
              <input
                type="text"
                className="text-input"
                style={{ flex: 1, fontSize: 12 }}
                value={workspaceRoot}
                onChange={e => setWorkspaceRoot(e.target.value)}
                placeholder="/path/to/workspace"
              />
              <button
                className="btn btn-sm"
                onClick={handleChangeWorkspace}
                disabled={workspaceLoading}
                title="Set workspace root"
              >
                {workspaceLoading ? '...' : 'Set'}
              </button>
            </div>
          </SettingRow>
          {workspaceError && (
            <div style={{ color: '#ef4444', fontSize: 11, marginTop: 4, marginLeft: 8 }}>{workspaceError}</div>
          )}
        </div>

        {/* Canvas */}
        <div className="settings-group">
          <div className="settings-group-title">Canvas</div>
          <SettingRow label="Snap to Grid" desc="Align nodes to grid">
            <div className={`toggle ${get('bionodulo.snapToGrid') ? 'on' : ''}`} onClick={() => toggle('bionodulo.snapToGrid')} />
          </SettingRow>
          <SettingRow label="Lock Viewport" desc="Prevent canvas pan/zoom">
            <div className={`toggle ${get('bionodulo.viewportLocked') ? 'on' : ''}`} onClick={() => toggle('bionodulo.viewportLocked')} />
          </SettingRow>
          <SettingRow label="Preserve View" desc="Remember canvas position">
            <div className={`toggle ${get('bionodulo.preserveView') ? 'on' : ''}`} onClick={() => toggle('bionodulo.preserveView')} />
          </SettingRow>
          <SettingRow label="Auto Save" desc="Automatically save workflows">
            <select className="select-input" value={String(get('bionodulo.autoSave'))} onChange={e => set('bionodulo.autoSave', e.target.value)}>
              <option value="off">Off</option>
              <option value="30s">Every 30s</option>
              <option value="60s">Every minute</option>
            </select>
          </SettingRow>
        </div>

        {/* Execution */}
        <div className="settings-group">
          <div className="settings-group-title">Execution</div>
          <SettingRow label="Queue History Size" desc="Maximum history entries">
            <input type="number" className="text-input" style={{ width: 60 }} value={Number(get('bionodulo.queueHistorySize'))} onChange={e => set('bionodulo.queueHistorySize', parseInt(e.target.value))} />
          </SettingRow>
          <SettingRow label="Strong Hashing" desc="Use stronger cache keys">
            <div className={`toggle ${get('bionodulo.strongHashing') ? 'on' : ''}`} onClick={() => toggle('bionodulo.strongHashing')} />
          </SettingRow>
        </div>

        {/* Files */}
        <div className="settings-group">
          <div className="settings-group-title">Files</div>
          <SettingRow label="Explorer Depth" desc="File tree nesting limit">
            <input type="number" className="text-input" style={{ width: 60 }} value={Number(get('bionodulo.fileExplorerDepth'))} onChange={e => set('bionodulo.fileExplorerDepth', parseInt(e.target.value))} />
          </SettingRow>
          <SettingRow label="Show Hidden Files" desc="Display dotfiles">
            <div className={`toggle ${get('bionodulo.showHiddenFiles') ? 'on' : ''}`} onClick={() => toggle('bionodulo.showHiddenFiles')} />
          </SettingRow>
          <SettingRow label="Confirm Delete" desc="Prompt before file deletion">
            <div className={`toggle ${get('bionodulo.confirmFileDelete') ? 'on' : ''}`} onClick={() => toggle('bionodulo.confirmFileDelete')} />
          </SettingRow>
        </div>

        {/* LLM */}
        <div className="settings-group">
          <div className="settings-group-title">AI Assistant</div>
          <SettingRow label="Provider" desc="LLM API provider">
            <select className="select-input" value={String(get('bionodulo.llm.provider'))} onChange={e => set('bionodulo.llm.provider', e.target.value)}>
              <option value="openai">OpenAI</option>
              <option value="anthropic">Anthropic</option>
              <option value="custom">Custom</option>
            </select>
          </SettingRow>
          <SettingRow label="Model" desc="Model name">
            <input type="text" className="text-input" value={String(get('bionodulo.llm.model'))} onChange={e => set('bionodulo.llm.model', e.target.value)} />
          </SettingRow>
          <SettingRow label="Base URL" desc="API base URL (optional)">
            <input type="text" className="text-input" value={String(get('bionodulo.llm.baseUrl') || '')} onChange={e => set('bionodulo.llm.baseUrl', e.target.value)} placeholder="https://api.openai.com/v1" />
          </SettingRow>
          <SettingRow label="API Key" desc="Your API key">
            <input type="password" className="text-input" value={String(get('bionodulo.llm.apiKey') || '')} onChange={e => set('bionodulo.llm.apiKey', e.target.value)} placeholder="sk-..." />
          </SettingRow>
          <SettingRow label="Temperature" desc="Sampling temperature">
            <input type="number" className="text-input" style={{ width: 60 }} min={0} max={2} step={0.1} value={Number(get('bionodulo.llm.temperature'))} onChange={e => set('bionodulo.llm.temperature', parseFloat(e.target.value))} />
          </SettingRow>
        </div>
      </div>
    </div>
  );
}

function SettingRow({ label, desc, children }: { label: string; desc: string; children: React.ReactNode }) {
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
