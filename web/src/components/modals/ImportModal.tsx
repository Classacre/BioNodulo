import { useRef, useState } from 'react';
import type { Workflow } from '../../types';
import { alertDialog } from '../ui';
import { extractWorkflowFromPng } from '../../utils/pngMetadata';
import { useFocusTrap } from '../../hooks/useFocusTrap';

interface ImportModalProps {
  onImport: (workflow: Workflow) => void;
  onClose: () => void;
}

type ImportFormat = 'json' | 'snakemake' | 'nextflow' | 'cwl' | 'galaxy';

const FORMATS: { id: ImportFormat; name: string; placeholder: string }[] = [
  { id: 'json', name: 'BioNodulo JSON', placeholder: '{\n  "version": "2.0",\n  "nodes": [...],\n  "edges": [...]\n}' },
  { id: 'snakemake', name: 'SnakeMake', placeholder: 'rule example:\n    input: "reads.fastq"\n    output: "aligned.bam"\n    shell: "bwa mem ref {input} > {output}"' },
  { id: 'nextflow', name: 'NextFlow', placeholder: 'process align {\n  input: path reads\n  output: path "*.bam"\n  script:\n  \"bwa mem ref $reads > out.bam\"\n}' },
  { id: 'cwl', name: 'CWL', placeholder: 'class: Workflow\ninputs:\n  reads: File\noutputs:\n  aligned: File\nsteps:\n  ...' },
  { id: 'galaxy', name: 'Galaxy (.ga)', placeholder: '{\n  "a_galaxy_workflow": "true",\n  "steps": {...}\n}' },
];

export default function ImportModal({ onImport, onClose }: ImportModalProps) {
  const [format, setFormat] = useState<ImportFormat>('json');
  const [source, setSource] = useState('');
  const [parsing, setParsing] = useState(false);

  const parse = async () => {
    setParsing(true);
    try {
      if (format === 'json') {
        const wf = JSON.parse(source) as Workflow;
        onImport(wf);
        onClose();
        return;
      }
      const r = await fetch('/api/workflow/import', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ source, format }),
      });
      if (r.ok) {
        const data = await r.json();
        if (data.workflow) {
          onImport(data.workflow as Workflow);
          onClose();
          return;
        }
      }
      // Fallback: try JSON
      try {
        const wf = JSON.parse(source) as Workflow;
        onImport(wf);
        onClose();
      } catch {
        await alertDialog('Could not parse the workflow. Ensure the format is correct.');
      }
    } catch {
      try {
        const wf = JSON.parse(source) as Workflow;
        onImport(wf);
        onClose();
      } catch {
        await alertDialog('Could not parse the workflow.');
      }
    }
    setParsing(false);
  };

  const dialogRef = useRef<HTMLDivElement>(null);
  useFocusTrap(dialogRef, true, onClose);

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div
        ref={dialogRef}
        className="modal-content"
        role="dialog"
        aria-modal="true"
        aria-label="Import workflow"
        style={{ width: 700, maxHeight: '80vh' }}
        onClick={e => e.stopPropagation()}
      >
        <div className="modal-header">Import Workflow</div>
        <div className="modal-body">
          <div style={{ display: 'flex', gap: 8, marginBottom: 12, flexWrap: 'wrap' }}>
            {FORMATS.map(f => (
              <button key={f.id} className={`env-type-tab ${format === f.id ? 'active' : ''}`} onClick={() => setFormat(f.id)}>
                {f.name}
              </button>
            ))}
          </div>
          <textarea
            value={source}
            onChange={e => setSource(e.target.value)}
            placeholder={FORMATS.find(f => f.id === format)?.placeholder}
            style={{ width: '100%', minHeight: 300, fontFamily: 'JetBrains Mono, monospace', fontSize: 11, padding: 12, border: '1px solid var(--border)', borderRadius: 8, background: 'var(--surface-2)', color: 'var(--text)', resize: 'vertical' }}
          />
          <div style={{ marginTop: 8, fontSize: 11, color: 'var(--muted)' }}>
            Paste workflow code above, or upload a file (PNGs with embedded workflow metadata are decoded automatically):
            <input
              type="file"
              accept=".json,.smk,.nf,.cwl,.ga,.png,.txt,application/json,image/png"
              style={{ marginLeft: 8 }}
              onChange={async e => {
                const file = e.target.files?.[0];
                if (!file) return;
                if (file.type === 'image/png' || file.name.toLowerCase().endsWith('.png')) {
                  try {
                    const buffer = await file.arrayBuffer();
                    const workflow = extractWorkflowFromPng(new Uint8Array(buffer));
                    if (workflow) {
                      onImport(workflow);
                      onClose();
                      return;
                    }
                    await alertDialog({
                      title: 'No workflow found',
                      message: 'This PNG does not contain a BioNodulo workflow tEXt chunk. Export with the "PNG (workflow embedded)" option to produce one.',
                    });
                  } catch (err) {
                    await alertDialog({
                      title: 'PNG read failed',
                      message: err instanceof Error ? err.message : String(err),
                    });
                  }
                  return;
                }
                const reader = new FileReader();
                reader.onload = () => setSource(reader.result as string);
                reader.readAsText(file);
              }}
            />
          </div>
        </div>
        <div className="modal-footer">
          <button className="btn" onClick={onClose}>Cancel</button>
          <button className="btn btn-primary" onClick={parse} disabled={!source.trim() || parsing}>
            {parsing ? 'Parsing...' : 'Import'}
          </button>
        </div>
      </div>
    </div>
  );
}
