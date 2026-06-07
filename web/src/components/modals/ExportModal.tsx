import { useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import type { Workflow } from '../../types';
import { saveToFile } from '../../utils';
import { embedWorkflowInPngDataUrl } from '../../utils/pngMetadata';
import { renderWorkflowThumbnail } from '../../utils/workflowThumbnail';
import { useFocusTrap } from '../../hooks/ui';
import { apiPost } from '../../api/client';
import { logError } from '../../state/logging';

interface ExportModalProps {
  workflow: Workflow;
  onClose: () => void;
}

type ExportFormat = 'png' | 'json' | 'snakemake' | 'nextflow' | 'cwl' | 'galaxy';

const FORMATS: { id: ExportFormat; labelKey: string; ext: string }[] = [
  { id: 'png', labelKey: 'exportModal.formats.png', ext: '.png' },
  { id: 'json', labelKey: 'exportModal.formats.json', ext: '.json' },
  { id: 'snakemake', labelKey: 'exportModal.formats.snakemake', ext: '.smk' },
  { id: 'nextflow', labelKey: 'exportModal.formats.nextflow', ext: '.nf' },
  { id: 'cwl', labelKey: 'exportModal.formats.cwl', ext: '.cwl' },
  { id: 'galaxy', labelKey: 'exportModal.formats.galaxy', ext: '.ga' },
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
  const { t } = useTranslation();
  // PNG is now the default because (a) it carries the workflow in a tEXt
  // chunk so it doubles as both share image and importable artifact, and
  // (b) the user can always tick "JSON only" to fall back to a plain .json
  // payload without re-selecting the format.
  const [format, setFormat] = useState<ExportFormat>('png');
  const [content, setContent] = useState('');
  const [generating, setGenerating] = useState(false);
  const [pngPreview, setPngPreview] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  // PNG-specific options.
  const [transparentBg, setTransparentBg] = useState(false);
  const [pngQuality, setPngQuality] = useState(0.92);
  const [pngJsonOnly, setPngJsonOnly] = useState(false);

  const resetState = () => {
    setContent('');
    setPngPreview(null);
    setError(null);
  };

  const generate = async () => {
    setGenerating(true);
    setError(null);
    try {
      if (format === 'json' || (format === 'png' && pngJsonOnly)) {
        setContent(JSON.stringify(workflow, null, 2));
        setPngPreview(null);
      } else if (format === 'png') {
        const dataUrl = renderWorkflowThumbnail(workflow, {
          transparent: transparentBg,
          quality: pngQuality,
        });
        setPngPreview(dataUrl);
        setContent('');
      } else {
        const data = await apiPost<{ content?: string; workflow?: string }>(
          '/workflow/export',
          { workflow, format },
        );
        setContent(data.content || data.workflow || '');
        setPngPreview(null);
      }
    } catch (err) {
      logError('exportModal.generate', err);
      setError(err instanceof Error ? err.message : String(err));
      setContent('');
      setPngPreview(null);
    }
    setGenerating(false);
  };

  // Auto-regenerate the PNG preview when its options change AND a preview is
  // already on screen. We don't auto-trigger the very first render — the user
  // still clicks "Render thumbnail" once so we don't waste cycles on someone
  // who only opened the modal to grab JSON.
  useEffect(() => {
    if (format !== 'png') return;
    if (!pngPreview && !pngJsonOnly) return;
    if (pngJsonOnly) {
      setContent(JSON.stringify(workflow, null, 2));
      setPngPreview(null);
      return;
    }
    let cancelled = false;
    (async () => {
      try {
        const dataUrl = renderWorkflowThumbnail(workflow, {
          transparent: transparentBg,
          quality: pngQuality,
        });
        if (!cancelled) setPngPreview(dataUrl);
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : String(err));
      }
    })();
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [transparentBg, pngQuality, pngJsonOnly, format]);

  const download = () => {
    const fmt = FORMATS.find(f => f.id === format);
    const baseName = workflow.name?.trim() || t('exportModal.defaultFilename');
    if (format === 'png' && !pngJsonOnly && pngPreview) {
      try {
        const blob = embedWorkflowInPngDataUrl(pngPreview, workflow);
        triggerDownload(blob, `${baseName}.png`);
      } catch (err) {
        logError('exportModal.downloadPng', err);
        setError(err instanceof Error ? err.message : String(err));
      }
      return;
    }
    if (format === 'png' && pngJsonOnly) {
      saveToFile(JSON.stringify(workflow, null, 2), `${baseName}.json`, 'application/json');
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
        aria-label={t('exportModal.title')}
        style={{ width: 720, maxHeight: '80vh' }}
        onClick={event => event.stopPropagation()}
      >
        <div className="modal-header">{t('exportModal.title')}</div>
        <div className="modal-body">
          <div style={{ display: 'flex', gap: 8, marginBottom: 12, flexWrap: 'wrap' }}>
            {FORMATS.map(f => (
              <button
                key={f.id}
                className={`env-type-tab ${format === f.id ? 'active' : ''}`}
                onClick={() => { setFormat(f.id); resetState(); }}
                type="button"
              >
                {t(f.labelKey)}
              </button>
            ))}
          </div>

          {format === 'png' && (
            <div
              style={{
                background: 'var(--surface-2)',
                border: '1px solid var(--border)',
                borderRadius: 6,
                padding: 10,
                marginBottom: 12,
                display: 'flex',
                flexDirection: 'column',
                gap: 8,
              }}
            >
              <div style={{ fontSize: 11, color: 'var(--muted)' }}>
                {t('exportModal.pngHelp')}
              </div>
              <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 12 }}>
                <input
                  type="checkbox"
                  checked={transparentBg}
                  onChange={event => setTransparentBg(event.target.checked)}
                  disabled={pngJsonOnly}
                />
                {t('exportModal.transparentBackground')}
              </label>
              <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 12 }}>
                <span style={{ minWidth: 96 }}>{t('exportModal.resolution')}</span>
                <input
                  type="range"
                  min={0.5}
                  max={1}
                  step={0.05}
                  value={pngQuality}
                  onChange={event => setPngQuality(parseFloat(event.target.value))}
                  disabled={pngJsonOnly}
                  style={{ flex: 1 }}
                />
                <span style={{ width: 48, textAlign: 'right', fontVariantNumeric: 'tabular-nums', color: 'var(--muted)' }}>
                  {Math.round(pngQuality * 100)}%
                </span>
              </label>
              <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 12 }}>
                <input
                  type="checkbox"
                  checked={pngJsonOnly}
                  onChange={event => setPngJsonOnly(event.target.checked)}
                />
                {t('exportModal.jsonOnly')}
              </label>
            </div>
          )}

          {!content && !pngPreview && (
            <button className="btn btn-primary" onClick={generate} disabled={generating}>
              {generating ? t('exportModal.generating') : format === 'png' && !pngJsonOnly ? t('exportModal.renderThumbnail') : t('exportModal.generate')}
            </button>
          )}

          {error && (
            <div style={{ color: 'var(--danger, #dc3545)', fontSize: 12, marginBottom: 8 }}>{error}</div>
          )}

          {pngPreview && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10, alignItems: 'flex-start' }}>
              <img
                src={pngPreview}
                alt={t('exportModal.thumbnailAlt')}
                style={{
                  width: '100%',
                  maxWidth: 640,
                  borderRadius: 6,
                  border: '1px solid var(--border)',
                  // Checkerboard background reveals transparency at a glance.
                  backgroundImage: transparentBg
                    ? 'linear-gradient(45deg, rgba(127,127,127,0.18) 25%, transparent 25%), linear-gradient(-45deg, rgba(127,127,127,0.18) 25%, transparent 25%), linear-gradient(45deg, transparent 75%, rgba(127,127,127,0.18) 75%), linear-gradient(-45deg, transparent 75%, rgba(127,127,127,0.18) 75%)'
                    : undefined,
                  backgroundSize: transparentBg ? '16px 16px' : undefined,
                  backgroundPosition: transparentBg ? '0 0, 0 8px, 8px -8px, -8px 0px' : undefined,
                }}
              />
              <div style={{ display: 'flex', gap: 8 }}>
                <button className="btn btn-primary" onClick={download}>{t('exportModal.downloadPng')}</button>
                <button className="btn" onClick={generate}>{t('exportModal.regenerate')}</button>
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
                <button className="btn btn-primary" onClick={download}>{t('common.download')}</button>
                <button className="btn" onClick={() => navigator.clipboard.writeText(content)}>{t('exportModal.copyToClipboard')}</button>
                <button className="btn" onClick={generate}>{t('exportModal.regenerate')}</button>
              </div>
            </>
          )}
        </div>
        <div className="modal-footer">
          <button className="btn" onClick={onClose}>{t('common.close')}</button>
        </div>
      </div>
    </div>
  );
}
