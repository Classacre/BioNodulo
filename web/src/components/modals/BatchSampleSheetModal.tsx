import { useEffect, useMemo, useRef, useState } from 'react';
import type { ChangeEvent } from 'react';
import { useTranslation } from 'react-i18next';
import Icon from '../ui/Icon';
import { Skeleton } from '../ui/Skeleton';
import type { Workflow, WorkflowNode, WorkflowParameter } from '../../types';
import { useFocusTrap } from '../../hooks/ui';
import { coerceWorkflowParameterInput } from '../../utils/workflowParameters';

export interface SampleSheetRun {
  rowIndex: number;
  name: string;
  workflow: Workflow;
  parameters?: Record<string, unknown>;
}

interface BatchSampleSheetModalProps {
  workflow: Workflow;
  onClose: () => void;
  onSubmit: (runs: SampleSheetRun[]) => void | Promise<void>;
}

interface ParsedSheet {
  delimiter: ',' | '\t';
  headers: string[];
  rows: string[][];
}

const MAX_PREVIEW_ROWS = 8;
const SKIP_VALUE = '__skip__';
const NAME_VALUE = '__name__';
const WORKFLOW_PARAMETER_PREFIX = '__workflow_parameter__::';

const INPUT_STYLE = {
  padding: '6px 10px',
  border: '1px solid var(--border)',
  borderRadius: 6,
  background: 'var(--surface-2)',
  color: 'var(--text)',
  fontSize: 12,
} as const;

function detectDelimiter(line: string): ',' | '\t' {
  const tabs = (line.match(/\t/g) ?? []).length;
  const commas = (line.match(/,/g) ?? []).length;
  return tabs > commas ? '\t' : ',';
}

function splitLineRespectingQuotes(line: string, delimiter: string): string[] {
  const out: string[] = [];
  let buf = '';
  let inQuotes = false;
  for (let i = 0; i < line.length; i += 1) {
    const ch = line[i];
    if (ch === '"') {
      if (inQuotes && line[i + 1] === '"') {
        buf += '"';
        i += 1;
      } else {
        inQuotes = !inQuotes;
      }
    } else if (ch === delimiter && !inQuotes) {
      out.push(buf);
      buf = '';
    } else {
      buf += ch;
    }
  }
  out.push(buf);
  return out.map(cell => cell.trim());
}

function parseSheet(text: string): ParsedSheet | null {
  const lines = text.replace(/\r\n?/g, '\n').split('\n').filter(line => line.trim().length > 0);
  if (lines.length === 0) return null;
  const delimiter = detectDelimiter(lines[0]);
  const headers = splitLineRespectingQuotes(lines[0], delimiter);
  if (headers.length === 0) return null;
  const rows = lines.slice(1).map(line => splitLineRespectingQuotes(line, delimiter));
  return { delimiter, headers, rows };
}

function coerceValue(raw: string, sample: unknown): unknown {
  if (typeof sample === 'number') {
    const n = Number(raw);
    return Number.isFinite(n) ? n : raw;
  }
  if (typeof sample === 'boolean') {
    const lower = raw.toLowerCase();
    if (lower === 'true' || lower === '1' || lower === 'yes') return true;
    if (lower === 'false' || lower === '0' || lower === 'no') return false;
    return raw;
  }
  return raw;
}

function nodeLabel(node: WorkflowNode): string {
  return node.ui?.title || node.node_info?.display_name || node.type;
}

function workflowParameterMapping(parameter: WorkflowParameter): string {
  return `${WORKFLOW_PARAMETER_PREFIX}${parameter.name}`;
}

function workflowParameterName(mapping: string): string | null {
  if (!mapping.startsWith(WORKFLOW_PARAMETER_PREFIX)) return null;
  return mapping.slice(WORKFLOW_PARAMETER_PREFIX.length);
}

export default function BatchSampleSheetModal({ workflow, onClose, onSubmit }: BatchSampleSheetModalProps) {
  const { t } = useTranslation();
  const [rawText, setRawText] = useState('');
  const [columnMap, setColumnMap] = useState<Record<number, string>>({});
  const [namePrefix, setNamePrefix] = useState(workflow.name || t('batchSampleSheet.defaultNamePrefix'));
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const parsed = useMemo(() => parseSheet(rawText), [rawText]);

  useEffect(() => {
    if (!parsed) {
      setColumnMap({});
      return;
    }
    setColumnMap(prev => {
      const next: Record<number, string> = {};
      let nameAssigned = false;
      parsed.headers.forEach((header, index) => {
        const lower = header.toLowerCase();
        if (prev[index]) {
          next[index] = prev[index];
          if (prev[index] === NAME_VALUE) nameAssigned = true;
          return;
        }
        const workflowParameter = workflow.parameters?.find(parameter => parameter.name.toLowerCase() === lower);
        if (workflowParameter) {
          next[index] = workflowParameterMapping(workflowParameter);
          return;
        }
        if (!nameAssigned && (lower === 'sample' || lower === 'name' || lower === 'sample_id' || lower === 'id')) {
          next[index] = NAME_VALUE;
          nameAssigned = true;
          return;
        }
        const guess = workflow.nodes.find(node => {
          const params = node.params || {};
          return Object.keys(params).some(param => param.toLowerCase() === lower);
        });
        if (guess) {
          const paramKey = Object.keys(guess.params || {}).find(param => param.toLowerCase() === lower);
          if (paramKey) {
            next[index] = `${guess.id}::${paramKey}`;
            return;
          }
        }
        next[index] = SKIP_VALUE;
      });
      return next;
    });
  }, [parsed, workflow.nodes, workflow.parameters]);

  const paramOptions = useMemo(() => {
    const options: { value: string; label: string; group: string }[] = [];
    for (const parameter of workflow.parameters ?? []) {
      options.push({
        value: workflowParameterMapping(parameter),
        label: t('batchSampleSheet.workflowParamOptionLabel', { param: parameter.name }),
        group: 'workflow',
      });
    }
    for (const node of workflow.nodes) {
      const label = nodeLabel(node);
      const params = node.params || {};
      for (const param of Object.keys(params)) {
        options.push({
          value: `${node.id}::${param}`,
          label: t('batchSampleSheet.paramOptionLabel', { node: label, param }),
          group: node.type,
        });
      }
    }
    return options;
  }, [t, workflow.nodes, workflow.parameters]);

  const handleFile = (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => {
      setRawText(String(reader.result || ''));
    };
    reader.readAsText(file);
  };

  const buildRuns = (): SampleSheetRun[] => {
    if (!parsed) return [];
    const runs: SampleSheetRun[] = [];
    parsed.rows.forEach((row, rowIndex) => {
      const overrides = new Map<string, Record<string, unknown>>();
      const workflowParameterOverrides: Record<string, unknown> = {};
      let rowName = `${namePrefix} ${rowIndex + 1}`;
      parsed.headers.forEach((_, columnIndex) => {
        const mapping = columnMap[columnIndex];
        const rawValue = row[columnIndex] ?? '';
        if (!mapping || mapping === SKIP_VALUE) return;
        if (mapping === NAME_VALUE) {
          if (rawValue.trim().length > 0) rowName = rawValue.trim();
          return;
        }
        const parameterName = workflowParameterName(mapping);
        if (parameterName) {
          const parameter = workflow.parameters?.find(candidate => candidate.name === parameterName);
          if (!parameter) return;
          const value = coerceWorkflowParameterInput(parameter, rawValue);
          if (value !== undefined) {
            workflowParameterOverrides[parameter.name] = value;
          }
          return;
        }
        const [nodeId, paramKey] = mapping.split('::');
        const node = workflow.nodes.find(candidate => candidate.id === nodeId);
        if (!node) return;
        const existing = overrides.get(nodeId) ?? {};
        existing[paramKey] = coerceValue(rawValue, node.params?.[paramKey]);
        overrides.set(nodeId, existing);
      });

      const nextNodes = workflow.nodes.map(node => {
        const patch = overrides.get(node.id);
        if (!patch) return node;
        return { ...node, params: { ...(node.params || {}), ...patch } };
      });
      runs.push({
        rowIndex,
        name: rowName,
        workflow: { ...workflow, nodes: nextNodes, name: rowName },
        parameters: workflowParameterOverrides,
      });
    });
    return runs;
  };

  const previewRuns = useMemo(() => parsed ? buildRuns().slice(0, MAX_PREVIEW_ROWS) : [], [parsed, columnMap, namePrefix, workflow]);
  const mappedColumnCount = useMemo(() => (
    Object.values(columnMap).filter(value => value !== SKIP_VALUE).length
  ), [columnMap]);

  const handleSubmit = async () => {
    if (!parsed) {
      setError(t('batchSampleSheet.errors.emptySheet'));
      return;
    }
    if (parsed.rows.length === 0) {
      setError(t('batchSampleSheet.errors.noRows'));
      return;
    }
    if (mappedColumnCount === 0) {
      setError(t('batchSampleSheet.errors.noMapping'));
      return;
    }
    setError(null);
    setSubmitting(true);
    try {
      await onSubmit(buildRuns());
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setSubmitting(false);
    }
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
        aria-label={t('batchSampleSheet.title')}
        style={{ width: 760, maxHeight: '85vh' }}
        onClick={event => event.stopPropagation()}
      >
        <div className="modal-header">
          <h3>{t('batchSampleSheet.title')}</h3>
          <button className="btn btn-icon btn-sm" onClick={onClose} title={t('common.close')}>
            <Icon name="close" size={14} />
          </button>
        </div>
        <div className="modal-body" style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          <p style={{ margin: 0, color: 'var(--text-muted)', fontSize: 12 }}>
            {t('batchSampleSheet.description')}
          </p>
          <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            <label className="btn btn-sm" style={{ cursor: 'pointer' }}>
              <Icon name="import" size={12} /> {t('batchSampleSheet.upload')}
              <input
                type="file"
                accept=".csv,.tsv,.txt"
                style={{ display: 'none' }}
                onChange={handleFile}
              />
            </label>
            <input
              placeholder={t('batchSampleSheet.runNamePrefixPlaceholder')}
              value={namePrefix}
              onChange={event => setNamePrefix(event.target.value)}
              style={{ ...INPUT_STYLE, flex: 1, maxWidth: 240 }}
            />
            {parsed && (
              <span style={{ color: 'var(--text-muted)', fontSize: 12 }}>
                {t('batchSampleSheet.sheetSummary', {
                  rows: t('batchSampleSheet.rowCount', { count: parsed.rows.length }),
                  columns: t('batchSampleSheet.columnCount', { count: parsed.headers.length }),
                  format: parsed.delimiter === '\t' ? 'TSV' : 'CSV',
                })}
              </span>
            )}
          </div>
          <textarea
            placeholder={t('batchSampleSheet.sheetPlaceholder')}
            value={rawText}
            onChange={event => setRawText(event.target.value)}
            style={{ ...INPUT_STYLE, minHeight: 120, fontFamily: 'JetBrains Mono, ui-monospace, monospace', resize: 'vertical' }}
          />
          {!parsed && rawText.length === 0 && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6, padding: '8px 12px' }}>
              <Skeleton variant="text" width="40%" height={12} />
              <Skeleton variant="text" width="80%" height={12} />
              <Skeleton variant="text" width="60%" height={12} />
            </div>
          )}
          {parsed && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              <strong style={{ fontSize: 12, color: 'var(--text-muted)' }}>{t('batchSampleSheet.columnMapping')}</strong>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 6 }}>
                {parsed.headers.map((header, index) => (
                  <div key={`${header}-${index}`} style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                    <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>{header || t('batchSampleSheet.columnFallback', { index: index + 1 })}</span>
                    <select
                      value={columnMap[index] ?? SKIP_VALUE}
                      onChange={event => setColumnMap(prev => ({ ...prev, [index]: event.target.value }))}
                      style={INPUT_STYLE}
                    >
                      <option value={SKIP_VALUE}>{t('batchSampleSheet.skip')}</option>
                      <option value={NAME_VALUE}>{t('batchSampleSheet.useAsRunName')}</option>
                      {paramOptions.map(option => (
                        <option key={option.value} value={option.value}>{option.label}</option>
                      ))}
                    </select>
                  </div>
                ))}
              </div>
            </div>
          )}
          {parsed && previewRuns.length > 0 && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
              <strong style={{ fontSize: 12, color: 'var(--text-muted)' }}>
                {t('batchSampleSheet.preview', {
                  shown: Math.min(previewRuns.length, MAX_PREVIEW_ROWS),
                  total: parsed.rows.length,
                })}
              </strong>
              <ol style={{ margin: 0, paddingLeft: 18, fontSize: 12, color: 'var(--text)' }}>
                {previewRuns.map(run => (
                  <li key={run.rowIndex}>{run.name}</li>
                ))}
              </ol>
            </div>
          )}
          {error && <div style={{ color: 'var(--danger, #dc3545)', fontSize: 12 }}>{error}</div>}
        </div>
        <div className="modal-footer">
          <button className="btn btn-sm" onClick={onClose}>{t('common.cancel')}</button>
          <button
            className="btn btn-primary btn-sm"
            disabled={!parsed || parsed.rows.length === 0 || mappedColumnCount === 0 || submitting}
            onClick={handleSubmit}
          >
            <Icon name="play" size={12} />
            {submitting
              ? ` ${t('batchSampleSheet.submitting')}`
              : ` ${t('batchSampleSheet.queueRuns', { count: parsed?.rows.length ?? 0 })}`}
          </button>
        </div>
      </div>
    </div>
  );
}
