import { useState } from 'react';
import type { Workflow } from '../../types';
import { saveToFile } from '../../utils';

interface ExportModalProps {
  workflow: Workflow;
  onClose: () => void;
}

type ExportFormat = 'json' | 'snakemake' | 'nextflow' | 'cwl' | 'galaxy';

const FORMATS: { id: ExportFormat; name: string; ext: string }[] = [
  { id: 'json', name: 'BioNodulo JSON', ext: '.json' },
  { id: 'snakemake', name: 'SnakeMake', ext: '.smk' },
  { id: 'nextflow', name: 'NextFlow', ext: '.nf' },
  { id: 'cwl', name: 'CWL', ext: '.cwl' },
  { id: 'galaxy', name: 'Galaxy (.ga)', ext: '.ga' },
];

export default function ExportModal({ workflow, onClose }: ExportModalProps) {
  const [format, setFormat] = useState<ExportFormat>('json');
  const [content, setContent] = useState('');
  const [generating, setGenerating] = useState(false);

  const generate = async () => {
    setGenerating(true);
    try {
      if (format === 'json') {
        setContent(JSON.stringify(workflow, null, 2));
      } else {
        const r = await fetch('/api/workflow/export', {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ workflow, format }),
        });
        if (r.ok) {
          const data = await r.json();
          setContent(data.content || data.workflow || JSON.stringify(workflow, null, 2));
        } else {
          setContent(`# ${format} export\n# TODO: Backend converter not available\n\n${JSON.stringify(workflow, null, 2)}`);
        }
      }
    } catch {
      setContent(JSON.stringify(workflow, null, 2));
    }
    setGenerating(false);
  };

  const download = () => {
    const fmt = FORMATS.find(f => f.id === format);
    saveToFile(content, `${workflow.name || 'workflow'}${fmt?.ext || '.txt'}`, 'text/plain');
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" style={{ width: 700, maxHeight: '80vh' }} onClick={e => e.stopPropagation()}>
        <div className="modal-header">Export Workflow</div>
        <div className="modal-body">
          <div style={{ display: 'flex', gap: 8, marginBottom: 12, flexWrap: 'wrap' }}>
            {FORMATS.map(f => (
              <button key={f.id} className={`env-type-tab ${format === f.id ? 'active' : ''}`} onClick={() => { setFormat(f.id); setContent(''); }}>
                {f.name}
              </button>
            ))}
          </div>

          {!content && (
            <button className="btn btn-primary" onClick={generate} disabled={generating}>
              {generating ? 'Generating...' : 'Generate'}
            </button>
          )}

          {content && (
            <>
              <textarea
                readOnly
                value={content}
                style={{ width: '100%', minHeight: 300, fontFamily: 'JetBrains Mono, monospace', fontSize: 11, padding: 12, border: '1px solid var(--border)', borderRadius: 8, background: 'var(--surface-2)', color: 'var(--text)', resize: 'vertical' }}
              />
              <div style={{ marginTop: 12, display: 'flex', gap: 8 }}>
                <button className="btn btn-primary" onClick={download}>Download</button>
                <button className="btn" onClick={() => navigator.clipboard.writeText(content)}>Copy to Clipboard</button>
                <button className="btn" onClick={generate}>Regenerate</button>
              </div>
            </>
          )}
        </div>
        <div className="modal-footer">
          <button className="btn" onClick={onClose}>Close</button>
        </div>
      </div>
    </div>
  );
}
