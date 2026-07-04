// Native React Flow custom node for the BioNodulo workflow canvas.
//
// Full-rewrite clean core: a header (colour swatch, title, run-status dot) plus
// one row per input/output port, each carrying a native <Handle> whose id IS the
// port name — so edges map 1:1 to WorkflowEdge.from.output / to.input. The on-
// node action menu is React Flow's native <NodeToolbar>, shown while the node is
// selected. Interactive params render as on-node widgets (NodeWidgets). No custom
// overlays, previews, comments or collab cursors — those were removed in the rewrite.
import { memo, useContext } from 'react';
import { Handle, Position, NodeToolbar, NodeResizer, type NodeProps } from '@xyflow/react';
import { useTranslation } from 'react-i18next';
import { NODE_HEADER_H, NODE_PIN_H } from '../../utils/nodeLayout';
import type { GraphNode } from './canvasModel';
import { BioNodeActionsContext, MultiSelectContext } from './bioNodeActions';
import NodeWidgets from './NodeWidgets';

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

function BioNodeComponent({ id, data, selected }: NodeProps) {
  const { t } = useTranslation();
  const actions = useContext(BioNodeActionsContext);
  const multiSelected = useContext(MultiSelectContext);
  const { g, categoryLabel, missingDependency, running } = data as BioNodeData;

  // Reroute: a bare pass-through dot with a single in/out handle.
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
  // React Flow's <NodeToolbar> shows on selection by default — no hover state
  // (which would re-render the node on every mouse move). Suppressed during a
  // multi-select, where the canvas-level shared toolbar takes over.
  const showToolbar = selected && !multiSelected && g.type !== 'reroute';

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
        g.collapsed ? 'bio-node-collapsed' : '',
      ].filter(Boolean).join(' ')}
      style={{ ['--bio-node-color' as string]: g.color }}
      data-node-id={g.id}
      data-status={g.status ?? ''}
      data-category={categoryLabel}
    >
      {/* Native drag-to-resize handles — only for real (non-note) nodes and only
          while selected. Commit the final size back to the workflow on end. */}
      {!g.visualOnly && (
        <NodeResizer
          isVisible={selected}
          minWidth={140}
          minHeight={56}
          onResizeEnd={(_e, params) => actions?.resize(id, Math.round(params.width), Math.round(params.height))}
        />
      )}

      {/* Native React Flow toolbar — the "menu when clicking / hovering a node".
          Portalled + viewport-synced by React Flow, so no custom overlay math. */}
      <NodeToolbar isVisible={showToolbar} position={Position.Top} className="bio-node-toolbar">
        <button type="button" title={t('canvas.menu.run')} onClick={() => actions?.run(id)}>▶</button>
        <button type="button" title={t('canvas.menu.rename')} onClick={() => actions?.rename(id)}>A</button>
        <button type="button" title={t('canvas.menu.duplicate')} onClick={() => actions?.duplicate(id)}>⧉</button>
        <button type="button" title={t('canvas.menu.collapse')} onClick={() => actions?.toggleCollapse(id)}>{g.collapsed ? '▸' : '▾'}</button>
        <button type="button" className="danger" title={t('canvas.menu.delete')} onClick={() => actions?.remove(id)}>✕</button>
      </NodeToolbar>

      <div className="bio-node-header" style={{ height: NODE_HEADER_H, background: statusTint ?? g.color }}>
        <span className="bio-node-swatch" style={{ background: g.color }} />
        <span className="bio-node-title" title={g.title}>{g.title}</span>
        {g.pinned && <span className="bio-node-flag" aria-hidden>📌</span>}
        {g.status && <span className="bio-node-status" data-status={g.status} title={g.status} />}
      </div>

      {/* Note nodes are a text card; collapsed nodes hide their body. Every real
          port still gets a <Handle> so edges stay anchored — collapsed handles
          are pinned to the header centre via CSS. */}
      {g.visualOnly && g.type === 'note' ? (
        <div className="bio-node-note-body">{String(g.params?.text ?? '')}</div>
      ) : !g.visualOnly && !g.collapsed ? (
        <>
        <div className="bio-node-io">
          <div className="bio-node-inputs">
            {g.inputs.map(input => (
              <div className="bio-node-port bio-node-port-in" key={`in-${input.name}`} style={{ height: NODE_PIN_H }}>
                <Handle
                  type="target"
                  position={Position.Left}
                  id={input.name}
                  className={`bio-handle bio-handle-in ${input.connected ? 'connected' : ''}`}
                />
                <span className="bio-node-port-label">{input.name}</span>
              </div>
            ))}
          </div>
          <div className="bio-node-outputs">
            {g.outputs.map(output => (
              <div className="bio-node-port bio-node-port-out" key={`out-${output.name}`} style={{ height: NODE_PIN_H }}>
                <span className="bio-node-port-label">{output.name}</span>
                <Handle
                  type="source"
                  position={Position.Right}
                  id={output.name}
                  className={`bio-handle bio-handle-out ${output.connected ? 'connected' : ''}`}
                />
              </div>
            ))}
          </div>
        </div>
        <NodeWidgets nodeId={id} meta={g.meta} params={g.params} />
        </>
      ) : g.collapsed && !g.visualOnly ? (
        // Collapsed: keep handles for every port, pinned to header centre.
        <>
          {g.inputs.map(input => (
            <Handle
              key={`in-${input.name}`}
              type="target"
              position={Position.Left}
              id={input.name}
              className={`bio-handle bio-handle-in ${input.connected ? 'connected' : ''}`}
              style={{ top: NODE_HEADER_H / 2 }}
            />
          ))}
          {g.outputs.map(output => (
            <Handle
              key={`out-${output.name}`}
              type="source"
              position={Position.Right}
              id={output.name}
              className={`bio-handle bio-handle-out ${output.connected ? 'connected' : ''}`}
              style={{ top: NODE_HEADER_H / 2 }}
            />
          ))}
        </>
      ) : null}
    </div>
  );
}

// React Flow supplies a fresh `data` object every render (incl. every drag
// frame, where only x/y changed). Compare only the fields that affect what this
// node paints — never position (React Flow moves the wrapper via CSS transform).
function bioNodePropsEqual(prev: NodeProps, next: NodeProps): boolean {
  if (prev.selected !== next.selected || prev.dragging !== next.dragging) return false;
  const a = prev.data as BioNodeData;
  const b = next.data as BioNodeData;
  if (a === b) return true;
  if (a.categoryLabel !== b.categoryLabel || a.missingDependency !== b.missingDependency || a.running !== b.running) return false;
  const ga = a.g;
  const gb = b.g;
  if (ga === gb) return true;
  return (
    ga.width === gb.width &&
    ga.height === gb.height &&
    ga.color === gb.color &&
    ga.title === gb.title &&
    ga.status === gb.status &&
    ga.collapsed === gb.collapsed &&
    ga.muted === gb.muted &&
    ga.bypassed === gb.bypassed &&
    ga.pinned === gb.pinned &&
    ga.shape === gb.shape &&
    ga.visualOnly === gb.visualOnly &&
    ga.inputs === gb.inputs &&
    ga.outputs === gb.outputs &&
    ga.params === gb.params &&
    ga.meta === gb.meta
  );
}

const BioNode = memo(BioNodeComponent, bioNodePropsEqual);
export default BioNode;
