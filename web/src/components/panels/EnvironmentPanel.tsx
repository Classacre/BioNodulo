import { useState, useEffect, useCallback } from 'react';
import Icon from '../ui/Icon';
import type { CondaEnvironment, DependencyStatus, EnvPackage, Workflow } from '../../types';

interface EnvironmentPanelProps {
  onClose: () => void;
  currentWorkflow?: Workflow;
}

const PRESET_PACKAGES: Record<string, string[]> = {
  'QC': ['bwa', 'samtools', 'fastqc', 'multiqc'],
  'RNA-Seq': ['star', 'featurecounts', 'salmon'],
  'Variant': ['gatk4', 'bcftools', 'freebayes'],
  'Assembly': ['spades', 'quast', 'megahit'],
  'Metagenomics': ['kraken2', 'bracken', 'metaphlan'],
};

export default function EnvironmentPanel({ onClose, currentWorkflow }: EnvironmentPanelProps) {
  const [envs, setEnvs] = useState<CondaEnvironment[]>([]);
  const [selectedEnv, setSelectedEnv] = useState<string | null>(null);
  const [envPackages, setEnvPackages] = useState<EnvPackage[]>([]);
  const [deps, setDeps] = useState<DependencyStatus[]>([]);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState('');
  const [creating, setCreating] = useState(false);
  const [newEnvName, setNewEnvName] = useState('');
  const [newEnvPackages, setNewEnvPackages] = useState('');
  const [activeTab, setActiveTab] = useState<'envs' | 'deps' | 'create'>('envs');

  // Fetch environments
  const fetchEnvs = useCallback(async () => {
    try {
      const r = await fetch('/api/manager/environments');
      if (r.ok) {
        const data = await r.json();
        setEnvs(data.environments || []);
      }
    } catch { /* offline */ }
  }, []);

  // Fetch dependency tree for current workflow
  const fetchDeps = useCallback(async () => {
    if (!currentWorkflow || currentWorkflow.nodes.length === 0) {
      setDeps([]);
      return;
    }
    try {
      const r = await fetch('/api/manager/dependency-tree', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ workflow: currentWorkflow }),
      });
      if (r.ok) {
        const data = await r.json();
        setDeps(data.dependencies || []);
      }
    } catch { /* offline */ }
  }, [currentWorkflow]);

  useEffect(() => {
    fetchEnvs();
    fetchDeps();
  }, [fetchEnvs, fetchDeps]);

  // Fetch packages when an env is selected
  useEffect(() => {
    if (!selectedEnv) {
      setEnvPackages([]);
      return;
    }
    (async () => {
      try {
        const r = await fetch(`/api/manager/environments/${encodeURIComponent(selectedEnv)}`);
        if (r.ok) {
          const data = await r.json();
          setEnvPackages(data.packages || []);
        }
      } catch { /* offline */ }
    })();
  }, [selectedEnv]);

  const handleCreateEnv = async () => {
    if (!newEnvName.trim()) return;
    setCreating(true);
    setMessage('');
    const packages = newEnvPackages.split('\n').map(s => s.trim()).filter(Boolean);
    try {
      const r = await fetch('/api/manager/environments', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: newEnvName.trim(), packages }),
      });
      const data = await r.json();
      if (r.ok) {
        setMessage(`Created environment '${newEnvName.trim()}'`);
        setNewEnvName('');
        setNewEnvPackages('');
        fetchEnvs();
        setActiveTab('envs');
      } else {
        setMessage(data.detail || 'Failed to create environment');
      }
    } catch {
      setMessage('Network error');
    }
    setCreating(false);
  };

  const handleDeleteEnv = async (name: string) => {
    if (!confirm(`Delete environment '${name}'?`)) return;
    try {
      const r = await fetch(`/api/manager/environments/${encodeURIComponent(name)}`, { method: 'DELETE' });
      if (r.ok) {
        setMessage(`Deleted '${name}'`);
        if (selectedEnv === name) setSelectedEnv(null);
        fetchEnvs();
      } else {
        const data = await r.json();
        setMessage(data.detail || 'Failed to delete');
      }
    } catch {
      setMessage('Network error');
    }
  };

  const handleIsolateWorkflow = async () => {
    if (!currentWorkflow) return;
    setLoading(true);
    setMessage('');
    try {
      const r = await fetch('/api/manager/create-workflow-env', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ workflow: currentWorkflow, environment: {} }),
      });
      const data = await r.json();
      if (r.ok) {
        setMessage(data.message || 'Workflow environment created');
        fetchEnvs();
        fetchDeps();
      } else {
        setMessage(data.detail || 'Failed to create workflow environment');
      }
    } catch {
      setMessage('Network error');
    }
    setLoading(false);
  };

  const missingCount = deps.filter(d => d.status === 'missing').length;
  const installedCount = deps.filter(d => d.status === 'installed').length;

  return (
    <div className="rail-panel">
      <div className="rail-panel-header">
        <span>Environments</span>
        <button className="btn btn-icon" onClick={onClose}><Icon name="close" size={14} /></button>
      </div>

      <div className="env-tabs">
        {(['envs', 'deps', 'create'] as const).map(t => (
          <button
            key={t}
            className={`env-type-tab ${activeTab === t ? 'active' : ''}`}
            onClick={() => setActiveTab(t)}
          >
            {t === 'envs' && `Envs (${envs.length})`}
            {t === 'deps' && `Deps (${deps.length})`}
            {t === 'create' && 'Create'}
          </button>
        ))}
      </div>

      {message && (
        <div className={`env-message ${message.includes('Failed') || message.includes('error') ? 'err' : 'ok'}`}>
          {message}
        </div>
      )}

      {activeTab === 'envs' && (
        <div className="rail-panel-body">
          {envs.length === 0 && (
            <div style={{ padding: 20, textAlign: 'center', color: 'var(--muted)', fontSize: 12 }}>
              No conda environments found.<br />
              Install micromamba/conda or create an environment.
            </div>
          )}
          <div className="env-list">
            {envs.map(env => (
              <div
                key={env.name}
                className={`env-item ${selectedEnv === env.name ? 'selected' : ''}`}
                onClick={() => setSelectedEnv(env.name)}
              >
                <div className="env-item-main">
                  <span className="env-item-name">{env.name}</span>
                  <span className="env-item-path">{env.path}</span>
                </div>
                <button
                  className="btn btn-sm btn-ghost"
                  onClick={(e) => { e.stopPropagation(); handleDeleteEnv(env.name); }}
                  title="Delete"
                >
                  <Icon name="close" size={12} />
                </button>
              </div>
            ))}
          </div>

          {selectedEnv && (
            <div className="env-packages">
              <h4>Packages in <code>{selectedEnv}</code></h4>
              {envPackages.length === 0 ? (
                <span className="muted">No packages or still loading...</span>
              ) : (
                <div className="env-package-grid">
                  {envPackages.slice(0, 50).map(pkg => (
                    <div key={pkg.name} className="env-package-chip" title={`${pkg.channel} ${pkg.build}`}>
                      <strong>{pkg.name}</strong> <span>{pkg.version}</span>
                    </div>
                  ))}
                  {envPackages.length > 50 && (
                    <span className="muted">+{envPackages.length - 50} more</span>
                  )}
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {activeTab === 'deps' && (
        <div className="rail-panel-body">
          {deps.length === 0 && (
            <div style={{ padding: 20, textAlign: 'center', color: 'var(--muted)', fontSize: 12 }}>
              {currentWorkflow && currentWorkflow.nodes.length > 0
                ? 'All dependencies satisfied or no nodes requiring external tools.'
                : 'Add nodes to the workflow to see dependencies.'}
            </div>
          )}

          {currentWorkflow && currentWorkflow.nodes.length > 0 && (
            <div className="dep-summary">
              <span className="dep-badge ok">{installedCount} installed</span>
              {missingCount > 0 && <span className="dep-badge err">{missingCount} missing</span>}
              <button
                className="btn btn-primary btn-sm"
                onClick={handleIsolateWorkflow}
                disabled={loading || missingCount === 0}
              >
                {loading ? <><Icon name="spinner" size={12} /> Creating...</> : 'Isolate Workflow'}
              </button>
            </div>
          )}

          <div className="dep-list">
            {deps.map(d => (
              <div key={`${d.type}-${d.name}`} className={`dep-item ${d.status}`}>
                <span className={`dep-dot ${d.status}`} />
                <div className="dep-info">
                  <span className="dep-name">{d.name}</span>
                  <span className="dep-type">{d.type}</span>
                </div>
                <span className="dep-msg">{d.message}</span>
                {d.envs.length > 0 && (
                  <span className="dep-envs">{d.envs.join(', ')}</span>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {activeTab === 'create' && (
        <div className="rail-panel-body">
          <div className="param-row">
            <label className="param-label">Environment Name</label>
            <input
              type="text"
              className="text-input"
              placeholder="my-bio-env"
              value={newEnvName}
              onChange={e => setNewEnvName(e.target.value)}
            />
          </div>
          <div className="param-row">
            <label className="param-label">Packages (one per line)</label>
            <textarea
              className="text-input"
              style={{ minHeight: 100, fontSize: 11, fontFamily: 'JetBrains Mono, monospace' }}
              placeholder="bwa=0.7.17&#10;samtools=1.17&#10;fastqc=0.12.1"
              value={newEnvPackages}
              onChange={e => setNewEnvPackages(e.target.value)}
            />
          </div>
          <div className="param-row">
            <label className="param-label">Quick Presets</label>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
              {Object.entries(PRESET_PACKAGES).map(([label, pkgs]) => (
                <button
                  key={label}
                  className="btn btn-sm"
                  style={{ justifyContent: 'flex-start' }}
                  onClick={() => setNewEnvPackages(pkgs.join('\n'))}
                >
                  {label}
                </button>
              ))}
            </div>
          </div>
          <button
            className="btn btn-primary"
            style={{ width: '100%', marginTop: 12 }}
            onClick={handleCreateEnv}
            disabled={creating || !newEnvName.trim()}
          >
            {creating ? <><Icon name="spinner" size={12} /> Creating...</> : 'Create Environment'}
          </button>
        </div>
      )}
    </div>
  );
}
