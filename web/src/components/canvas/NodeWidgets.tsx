// Interactive on-node controls (buttons/toggles/sliders/selects/number/text/
// colour), rendered INSIDE the custom node the native React Flow way: the
// `nodrag`/`nopan` classes stop the control from dragging the node or panning
// the canvas, and edits are written straight back to the node's params via the
// BioNodeActions context. The node auto-sizes to fit these (React Flow measures
// the DOM), so there's no height math here.
import { memo, useContext, useEffect, useState } from 'react';
import { Handle, Position, useNodeConnections } from '@xyflow/react';
import type { InputSpec, NodeMetadata } from '../../types';
import {
  formatJsonWidgetValue,
  getInteractiveWidgetEntries,
  isColorParam,
  parseJsonWidgetValue,
  parseNumericWidgetValue,
  toHexColor,
} from '../../utils/nodeLayout';
import { BioNodeActionsContext } from './bioNodeActions';

// Input dot beside a promoted widget: a native target <Handle> (id = param key)
// so an edge can drive the widget's value. The widget itself stays rendered —
// this only exposes a connection point. Fills in when an edge is attached.
function WidgetHandle({ pKey }: { pKey: string }) {
  const connections = useNodeConnections({ handleType: 'target', handleId: pKey });
  return (
    <Handle
      type="target"
      position={Position.Left}
      id={pKey}
      className={`bio-handle bio-handle-in bio-widget-handle ${connections.length ? 'connected' : ''}`}
    />
  );
}

interface WidgetRowProps {
  nodeId: string;
  pKey: string;
  spec: InputSpec;
  value: unknown;
  optional: boolean;
  onSet: (id: string, key: string, value: unknown, history?: boolean) => void;
}

// Continuous inputs (text/number/slider/colour) edit LOCAL state so a keystroke
// or slider drag never rebuilds the whole workflow — the value is committed to
// the node's params only on blur / pointer-up. Discrete inputs (checkbox/select)
// commit immediately. This is React Flow's interactive-node pattern (local state
// + commit) and keeps large graphs responsive.
function WidgetRow({ nodeId, pKey, spec, value, optional, onSet }: WidgetRowProps) {
  const label = spec.label || pKey;
  const external = value ?? spec.default;
  const [local, setLocal] = useState<unknown>(external);
  // Resync when the param changes from outside (undo/redo, collab, reset).
  useEffect(() => { setLocal(external); }, [external]);

  // Boolean -> toggle checkbox (commit immediately).
  if (spec.type === 'BOOLEAN') {
    if (optional && spec.default == null) {
      return (
        <label className="bio-widget nodrag nopan" title={spec.tooltip || label}>
          <span className="bio-widget-label">{label}</span>
          <select value={external == null ? '' : String(external)}
            onChange={e => onSet(nodeId, pKey, e.target.value === '' ? undefined : e.target.value === 'true', true)}>
            <option value="">Use tool default</option>
            <option value="true">True</option>
            <option value="false">False</option>
          </select>
        </label>
      );
    }
    return (
      <label className="bio-widget bio-widget-bool nodrag nopan" title={spec.tooltip || label}>
        <span className="bio-widget-label">{label}</span>
        <input
          type="checkbox"
          checked={Boolean(external)}
          onChange={(e) => onSet(nodeId, pKey, e.target.checked, true)}
        />
      </label>
    );
  }

  // Enum / options -> select (commit immediately).
  if (Array.isArray(spec.options) && spec.options.length > 0) {
    return (
      <label className="bio-widget nodrag nopan" title={spec.tooltip || label}>
        <span className="bio-widget-label">{label}</span>
        <select
          className="nodrag nopan"
          value={String(external ?? '')}
          onChange={(e) => onSet(nodeId, pKey, e.target.value === '' && !spec.options?.includes('') ? undefined : e.target.value, true)}
        >
          {!spec.options.includes('') && <option value="">{optional ? 'Use tool default' : 'Choose a value'}</option>}
          {spec.options.map((opt) => <option key={opt} value={opt}>{opt}</option>)}
        </select>
      </label>
    );
  }

  // Numeric -> slider (when display:'slider' with bounds) or number input.
  if (spec.type === 'INT' || spec.type === 'FLOAT') {
    const step = spec.step ?? (spec.type === 'INT' ? 1 : 0.1);
    const num = local == null || local === '' ? NaN : Number(local);
    const shown = Number.isFinite(num) ? num : (spec.min ?? 0);
    const coerce = (v: string) => parseNumericWidgetValue(v, spec.type);
    if (spec.display === 'slider' && (!optional || typeof spec.default === 'number') && typeof spec.min === 'number' && typeof spec.max === 'number') {
      return (
        <label className="bio-widget bio-widget-slider nodrag nopan" title={spec.tooltip || label}>
          <span className="bio-widget-label">{label}</span>
          <input
            type="range"
            className="nodrag nopan"
            min={spec.min}
            max={spec.max}
            step={step}
            value={shown}
            onChange={(e) => setLocal(coerce(e.target.value))}
            onPointerUp={(e) => onSet(nodeId, pKey, coerce((e.target as HTMLInputElement).value), true)}
          />
          <output className="bio-widget-value">{shown}</output>
        </label>
      );
    }
    return (
      <label className="bio-widget nodrag nopan" title={spec.tooltip || label}>
        <span className="bio-widget-label">{label}</span>
        <input
          type="number"
          className="nodrag nopan"
          min={spec.min}
          max={spec.max}
          step={step}
          value={Number.isFinite(num) ? num : ''}
          placeholder={optional ? 'Use tool default' : undefined}
          onChange={(e) => setLocal(coerce(e.target.value))}
          onBlur={(e) => onSet(nodeId, pKey, coerce(e.target.value), true)}
        />
      </label>
    );
  }

  if (spec.type === 'JSON') {
    const text = formatJsonWidgetValue(local);
    return (
      <label className="bio-widget nodrag nopan" title={spec.tooltip || spec.description || label}>
        <span className="bio-widget-label">{label}</span>
        <textarea
          className="nodrag nopan"
          value={text}
          onChange={(e) => setLocal(e.target.value)}
          onBlur={(e) => {
            try {
              onSet(nodeId, pKey, optional && !e.target.value.trim() ? undefined : parseJsonWidgetValue(e.target.value), true);
              e.target.setCustomValidity('');
            } catch {
              e.target.setCustomValidity('Enter valid JSON.');
              e.target.reportValidity();
            }
          }}
        />
      </label>
    );
  }

  // Colour string -> swatch picker (commit on blur).
  if (isColorParam(pKey, spec)) {
    return (
      <label className="bio-widget bio-widget-color nodrag nopan" title={spec.tooltip || label}>
        <span className="bio-widget-label">{label}</span>
        <input
          type="color"
          className="nodrag nopan"
          value={toHexColor(local)}
          onChange={(e) => setLocal(e.target.value)}
          onBlur={(e) => onSet(nodeId, pKey, e.target.value, true)}
        />
      </label>
    );
  }

  // String -> text input (commit on blur).
  return (
    <label className="bio-widget nodrag nopan" title={spec.tooltip || spec.description || label}>
      <span className="bio-widget-label">{label}</span>
      <input
        type="text"
        className="nodrag nopan"
        value={String(local ?? '')}
        onChange={(e) => setLocal(e.target.value)}
        onBlur={(e) => onSet(nodeId, pKey, optional && spec.default !== '' && e.target.value === '' ? undefined : e.target.value, true)}
      />
    </label>
  );
}

function NodeWidgetsComponent({ nodeId, meta, params, promoted }: {
  nodeId: string;
  meta: NodeMetadata | null;
  params: Record<string, unknown>;
  // Param keys promoted to input ports — rendered as handles, not widgets.
  promoted?: readonly string[];
}) {
  const actions = useContext(BioNodeActionsContext);
  const entries = getInteractiveWidgetEntries(meta, params);
  if (entries.length === 0 || !actions) return null;
  const promotedSet = promoted && promoted.length ? new Set(promoted) : null;
  return (
    <div className="bio-node-widgets">
      {entries.map(({ key, spec }) => {
        const isPromoted = promotedSet?.has(key) ?? false;
        return (
          <div className={`bio-widget-wrap ${isPromoted ? 'has-input' : ''}`} key={key}>
            {isPromoted && <WidgetHandle pKey={key} />}
            <WidgetRow nodeId={nodeId} pKey={key} spec={spec} value={params[key]}
              optional={Object.prototype.hasOwnProperty.call(meta?.input_types?.optional || {}, key)} onSet={actions.setParam} />
          </div>
        );
      })}
    </div>
  );
}

const NodeWidgets = memo(NodeWidgetsComponent);
export default NodeWidgets;
