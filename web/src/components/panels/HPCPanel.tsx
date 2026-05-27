import { useState } from 'react';
import type { HPCConfig } from '../../types';
import Icon from '../ui/Icon';
import { apiGet, ApiError } from '../../api/client';

interface HPCPanelProps {
  config: HPCConfig;
  onChange: (config: HPCConfig) => void;
  onClose: () => void;
}

export default function HPCPanel({ config, onChange, onClose }: HPCPanelProps) {
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<string | null>(null);

  const update = (partial: Partial<HPCConfig>) => onChange({ ...config, ...partial });

  const testConnection = async () => {
    setTesting(true);
    setTestResult(null);
    try {
      const data = await apiGet<{ backend?: string; partition?: string }>('/hpc/status');
      setTestResult(`Connected: ${data.backend || config.backend}${data.partition ? ` (partition: ${data.partition})` : ''}`);
    } catch (err) {
      if (err instanceof ApiError) {
        setTestResult(`Failed to connect (${err.status}). Check your HPC configuration.`);
      } else {
        setTestResult('Backend not available. Ensure the HPC module is configured.');
      }
    }
    setTesting(false);
  };

  return (
    <div className="rail-panel">
      <div className="rail-panel-header">
        <span>HPC Configuration</span>
        <button className="btn btn-icon btn-sm" onClick={onClose}><Icon name="close" size={14} /></button>
      </div>
      <div className="rail-panel-body">
        {/* Enable Toggle */}
        <div className="setting-row">
          <div>
            <div className="setting-label">Enable HPC Mode</div>
            <div className="setting-desc">Submit jobs to cluster instead of local execution</div>
          </div>
          <div className={`toggle ${config.enabled ? 'on' : ''}`} onClick={() => update({ enabled: !config.enabled })} />
        </div>

        {config.enabled && (
          <>
            <div className="hpc-status connected" style={{ marginTop: 8 }}>
              <strong>HPC is enabled</strong><br />
              Jobs will be submitted to the configured scheduler.
            </div>

            <div className="settings-group" style={{ marginTop: 12 }}>
              <div className="settings-group-title">Scheduler</div>
              <div className="param-row">
                <label className="param-label">Backend</label>
                <select className="select-input" value={config.backend} onChange={e => update({ backend: e.target.value as 'slurm' | 'pbs' | 'sge' })}>
                  <option value="slurm">SLURM</option>
                  <option value="pbs">PBS / Torque</option>
                  <option value="sge">Sun Grid Engine</option>
                </select>
              </div>
            </div>

            <div className="settings-group">
              <div className="settings-group-title">Job Resources</div>
              <div className="param-row">
                <label className="param-label">Partition / Queue</label>
                <input type="text" className="text-input" value={config.partition || ''} onChange={e => update({ partition: e.target.value })} placeholder="normal, gpu, etc." />
              </div>
              <div className="param-row">
                <label className="param-label">Account / Project</label>
                <input type="text" className="text-input" value={config.account || ''} onChange={e => update({ account: e.target.value })} placeholder="project ID" />
              </div>
              <div className="param-row">
                <label className="param-label">Walltime</label>
                <input type="text" className="text-input" value={config.walltime || '01:00:00'} onChange={e => update({ walltime: e.target.value })} placeholder="HH:MM:SS" />
              </div>
              <div className="param-row">
                <label className="param-label">CPUs per Task</label>
                <input type="number" className="text-input" style={{ width: 60 }} value={config.cpus_per_task || 4} onChange={e => update({ cpus_per_task: parseInt(e.target.value) })} min={1} max={128} />
              </div>
              <div className="param-row">
                <label className="param-label">Memory per CPU</label>
                <input type="text" className="text-input" style={{ width: 80 }} value={config.mem_per_cpu || '4G'} onChange={e => update({ mem_per_cpu: e.target.value })} placeholder="4G" />
              </div>
            </div>

            <div className="settings-group">
              <div className="settings-group-title">Environment</div>
              <div className="param-row">
                <label className="param-label">Modules (one per line)</label>
                <textarea className="text-input" style={{ minHeight: 60, fontSize: 11, fontFamily: 'JetBrains Mono, monospace' }} value={(config.modules || []).join('\n')} onChange={e => update({ modules: e.target.value.split('\n').map(s => s.trim()).filter(Boolean) })} placeholder="bioinfo/BWA/0.7.17&#10;bioinfo/samtools/1.17" />
              </div>
              <div className="param-row">
                <label className="param-label">Container (optional)</label>
                <input type="text" className="text-input" value={config.container || ''} onChange={e => update({ container: e.target.value })} placeholder="path/to/container.sif" />
              </div>
              <div className="param-row">
                <label className="param-label">Extra Args</label>
                <input type="text" className="text-input" value={config.extra_args || ''} onChange={e => update({ extra_args: e.target.value })} placeholder="--gres=gpu:1" />
              </div>
            </div>

            <div style={{ marginTop: 12 }}>
              <button className="btn btn-primary btn-sm" onClick={testConnection} disabled={testing}>
                {testing ? 'Testing...' : 'Test Connection'}
              </button>
              {testResult && (
                <div style={{ marginTop: 8, padding: 8, borderRadius: 6, background: testResult.startsWith('Connected') ? '#dcfce7' : '#fee2e2', color: testResult.startsWith('Connected') ? '#15803d' : '#b91c1c', fontSize: 11 }}>
                  {testResult}
                </div>
              )}
            </div>

            <div style={{ marginTop: 16, padding: 10, borderRadius: 6, border: '1px solid var(--border)' }}>
              <strong style={{ fontSize: 11, color: 'var(--muted)', textTransform: 'uppercase' }}>Job Script Preview</strong>
              <pre style={{ marginTop: 6, fontSize: 10, overflow: 'auto', fontFamily: 'JetBrains Mono, monospace' }}>
{config.backend === 'slurm' ? `#!/bin/bash
#SBATCH --partition=${config.partition || 'normal'}
#SBATCH --account=${config.account || 'default'}
#SBATCH --time=${config.walltime || '01:00:00'}
#SBATCH --cpus-per-task=${config.cpus_per_task || 4}
#SBATCH --mem-per-cpu=${config.mem_per_cpu || '4G'}
${(config.modules || []).map(m => `module load ${m}`).join('\n')}
${config.container ? `apptainer exec ${config.container} bash -c '` : ''}
# Workflow commands here
${config.container ? `'` : ''}` : config.backend === 'pbs' ? `#!/bin/bash
#PBS -q ${config.partition || 'normal'}
#PBS -l walltime=${config.walltime || '01:00:00'}
#PBS -l select=1:ncpus=${config.cpus_per_task || 4}:mem=${config.mem_per_cpu || '4G'}
${(config.modules || []).map(m => `module load ${m}`).join('\n')}
# Workflow commands here` : `#!/bin/bash
#$ -q ${config.partition || 'normal'}
#$ -l h_rt=${config.walltime || '01:00:00'}
#$ -pe smp ${config.cpus_per_task || 4}
${(config.modules || []).map(m => `module load ${m}`).join('\n')}
# Workflow commands here`}
              </pre>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
