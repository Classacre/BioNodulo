import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import type { Workflow } from '../../types';
import { alertDialog, toast } from '../ui';
import { extractWorkflowFromPng } from '../../utils/pngMetadata';
import { apiPost, ApiError } from '../../api/client';
import { logError } from '../../state/logging';
import Dialog from '../ui/Dialog';

interface ImportModalProps {
  onImport: (workflow: Workflow) => void;
  onClose: () => void;
}

type ImportFormat = 'json' | 'snakemake' | 'nextflow' | 'cwl' | 'galaxy';

const FORMATS: { id: ImportFormat; labelKey: string; placeholderKey: string }[] = [
  {
    id: 'json',
    labelKey: 'importModal.formats.json',
    placeholderKey: 'importModal.placeholders.json',
  },
  {
    id: 'snakemake',
    labelKey: 'importModal.formats.snakemake',
    placeholderKey: 'importModal.placeholders.snakemake',
  },
  {
    id: 'nextflow',
    labelKey: 'importModal.formats.nextflow',
    placeholderKey: 'importModal.placeholders.nextflow',
  },
  {
    id: 'cwl',
    labelKey: 'importModal.formats.cwl',
    placeholderKey: 'importModal.placeholders.cwl',
  },
  {
    id: 'galaxy',
    labelKey: 'importModal.formats.galaxy',
    placeholderKey: 'importModal.placeholders.galaxy',
  },
];

function asWorkflow(value: unknown): Workflow | null {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return null;
  const candidate = value as Record<string, unknown>;
  if (!Array.isArray(candidate.nodes) || !Array.isArray(candidate.edges)) return null;
  if (!candidate.nodes.every(node => node && typeof node === 'object'
    && typeof node.id === 'string' && typeof node.type === 'string')) return null;
  const ids = new Set(candidate.nodes.map(node => node.id as string));
  if (ids.size !== candidate.nodes.length) return null;
  if (!candidate.edges.every(edge => {
    if (!edge || typeof edge !== 'object') return false;
    const from = edge.from;
    const to = edge.to;
    return from && typeof from === 'object' && typeof from.node === 'string'
      && to && typeof to === 'object' && typeof to.node === 'string'
      && ids.has(from.node) && ids.has(to.node);
  })) return null;
  return candidate as unknown as Workflow;
}

function parseWorkflowJson(source: string): Workflow | null {
  try { return asWorkflow(JSON.parse(source) as unknown); } catch { return null; }
}

function converterErrorMessage(error: unknown): string | null {
  if (!(error instanceof ApiError) || !error.body || typeof error.body !== 'object') return null;
  const detail = (error.body as { detail?: unknown }).detail;
  return typeof detail === 'string' && detail.trim() ? detail : null;
}

export default function ImportModal({ onImport, onClose }: ImportModalProps) {
  const { t } = useTranslation();
  const [format, setFormat] = useState<ImportFormat>('json');
  const [source, setSource] = useState('');
  const [parsing, setParsing] = useState(false);

  const parse = async () => {
    setParsing(true);
    try {
      if (format === 'json') {
        const wf = parseWorkflowJson(source);
        if (wf) { onImport(wf); onClose(); }
        else await alertDialog(t('importModal.errors.parse'));
        return;
      }
      const data = await apiPost<{ workflow?: Workflow; warnings?: string[] }>('/workflow/import', {
        source: format,
        content: source,
      });
      const imported = asWorkflow(data?.workflow);
      if (imported) {
        onImport(imported);
        onClose();
        const warnings = Array.isArray(data.warnings)
          ? data.warnings.filter(warning => typeof warning === 'string' && warning.trim()) : [];
        if (warnings.length) toast.show({
          id: 'workflow-structural-import', tone: 'warning', duration: 0, dismissible: true,
          title: t('importModal.structuralWarningTitle'), message: warnings.join('\n'),
        });
      }
      else await alertDialog(t('importModal.errors.parseFormat'));
    } catch (err) {
      logError(format === 'json' ? 'importModal.import' : 'importModal.backendImport', err);
      await alertDialog(converterErrorMessage(err) || t('importModal.errors.parseFormat'));
    } finally {
      setParsing(false);
    }
  };

  return (
    <Dialog
      title={t('importModal.title')}
      onClose={onClose}
      width={700}
      maxHeight="80vh"
      footer={(
        <>
          <button className="btn" onClick={onClose}>
            {t('common.cancel')}
          </button>
          <button className="btn btn-primary" onClick={parse} disabled={!source.trim() || parsing}>
            {parsing ? t('importModal.parsing') : t('common.import')}
          </button>
        </>
      )}
    >
      <div style={{ display: 'flex', gap: 8, marginBottom: 12, flexWrap: 'wrap' }}>
        {FORMATS.map((f) => (
          <button
            key={f.id}
            type="button"
            className={`env-type-tab ${format === f.id ? 'active' : ''}`}
            aria-pressed={format === f.id}
            onClick={() => setFormat(f.id)}
          >
            {t(f.labelKey)}
          </button>
        ))}
      </div>
      <textarea
        aria-label={t('importModal.sourceLabel')}
        value={source}
        onChange={(e) => setSource(e.target.value)}
        placeholder={t(
          FORMATS.find((f) => f.id === format)?.placeholderKey ??
            'importModal.placeholders.json',
        )}
        style={{
          width: '100%',
          minHeight: 300,
          fontFamily: 'JetBrains Mono, monospace',
          fontSize: 11,
          padding: 12,
          border: '1px solid var(--border)',
          borderRadius: 8,
          background: 'var(--surface-2)',
          color: 'var(--text)',
          resize: 'vertical',
        }}
      />
      <label style={{ display: 'block', marginTop: 8, fontSize: 11, color: 'var(--muted)' }}>
        {t('importModal.uploadHint')}
        <input
          type="file"
          accept=".json,.smk,.nf,.cwl,.ga,.png,.txt,application/json,image/png"
          style={{ marginLeft: 8 }}
          onChange={async (e) => {
            const file = e.target.files?.[0];
            if (!file) return;
            if (file.type === 'image/png' || file.name.toLowerCase().endsWith('.png')) {
              try {
                const buffer = await file.arrayBuffer();
                const workflow = asWorkflow(extractWorkflowFromPng(new Uint8Array(buffer)));
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
                logError('importModal.pngRead', err);
                await alertDialog({
                  title: t('importModal.errors.pngReadFailedTitle'),
                  message: t('importModal.errors.pngReadFailedMessage'),
                });
              }
              return;
            }
            const lowerName = file.name.toLowerCase();
            const extension = lowerName.split('.').pop();
            const formatForExtension: Record<string, ImportFormat> = {
              json: 'json', smk: 'snakemake', nf: 'nextflow', cwl: 'cwl', ga: 'galaxy',
            };
            if (lowerName.endsWith('.cwl-bundle.json')) setFormat('cwl');
            else if (extension && formatForExtension[extension]) setFormat(formatForExtension[extension]);
            const reader = new FileReader();
            reader.onload = () => setSource(reader.result as string);
            reader.readAsText(file);
          }}
        />
      </label>
    </Dialog>
  );
}
