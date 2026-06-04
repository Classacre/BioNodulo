import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import type { HPCConfig } from '../../types';
import Icon from '../ui/Icon';
import { apiGet, ApiError } from '../../api/client';

interface HPCPanelProps {
  config: HPCConfig;
  onChange: (config: HPCConfig) => void;
  onClose: () => void;
}

export default function HPCPanel({ config, onChange, onClose }: HPCPanelProps) {
  const { t } = useTranslation();
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<string | null>(null);

  const update = (partial: Partial<HPCConfig>) => onChange({ ...config, ...partial });

  const testConnection = async () => {
    setTesting(true);
    setTestResult(null);
    try {
      const data = await apiGet<{ backend?: string; partition?: string }>('/hpc/status');
      setTestResult(t('hpc.connectionSucceeded', {
        backend: data.backend || config.backend,
        partition: data.partition ? t('hpc.partitionSuffix', { partition: data.partition }) : '',
      }));
    } catch (err) {
      if (err instanceof ApiError) {
        setTestResult(t('hpc.connectionFailed', { status: err.status }));
      } else {
        setTestResult(t('hpc.backendUnavailable'));
      }
    }
    setTesting(false);
  };

  return (
    <div className="rail-panel">
      <div className="rail-panel-header">
        <span>{t('hpc.configurationTitle')}</span>
        <button className="btn btn-icon btn-sm" onClick={onClose} title={t('common.close')} aria-label={t('common.close')}><Icon name="close" size={14} /></button>
      </div>
      <div className="rail-panel-body">
        {/* Enable Toggle */}
        <div className="setting-row">
          <div>
            <div className="setting-label">{t('hpc.enableMode')}</div>
            <div className="setting-desc">{t('hpc.enableModeDescription')}</div>
          </div>
          <div className={`toggle ${config.enabled ? 'on' : ''}`} onClick={() => update({ enabled: !config.enabled })} />
        </div>

        {config.enabled && (
          <>
            <div className="hpc-status connected" style={{ marginTop: 8 }}>
              <strong>{t('hpc.enabledStatus')}</strong><br />
              {t('hpc.enabledDescription')}
            </div>

            <div className="settings-group" style={{ marginTop: 12 }}>
              <div className="settings-group-title">{t('hpc.scheduler')}</div>
              <div className="param-row">
                <label className="param-label">{t('hpc.backend')}</label>
                <select className="select-input" value={config.backend} onChange={e => update({ backend: e.target.value as 'slurm' | 'pbs' | 'sge' })}>
                  <option value="slurm">SLURM</option>
                  <option value="pbs">PBS / Torque</option>
                  <option value="sge">Sun Grid Engine</option>
                </select>
              </div>
            </div>

            <div className="settings-group">
              <div className="settings-group-title">{t('hpc.jobResources')}</div>
              <div className="param-row">
                <label className="param-label">{t('hpc.partitionQueue')}</label>
                <input type="text" className="text-input" value={config.partition || ''} onChange={e => update({ partition: e.target.value })} placeholder={t('hpc.partitionPlaceholder')} />
              </div>
              <div className="param-row">
                <label className="param-label">{t('hpc.accountProject')}</label>
                <input type="text" className="text-input" value={config.account || ''} onChange={e => update({ account: e.target.value })} placeholder={t('hpc.accountPlaceholder')} />
              </div>
              <div className="param-row">
                <label className="param-label">{t('hpc.walltime')}</label>
                <input type="text" className="text-input" value={config.walltime || '01:00:00'} onChange={e => update({ walltime: e.target.value })} placeholder={t('hpc.walltimePlaceholder')} />
              </div>
              <div className="param-row">
                <label className="param-label">{t('hpc.cpusPerTask')}</label>
                <input type="number" className="text-input" style={{ width: 60 }} value={config.cpus_per_task || 4} onChange={e => update({ cpus_per_task: parseInt(e.target.value) })} min={1} max={128} />
              </div>
              <div className="param-row">
                <label className="param-label">{t('hpc.memoryPerCpu')}</label>
                <input type="text" className="text-input" style={{ width: 80 }} value={config.mem_per_cpu || '4G'} onChange={e => update({ mem_per_cpu: e.target.value })} placeholder={t('hpc.memoryPlaceholder')} />
              </div>
            </div>

            <div className="settings-group">
              <div className="settings-group-title">{t('hpc.environment')}</div>
              <div className="param-row">
                <label className="param-label">{t('hpc.modules')}</label>
                <textarea className="text-input" style={{ minHeight: 60, fontSize: 11, fontFamily: 'JetBrains Mono, monospace' }} value={(config.modules || []).join('\n')} onChange={e => update({ modules: e.target.value.split('\n').map(s => s.trim()).filter(Boolean) })} placeholder={t('hpc.modulesPlaceholder')} />
              </div>
              <div className="param-row">
                <label className="param-label">{t('hpc.container')}</label>
                <input type="text" className="text-input" value={config.container || ''} onChange={e => update({ container: e.target.value })} placeholder={t('hpc.containerPlaceholder')} />
              </div>
              <div className="param-row">
                <label className="param-label">{t('hpc.extraArgs')}</label>
                <input type="text" className="text-input" value={config.extra_args || ''} onChange={e => update({ extra_args: e.target.value })} placeholder={t('hpc.extraArgsPlaceholder')} />
              </div>
            </div>

            <div style={{ marginTop: 12 }}>
              <button className="btn btn-primary btn-sm" onClick={testConnection} disabled={testing}>
                {testing ? t('hpc.testingConnection') : t('hpc.testConnection')}
              </button>
              {testResult && (
                <div style={{ marginTop: 8, padding: 8, borderRadius: 6, background: testResult.startsWith(t('hpc.connectedPrefix')) ? '#dcfce7' : '#fee2e2', color: testResult.startsWith(t('hpc.connectedPrefix')) ? '#15803d' : '#b91c1c', fontSize: 11 }}>
                  {testResult}
                </div>
              )}
            </div>

            <div style={{ marginTop: 16, padding: 10, borderRadius: 6, border: '1px solid var(--border)' }}>
              <strong style={{ fontSize: 11, color: 'var(--muted)', textTransform: 'uppercase' }}>{t('hpc.jobScriptPreview')}</strong>
              <pre style={{ marginTop: 6, fontSize: 10, overflow: 'auto', fontFamily: 'JetBrains Mono, monospace' }}>
{config.backend === 'slurm' ? `#!/bin/bash
#SBATCH --partition=${config.partition || 'normal'}
#SBATCH --account=${config.account || 'default'}
#SBATCH --time=${config.walltime || '01:00:00'}
#SBATCH --cpus-per-task=${config.cpus_per_task || 4}
#SBATCH --mem-per-cpu=${config.mem_per_cpu || '4G'}
${(config.modules || []).map(m => `module load ${m}`).join('\n')}
${config.container ? `apptainer exec ${config.container} bash -c '` : ''}
${t('hpc.workflowCommandsPlaceholder')}
${config.container ? `'` : ''}` : config.backend === 'pbs' ? `#!/bin/bash
#PBS -q ${config.partition || 'normal'}
#PBS -l walltime=${config.walltime || '01:00:00'}
#PBS -l select=1:ncpus=${config.cpus_per_task || 4}:mem=${config.mem_per_cpu || '4G'}
${(config.modules || []).map(m => `module load ${m}`).join('\n')}
${t('hpc.workflowCommandsPlaceholder')}` : `#!/bin/bash
#$ -q ${config.partition || 'normal'}
#$ -l h_rt=${config.walltime || '01:00:00'}
#$ -pe smp ${config.cpus_per_task || 4}
${(config.modules || []).map(m => `module load ${m}`).join('\n')}
${t('hpc.workflowCommandsPlaceholder')}`}
              </pre>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
