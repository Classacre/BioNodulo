import { useRef, useState } from 'react';
import type { Workflow } from '../../types';
import { saveToFile } from '../../utils';
import { embedWorkflowInPngDataUrl } from '../../utils/pngMetadata';
import { renderWorkflowThumbnail } from '../../utils/workflowThumbnail';
import { useFocusTrap } from '../../hooks/useFocusTrap';
import { apiPost, ApiError } from '../../api/client';

interface ExportModalProps {
  workflow: Workflow;
  onClose: () => void;
}

type ExportFormat = 'json' | 'png' | 'snakemake' | 'nextflow' | 'cwl' | 'galaxy';

const FORMATS: { id: ExportFormat; name: string; ext: string }[] = [
  { id: 'json', name: 'BioNodulo JSON', ext: '.json' },
  { id: 'png', name: 'PNG (workflow embedded)', ext: '.png' },
  { id: 'snakemake', name: 'SnakeMake', ext: '.smk' },
  { id: 'nextflow', name: 'NextFlow', ext: '.nf' },
  { id: 'cwl', name: 'CWL', ext: '.cwl' },
  { id: 'galaxy', name: 'Galaxy (.ga)', ext: '.ga' },
];

function triggerDownload(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export default function ExportModal({ workflow, onClose }: ExportModalProps) {
  const [format, setFormat] = useState<ExportFormat>('json');
  const [content, setContent] = useState('');
  const [generating, setGenerating] = useState(false);
  const [pngPreview, setPngPreview] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const resetState = () => {
    setContent('');
    setPngPreview(null);
    setError(null);
  };

  const generate = async () => {
    setGenerating(true);
    setError(null);
    try {
      if (format === 'json') {
        setContent(JSON.stringify(workflow, null, 2));
        setPngPreview(null);
      } else if (format === 'png') {
        const dataUrl = renderWorkflowThumbnail(workflow);
        setPngPreview(dataUrl);
        setContent('');
      } else {
        try {
          const data = await apiPost<{ content?: string; workflow?: string }>(
            '/workflow/export',
            { workflow, format },
          );
          setContent(data.content || data.workflow || JSON.stringify(workflow, null, 2));
        } catch (err) {
          if (err instanceof ApiError) {
            // Backend converter unavailable — keep the JSON fallback so the
            // user always has something to copy.
            setContent(`# ${format} export\n# Backend converter not available (${err.status})\n\n${JSON.stringify(workflow, null, 2)}`);
          } else {
            throw err;
          }
        }
        setPngPreview(null);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      setContent(JSON.stringify(workflow, null, 2));
    }
    setGenerating(false);
  };

  const download = () => {
    const fmt = FORMATS.find(f => f.id === format);
    const baseName = workflow.name?.trim() || 'workflow';
    if (format === 'png' && pngPreview) {
      try {
        const blob = embedWorkflowInPngDataUrl(pngPreview, workflow);
        triggerDownload(blob, `${baseName}.png`);
      } catch (err) {
        setError(err instanceof Error ? err.message : String(err));
      }
      return;
    }
    saveToFile(content, `${baseName}${fmt?.ext || '.txt'}`, 'text/plain');
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
        aria-label="Export workflow"
        style={{ width: 720, maxHeight: '80vh' }}
        onClick={event => event.stopPropagation()}
      >
        <div className="modal-header">Export Workflow</div>
        <div className="modal-body">
          <div style={{ display: 'flex', gap: 8, marginBottom: 12, flexWrap: 'wrap' }}>
            {FORMATS.map(f => (
              <button
                key={f.id}
                className={`env-type-tab ${format === f.id ? 'active' : ''}`}
                onClick={() => { setFormat(f.id); resetState(); }}
                type="button"
              >
                {f.name}
              </button>
            ))}
          </div>

          {format === 'png' && (
            <div style={{ fontSize: 11, color: 'var(--muted)', marginBottom: 12 }}>
              The PNG carries the full workflow JSON in a tEXt chunk; drag it back into Import to restore the graph.
            </div>
          )}

          {!content && !pngPreview && (
            <button className="btn btn-primary" onClick={generate} disabled={generating}>
              {generating ? 'Generating...' : format === 'png' ? 'Render thumbnail' : 'Generate'}
            </button>
          )}

          {error && (
            <div style={{ color: 'var(--danger, #dc3545)', fontSize: 12, marginBottom: 8 }}>{error}</div>
          )}

          {pngPreview && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10, alignItems: 'flex-start' }}>
              <img
                src={pngPreview}
                alt="Workflow thumbnail preview"
                style={{ width: '100%', maxWidth: 640, borderRadius: 6, border: '1px solid var(--border)' }}
              />
              <div style={{ display: 'flex', gap: 8 }}>
                <button className="btn btn-primary" onClick={download}>Download PNG</button>
                <button className="btn" onClick={generate}>Regenerate</button>
              </div>
            </div>
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
