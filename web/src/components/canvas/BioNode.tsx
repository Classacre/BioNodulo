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
import { useAtomValue } from 'jotai';
import { nodeDownloadProgressAtom } from '../../state/runAtoms';
import { NODE_HEADER_H, NODE_PIN_H, toHexColor } from '../../utils/nodeLayout';
import type { GraphNode } from './canvasModel';
import { BioNodeActionsContext, MultiSelectContext } from './bioNodeActions';
import NodeWidgets from './NodeWidgets';
import NodePreview from './NodePreview';

export interface BioNodeData extends Record<string, unknown> {
  g: GraphNode;
  categoryLabel: string;
  missingDependency: boolean;
  running: boolean;
}

function BioNodeComponent({ id, data, selected }: NodeProps) {
  const { t } = useTranslation();
  const actions = useContext(BioNodeActionsContext);
  const multiSelected = useContext(MultiSelectContext);
  const { g, categoryLabel, missingDependency, running } = data as BioNodeData;
  // Remote-input download progress for THIS node. Shown on the node because a
  // toast in the corner is both far from the work and easy to miss; toasts are
  // reserved for the user's own uploads.
  const download = useAtomValue(nodeDownloadProgressAtom)[g.id];

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
        g.isSubgraph ? 'bio-node-subgraph' : '',
      ].filter(Boolean).join(' ')}
      style={{ ['--bio-node-color' as string]: g.color }}
      data-node-id={g.id}
      data-status={g.status ?? ''}
      data-category={categoryLabel}
    >
      {download && (
        <div
          className={`bio-node-download ${download.total > 0 ? '' : 'is-indeterminate'}`}
          role="progressbar"
          aria-valuemin={0}
          aria-valuemax={download.total || undefined}
          aria-valuenow={download.total ? download.downloaded : undefined}
          title={download.url}
        >
          <div
            className="bio-node-download-fill"
            style={
              download.total > 0
                ? { width: `${Math.min(100, (download.downloaded / download.total) * 100)}%` }
                : undefined
            }
          />
        </div>
      )}

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
        <button type="button" title={t('canvas.menu.run')} aria-label={t('canvas.menu.run')} onClick={() => actions?.run(id)}><span aria-hidden>▶</span></button>
        <button type="button" title={t('canvas.menu.rename')} aria-label={t('canvas.menu.rename')} onClick={() => actions?.rename(id)}><span aria-hidden>A</span></button>
        <button type="button" title={t('canvas.menu.duplicate')} aria-label={t('canvas.menu.duplicate')} onClick={() => actions?.duplicate(id)}><span aria-hidden>⧉</span></button>
        <button type="button" title={t('canvas.menu.collapse')} aria-label={t('canvas.menu.collapse')} onClick={() => actions?.toggleCollapse(id)}><span aria-hidden>{g.collapsed ? '▸' : '▾'}</span></button>
        {/* Node colour: the swatch IS a native colour input (opens the OS picker). */}
        <label className="bio-node-color-swatch nodrag nopan" title={t('canvas.menu.color')} style={{ background: g.color }}>
          <input
            type="color"
            aria-label={t('canvas.menu.color')}
            value={toHexColor(g.color)}
            onChange={(e) => actions?.setColor?.(id, e.target.value)}
          />
        </label>
        <button type="button" className="danger" title={t('canvas.menu.delete')} aria-label={t('canvas.menu.delete')} onClick={() => actions?.remove(id)}><span aria-hidden>✕</span></button>
      </NodeToolbar>

      <div className="bio-node-header" style={{ height: NODE_HEADER_H, background: g.color }}>
        {g.isSubgraph && <span className="bio-node-subgraph-chip">{t('canvas.subgraphChip')}</span>}
        <span className="bio-node-title" title={g.title}>{g.title}</span>
        {g.pinned && <span className="bio-node-flag" aria-hidden>📌</span>}
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
        <NodeWidgets nodeId={id} meta={g.meta} params={g.params} promoted={g.promotedInputs} />
        {/* Inline run-output preview (image / mini-table / chip). Subscribes
            to the previews atom itself, so the memoized node does not
            re-render when run history changes; the node auto-sizes to fit. */}
        <NodePreview nodeId={g.id} />
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
          {/* Promoted param inputs (widget dots) live in the body, which is hidden
              while collapsed — keep a header-pinned handle so their edges stay
              anchored. */}
          {g.promotedInputs.map(key => (
            <Handle
              key={`pin-${key}`}
              type="target"
              position={Position.Left}
              id={key}
              className="bio-handle bio-handle-in"
              style={{ top: NODE_HEADER_H / 2 }}
            />
          ))}
        </>
      ) : null}
    </div>
  );
}

type Port = GraphNode['inputs'][number];

// Content-compare port lists: the reconcile rebuilds inputs/outputs with fresh
// array + object identities every pass, so a reference check (a === b) would
// ALWAYS differ and defeat the memo — re-rendering every node on each status
// tick. Compare by the fields that actually paint a port instead.
function portsEqual(a: Port[], b: Port[]): boolean {
  if (a === b) return true;
  if (a.length !== b.length) return false;
  for (let i = 0; i < a.length; i += 1) {
    if (a[i].name !== b[i].name || a[i].type !== b[i].type || a[i].connected !== b[i].connected) return false;
  }
  return true;
}

// Shallow-compare param maps (widget values). New object identity each reconcile,
// so compare keys + values by reference (values are primitives or stable refs).
function paramsEqual(a: Record<string, unknown>, b: Record<string, unknown>): boolean {
  if (a === b) return true;
  const ka = Object.keys(a);
  const kb = Object.keys(b);
  if (ka.length !== kb.length) return false;
  for (const k of ka) {
    if (a[k] !== b[k]) return false;
  }
  return true;
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
    ga.isSubgraph === gb.isSubgraph &&
    ga.meta === gb.meta &&
    portsEqual(ga.inputs, gb.inputs) &&
    portsEqual(ga.outputs, gb.outputs) &&
    stringListEqual(ga.promotedInputs, gb.promotedInputs) &&
    paramsEqual(ga.params, gb.params)
  );
}

// Content-compare the promoted-input key list (fresh array each reconcile).
function stringListEqual(a: readonly string[], b: readonly string[]): boolean {
  if (a === b) return true;
  if (a.length !== b.length) return false;
  for (let i = 0; i < a.length; i += 1) if (a[i] !== b[i]) return false;
  return true;
}

const BioNode = memo(BioNodeComponent, bioNodePropsEqual);
export default BioNode;
