// Interactive on-node controls (buttons/toggles/sliders/selects/number/text/
// colour), rendered INSIDE the custom node the native React Flow way: the
// `nodrag`/`nopan` classes stop the control from dragging the node or panning
// the canvas, and edits are written straight back to the node's params via the
// BioNodeActions context. The node auto-sizes to fit these (React Flow measures
// the DOM), so there's no height math here.
import { memo, useContext } from 'react';
import type { InputSpec, NodeMetadata } from '../../types';
import { getInteractiveWidgetEntries, isColorParam, toHexColor } from '../../utils/nodeLayout';
import { BioNodeActionsContext } from './bioNodeActions';

interface WidgetRowProps {
  nodeId: string;
  pKey: string;
  spec: InputSpec;
  value: unknown;
  onSet: (id: string, key: string, value: unknown, history?: boolean) => void;
}

function WidgetRow({ nodeId, pKey, spec, value, onSet }: WidgetRowProps) {
  const label = spec.label || pKey;
  const current = value ?? spec.default;

  // Boolean -> toggle checkbox.
  if (spec.type === 'BOOLEAN') {
    return (
      <label className="bio-widget bio-widget-bool nodrag nopan" title={spec.tooltip || label}>
        <span className="bio-widget-label">{label}</span>
        <input
          type="checkbox"
          checked={Boolean(current)}
          onChange={(e) => onSet(nodeId, pKey, e.target.checked)}
        />
      </label>
    );
  }

  // Enum / options -> select.
  if (Array.isArray(spec.options) && spec.options.length > 0) {
    return (
      <label className="bio-widget nodrag nopan" title={spec.tooltip || label}>
        <span className="bio-widget-label">{label}</span>
        <select
          className="nodrag nopan"
          value={String(current ?? '')}
          onChange={(e) => onSet(nodeId, pKey, e.target.value)}
        >
          {spec.options.map((opt) => <option key={opt} value={opt}>{opt}</option>)}
        </select>
      </label>
    );
  }

  // Numeric -> slider (when display:'slider' with bounds) or number input.
  if (spec.type === 'INT' || spec.type === 'FLOAT') {
    const step = spec.step ?? (spec.type === 'INT' ? 1 : 0.1);
    const num = typeof current === 'number' ? current : Number(current ?? 0);
    const coerce = (v: string) => (spec.type === 'INT' ? Math.round(Number(v)) : Number(v));
    if (spec.display === 'slider' && typeof spec.min === 'number' && typeof spec.max === 'number') {
      return (
        <label className="bio-widget bio-widget-slider nodrag nopan" title={spec.tooltip || label}>
          <span className="bio-widget-label">{label}</span>
          <input
            type="range"
            className="nodrag nopan"
            min={spec.min}
            max={spec.max}
            step={step}
            value={Number.isFinite(num) ? num : spec.min}
            onChange={(e) => onSet(nodeId, pKey, coerce(e.target.value), false)}
            onPointerUp={(e) => onSet(nodeId, pKey, coerce((e.target as HTMLInputElement).value), true)}
          />
          <output className="bio-widget-value">{Number.isFinite(num) ? num : spec.min}</output>
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
          onChange={(e) => onSet(nodeId, pKey, coerce(e.target.value), false)}
          onBlur={(e) => onSet(nodeId, pKey, coerce(e.target.value), true)}
        />
      </label>
    );
  }

  // Colour string -> swatch picker + hex text.
  if (isColorParam(pKey, spec)) {
    const hex = toHexColor(current);
    return (
      <label className="bio-widget bio-widget-color nodrag nopan" title={spec.tooltip || label}>
        <span className="bio-widget-label">{label}</span>
        <input
          type="color"
          className="nodrag nopan"
          value={hex}
          onChange={(e) => onSet(nodeId, pKey, e.target.value, false)}
          onBlur={(e) => onSet(nodeId, pKey, e.target.value, true)}
        />
      </label>
    );
  }

  // String -> text input.
  return (
    <label className="bio-widget nodrag nopan" title={spec.tooltip || label}>
      <span className="bio-widget-label">{label}</span>
      <input
        type="text"
        className="nodrag nopan"
        value={String(current ?? '')}
        onChange={(e) => onSet(nodeId, pKey, e.target.value, false)}
        onBlur={(e) => onSet(nodeId, pKey, e.target.value, true)}
      />
    </label>
  );
}

function NodeWidgetsComponent({ nodeId, meta, params }: {
  nodeId: string;
  meta: NodeMetadata | null;
  params: Record<string, unknown>;
}) {
  const actions = useContext(BioNodeActionsContext);
  const entries = getInteractiveWidgetEntries(meta, params);
  if (entries.length === 0 || !actions) return null;
  return (
    <div className="bio-node-widgets">
      {entries.map(({ key, spec }) => (
        <WidgetRow key={key} nodeId={nodeId} pKey={key} spec={spec} value={params[key]} onSet={actions.setParam} />
      ))}
    </div>
  );
}

const NodeWidgets = memo(NodeWidgetsComponent);
export default NodeWidgets;
