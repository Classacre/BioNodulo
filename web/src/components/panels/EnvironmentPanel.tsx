import { useState } from 'react';
import type { EnvironmentSpec } from '../../types';

interface EnvironmentPanelProps {
  onClose: () => void;
}

export default function EnvironmentPanel({ onClose: _onClose }: EnvironmentPanelProps) {
  const [env, setEnv] = useState<EnvironmentSpec>({ type: 'none' });
  const [packages, setPackages] = useState('');

  const renderCondaPanel = () => (
    <>
      <div className="param-row">
        <label className="param-label">Environment Name</label>
        <input type="text" className="text-input" placeholder="bionodulo-env" value={env.name || ''} onChange={e => setEnv({ ...env, name: e.target.value })} />
      </div>
      <div className="param-row">
        <label className="param-label">Channels</label>
        <input type="text" className="text-input" placeholder="bioconda,conda-forge,defaults" value={(env.channels || []).join(',')} onChange={e => setEnv({ ...env, channels: e.target.value.split(',').map(s => s.trim()).filter(Boolean) })} />
      </div>
      <div className="param-row">
        <label className="param-label">Packages</label>
        <textarea className="text-input" style={{ minHeight: 80, fontSize: 11, fontFamily: 'JetBrains Mono, monospace' }} placeholder="bwa=0.7.17&#10;samtools=1.17&#10;fastqc=0.12.1" value={packages} onChange={e => setPackages(e.target.value)} />
      </div>
      <div className="param-row">
        <label className="param-label">Environment File</label>
        <input type="text" className="text-input" placeholder="env.yaml" value={env.file || ''} onChange={e => setEnv({ ...env, file: e.target.value })} />
      </div>
      <div style={{ marginTop: 12, padding: 10, borderRadius: 6, background: 'var(--surface-2)', fontSize: 11 }}>
        <strong style={{ color: 'var(--muted)' }}>Quick Install</strong>
        <div style={{ marginTop: 6, display: 'flex', flexDirection: 'column', gap: 4 }}>
          <button className="btn btn-sm" style={{ justifyContent: 'flex-start' }} onClick={() => setPackages('bwa\nsamtools\nfastqc\nmultiqc')}>
            QC Package (bwa, samtools, fastqc, multiqc)
          </button>
          <button className="btn btn-sm" style={{ justifyContent: 'flex-start' }} onClick={() => setPackages('star\nfeaturecounts\nsalmon')}>RNA-Seq Package</button>
          <button className="btn btn-sm" style={{ justifyContent: 'flex-start' }} onClick={() => setPackages('gatk4\nbcftools\nfreebayes')}>Variant Package</button>
          <button className="btn btn-sm" style={{ justifyContent: 'flex-start' }} onClick={() => setPackages('spades\nquast\nmegahit')}>Assembly Package</button>
          <button className="btn btn-sm" style={{ justifyContent: 'flex-start' }} onClick={() => setPackages('kraken2\nbracken\nmetaphlan')}>Metagenomics Package</button>
        </div>
      </div>
    </>
  );

  const renderContainerPanel = () => (
    <>
      <div className="param-row">
        <label className="param-label">Container Image</label>
        <input type="text" className="text-input" placeholder="docker.io/biocontainers/bwa:v0.7.17" value={env.image || ''} onChange={e => setEnv({ ...env, image: e.target.value })} />
      </div>
      <div className="param-row">
        <label className="param-label">Mount Points</label>
        <input type="text" className="text-input" placeholder="/data:/data,/refs:/refs" value={(env.mounts || []).join(',')} onChange={e => setEnv({ ...env, mounts: e.target.value.split(',').map(s => s.trim()).filter(Boolean) })} />
      </div>
    </>
  );

  return (
    <div className="rail-panel">
      <div className="rail-panel-header">Environments</div>
      <div className="rail-panel-body">
        <div className="env-type-tabs">
          {(['none', 'conda', 'mamba', 'micromamba', 'docker', 'apptainer'] as const).map(t => (
            <button key={t} className={`env-type-tab ${env.type === t ? 'active' : ''}`} onClick={() => setEnv({ ...env, type: t })}>
              {t}
            </button>
          ))}
        </div>

        {env.type === 'none' && (
          <div style={{ padding: 20, textAlign: 'center', color: 'var(--muted)', fontSize: 12 }}>
            No environment isolation. Tools must be available in the system PATH.
          </div>
        )}

        {(env.type === 'conda' || env.type === 'mamba' || env.type === 'micromamba') && renderCondaPanel()}

        {(env.type === 'docker' || env.type === 'apptainer') && renderContainerPanel()}

        {env.type !== 'none' && (
          <div style={{ marginTop: 16, display: 'flex', gap: 8 }}>
            <button className="btn btn-primary btn-sm" onClick={() => {}}>Apply</button>
            <button className="btn btn-sm" onClick={() => setEnv({ type: 'none' })}>Reset</button>
          </div>
        )}

        <div style={{ marginTop: 20, padding: 10, borderRadius: 6, border: '1px solid var(--border)' }}>
          <strong style={{ fontSize: 11, color: 'var(--muted)', textTransform: 'uppercase' }}>Environment YAML Preview</strong>
          <pre style={{ marginTop: 6, fontSize: 10, overflow: 'auto' }}>
{env.type !== 'none' ? `name: ${env.name || 'bionodulo-env'}
channels:
${(env.channels || ['bioconda', 'conda-forge']).map(c => `  - ${c}`).join('\n')}
dependencies:
${packages.split('\n').filter(Boolean).map(p => `  - ${p}`).join('\n') || '  - python=3.11'}` : '# No environment configured'}
          </pre>
        </div>
      </div>
    </div>
  );
}
