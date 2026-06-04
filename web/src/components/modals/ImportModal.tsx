import { useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import type { Workflow } from '../../types';
import { alertDialog } from '../ui';
import { extractWorkflowFromPng } from '../../utils/pngMetadata';
import { useFocusTrap } from '../../hooks/useFocusTrap';
import { apiPost, ApiError } from '../../api/client';

interface ImportModalProps {
  onImport: (workflow: Workflow) => void;
  onClose: () => void;
}

type ImportFormat = 'json' | 'snakemake' | 'nextflow' | 'cwl' | 'galaxy';

const FORMATS: { id: ImportFormat; name: string; placeholder: string }[] = [
  { id: 'json', name: 'BioNodulo JSON', placeholder: '{\n  "version": "2.0",\n  "nodes": [...],\n  "edges": [...]\n}' },
  { id: 'snakemake', name: 'SnakeMake', placeholder: 'rule example:\n    input: "reads.fastq"\n    output: "aligned.bam"\n    shell: "bwa mem ref {input} > {output}"' },
  { id: 'nextflow', name: 'NextFlow', placeholder: 'process align {\n  input: path reads\n  output: path "*.bam"\n  script:\n  "bwa mem ref $reads > out.bam"\n}' },
  { id: 'cwl', name: 'CWL', placeholder: 'class: Workflow\ninputs:\n  reads: File\noutputs:\n  aligned: File\nsteps:\n  ...' },
  { id: 'galaxy', name: 'Galaxy (.ga)', placeholder: '{\n  "a_galaxy_workflow": "true",\n  "steps": {...}\n}' },
];

export default function ImportModal({ onImport, onClose }: ImportModalProps) {
  const { t } = useTranslation();
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
      try {
        const data = await apiPost<{ workflow?: Workflow }>('/workflow/import', { source, format });
        if (data.workflow) {
          onImport(data.workflow);
          onClose();
          return;
        }
      } catch (err) {
        if (!(err instanceof ApiError)) throw err;
        // Backend converter unavailable: fall through to the local JSON
        // parse attempt below.
      }
      // Fallback: try JSON
      try {
        const wf = JSON.parse(source) as Workflow;
        onImport(wf);
        onClose();
      } catch {
        await alertDialog(t('importModal.errors.parseFormat'));
      }
    } catch {
      try {
        const wf = JSON.parse(source) as Workflow;
        onImport(wf);
        onClose();
      } catch {
        await alertDialog(t('importModal.errors.parse'));
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
        aria-label={t('importModal.title')}
        style={{ width: 700, maxHeight: '80vh' }}
        onClick={e => e.stopPropagation()}
      >
        <div className="modal-header">{t('importModal.title')}</div>
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
            {t('importModal.uploadHint')}
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
                      title: t('importModal.errors.noPngWorkflowTitle'),
                      message: t('importModal.errors.noPngWorkflowMessage'),
                    });
                  } catch (err) {
                    await alertDialog({
                      title: t('importModal.errors.pngReadFailedTitle'),
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
          <button className="btn" onClick={onClose}>{t('common.cancel')}</button>
          <button className="btn btn-primary" onClick={parse} disabled={!source.trim() || parsing}>
            {parsing ? t('importModal.parsing') : t('common.import')}
          </button>
        </div>
      </div>
    </div>
  );
}
