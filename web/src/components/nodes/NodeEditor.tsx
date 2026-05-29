import { useState, useCallback } from 'react';
import type { GraphNode } from '../canvas/WorkflowCanvas';
import Icon from '../ui/Icon';

interface NodeEditorProps {
  node?: GraphNode;
  onParamChange: (nodeId: string, key: string, value: unknown) => void;
  onClose: () => void;
}

export default function NodeEditor({ node, onParamChange, onClose }: NodeEditorProps) {
  const [showAdvanced, setShowAdvanced] = useState(false);
  if (!node) return null;
  const meta = node.meta;
  const required = meta?.input_types?.required || {};
  const optional = meta?.input_types?.optional || {};

  const hasAdvanced = Object.values(optional).some((s: any) => s?.advanced);

  return (
    <div className="node-editor">
      <div className="node-editor-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', background: node.color, color: 'white', borderRadius: '10px 10px 0 0' }}>
        <span>{node.title}</span>
        <button className="btn btn-icon btn-sm" onClick={onClose} style={{ background: 'transparent', border: 'none', color: 'white' }}>
          <Icon name="close" size={14} />
        </button>
      </div>
      <div className="node-editor-body">
        {meta?.description && <p style={{ fontSize: 11, color: 'var(--muted)', marginBottom: 10 }}>{meta.description}</p>}

        {Object.keys(required).length > 0 && (
          <>
            <div style={{ fontSize: 10, fontWeight: 700, textTransform: 'uppercase', color: 'var(--muted)', marginBottom: 8, letterSpacing: '0.05em' }}>Required</div>
            {Object.entries(required).map(([key, spec]) => renderParam(key, spec as any, node, onParamChange))}
          </>
        )}

        {Object.keys(optional).length > 0 && (
          <>
            <div style={{ fontSize: 10, fontWeight: 700, textTransform: 'uppercase', color: 'var(--muted)', margin: '12px 0 8px', letterSpacing: '0.05em' }}>
              Optional
              {hasAdvanced && (
                <button
                  onClick={() => setShowAdvanced(v => !v)}
                  style={{ marginLeft: 8, fontSize: 9, padding: '2px 6px', borderRadius: 4, border: '1px solid var(--border)', background: 'var(--surface-2)', color: 'var(--muted)', cursor: 'pointer' }}
                >
                  {showAdvanced ? 'Hide Advanced' : 'Show Advanced'}
                </button>
              )}
            </div>
            {Object.entries(optional).map(([key, spec]) => {
              const s = spec as any;
              if (s?.advanced && !showAdvanced) return null;
              return renderParam(key, s, node, onParamChange);
            })}
          </>
        )}

        {meta?.requires_external_tools && meta.requires_external_tools.length > 0 && (
          <div style={{ marginTop: 12, padding: 8, borderRadius: 6, background: 'var(--surface-2)', fontSize: 11 }}>
            <strong style={{ fontSize: 10, textTransform: 'uppercase', color: 'var(--muted)' }}>Required Tools</strong>
            <div style={{ display: 'flex', gap: 4, marginTop: 4, flexWrap: 'wrap' }}>
              {meta.requires_external_tools.map(t => (
                <span key={t} style={{ padding: '2px 6px', borderRadius: 4, background: 'var(--accent-light)', color: 'var(--accent-dark)', fontSize: 10 }}>{t}</span>
              ))}
            </div>
          </div>
        )}

        {meta?.documentation_url && (
          <div style={{ marginTop: 8 }}>
            <a href={meta.documentation_url} target="_blank" rel="noopener noreferrer" style={{ fontSize: 11, color: 'var(--accent)' }}>
              Documentation ↗
            </a>
          </div>
        )}
      </div>
    </div>
  );
}

function FileDropZone({ value, accept, directory, onChange }: { value: string; accept?: string; directory?: boolean; onChange: (v: string) => void }) {
  const [dragOver, setDragOver] = useState(false);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    void accept;
    const item = e.dataTransfer.items?.[0];
    if (item) {
      const entry = item.webkitGetAsEntry?.();
      if (entry) {
        if (directory && entry.isDirectory) {
          onChange('');
        } else if (!directory && entry.isFile) {
          const file = e.dataTransfer.files[0];
          if (file) onChange(file.name);
        }
      } else {
        const file = e.dataTransfer.files[0];
        if (file) onChange(file.name);
      }
    }
  }, [accept, directory, onChange]);

  return (
    <div
      onDragOver={e => { e.preventDefault(); setDragOver(true); }}
      onDragLeave={() => setDragOver(false)}
      onDrop={handleDrop}
      style={{
        border: `2px dashed ${dragOver ? 'var(--accent)' : 'var(--border-2)'}`,
        borderRadius: 6,
        padding: '6px 8px',
        background: dragOver ? 'var(--accent-light)' : 'var(--surface-2)',
        transition: 'all 0.2s',
        display: 'flex',
        alignItems: 'center',
        gap: 6,
      }}
    >
      <input
        type="text"
        className="text-input param-input"
        style={{ border: 'none', background: 'transparent', flex: 1, padding: 0 }}
        value={String(value)}
        placeholder={directory ? 'Drop directory or type path...' : 'Drop file or type path...'}
        onChange={e => onChange(e.target.value)}
      />
      <span style={{ fontSize: 10, color: 'var(--muted)', whiteSpace: 'nowrap' }}>📁</span>
    </div>
  );
}

function SliderInput({ value, min, max, step, onChange }: { value: number; min?: number; max?: number; step?: number; onChange: (v: number) => void }) {
  const num = Number(value) || 0;
  const pmin = min ?? 0;
  const pmax = max ?? 100;

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
      <input
        type="range"
        min={pmin} max={pmax} step={step || 1}
        value={num}
        onChange={e => onChange(parseFloat(e.target.value))}
        style={{ flex: 1, accentColor: 'var(--accent)' }}
      />
      <input
        type="number"
        className="text-input param-input"
        style={{ width: 60, fontSize: 11, padding: '4px 6px' }}
        min={pmin} max={pmax} step={step || 1}
        value={num}
        onChange={e => onChange(parseFloat(e.target.value))}
      />
    </div>
  );
}

function renderParam(key: string, spec: {
  type: string; default?: unknown; options?: string[]; min?: number; max?: number; step?: number;
  tooltip?: string; label?: string; advanced?: boolean; multiline?: boolean; display?: string;
  accept?: string; directory?: boolean;
}, node: GraphNode, onChange: (nodeId: string, key: string, value: unknown) => void) {
  const label = spec.label || key;
  const value = node.params[key] ?? spec.default ?? '';
  const isFileLike = spec.type === 'FILE' || spec.type === 'FASTA' || spec.type === 'FASTQ' || spec.type === 'BAM' || spec.type === 'VCF' || spec.type === 'GFF' || spec.type === 'GTF' || spec.type === 'BED' || spec.type === 'ASSEMBLY' || spec.type === 'CONTIGS' || spec.type === 'INDEX_DIR' || spec.type === 'QC_REPORT_DIR' || spec.type === 'HTML_REPORT' || spec.type === 'KRAKEN_REPORT';
  const isDirLike = spec.type === 'DIRECTORY' || spec.type === 'INDEX_DIR' || spec.type === 'QC_REPORT_DIR';

  let control: React.ReactNode;

  if (spec.type === 'BOOLEAN') {
    control = (
      <div className={`toggle ${value ? 'on' : ''}`} onClick={() => onChange(node.id, key, !value)} />
    );
  } else if (spec.options && spec.options.length > 0) {
    control = (
      <select className="select-input param-input" value={String(value)} onChange={e => onChange(node.id, key, e.target.value)}>
        {spec.options.map(o => <option key={o} value={o}>{o}</option>)}
      </select>
    );
  } else if ((spec.type === 'INT' || spec.type === 'FLOAT') && spec.display === 'slider') {
    control = <SliderInput value={Number(value)} min={spec.min} max={spec.max} step={spec.step} onChange={v => onChange(node.id, key, spec.type === 'INT' ? Math.round(v) : v)} />;
  } else if (spec.type === 'INT' || spec.type === 'FLOAT') {
    control = (
      <input
        type="number"
        className="text-input param-input"
        value={value as number}
        min={spec.min} max={spec.max} step={spec.step}
        onChange={e => onChange(node.id, key, spec.type === 'INT' ? parseInt(e.target.value) : parseFloat(e.target.value))}
      />
    );
  } else if (spec.multiline) {
    control = (
      <textarea
        className="text-input param-input"
        style={{ minHeight: 60, resize: 'vertical', fontFamily: 'JetBrains Mono, monospace', fontSize: 11 }}
        value={String(value)}
        onChange={e => onChange(node.id, key, e.target.value)}
      />
    );
  } else if (isFileLike || isDirLike) {
    control = <FileDropZone value={String(value)} accept={spec.accept} directory={isDirLike} onChange={v => onChange(node.id, key, v)} />;
  } else {
    control = (
      <input
        type="text"
        className="text-input param-input"
        value={String(value)}
        onChange={e => onChange(node.id, key, e.target.value)}
      />
    );
  }

  return (
    <div key={key} className="param-row">
      <label className="param-label" title={spec.tooltip}>{label}{spec.advanced ? <span style={{ fontSize: 9, color: 'var(--warning)', marginLeft: 4 }}>adv</span> : null}</label>
      {control}
    </div>
  );
}
