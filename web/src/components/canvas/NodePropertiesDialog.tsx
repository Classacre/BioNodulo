// Node info + edit-properties modal, opened from the node context menu. Shows the
// node's metadata (type / category / description / ports) and lets you rename it
// and edit its parameter values. Reuses the same interactive-widget detection as
// the on-node widgets so the same params are editable here.
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import type { WorkflowNode, ObjectInfo, InputSpec } from '../../types';
import { getVisibleInputSpecs } from '../../utils/nodeInputVisibility';
import { resolveNodeOutputs } from '../../utils/nodeOutputs';
import { isInteractiveWidgetSpec, isColorParam, toHexColor } from '../../utils/nodeLayout';

interface NodePropertiesDialogProps {
  node: WorkflowNode;
  objectInfo: ObjectInfo;
  onRename: (id: string, title: string) => void;
  onParamChange: (id: string, key: string, value: unknown) => void;
  onClose: () => void;
}

function ParamField({ pKey, spec, value, onChange }: {
  pKey: string; spec: InputSpec; value: unknown; onChange: (v: unknown) => void;
}) {
  const label = spec.label || pKey;
  if (spec.type === 'BOOLEAN') {
    return (
      <label className="bio-props-field bio-props-bool">
        <span>{label}</span>
        <input type="checkbox" checked={Boolean(value ?? spec.default)} onChange={e => onChange(e.target.checked)} />
      </label>
    );
  }
  if (Array.isArray(spec.options) && spec.options.length > 0) {
    return (
      <label className="bio-props-field">
        <span>{label}</span>
        <select value={String(value ?? spec.default ?? '')} onChange={e => onChange(e.target.value)}>
          {spec.options.map(o => <option key={o} value={o}>{o}</option>)}
        </select>
      </label>
    );
  }
  if (spec.type === 'INT' || spec.type === 'FLOAT') {
    const step = spec.step ?? (spec.type === 'INT' ? 1 : 0.1);
    return (
      <label className="bio-props-field">
        <span>{label}</span>
        <input type="number" min={spec.min} max={spec.max} step={step} defaultValue={Number(value ?? spec.default ?? 0)}
          onBlur={e => onChange(spec.type === 'INT' ? Math.round(Number(e.target.value)) : Number(e.target.value))} />
      </label>
    );
  }
  if (isColorParam(pKey, spec)) {
    return (
      <label className="bio-props-field">
        <span>{label}</span>
        <input type="color" defaultValue={toHexColor(value)} onBlur={e => onChange(e.target.value)} />
      </label>
    );
  }
  return (
    <label className="bio-props-field">
      <span>{label}</span>
      <input type="text" defaultValue={String(value ?? spec.default ?? '')} onBlur={e => onChange(e.target.value)} />
    </label>
  );
}

export default function NodePropertiesDialog({ node, objectInfo, onRename, onParamChange, onClose }: NodePropertiesDialogProps) {
  const { t } = useTranslation();
  const meta = node.type ? (objectInfo[node.type] || node.node_info || null) : (node.node_info || null);
  const [title, setTitle] = useState(node.ui?.title || meta?.display_name || node.type || '');
  const visible = getVisibleInputSpecs(meta, node.params || {});
  const editable = [...Object.entries(visible.required), ...Object.entries(visible.optional)]
    .filter(([, spec]) => isInteractiveWidgetSpec(spec));
  const outputs = resolveNodeOutputs(meta, node.params || {});
  const ports = [...Object.keys(visible.required), ...Object.keys(visible.optional)].filter(k => !editable.some(([ek]) => ek === k));

  return (
    <div className="bn-ui-overlay" role="presentation" onMouseDown={onClose}>
      <div className="bn-ui-dialog bio-props-dialog" role="dialog" aria-modal onMouseDown={e => e.stopPropagation()}>
        <header className="bn-ui-dialog-header">
          <div className="bn-ui-dialog-title">{t('canvas.props.title')}</div>
          <button type="button" className="bio-props-close" aria-label={t('common.close', 'Close')} onClick={onClose}><span aria-hidden>✕</span></button>
        </header>
        <div className="bn-ui-dialog-body bio-props-body">
          <label className="bio-props-field">
            <span>{t('canvas.props.name')}</span>
            <input type="text" value={title} onChange={e => setTitle(e.target.value)} onBlur={() => onRename(node.id, title)} />
          </label>
          <div className="bio-props-meta">
            <div><b>{t('canvas.props.type')}:</b> {node.type}</div>
            {meta?.category && <div><b>{t('canvas.props.category')}:</b> {meta.category}</div>}
            {meta?.description && <p className="bio-props-desc">{meta.description}</p>}
          </div>

          {editable.length > 0 && (
            <section className="bio-props-section">
              <h4>{t('canvas.props.parameters')}</h4>
              {editable.map(([key, spec]) => (
                <ParamField key={key} pKey={key} spec={spec} value={node.params?.[key]} onChange={v => onParamChange(node.id, key, v)} />
              ))}
            </section>
          )}

          {(ports.length > 0 || outputs.length > 0) && (
            <section className="bio-props-section bio-props-ports">
              {ports.length > 0 && <div><b>{t('canvas.props.inputs')}:</b> {ports.join(', ')}</div>}
              {outputs.length > 0 && <div><b>{t('canvas.props.outputs')}:</b> {outputs.map(o => o.name).join(', ')}</div>}
            </section>
          )}
        </div>
        <footer className="bn-ui-dialog-footer">
          <button type="button" className="bn-ui-button" onClick={onClose}>{t('common.done', 'Done')}</button>
        </footer>
      </div>
    </div>
  );
}
