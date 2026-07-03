// Custom React Flow node for the BioNodulo workflow canvas. Renders the node
// "body" that the legacy Canvas2D implementation used to draw: header (title,
// category, status/muted/bypassed state) plus input/output port rows whose
// React Flow <Handle> ids are the port names, so edges map 1:1 to
// WorkflowEdge.from.output / to.input. Interactive widgets, inline previews,
// error badges and comment pins remain separate viewport-synced overlays
// rendered by WorkflowCanvas (unchanged from the legacy DOM layer).
import { memo } from 'react';
import { Handle, Position, type NodeProps } from '@xyflow/react';
import { useTranslation } from 'react-i18next';
import type { TFunction } from 'i18next';
import { NODE_HEADER_H, NODE_PIN_H, getInteractiveWidgetEntries } from '../../utils/nodeLayout';
import type { GraphNode } from './canvasModel';

// Compact display of a node parameter value for the on-node summary rows (the
// non-interactive params that have no widget). Mirrors the legacy Canvas2D
// param formatter, including the localized array item count.
function formatNodeParamValue(value: unknown, t: TFunction): string {
  if (value === null || value === undefined || value === '') return '-';
  if (typeof value === 'boolean') return value ? 'true' : 'false';
  if (typeof value === 'number') {
    if (Number.isInteger(value)) return String(value);
    // Round to 3 dp but don't strip via a trailing-zero regex — that turned
    // sub-millidecimals like 0.0001 into an empty string ("0.000" → ""). Let
    // Number re-parse handle the trimming instead.
    return String(Number(value.toFixed(3)));
  }
  if (Array.isArray(value)) return t('canvas.itemCount', { count: value.length });
  if (typeof value === 'object') return '{...}';
  const text = String(value);
  return text.length > 24 ? `${text.slice(0, 21)}...` : text;
}

export interface BioNodeData extends Record<string, unknown> {
  g: GraphNode;
  categoryLabel: string;
  missingDependency: boolean;
  running: boolean;
}

const STATUS_TINT: Record<string, string> = {
  running: '#3b82f6',
  completed: '#22c55e',
  cached: '#a855f7',
  error: '#ef4444',
  skipped: '#64748b',
  pending: '#f59e0b',
};

function BioNodeComponent({ data, selected }: NodeProps) {
  const { t } = useTranslation();
  const { g, categoryLabel, missingDependency, running } = data as BioNodeData;

  if (g.type === 'reroute') {
    return (
      <div
        className={`bio-node bio-node-reroute ${selected ? 'selected' : ''}`}
        style={{ width: g.width, height: g.height, background: g.color }}
        title={g.title}
      >
        <Handle type="target" position={Position.Left} id="input" className="bio-handle bio-handle-in" />
        <Handle type="source" position={Position.Right} id="output" className="bio-handle bio-handle-out" />
      </div>
    );
  }

  const statusTint = g.status ? STATUS_TINT[g.status] : undefined;
  const ioCount = Math.max(g.inputs.length, g.outputs.length);
  const ioHeight = ioCount * NODE_PIN_H;

  // Collapsed nodes shrink to just their header (height === NODE_HEADER_H), so
  // the per-port IO rows are hidden. React Flow still anchors edges at each
  // <Handle>'s DOM position, so we MUST keep a handle for every real port id
  // (edges reference port names as source/targetHandle) — but pin them all to
  // the header's vertical center so edges attach to the visible node instead of
  // dangling below it (the pre-fix bug: handles positioned by index math at
  // ≥43px, outside the 32px collapsed body and clipped by overflow:hidden).
  if (g.collapsed) {
    const handleTop = NODE_HEADER_H / 2;
    return (
      <div
        className={[
          'bio-node',
          'bio-node-collapsed',
          `bio-node-shape-${g.shape}`,
          selected ? 'selected' : '',
          g.muted ? 'muted' : '',
          g.bypassed ? 'bypassed' : '',
          missingDependency ? 'missing-dep' : '',
          running ? 'running' : '',
        ].filter(Boolean).join(' ')}
        style={{ width: g.width, height: g.height, ['--bio-node-color' as string]: g.color }}
        data-node-id={g.id}
        data-status={g.status ?? ''}
        data-category={categoryLabel}
      >
        <div className="bio-node-header" style={{ height: NODE_HEADER_H, background: statusTint ?? g.color }}>
          <span className="bio-node-swatch" style={{ background: g.color }} />
          <span className="bio-node-title" title={g.title}>{g.title}</span>
          {g.pinned && <span className="bio-node-flag" aria-hidden>📌</span>}
          {g.status && <span className="bio-node-status" data-status={g.status} title={g.status} />}
        </div>
        {g.inputs.map(input => (
          <Handle
            key={`in-${input.name}`}
            type="target"
            position={Position.Left}
            id={input.name}
            className={`bio-handle bio-handle-in ${input.connected ? 'connected' : ''}`}
            style={{ top: handleTop }}
          />
        ))}
        {g.outputs.map(output => (
          <Handle
            key={`out-${output.name}`}
            type="source"
            position={Position.Right}
            id={output.name}
            className={`bio-handle bio-handle-out ${output.connected ? 'connected' : ''}`}
            style={{ top: handleTop }}
          />
        ))}
      </div>
    );
  }

  // Non-interactive params (no widget) get a compact read-only summary row so
  // key configuration stays visible on the node face, mirroring the legacy
  // Canvas2D param summaries.
  const widgetKeys = new Set(getInteractiveWidgetEntries(g.meta, g.params).map(entry => entry.key));
  const summaryEntries = g.visualOnly
    ? []
    : Object.entries(g.params)
      .filter(([key, value]) => !widgetKeys.has(key) && !key.startsWith('_') && value !== null && value !== undefined && value !== '')
      .slice(0, 4);

  return (
    <div
      className={[
        'bio-node',
        `bio-node-shape-${g.shape}`,
        selected ? 'selected' : '',
        g.muted ? 'muted' : '',
        g.bypassed ? 'bypassed' : '',
        missingDependency ? 'missing-dep' : '',
        running ? 'running' : '',
      ].filter(Boolean).join(' ')}
      style={{ width: g.width, height: g.height, ['--bio-node-color' as string]: g.color }}
      data-node-id={g.id}
      data-status={g.status ?? ''}
      data-category={categoryLabel}
    >
      <div
        className="bio-node-header"
        style={{ height: NODE_HEADER_H, background: statusTint ?? g.color }}
      >
        <span className="bio-node-swatch" style={{ background: g.color }} />
        <span className="bio-node-title" title={g.title}>{g.title}</span>
        {g.pinned && <span className="bio-node-flag" aria-hidden>📌</span>}
        {g.status && <span className="bio-node-status" data-status={g.status} title={g.status} />}
      </div>

      {g.visualOnly ? (
        g.type === 'note' ? (
          <div className="bio-node-note-body">{String(g.params?.text ?? '')}</div>
        ) : null
      ) : (
        <div className="bio-node-io" style={{ minHeight: ioHeight }}>
          <div className="bio-node-inputs">
            {g.inputs.map((input, index) => (
              <div
                className="bio-node-port bio-node-port-in"
                key={`in-${input.name}`}
                style={{ height: NODE_PIN_H }}
              >
                <Handle
                  type="target"
                  position={Position.Left}
                  id={input.name}
                  className={`bio-handle bio-handle-in ${input.connected ? 'connected' : ''}`}
                  style={{ top: NODE_HEADER_H + NODE_PIN_H / 2 + index * NODE_PIN_H }}
                />
                <span className="bio-node-port-label">{input.name}</span>
              </div>
            ))}
          </div>
          <div className="bio-node-outputs">
            {g.outputs.map((output, index) => (
              <div
                className="bio-node-port bio-node-port-out"
                key={`out-${output.name}`}
                style={{ height: NODE_PIN_H }}
              >
                <span className="bio-node-port-label">{output.name}</span>
                <Handle
                  type="source"
                  position={Position.Right}
                  id={output.name}
                  className={`bio-handle bio-handle-out ${output.connected ? 'connected' : ''}`}
                  style={{ top: NODE_HEADER_H + NODE_PIN_H / 2 + index * NODE_PIN_H }}
                />
              </div>
            ))}
          </div>
        </div>
      )}

      {summaryEntries.length > 0 && (
        <div className="bio-node-params">
          {summaryEntries.map(([key, value]) => (
            <div className="bio-node-param" key={`param-${key}`}>{`${key}: ${formatNodeParamValue(value, t)}`}</div>
          ))}
        </div>
      )}
    </div>
  );
}

const BioNode = memo(BioNodeComponent);
export default BioNode;
