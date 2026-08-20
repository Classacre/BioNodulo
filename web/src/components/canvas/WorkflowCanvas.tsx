// BioNodulo workflow canvas — full rewrite on native React Flow (@xyflow/react).
//
// Everything the canvas does now comes from React Flow itself: pan/zoom, node
// drag, multi-select, box-select, edge creation, deletion, the <Controls>
// widget, the <MiniMap>, the dotted <Background>, and the per-node <NodeToolbar>
// action menu (in BioNode). All the old custom chrome (hand-rolled minimap,
// selection toolbox, group boxes, subgraph nesting, inline previews, on-node
// widgets, collab cursors/comments) was deleted — this file is intentionally
// small so there is far less bespoke canvas code to maintain.
import {
  useEffect, useRef, useCallback, useMemo, useState, forwardRef, useImperativeHandle,
} from 'react';
import {
  ReactFlow,
  ReactFlowProvider,
  Background,
  BackgroundVariant,
  Controls,
  ControlButton,
  MiniMap,
  NodeToolbar,
  Position,
  MarkerType,
  ConnectionLineType,
  SelectionMode,
  applyNodeChanges,
  applyEdgeChanges,
  useReactFlow,
  useKeyPress,
  type Node as RFNode,
  type Edge as RFEdge,
  type NodeChange,
  type NodePositionChange,
  type EdgeChange,
  type Connection,
  type OnSelectionChangeParams,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { useAtomValue, useSetAtom } from 'jotai';
import { useTranslation } from 'react-i18next';
import { toast } from '../../state/notifications';
import { setViewportCenterReader } from '../../state/canvasViewport';
import type { WorkflowNode, WorkflowEdge, ObjectInfo, NodeStatus, WorkflowParameter } from '../../types';
import type { AwarenessState, Comment } from '../../collab/types';
import { edgeColorForSource } from '../../utils';
import { nodeCategoryDisplayLabel } from '../../utils/nodeCategories';
import { getVisibleInputSpecs } from '../../utils/nodeInputVisibility';
import { resolveNodeOutputs } from '../../utils/nodeOutputs';
import {
  NODE_WIDTH, NODE_NOTE_WIDTH, nodeColor,
  type GraphNode, type WorkflowCanvasRef,
} from './canvasModel';
import { NODE_HEADER_H, isInteractiveWidgetSpec, getPromotableParamKeys } from '../../utils/nodeLayout';
import { dagreLayout } from '../../utils/dagreLayout';
import { useSettings } from '../../hooks/settings';
import { promptDialog } from '../ui';
import { logError } from '../../state/logging';
import { getResolvedPaletteMode } from '../../state/palettes';
import { selectedNodeIdAtom } from '../../state/uiAtoms';
import {
  subgraphNavAtom, enterSubgraphAtom, jumpToDepthAtom,
  navStackFor, cacheViewport, readCachedViewport,
  cachePanelPositions, readPanelPositions,
} from '../../state/subgraphNav';
import {
  deriveView, writeViewBack, writeLevelBack, resolveLevel, getInnerWorkflow,
  getSubgraphPorts, wirePort, unwirePort, boundaryEdgePort, viewPrefix,
  IO_INPUTS_TYPE, IO_OUTPUTS_TYPE, ADD_PORT_HANDLE, isIOPanelNode, isIOPanelNodeId,
} from '../../utils/subgraphView';
import { convertSelectionToSubgraph, unpackSubgraph } from '../../utils/subgraph';
import BioNode from './BioNode';
import BioEdge from './BioEdge';
import GroupNode from './GroupNode';
import SubgraphIONode from './SubgraphIONode';
import SubgraphBreadcrumb from './SubgraphBreadcrumb';
import Devtools from './Devtools';
import CollabCursors from './CollabCursors';
import NodeComments from './NodeComments';
import ContextMenu, { type MenuItem } from './ContextMenu';
import NodePropertiesDialog from './NodePropertiesDialog';
import NodeLogsPopover from './NodeLogsPopover';
import { captureCanvasThumbnail } from '../../utils/canvasThumbnail';
import HelperLines from './HelperLines';
import { getHelperLines } from './helperLineCalc';
import { BioNodeActionsContext, MultiSelectContext, type BioNodeActions } from './bioNodeActions';
import { BioEdgeActionsContext, type BioEdgeActions } from './bioEdgeActions';

export type { GraphNode, WorkflowCanvasRef };

const NODE_TYPES = { bio: BioNode, group: GroupNode, subgraphIO: SubgraphIONode };
const GROUP_DEFAULT_COLOR = '#6366f1';
const EDGE_TYPES = { bio: BioEdge };

// Stable prop references — React Flow re-processes when array/object/function
// props change identity, so any that don't depend on state live at module scope
// (React Flow performance guidance).
const DELETE_KEYS = ['Backspace', 'Delete'];
const MULTISELECT_KEYS = ['Shift', 'Meta', 'Control'];
const PAN_ON_DRAG = [1, 2];
const FIT_VIEW_OPTIONS = { padding: 0.2, maxZoom: 1.5 };
const PRO_OPTIONS = { hideAttribution: true };
const DEFAULT_EDGE_OPTIONS = { type: 'bio' };
const EMPTY_COMMENTS: Comment[] = [];
// Stable empty array so nodes with no promoted params keep a value-stable
// `promotedInputs` (a fresh `[]` each reconcile would defeat the BioNode memo).
const EMPTY_PROMOTED: string[] = [];
const MINIMAP_NODE_COLOR = (n: RFNode) => {
  const d = n.data as { g?: { color?: string }; color?: string } | undefined;
  return d?.g?.color ?? d?.color ?? '#64748b';
};

// Fire an action once on the RISING edge of a React Flow useKeyPress combo (i.e.
// on the initial press, not repeatedly while the key is held). Keeps the latest
// action in a ref so the effect only re-runs when the key state flips.
function useKeyPressAction(keyCode: string[], action: () => void) {
  const pressed = useKeyPress(keyCode, { preventDefault: true });
  const actionRef = useRef(action);
  actionRef.current = action;
  const wasPressed = useRef(false);
  useEffect(() => {
    if (pressed && !wasPressed.current) actionRef.current();
    wasPressed.current = pressed;
  }, [pressed]);
}

// React Flow's colorMode + the Background pattern, both driven off the app's
// active palette (the .dark class / data-canvas-pattern attribute it writes on
// <html>). Reactive via a MutationObserver so switching palette re-themes the
// canvas natively — no custom light/dark canvas CSS needed.
function useCanvasChrome(): { colorMode: 'light' | 'dark'; pattern: string } {
  const read = (): { colorMode: 'light' | 'dark'; pattern: string } => ({
    colorMode: getResolvedPaletteMode(),
    pattern: (typeof document !== 'undefined' ? document.documentElement.dataset.canvasPattern : '') || 'dots',
  });
  const [chrome, setChrome] = useState(read);
  useEffect(() => {
    const root = document.documentElement;
    const update = () => setChrome(read());
    const obs = new MutationObserver(update);
    obs.observe(root, { attributes: true, attributeFilter: ['class', 'data-theme', 'data-canvas-pattern'] });
    update();
    return () => obs.disconnect();
  }, []);
  return chrome;
}

// Loose type-compatibility for connection validation. Anything goes if either
// side is unknown or generic (ANY/*). Otherwise the source output type must be
// in the target input's accepted set (inputs may be a `A|B` union) OR share the
// same type family — so BAM_INDEXED→BAM and FASTQ_PAIRED→FASTQ stay valid while
// cross-family links (FASTQ→VCF) are rejected. Deliberately lenient: better to
// allow an odd link than to block a real one the backend would accept.
/**
 * Why a link was refused, in the user's terms, or null when it is fine.
 *
 * Type checking used to silently grey out the port, which left people
 * reasonably concluding the editor was broken: "don't know why i can't connect
 * fastqc to multiqc". A refusal has to say what it refused and why.
 */
export function connectionTypeWarning(
  outType: string,
  inType: string,
  labels: { source: string; target: string },
): string | null {
  if (typesCompatible(outType, inType)) return null;
  return (
    `${labels.source} produces ${outType}, but ${labels.target} expects ${inType}. ` +
    `Connect it anyway if the tool accepts it — the run will report the real error if not.`
  );
}

function typesCompatible(outType: string, inType: string): boolean {
  if (!outType || !inType) return true;
  const o = outType.toUpperCase();
  if (o === 'ANY' || o === '*') return true;
  const accepted = inType.toUpperCase().split(/[|,]/).map(s => s.trim()).filter(Boolean);
  if (accepted.some(a => a === 'ANY' || a === '*' || a === o)) return true;
  const oFamily = o.split('_')[0];
  return accepted.some(a => a.split('_')[0] === oFamily);
}

interface WorkflowCanvasProps {
  nodes: WorkflowNode[];
  edges: WorkflowEdge[];
  objectInfo: ObjectInfo;
  workflowParameters?: WorkflowParameter[];
  /** Active workflow (tab) id + display name — own the subgraph nav stack and
   *  the breadcrumb's root crumb. */
  workflowId?: string;
  workflowName?: string;
  onNodesChange: (nodes: WorkflowNode[]) => void;
  onEdgesChange: (edges: WorkflowEdge[]) => void;
  onPushHistory: () => void;
  onUndo: () => void;
  onRedo: () => void;
  snapToGrid: boolean;
  showMinimap: boolean;
  nodeStatusMap?: Map<string, NodeStatus['status']>;
  nodeErrorsMap?: Map<string, string>;
  missingDependencyNodeIds?: Set<string>;
  onExecuteSelected?: (nodeIds: string[]) => void;
  /** Open the node library (from the pane "Add node" context menu). */
  onOpenNodeLibrary?: () => void;
  // --- Collaboration (multiplayer + comments) ---
  collabSessionActive?: boolean;
  collabUsers?: AwarenessState[];
  currentUserId?: string;
  currentUserName?: string;
  currentUserColor?: string;
  /** Publish this client's cursor (world coords) to awareness. */
  onCollabCursor?: (cursor: AwarenessState['cursor']) => void;
  /** Publish this client's node selection to awareness. */
  onCollabSelection?: (selection: AwarenessState['selection']) => void;
  nodeComments?: Comment[];
  onAddComment?: (content: string, nodeId: string | null, parentId: string | null) => void;
  onResolveComment?: (id: string) => void;
  onDeleteComment?: (id: string) => void;
}

// WorkflowNode -> GraphNode: resolve metadata, geometry, ports, colour. The
// GraphNode shape is shared with the inspector/editor panels, so we still fill
// every field (unused-in-canvas ones default to false).
function toGraphNode(
  wn: WorkflowNode,
  connectedIn: Set<string>,
  connectedOut: Set<string>,
  objectInfo: ObjectInfo,
  status: NodeStatus['status'] | undefined,
  defaultShape: string,
  allParamInputs: boolean,
  t: (key: string, opts?: Record<string, unknown>) => string,
): GraphNode {
  const meta = wn.type ? (objectInfo[wn.type] || wn.node_info || null) : (wn.node_info || null);
  const collapsed = wn.ui?.collapsed ?? false;
  const isNote = meta?.id === 'note';
  const isReroute = meta?.id === 'reroute';
  const visualOnly = meta?.visual_only ?? isNote;
  const nodeWidth = isNote
    ? (wn.ui?.width ?? NODE_NOTE_WIDTH)
    : (isReroute ? 20 : (wn.ui?.width ?? NODE_WIDTH));
  // Height: 0 means "auto" — React Flow measures the rendered DOM and sizes the
  // node to its content (header + ports + widgets). Only reroute (fixed dot),
  // collapsed (header only), and user-resized nodes carry an explicit height.
  let nodeHeight: number;
  if (isReroute) nodeHeight = 20;
  else if (collapsed) nodeHeight = NODE_HEADER_H;
  else nodeHeight = wn.ui?.height ?? 0;
  const visibleInputs = getVisibleInputSpecs(meta, wn.params || {});
  // Effective input dots: the "enable all by default" setting shows a dot on
  // every widget param; otherwise only the per-node promoted keys.
  const promotedInputs = allParamInputs
    ? getPromotableParamKeys(meta, wn.params || {})
    : (wn.ui?.promotedInputs ?? EMPTY_PROMOTED);
  // Subgraph nodes: the visible handles are derived from params.input_ports /
  // params.output_ports (the engine contract), NOT from the stored node_info —
  // params stay authoritative as boundary edits add/remove ports.
  const isSubgraph = wn.type === 'subgraph';
  const subgraphInputs = isSubgraph ? getSubgraphPorts(wn, 'input_ports') : null;
  const subgraphOutputs = isSubgraph ? getSubgraphPorts(wn, 'output_ports') : null;
  return {
    id: wn.id,
    type: wn.type,
    display_name: meta?.display_name || wn.type || t('canvas.unknownNodeDisplayName'),
    category: meta?.category || 'Utility',
    x: wn.position[0],
    y: wn.position[1],
    width: nodeWidth,
    height: nodeHeight,
    // Ports are data-flow inputs only — interactive scalar params render as
    // on-node widgets instead (see NodeWidgets), so exclude them here to avoid
    // showing the same param as both a port and a widget.
    inputs: subgraphInputs ? subgraphInputs.map(p => ({
      name: p.name, type: p.type, connected: connectedIn.has(`${wn.id}:${p.name}`),
    })) : (meta && !visualOnly) ? [
      ...Object.entries(visibleInputs.required),
      ...Object.entries(visibleInputs.optional),
    ].filter(([, spec]) => !isInteractiveWidgetSpec(spec)).map(([name, spec]) => ({
      name, type: spec.type || 'STRING', connected: connectedIn.has(`${wn.id}:${name}`),
    })) : [],
    outputs: subgraphOutputs ? subgraphOutputs.map(p => ({
      name: p.name, type: p.type, connected: connectedOut.has(`${wn.id}:${p.name}`),
    })) : (meta && !visualOnly) ? resolveNodeOutputs(meta, wn.params || {}).map(output => ({
      name: output.name, type: output.type,
      connected: connectedOut.has(`${wn.id}:${output.name}`),
    })) : [],
    params: wn.params || {},
    promotedInputs,
    meta,
    color: wn.ui?.color || nodeColor(meta),
    muted: wn.ui?.muted ?? false,
    bypassed: wn.ui?.bypassed ?? false,
    selected: false,
    collapsed,
    pinned: wn.ui?.pinned || false,
    shape: wn.ui?.shape || (isNote ? 'card' : (defaultShape as GraphNode['shape'])),
    title: wn.ui?.title || meta?.display_name || wn.type || t('canvas.nodeFallbackTitle'),
    status,
    visualOnly,
    isSubgraph,
    inlinePreview: false,
    previewCollapsed: false,
    showingPreview: false,
  };
}

const WorkflowCanvasInner = forwardRef<WorkflowCanvasRef, WorkflowCanvasProps>(function WorkflowCanvasInner({
  nodes, edges, objectInfo,
  workflowId, workflowName,
  onNodesChange, onEdgesChange, onPushHistory,
  snapToGrid, showMinimap,
  nodeStatusMap, missingDependencyNodeIds,
  onExecuteSelected,
  onOpenNodeLibrary,
  collabSessionActive = false,
  collabUsers,
  currentUserId = '',
  currentUserName = '',
  currentUserColor = '#6366f1',
  onCollabCursor,
  onCollabSelection,
  nodeComments,
  onAddComment,
  onResolveComment,
  onDeleteComment,
}, ref) {
  const { t } = useTranslation();
  const tRef = useRef(t); tRef.current = t;
  const rf = useReactFlow();

  const setSelectedNodeId = useSetAtom(selectedNodeIdAtom);
  const { getBool, getNumber, getString, set } = useSettings();
  const showGrid = getBool('bionodulo.canvas.showGrid', true);
  const gridSize = Math.min(200, Math.max(4, getNumber('bionodulo.canvas.gridSize', 20)));
  const showDebugOverlay = getBool('bionodulo.canvas.debugOverlay', false);
  const showComments = getBool('bionodulo.canvas.showComments', true);
  const showControls = getBool('bionodulo.canvas.showControls', true);
  // Appearance settings (see SettingsPanel → Canvas appearance).
  const edgeType = getString('bionodulo.canvas.edgeType', 'bezier');            // bezier|smoothstep|step|straight
  const edgeAnimated = getBool('bionodulo.canvas.edgeAnimated', false);
  const edgeWidth = Math.min(8, Math.max(1, getNumber('bionodulo.canvas.edgeWidth', 2)));
  const edgeArrows = getBool('bionodulo.canvas.edgeArrows', false);
  // Let users drag an edge endpoint off its port; dropping on empty canvas
  // deletes it. On by default.
  const edgeReconnectable = getBool('bionodulo.canvas.edgeReconnectable', true);
  const defaultNodeShape = getString('bionodulo.canvas.nodeShape', 'round');     // round|box|card
  const nodeRadius = Math.min(24, Math.max(0, getNumber('bionodulo.canvas.nodeRadius', 8)));
  const nodeShadow = getBool('bionodulo.canvas.nodeShadow', true);
  const connectionRadius = Math.min(80, Math.max(8, getNumber('bionodulo.canvas.connectionRadius', 28)));
  const bgPatternSetting = getString('bionodulo.canvas.backgroundPattern', 'auto'); // auto|dots|lines|cross|none
  const panOnScroll = getBool('bionodulo.canvas.panOnScroll', true);
  const zoomOnDoubleClick = getBool('bionodulo.canvas.zoomOnDoubleClick', false);
  const nodeFontSize = Math.min(18, Math.max(9, getNumber('bionodulo.canvas.nodeFontSize', 12)));
  // When on, every widget param shows an input dot by default (still off unless
  // the user opts in). Per-node "Add input" toggles layer on top.
  const allParamInputs = getBool('bionodulo.canvas.allParamInputs', false);
  const { colorMode, pattern } = useCanvasChrome();
  const effectivePattern = bgPatternSetting === 'auto' ? pattern : bgPatternSetting;
  const bgVariant = effectivePattern === 'lines' || effectivePattern === 'grid' ? BackgroundVariant.Lines
    : effectivePattern === 'cross' || effectivePattern === 'mesh' ? BackgroundVariant.Cross
    : BackgroundVariant.Dots;
  const showBackground = showGrid && effectivePattern !== 'none';
  const connectionLineType = edgeType === 'smoothstep' ? ConnectionLineType.SmoothStep
    : edgeType === 'step' ? ConnectionLineType.Step
    : edgeType === 'straight' ? ConnectionLineType.Straight
    : ConnectionLineType.Bezier;
  const snapGridValue = useMemo<[number, number]>(() => [gridSize, gridSize], [gridSize]);
  // Node appearance vars applied to the host so every node picks them up via CSS.
  const hostStyle = useMemo(() => ({
    ['--xy-node-border-radius-default' as string]: `${nodeRadius}px`,
    ['--bio-node-font-size' as string]: `${nodeFontSize}px`,
  }), [nodeRadius, nodeFontSize]);

  // Latest props for callbacks that must read fresh values without re-binding.
  const rootRef = useRef({ nodes, edges }); rootRef.current = { nodes, edges };

  // ---- Subgraph drill-down -------------------------------------------------
  // The canvas edits ONE level at a time: the root workflow, or the embedded
  // inner workflow of the subgraph node at the current nav path. `derived` is
  // the namespaced view of that level (panel nodes + boundary edges included);
  // every mutation callback below works in view space and folds back into the
  // root document through writeViewBack/writeLevelBack.
  const navState = useAtomValue(subgraphNavAtom);
  const enterSubgraph = useSetAtom(enterSubgraphAtom);
  const jumpToDepth = useSetAtom(jumpToDepthAtom);
  const stack = useMemo(() => navStackFor(navState, workflowId ?? null), [navState, workflowId]);
  const navPath = useMemo(() => stack.map(l => l.nodeId), [stack]);
  const derived = useMemo(() => {
    let path = navPath;
    let view = deriveView(nodes, edges, path, readPanelPositions(workflowId ?? null, path) ?? undefined);
    // The path can dangle after an undo/delete removed its host subgraph:
    // fall back to the deepest prefix that still resolves.
    while (!view && path.length > 0) {
      path = path.slice(0, -1);
      view = deriveView(nodes, edges, path, readPanelPositions(workflowId ?? null, path) ?? undefined);
    }
    return { view: view!, path };
  }, [nodes, edges, navPath, workflowId]);
  const viewNodes = derived.view.nodes;
  const viewEdges = derived.view.edges;
  // If the fallback above shortened the path, sync the nav atom once.
  useEffect(() => {
    if (workflowId && derived.path.length !== navPath.length) {
      jumpToDepth({ owner: workflowId, depth: derived.path.length });
    }
  }, [workflowId, derived.path.length, navPath.length, jumpToDepth]);

  const nodesRef = useRef(viewNodes); nodesRef.current = viewNodes;
  const edgesRef = useRef(viewEdges); edgesRef.current = viewEdges;
  const pathRef = useRef(derived.path); pathRef.current = derived.path;
  const isDraggingRef = useRef(false);
  const selectedIdsRef = useRef<Set<string>>(new Set());

  // Fold an edited view graph back into the root document and hand it up.
  // Both callbacks fire together: write-back can prune parent-level edges when
  // inner nodes (and with them port entries) disappear.
  const emitView = useCallback((nextViewNodes: WorkflowNode[], nextViewEdges: WorkflowEdge[]) => {
    const out = writeViewBack(rootRef.current.nodes, rootRef.current.edges, pathRef.current, nextViewNodes, nextViewEdges);
    onNodesChange(out.nodes);
    onEdgesChange(out.edges);
  }, [onNodesChange, onEdgesChange]);
  const emitNodes = useCallback((nextViewNodes: WorkflowNode[]) => {
    emitView(nextViewNodes, edgesRef.current);
  }, [emitView]);
  const emitEdges = useCallback((nextViewEdges: WorkflowEdge[]) => {
    emitView(nodesRef.current, nextViewEdges);
  }, [emitView]);
  // Commit a boundary (port) edit: these helpers already operate on the root
  // document, so no view fold is needed.
  const emitRoot = useCallback((out: { nodes: WorkflowNode[]; edges: WorkflowEdge[] }) => {
    onNodesChange(out.nodes);
    onEdgesChange(out.edges);
  }, [onNodesChange, onEdgesChange]);

  const [rfNodes, setRfNodes] = useState<RFNode[]>([]);
  const [helperLines, setHelperLines] = useState<{ horizontal?: number; vertical?: number }>({});
  // Reactive selection (for the multi-select toolbar); the ref mirror stays for
  // callbacks that need the latest value without re-binding.
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [commentOpenNodeId, setCommentOpenNodeId] = useState<string | null>(null);
  const [propsNodeId, setPropsNodeId] = useState<string | null>(null);
  // Per-node log viewer, opened from the node context menu. Position is the
  // click point so the panel appears next to the node you asked about.
  const [logsNode, setLogsNode] = useState<{ id: string; x: number; y: number } | null>(null);
  const [menu, setMenu] = useState<{ kind: 'node' | 'pane' | 'edge'; x: number; y: number; nodeId?: string; edgeId?: string; flow: { x: number; y: number } } | null>(null);
  const hostRef = useRef<HTMLDivElement>(null);
  // Publish where "the middle of what I'm looking at" is, so nodes added from
  // the library land in view instead of near the flow origin.
  useEffect(() => {
    setViewportCenterReader(() => {
      const bounds = hostRef.current?.getBoundingClientRect();
      if (!bounds || !bounds.width || !bounds.height) return null;
      // React Flow's own screen->flow conversion, rather than inverting the
      // transform by hand: it accounts for the container's offset on the page
      // and stays correct if the library changes how the viewport is applied.
      const { x, y } = rf.screenToFlowPosition({
        x: bounds.left + bounds.width / 2,
        y: bounds.top + bounds.height / 2,
      });
      return [x, y];
    });
    return () => setViewportCenterReader(null);
  }, [rf]);


  // Precompute the connected input/output port keys once per edges change, so
  // the node reconcile is O(nodes) instead of scanning all edges per node.
  const connectedPorts = useMemo(() => {
    const cin = new Set<string>();
    const cout = new Set<string>();
    for (const e of viewEdges) {
      cin.add(`${e.to.node}:${e.to.input}`);
      cout.add(`${e.from.node}:${e.from.output}`);
    }
    return { cin, cout };
  }, [viewEdges]);

  // Reconcile React Flow node state from props. Skipped mid-drag so a status
  // tick or parent re-render never stomps the in-flight drag position (React
  // Flow owns positions during a drag; we commit them on drag stop).
  //
  // Grouping (native sub-flows): a group is a `type: 'group'` node; children
  // reference it via `parentId`. workflow.nodes stores ABSOLUTE positions, so at
  // the React Flow boundary we convert a child's position to be relative to its
  // group, and emit parents before children (React Flow requires that order).
  useEffect(() => {
    if (isDraggingRef.current) return;
    setRfNodes(prev => {
      const prevSel = new Map(prev.map(n => [n.id, n.selected]));
      const groupAbs = new Map<string, { x: number; y: number }>();
      for (const wn of viewNodes) {
        if (wn.type === 'group') groupAbs.set(wn.id, { x: wn.position[0], y: wn.position[1] });
      }
      const built: RFNode[] = viewNodes.map(wn => {
        const selected = prevSel.get(wn.id) ?? false;
        const parent = wn.parentId && groupAbs.has(wn.parentId) ? groupAbs.get(wn.parentId)! : null;
        const position = parent
          ? { x: wn.position[0] - parent.x, y: wn.position[1] - parent.y }
          : { x: wn.position[0], y: wn.position[1] };

        // Subgraph IO boundary panels (synthesized by deriveView — never
        // stored). Not deletable; their positions cache on drag stop.
        if (isIOPanelNode(wn)) {
          const kind = wn.type === IO_INPUTS_TYPE ? 'inputs' : 'outputs';
          const ports = Array.isArray(wn.params?.ports)
            ? wn.params.ports as { name: string; type: string; connected: boolean }[]
            : [];
          const title = wn.params?.title ? String(wn.params.title) : kind;
          return {
            id: wn.id, type: 'subgraphIO', position, selected, deletable: false,
            style: { width: 200 },
            ariaLabel: title,
            data: { kind, ports },
          } satisfies RFNode;
        }

        if (wn.type === 'group') {
          const w = wn.ui?.width ?? 320;
          const h = wn.ui?.height ?? 200;
          const title = wn.ui?.title ?? tRef.current('canvas.group.defaultName');
          return {
            id: wn.id, type: 'group', position, selected,
            width: w, height: h, style: { width: w, height: h },
            ariaLabel: title,
            data: { title, color: wn.ui?.color ?? GROUP_DEFAULT_COLOR },
          } satisfies RFNode;
        }

        const g = toGraphNode(wn, connectedPorts.cin, connectedPorts.cout, objectInfo, nodeStatusMap?.get(wn.id), defaultNodeShape, allParamInputs, tRef.current);
        g.selected = selected;
        // Fix the width; leave height to React Flow's DOM measurement unless the
        // node has an explicit (fixed/collapsed/reroute/resized) height (g.height > 0).
        const style: React.CSSProperties = g.height > 0
          ? { width: g.width, height: g.height }
          : { width: g.width };
        const node: RFNode = {
          // Set an explicit width (height stays auto-measured) so overlays that
          // read node.width — e.g. comment pins at the top-right corner — have a
          // stable value on the first render and don't jump once measured.
          id: g.id, type: 'bio', position, selected, style, width: g.width,
          ariaLabel: g.status ? `${g.title} (${g.status})` : g.title,
          data: {
            g,
            categoryLabel: nodeCategoryDisplayLabel(g.category, tRef.current, tRef.current('nodeLibrary.otherCategory')),
            missingDependency: missingDependencyNodeIds?.has(g.id) ?? false,
            running: g.status === 'running',
          },
        };
        if (parent) { node.parentId = wn.parentId; node.extent = 'parent'; }
        return node;
      });
      // Parents (groups) must come before their children.
      built.sort((a, b) => (a.type === 'group' ? 0 : 1) - (b.type === 'group' ? 0 : 1));
      return built;
    });
  }, [viewNodes, connectedPorts, objectInfo, nodeStatusMap, missingDependencyNodeIds, defaultNodeShape, allParamInputs]);

  // Stable `${nodeId}:${outputName}` -> output type map for edge colour, keyed
  // on props (not node positions) so it does not churn during a drag.
  const outTypeByNodeOutput = useMemo(() => {
    const map = new Map<string, string>();
    for (const wn of viewNodes) {
      if (isIOPanelNode(wn)) {
        const ports = Array.isArray(wn.params?.ports) ? wn.params.ports as { name: string; type: string }[] : [];
        if (wn.type === IO_INPUTS_TYPE) {
          for (const p of ports) map.set(`${wn.id}:${p.name}`, p.type);
        }
        continue;
      }
      const meta = wn.type ? (objectInfo[wn.type] || wn.node_info || null) : (wn.node_info || null);
      if (!meta) continue;
      for (const output of resolveNodeOutputs(meta, wn.params || {})) {
        map.set(`${wn.id}:${output.name}`, output.type);
      }
    }
    // Subgraph nodes: output handle types come from params.output_ports.
    for (const wn of viewNodes) {
      if (wn.type !== 'subgraph') continue;
      for (const p of getSubgraphPorts(wn, 'output_ports')) {
        map.set(`${wn.id}:${p.name}`, p.type);
      }
    }
    return map;
  }, [viewNodes, objectInfo]);

  // Stable `${nodeId}:${inputName}` -> input type map, for connection validation.
  const inTypeByNodeInput = useMemo(() => {
    const map = new Map<string, string>();
    for (const wn of viewNodes) {
      if (isIOPanelNode(wn)) {
        const ports = Array.isArray(wn.params?.ports) ? wn.params.ports as { name: string; type: string }[] : [];
        if (wn.type === IO_OUTPUTS_TYPE) {
          for (const p of ports) map.set(`${wn.id}:${p.name}`, p.type);
        }
        continue;
      }
      const meta = wn.type ? (objectInfo[wn.type] || wn.node_info || null) : (wn.node_info || null);
      if (!meta) continue;
      const visible = getVisibleInputSpecs(meta, wn.params || {});
      for (const [name, spec] of [...Object.entries(visible.required), ...Object.entries(visible.optional)]) {
        map.set(`${wn.id}:${name}`, spec.type || '');
      }
    }
    for (const wn of viewNodes) {
      if (wn.type !== 'subgraph') continue;
      for (const p of getSubgraphPorts(wn, 'input_ports')) {
        map.set(`${wn.id}:${p.name}`, p.type);
      }
    }
    return map;
  }, [viewNodes, objectInfo]);

  // Edges are local React Flow state (like nodes), reconciled from props but
  // carrying their own `selected` flag — a controlled flow only surfaces edge
  // select/remove via onEdgesChange, so a pure-derived array could never select
  // (which would break the BioEdge delete button + elevateEdgesOnSelect).
  const [rfEdges, setRfEdges] = useState<RFEdge[]>([]);
  useEffect(() => {
    const prefix = viewPrefix(pathRef.current);
    setRfEdges(prev => {
      const prevSel = new Map(prev.map(e => [e.id, e.selected]));
      return viewEdges.map(edge => {
        const outType = outTypeByNodeOutput.get(`${edge.from.node}:${edge.from.output}`) || '';
        const stroke = edgeColorForSource(outType);
        // Derived boundary edges (IO panel <-> inner slot) are not draggable —
        // they move by rewiring the port, and are deleted via select+Delete.
        const boundary = boundaryEdgePort(edge.id, prefix) !== null;
        return {
          id: edge.id,
          source: edge.from.node,
          target: edge.to.node,
          sourceHandle: edge.from.output,
          targetHandle: edge.to.input,
          selected: prevSel.get(edge.id) ?? false,
          animated: edgeAnimated,
          reconnectable: !boundary,
          ariaLabel: `${edge.from.node} → ${edge.to.node}`,
          style: { stroke, strokeWidth: edgeWidth },
          data: { pathType: edgeType },
          ...(edgeArrows ? { markerEnd: { type: MarkerType.ArrowClosed, color: stroke, width: 18, height: 18 } } : {}),
        } satisfies RFEdge;
      });
    });
  }, [viewEdges, outTypeByNodeOutput, edgeType, edgeAnimated, edgeWidth, edgeArrows]);

  const handleEdgesChange = useCallback((changes: EdgeChange[]) => {
    setRfEdges(prev => applyEdgeChanges(changes, prev));
  }, []);

  const handleNodesChange = useCallback((changes: NodeChange[]) => {
    // Alignment helper lines: when a single node is being dragged (and grid-snap
    // is off), snap its position to the nearest other-node edge/center and show
    // the guide line. Grid-snap and helper-lines are mutually exclusive. Only
    // touch helperLines state when a single node is actively dragging, so the
    // guide layer doesn't churn on every pan/dimension/select change.
    const dragChanges = changes.filter(c => c.type === 'position' && c.dragging && c.position);
    if (!snapToGrid && dragChanges.length === 1) {
      const change = dragChanges[0] as NodePositionChange;
      const lines = getHelperLines(change, rf.getNodes());
      if (change.position) {
        change.position.x = lines.snapPosition.x ?? change.position.x;
        change.position.y = lines.snapPosition.y ?? change.position.y;
      }
      setHelperLines(prev => {
        const h = lines.horizontal;
        const v = lines.vertical;
        if (prev.horizontal === h && prev.vertical === v) return prev;
        return { horizontal: h, vertical: v };
      });
    } else {
      setHelperLines(prev => (prev.horizontal === undefined && prev.vertical === undefined ? prev : {}));
    }
    setRfNodes(prev => applyNodeChanges(changes, prev));
  }, [snapToGrid, rf]);

  const onNodeDragStart = useCallback(() => { isDraggingRef.current = true; }, []);

  const onNodeDragStop = useCallback(() => {
    isDraggingRef.current = false;
    setHelperLines({});
    // Commit live React Flow positions (honouring snap) as a single history step.
    // React Flow reports a grouped child's position RELATIVE to its parent, so we
    // add the parent's (absolute, top-level) position back to store absolutes.
    const rfById = new Map(rf.getNodes().map(n => [n.id, n]));
    // IO panel positions are canvas state, not document state: cache them per
    // nav level instead of writing them into the workflow.
    if (workflowId && pathRef.current.length > 0) {
      const prefix = viewPrefix(pathRef.current);
      const inputsPanel = rfById.get(`${prefix}${IO_INPUTS_TYPE}`);
      const outputsPanel = rfById.get(`${prefix}${IO_OUTPUTS_TYPE}`);
      cachePanelPositions(workflowId, pathRef.current, {
        ...(inputsPanel ? { inputs: [Math.round(inputsPanel.position.x), Math.round(inputsPanel.position.y)] as [number, number] } : {}),
        ...(outputsPanel ? { outputs: [Math.round(outputsPanel.position.x), Math.round(outputsPanel.position.y)] as [number, number] } : {}),
      });
    }
    const updated = nodesRef.current.map(wn => {
      const rfn = rfById.get(wn.id);
      if (!rfn) return wn;
      let ax = rfn.position.x;
      let ay = rfn.position.y;
      if (wn.parentId && rfById.has(wn.parentId)) {
        const parent = rfById.get(wn.parentId)!;
        ax += parent.position.x;
        ay += parent.position.y;
      }
      if (wn.position[0] === ax && wn.position[1] === ay) return wn;
      return { ...wn, position: [ax, ay] as [number, number] };
    });
    emitNodes(updated);
    onPushHistory();
  }, [rf, emitNodes, onPushHistory, workflowId]);

  const onConnect = useCallback((connection: Connection) => {
    if (!connection.source || !connection.target || !connection.sourceHandle || !connection.targetHandle) return;
    if (connection.source === connection.target) return;

    // Boundary wiring inside a subgraph: a connection touching an IO panel
    // edits the host's params.input_ports / params.output_ports (the engine
    // contract) instead of adding an edge. The visible wire is derived from
    // the port entry, so it appears on its own after the write-back.
    const path = pathRef.current;
    if (path.length > 0) {
      const prefix = viewPrefix(path);
      const inputsId = `${prefix}${IO_INPUTS_TYPE}`;
      const outputsId = `${prefix}${IO_OUTPUTS_TYPE}`;
      if (connection.source === inputsId) {
        if (connection.target === outputsId) return;
        const innerNode = connection.target.slice(prefix.length);
        const portType = connection.sourceHandle === ADD_PORT_HANDLE
          ? (inTypeByNodeInput.get(`${connection.target}:${connection.targetHandle}`) || '*')
          : (outTypeByNodeOutput.get(`${connection.source}:${connection.sourceHandle}`) || '*');
        emitRoot(wirePort(
          rootRef.current.nodes, rootRef.current.edges, path, 'input',
          connection.sourceHandle === ADD_PORT_HANDLE ? null : connection.sourceHandle,
          innerNode, connection.targetHandle, portType,
        ));
        onPushHistory();
        return;
      }
      if (connection.target === outputsId) {
        if (connection.source === inputsId) return;
        const innerNode = connection.source.slice(prefix.length);
        const portType = connection.targetHandle === ADD_PORT_HANDLE
          ? (outTypeByNodeOutput.get(`${connection.source}:${connection.sourceHandle}`) || '*')
          : (inTypeByNodeInput.get(`${connection.target}:${connection.targetHandle}`) || '*');
        emitRoot(wirePort(
          rootRef.current.nodes, rootRef.current.edges, path, 'output',
          connection.targetHandle === ADD_PORT_HANDLE ? null : connection.targetHandle,
          innerNode, connection.sourceHandle, portType,
        ));
        onPushHistory();
        return;
      }
      // Boundary edges themselves are not reconnectable, so a connection
      // landing on a panel handle can only come from the cases above.
      if (connection.source === outputsId || connection.target === inputsId) return;
    }

    const newEdge: WorkflowEdge = {
      id: `e_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`,
      from: { node: connection.source, output: connection.sourceHandle },
      to: { node: connection.target, input: connection.targetHandle },
    };
    // One connection per input slot: drop any edge already in that slot.
    const filtered = edgesRef.current.filter(e => !(e.to.node === connection.target && e.to.input === connection.targetHandle));
    emitEdges([...filtered, newEdge]);
    onPushHistory();

    // The link is made either way. If our type model disagrees with it, say so
    // rather than refusing: the model is sometimes wrong, and the tool itself
    // gives the authoritative answer when the workflow runs.
    const outType = outTypeByNodeOutput.get(`${connection.source}:${connection.sourceHandle}`) || '';
    const inType = inTypeByNodeInput.get(`${connection.target}:${connection.targetHandle}`) || '';
    const warning = connectionTypeWarning(outType, inType, {
      source: connection.sourceHandle,
      target: connection.targetHandle,
    });
    if (warning) {
      toast.warning(t('canvas.connection.typeMismatch', { defaultValue: 'Unusual connection' }), {
        message: warning,
        actions: [
          {
            label: t('common.undo', { defaultValue: 'Undo' }),
            onClick: () => {
              emitEdges(edgesRef.current.filter(e => e.id !== newEdge.id));
              onPushHistory();
            },
          },
        ],
      });
    }
  }, [emitEdges, emitRoot, onPushHistory, outTypeByNodeOutput, inTypeByNodeInput, t]);

  // Native connection gate: React Flow calls this while the user drags a link
  // and greys out ports it rejects. Block self-links, type-incompatible ports,
  // and any connection that would create a cycle (workflows must stay a DAG).
  // Adjacency (source node -> target nodes), memoized on edges so a connection
  // drag doesn't rebuild the graph for every hovered port.
  const adjacency = useMemo(() => {
    const map = new Map<string, string[]>();
    for (const e of viewEdges) {
      const list = map.get(e.from.node);
      if (list) list.push(e.to.node); else map.set(e.from.node, [e.to.node]);
    }
    return map;
  }, [viewEdges]);

  const isValidConnection = useCallback((conn: Connection | RFEdge): boolean => {
    const { source, target } = conn;
    if (!source || !target || source === target) return false;
    // Types are advisory, not a gate. Our own type model is not always right --
    // FastQC's report directory is exactly what MultiQC consumes, yet the
    // declared types disagreed -- and a wrong model must not stop a real
    // pipeline. A mismatch is reported on drop instead (see onConnect).
    //
    // Cycles stay blocked: a workflow that is not a DAG cannot execute at all,
    // so there is nothing for the tool to report later.
    // Reject if the target already reaches the source (adding source->target would
    // create a cycle). Iterative BFS over the memoized adjacency map.
    const seen = new Set<string>();
    const queue = [target];
    while (queue.length) {
      const id = queue.pop()!;
      if (id === source) return false;
      if (seen.has(id)) continue;
      seen.add(id);
      const next = adjacency.get(id);
      if (next) queue.push(...next);
    }
    return true;
  }, [adjacency]);

  // Native edge reconnection: drag an existing edge's end onto another port.
  // The ref tracks whether a drag actually landed on a valid handle — if it's
  // dropped on empty canvas, onReconnectEnd deletes the edge (React Flow's
  // "reconnect to nowhere = remove" pattern).
  const edgeReconnectSuccessful = useRef(true);
  const onReconnectStart = useCallback(() => { edgeReconnectSuccessful.current = false; }, []);
  const onReconnect = useCallback((oldEdge: RFEdge, newConn: Connection) => {
    if (!newConn.source || !newConn.target || !newConn.sourceHandle || !newConn.targetHandle) return;
    edgeReconnectSuccessful.current = true;
    const filtered = edgesRef.current.filter(e =>
      e.id !== oldEdge.id && !(e.to.node === newConn.target && e.to.input === newConn.targetHandle));
    filtered.push({
      id: oldEdge.id,
      from: { node: newConn.source, output: newConn.sourceHandle },
      to: { node: newConn.target, input: newConn.targetHandle },
    });
    emitEdges(filtered);
    onPushHistory();
  }, [emitEdges, onPushHistory]);
  const onReconnectEnd = useCallback((_evt: unknown, edge: RFEdge) => {
    if (!edgeReconnectSuccessful.current) {
      emitEdges(edgesRef.current.filter(e => e.id !== edge.id));
      onPushHistory();
    }
    edgeReconnectSuccessful.current = true;
  }, [emitEdges, onPushHistory]);

  // Split an edge with a reroute node dropped at `flow`: source -> reroute ->
  // target. Backs the edge context menu's "Insert reroute".
  const insertRerouteOnEdge = useCallback((edgeId: string, flow: { x: number; y: number }) => {
    const edge = edgesRef.current.find(e => e.id === edgeId);
    if (!edge) return;
    const rerouteId = `reroute_${Date.now()}`;
    const reroute: WorkflowNode = {
      id: rerouteId, type: 'reroute', params: {}, position: [flow.x, flow.y], ui: { title: '' },
    };
    emitView(nodesRef.current.concat(reroute), [
      ...edgesRef.current.filter(e => e.id !== edgeId),
      { id: `${edge.from.node}:${edge.from.output}->${rerouteId}:input`, from: edge.from, to: { node: rerouteId, input: 'input' } },
      { id: `${rerouteId}:output->${edge.to.node}:${edge.to.input}`, from: { node: rerouteId, output: 'output' }, to: edge.to },
    ]);
    onPushHistory();
  }, [emitView, onPushHistory]);

  // Remove one view edge, routing boundary edges to a port removal on the
  // host subgraph node (which also prunes the parent level's wires to it).
  const removeViewEdge = useCallback((edgeId: string) => {
    const path = pathRef.current;
    const boundary = boundaryEdgePort(edgeId, viewPrefix(path));
    if (boundary) {
      emitRoot(unwirePort(rootRef.current.nodes, rootRef.current.edges, path, boundary.direction, boundary.portName));
      onPushHistory();
      return;
    }
    emitEdges(edgesRef.current.filter(e => e.id !== edgeId));
    onPushHistory();
  }, [emitEdges, emitRoot, onPushHistory]);

  // Single native delete handler: React Flow passes the FULL cascade in one call
  // — the deleted nodes plus every edge removed as a consequence — so we commit
  // nodes + edges together with a single history push (using onNodesDelete +
  // onEdgesDelete separately double-fires off the same stale ref).
  const onDelete = useCallback(({ nodes: delNodes, edges: delEdges }: { nodes: RFNode[]; edges: RFEdge[] }) => {
    const path = pathRef.current;
    const prefix = viewPrefix(path);
    // Boundary-edge deletions remove the port on the host subgraph node. Fold
    // those first so the regular view write-back lands on the updated root.
    let roots = rootRef.current;
    let boundaryRemoved = false;
    for (const e of delEdges) {
      const boundary = boundaryEdgePort(e.id, prefix);
      if (!boundary) continue;
      roots = unwirePort(roots.nodes, roots.edges, path, boundary.direction, boundary.portName);
      boundaryRemoved = true;
    }
    const goneNodes = new Set(delNodes.map(n => n.id).filter(id => !isIOPanelNodeId(id, prefix)));
    const goneEdges = new Set(delEdges.map(e => e.id).filter(id => !boundaryEdgePort(id, prefix)));
    const nextViewNodes = nodesRef.current.filter(n => !goneNodes.has(n.id));
    const nextViewEdges = edgesRef.current.filter(e => !goneEdges.has(e.id));
    const out = writeViewBack(roots.nodes, roots.edges, path, nextViewNodes, nextViewEdges);
    if (goneNodes.size || goneEdges.size || boundaryRemoved) {
      onNodesChange(out.nodes);
      onEdgesChange(out.edges);
      onPushHistory();
    }
  }, [onNodesChange, onEdgesChange, onPushHistory]);

  // Native pre-delete guard: pinned nodes are protected. Return a filtered set so
  // React Flow deletes everything EXCEPT pinned nodes (and cancels entirely if the
  // only thing selected was pinned).
  const onBeforeDelete = useCallback(async ({ nodes: delNodes, edges: delEdges }: { nodes: RFNode[]; edges: RFEdge[] }) => {
    const pinned = new Set(nodesRef.current.filter(n => n.ui?.pinned).map(n => n.id));
    if (pinned.size === 0) return true;
    const keptNodes = delNodes.filter(n => !pinned.has(n.id));
    if (keptNodes.length === 0 && delEdges.length === 0) return false;
    return { nodes: keptNodes, edges: delEdges };
  }, []);

  const onCollabSelectionRef = useRef(onCollabSelection);
  onCollabSelectionRef.current = onCollabSelection;
  const handleSelectionChange = useCallback((params: OnSelectionChangeParams) => {
    const idList = params.nodes.map(n => n.id);
    const ids = new Set(idList);
    selectedIdsRef.current = ids;
    setSelectedIds(idList);
    setSelectedNodeId(ids.size === 1 ? idList[0] : null);
    // Broadcast selection to collaborators (awareness).
    onCollabSelectionRef.current?.({ nodeIds: idList, box: null });
  }, [setSelectedNodeId]);

  // Publish this client's cursor (in FLOW/world coords) to awareness, throttled
  // to one update per animation frame so pointer-move doesn't flood the network.
  const onCollabCursorRef = useRef(onCollabCursor);
  onCollabCursorRef.current = onCollabCursor;
  const cursorRafRef = useRef<number | null>(null);
  const pendingCursorRef = useRef<{ x: number; y: number } | null>(null);
  const onPaneMouseMove = useCallback((e: React.MouseEvent) => {
    if (!onCollabCursorRef.current) return;
    pendingCursorRef.current = { x: e.clientX, y: e.clientY };
    if (cursorRafRef.current != null) return;
    cursorRafRef.current = requestAnimationFrame(() => {
      cursorRafRef.current = null;
      const p = pendingCursorRef.current;
      if (!p) return;
      const world = rf.screenToFlowPosition({ x: p.x, y: p.y });
      onCollabCursorRef.current?.({ x: p.x, y: p.y, visible: true, worldX: world.x, worldY: world.y });
    });
  }, [rf]);
  const onPaneMouseLeave = useCallback(() => {
    if (cursorRafRef.current != null) { cancelAnimationFrame(cursorRafRef.current); cursorRafRef.current = null; }
    onCollabCursorRef.current?.({ x: 0, y: 0, visible: false });
  }, []);
  useEffect(() => () => {
    if (cursorRafRef.current != null) cancelAnimationFrame(cursorRafRef.current);
  }, []);

  // Route React Flow's internal warnings/errors into the app log instead of the
  // bare console (e.g. missing-styles or invalid-parent warnings).
  const onError = useCallback((code: string, message: string) => {
    logError('reactflow', new Error(`[${code}] ${message}`));
  }, []);

  // ---- On-node toolbar actions (native <NodeToolbar> in BioNode) ----
  const actions = useMemo<BioNodeActions>(() => ({
    run: (id) => onExecuteSelected?.([pathRef.current.length > 0 ? pathRef.current[0] : id]),
    rename: async (id) => {
      const wn = nodesRef.current.find(n => n.id === id);
      if (!wn) return;
      const current = wn.ui?.title || wn.type || '';
      const next = await promptDialog({ title: tRef.current('canvas.menu.rename'), message: tRef.current('canvas.menu.renamePrompt', 'New node name'), defaultValue: current });
      if (typeof next !== 'string') return;
      emitNodes(nodesRef.current.map(n => n.id === id ? { ...n, ui: { ...n.ui, title: next } } : n));
      onPushHistory();
    },
    duplicate: (id) => {
      const wn = nodesRef.current.find(n => n.id === id);
      if (!wn) return;
      const clone: WorkflowNode = {
        ...wn,
        id: `${wn.type}_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`,
        position: [wn.position[0] + 40, wn.position[1] + 40],
        params: { ...(wn.params || {}) },
        ui: { ...wn.ui },
      };
      emitNodes([...nodesRef.current, clone]);
      onPushHistory();
    },
    toggleCollapse: (id) => {
      emitNodes(nodesRef.current.map(n => n.id === id
        ? { ...n, ui: { ...n.ui, collapsed: !(n.ui?.collapsed ?? false) } }
        : n));
      onPushHistory();
    },
    remove: (id) => {
      emitView(nodesRef.current.filter(n => n.id !== id), edgesRef.current.filter(e => e.from.node !== id && e.to.node !== id));
      onPushHistory();
    },
    resize: (id, width, height) => {
      emitNodes(nodesRef.current.map(n => n.id === id ? { ...n, ui: { ...n.ui, width, height } } : n));
      onPushHistory();
    },
    setParam: (id, key, value, history = true) => {
      emitNodes(nodesRef.current.map(n => n.id === id
        ? { ...n, params: { ...(n.params || {}), [key]: value } }
        : n));
      if (history) onPushHistory();
    },
    setColor: (id, color) => {
      emitNodes(nodesRef.current.map(n => n.id === id ? { ...n, ui: { ...n.ui, color } } : n));
      onPushHistory();
    },
    ungroup: (groupId) => {
      emitNodes(nodesRef.current
        .filter(n => n.id !== groupId)
        .map(n => n.parentId === groupId ? { ...n, parentId: undefined } : n));
      onPushHistory();
    },
    deleteGroup: (groupId) => {
      const childIds = new Set(nodesRef.current.filter(n => n.parentId === groupId).map(n => n.id));
      childIds.add(groupId);
      emitView(nodesRef.current.filter(n => !childIds.has(n.id)), edgesRef.current.filter(e => !childIds.has(e.from.node) && !childIds.has(e.to.node)));
      onPushHistory();
    },
    comment: onAddComment ? (id) => setCommentOpenNodeId(prev => prev === id ? null : id) : undefined,
    toggleFlag: (id, flag) => {
      emitNodes(nodesRef.current.map(n => n.id === id
        ? { ...n, ui: { ...n.ui, [flag]: !(n.ui?.[flag] ?? false) } }
        : n));
      onPushHistory();
    },
    openProperties: (id) => setPropsNodeId(id),
    togglePromotedInput: (id, key) => {
      const node = nodesRef.current.find(n => n.id === id);
      const current = node?.ui?.promotedInputs ?? [];
      const isPromoted = current.includes(key);
      const next = isPromoted ? current.filter(k => k !== key) : [...current, key];
      emitNodes(nodesRef.current.map(n => n.id === id
        ? { ...n, ui: { ...n.ui, promotedInputs: next.length ? next : undefined } }
        : n));
      // Removing an input dot: drop any edge that was feeding it.
      if (isPromoted) {
        emitEdges(edgesRef.current.filter(e => !(e.to.node === id && e.to.input === key)));
      }
      onPushHistory();
    },
    setPromotedInputs: (id, keys) => {
      const node = nodesRef.current.find(n => n.id === id);
      const prev = node?.ui?.promotedInputs ?? [];
      const nextSet = new Set(keys);
      emitNodes(nodesRef.current.map(n => n.id === id
        ? { ...n, ui: { ...n.ui, promotedInputs: keys.length ? keys : undefined } }
        : n));
      // Drop edges feeding any input dot that was removed.
      const removed = prev.filter(k => !nextSet.has(k));
      if (removed.length) {
        const removedSet = new Set(removed);
        emitEdges(edgesRef.current.filter(e => !(e.to.node === id && removedSet.has(e.to.input))));
      }
      onPushHistory();
    },
  }), [onExecuteSelected, emitNodes, emitEdges, emitView, onPushHistory, onAddComment]);

  const edgeActions = useMemo<BioEdgeActions>(() => ({
    removeEdge: removeViewEdge,
  }), [removeViewEdge]);

  // ---- Imperative ref API used across App ----
  const fitView = useCallback(() => { rf.fitView({ padding: 0.2, duration: 220 }); }, [rf]);
  const focusNode = useCallback((nodeId: string) => {
    const n = rf.getNode(nodeId);
    if (n) rf.fitView({ nodes: [{ id: nodeId }], padding: 0.6, duration: 240, maxZoom: 1.4 });
  }, [rf]);
  const setViewport = useCallback((vp: { x: number; y: number; scale: number }) => {
    rf.setViewport({ x: vp.x, y: vp.y, zoom: vp.scale });
  }, [rf]);
  const getViewport = useCallback(() => {
    const vp = rf.getViewport();
    return { x: vp.x, y: vp.y, scale: vp.zoom };
  }, [rf]);
  const getSelectedNodeIds = useCallback(() => Array.from(selectedIdsRef.current), []);
  const screenToFlowPosition = useCallback((clientX: number, clientY: number) => {
    const p = rf.screenToFlowPosition({ x: clientX, y: clientY });
    return { x: p.x, y: p.y };
  }, [rf]);
  const executeSelected = useCallback(() => {
    const ids = Array.from(selectedIdsRef.current);
    if (!ids.length) return;
    onExecuteSelected?.(pathRef.current.length > 0 ? [pathRef.current[0]] : ids);
  }, [onExecuteSelected]);
  const autoLayout = useCallback(() => {
    const all = nodesRef.current;
    // Lay out top-level, non-group nodes only, so grouped sub-flows are left
    // intact (dagre has no notion of parent/child). Uses live measured sizes.
    const layoutable = all.filter(n => !n.parentId && n.type !== 'group' && !isIOPanelNode(n));
    const items = layoutable.map(n => {
      const rfn = rf.getNode(n.id);
      return {
        id: n.id,
        width: rfn?.measured?.width ?? n.ui?.width ?? NODE_WIDTH,
        height: rfn?.measured?.height ?? n.ui?.height ?? 80,
      };
    });
    const layoutableIds = new Set(layoutable.map(n => n.id));
    const dagreEdges = edgesRef.current
      .filter(e => layoutableIds.has(e.from.node) && layoutableIds.has(e.to.node))
      .map(e => ({ from: e.from.node, to: e.to.node }));
    const posById = dagreLayout(items, dagreEdges, { direction: 'LR' });
    emitNodes(all.map(wn => {
      const p = posById.get(wn.id);
      return p ? { ...wn, position: [p.x, p.y] as [number, number] } : wn;
    }));
    onPushHistory();
    requestAnimationFrame(() => rf.fitView({ padding: 0.2, duration: 240 }));
  }, [rf, emitNodes, onPushHistory]);

  // --- Right-click context menus (node + pane) ---
  const openNodeMenu = useCallback((e: React.MouseEvent, node: RFNode) => {
    e.preventDefault();
    setMenu({ kind: 'node', x: e.clientX, y: e.clientY, nodeId: node.id, flow: rf.screenToFlowPosition({ x: e.clientX, y: e.clientY }) });
  }, [rf]);
  const openPaneMenu = useCallback((e: React.MouseEvent | MouseEvent) => {
    e.preventDefault();
    setMenu({ kind: 'pane', x: e.clientX, y: e.clientY, flow: rf.screenToFlowPosition({ x: e.clientX, y: e.clientY }) });
  }, [rf]);
  const openEdgeMenu = useCallback((e: React.MouseEvent, edge: RFEdge) => {
    e.preventDefault();
    setMenu({ kind: 'edge', x: e.clientX, y: e.clientY, edgeId: edge.id, flow: rf.screenToFlowPosition({ x: e.clientX, y: e.clientY }) });
  }, [rf]);

  const selectAll = useCallback(() => {
    setRfNodes(ns => ns.map(n => (n.selectable === false ? n : { ...n, selected: true })));
  }, []);

  // Insert a lightweight reroute node at the given flow position.
  const addRerouteAt = useCallback((flow: { x: number; y: number }) => {
    const wn: WorkflowNode = {
      id: `reroute_${Date.now()}`, type: 'reroute', params: {},
      position: [flow.x, flow.y], ui: { title: '' },
    };
    emitNodes([...nodesRef.current, wn]);
    onPushHistory();
  }, [emitNodes, onPushHistory]);

  const exportThumbnail = useCallback(async () => {
    const host = hostRef.current;
    if (!host) return;
    try {
      const url = await captureCanvasThumbnail(host, { pixelRatio: 2 });
      const a = document.createElement('a');
      a.href = url;
      a.download = 'workflow.png';
      a.click();
    } catch (err) {
      console.error('thumbnail export failed', err);
    }
  }, []);

  // Wrap the current selection in a native group node. Children keep their
  // absolute positions in the workflow and gain a parentId; the group node is a
  // padded box around their bounding box with room for a header label.
  const createGroupFromSelection = useCallback(() => {
    const ids = new Set(selectedIdsRef.current);
    const sel = nodesRef.current.filter(n => ids.has(n.id) && n.type !== 'group' && !n.parentId);
    if (sel.length < 1) return;
    let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
    for (const wn of sel) {
      const rfn = rf.getNode(wn.id);
      const w = rfn?.measured?.width ?? rfn?.width ?? NODE_WIDTH;
      const h = rfn?.measured?.height ?? rfn?.height ?? 80;
      minX = Math.min(minX, wn.position[0]);
      minY = Math.min(minY, wn.position[1]);
      maxX = Math.max(maxX, wn.position[0] + w);
      maxY = Math.max(maxY, wn.position[1] + h);
    }
    const pad = 30;
    const header = 26;
    const groupId = `group_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`;
    const group: WorkflowNode = {
      id: groupId,
      type: 'group',
      position: [Math.round(minX - pad), Math.round(minY - pad - header)],
      params: {},
      ui: {
        title: tRef.current('canvas.group.defaultName'),
        color: GROUP_DEFAULT_COLOR,
        width: Math.round(maxX - minX + pad * 2),
        height: Math.round(maxY - minY + pad * 2 + header),
      },
    };
    const selIds = new Set(sel.map(s => s.id));
    // Parent first, then the children with their new parentId.
    const next = nodesRef.current.map(n => selIds.has(n.id) ? { ...n, parentId: groupId } : n);
    emitNodes([group, ...next]);
    onPushHistory();
  }, [rf, emitNodes, onPushHistory]);

  // Delete the current selection (respecting pinned nodes), cascading to the
  // children of any selected group. Backs the multi-select toolbar's delete.
  const deleteSelected = useCallback(() => {
    const selected = new Set(selectedIdsRef.current);
    const pinned = new Set(nodesRef.current.filter(n => n.ui?.pinned).map(n => n.id));
    const toDelete = new Set([...selected].filter(id => !pinned.has(id)));
    for (const n of nodesRef.current) {
      if (n.parentId && toDelete.has(n.parentId)) toDelete.add(n.id);
    }
    if (!toDelete.size) return;
    emitView(nodesRef.current.filter(n => !toDelete.has(n.id)), edgesRef.current.filter(e => !toDelete.has(e.from.node) && !toDelete.has(e.to.node)));
    onPushHistory();
  }, [emitView, onPushHistory]);

  // Dissolve every selected group, keeping its children (clears their parentId).
  const ungroupSelection = useCallback(() => {
    const groupIds = new Set(
      nodesRef.current.filter(n => n.type === 'group' && selectedIdsRef.current.has(n.id)).map(n => n.id),
    );
    if (!groupIds.size) return;
    emitNodes(nodesRef.current
      .filter(n => !groupIds.has(n.id))
      .map(n => n.parentId && groupIds.has(n.parentId) ? { ...n, parentId: undefined } : n));
    onPushHistory();
  }, [emitNodes, onPushHistory]);

  // Native keyboard shortcuts via React Flow's useKeyPress; the rising-edge fire
  // (once per press, not held) is handled by useKeyPressAction below.
  // Cmd/Ctrl+G groups the selection; Cmd/Ctrl+Shift+G ungroups selected groups.
  useKeyPressAction(['Meta+g', 'Control+g'], createGroupFromSelection);
  useKeyPressAction(['Meta+Shift+g', 'Control+Shift+g'], ungroupSelection);

  // ---- Subgraph drill-down actions ----------------------------------------
  // Enter a subgraph node (double-click body, or node context menu). The nav
  // stack stores RAW inner ids; the canvas derives the namespaced view.
  const enterSubgraphNode = useCallback((viewNodeId: string) => {
    if (!workflowId) return;
    const path = pathRef.current;
    const wn = nodesRef.current.find(n => n.id === viewNodeId);
    if (!wn || wn.type !== 'subgraph') return;
    if (!getInnerWorkflow(wn)) {
      toast.warning(tRef.current('canvas.subgraphMissingEmbeddedWorkflow'));
      return;
    }
    cacheViewport(workflowId, path, rf.getViewport());
    enterSubgraph({
      owner: workflowId,
      level: {
        nodeId: wn.id.slice(viewPrefix(path).length),
        title: wn.ui?.title || wn.node_info?.display_name || tRef.current('canvas.subgraphFallbackName'),
      },
    });
  }, [workflowId, rf, enterSubgraph]);

  const jumpToNavDepth = useCallback((depth: number) => {
    if (!workflowId || depth === pathRef.current.length) return;
    cacheViewport(workflowId, pathRef.current, rf.getViewport());
    jumpToDepth({ owner: workflowId, depth });
  }, [workflowId, rf, jumpToDepth]);

  // Esc exits one level (unless a context menu is open — the menu owns Esc).
  useKeyPressAction(['Escape'], () => {
    if (menu) return;
    jumpToNavDepth(pathRef.current.length - 1);
  });

  // Restore the per-level viewport after the path changes (cached position
  // when returning, fit-view on first entry).
  const lastNavKeyRef = useRef<string | null>(null);
  useEffect(() => {
    const key = `${workflowId ?? ''}::${derived.path.join('.')}`;
    if (lastNavKeyRef.current === null) {
      lastNavKeyRef.current = key;
      return;
    }
    if (key === lastNavKeyRef.current) return;
    lastNavKeyRef.current = key;
    const cached = readCachedViewport(workflowId ?? null, derived.path);
    if (cached) {
      rf.setViewport({ x: cached.x, y: cached.y, zoom: cached.zoom });
    } else {
      rf.fitView({ padding: 0.2, duration: 200 });
    }
  }, [derived.path, workflowId, rf]);

  const onNodeDoubleClick = useCallback((_e: React.MouseEvent, node: RFNode) => {
    enterSubgraphNode(node.id);
  }, [enterSubgraphNode]);

  // Convert the current selection (>= 2 nodes) into a single subgraph node,
  // synthesizing boundary ports for the edges that crossed the selection.
  const convertSelection = useCallback(() => {
    const path = pathRef.current;
    const prefix = viewPrefix(path);
    const level = resolveLevel(rootRef.current.nodes, rootRef.current.edges, path);
    if (!level) return;
    const selectedInner = Array.from(selectedIdsRef.current)
      .map(id => (id.startsWith(prefix) ? id.slice(prefix.length) : id));
    const result = convertSelectionToSubgraph(
      level.nodes, level.edges, selectedInner, tRef.current('canvas.subgraphFallbackName'),
    );
    if (!result) return;
    emitRoot(writeLevelBack(rootRef.current.nodes, rootRef.current.edges, path, result.nodes, result.edges));
    onPushHistory();
    toast.success(tRef.current('canvas.subgraphSelectionConverted'));
  }, [emitRoot, onPushHistory]);

  // Inverse of convertSelection: dissolve one subgraph node back into its
  // inner nodes/edges, re-pointing its boundary wires at the mapped slots.
  const unpackSubgraphNode = useCallback((viewNodeId: string) => {
    const path = pathRef.current;
    const prefix = viewPrefix(path);
    const level = resolveLevel(rootRef.current.nodes, rootRef.current.edges, path);
    if (!level) return;
    const result = unpackSubgraph(level.nodes, level.edges, viewNodeId.slice(prefix.length));
    if (!result) {
      toast.warning(tRef.current('canvas.subgraphMissingEmbeddedWorkflow'));
      return;
    }
    emitRoot(writeLevelBack(rootRef.current.nodes, rootRef.current.edges, path, result.nodes, result.edges));
    onPushHistory();
    toast.success(tRef.current('canvas.subgraphUnpacked'));
  }, [emitRoot, onPushHistory]);

  useImperativeHandle(ref, () => ({
    fitView, focusNode, setViewport, getViewport, getSelectedNodeIds, executeSelected, screenToFlowPosition, createGroupFromSelection, autoLayout,
  }), [fitView, focusNode, setViewport, getViewport, getSelectedNodeIds, executeSelected, screenToFlowPosition, createGroupFromSelection, autoLayout]);

  // Build the right-click menu items lazily from the current target. Node items
  // toggle ui flags / collapse / comments; pane items act on the whole canvas.
  const buildMenuItems = useCallback((m: NonNullable<typeof menu>): MenuItem[] => {
    if (m.kind === 'edge' && m.edgeId) {
      return [
        { key: 'reroute', label: t('canvas.menu.insertReroute'), icon: 'reroute', onClick: () => insertRerouteOnEdge(m.edgeId!, m.flow) },
        { key: 'sep1', separator: true },
        { key: 'delete', label: t('canvas.menu.deleteConnection'), icon: 'trash', danger: true, onClick: () => edgeActions.removeEdge(m.edgeId!) },
      ];
    }
    if (m.kind === 'node' && m.nodeId) {
      const wn = nodesRef.current.find(n => n.id === m.nodeId);
      if (!wn) return [];
      const ui = wn.ui ?? {};
      const collapsed = Boolean(ui.collapsed);
      const items: MenuItem[] = [
        { key: 'info', label: t('canvas.menu.nodeInfo'), icon: 'info', onClick: () => setPropsNodeId(m.nodeId!) },
        {
          key: 'logs',
          label: t('canvas.menu.viewLogs', { defaultValue: 'View logs' }),
          icon: 'console',
          onClick: () => setLogsNode({ id: m.nodeId!, x: m.x, y: m.y }),
        },
        { key: 'edit', label: t('canvas.menu.editProperties'), icon: 'edit', onClick: () => setPropsNodeId(m.nodeId!) },
      ];
      if (onAddComment) items.push({ key: 'comment', label: t('canvas.menu.addComment'), icon: 'comment', onClick: () => setCommentOpenNodeId(m.nodeId!) });

      // Subgraph actions: drill into / dissolve a subgraph node, or wrap the
      // current multi-selection in one.
      if (wn.type === 'subgraph') {
        items.push(
          { key: 'enterSubgraph', label: t('canvas.subgraphEnter'), icon: 'target', onClick: () => enterSubgraphNode(m.nodeId!) },
          { key: 'unpackSubgraph', label: t('canvas.subgraphUnpack'), icon: 'layout', onClick: () => unpackSubgraphNode(m.nodeId!) },
        );
      }
      if (selectedIdsRef.current.size >= 2 && !isIOPanelNode(wn)) {
        items.push({ key: 'convertToSubgraph', label: t('canvas.subgraphConvertSelection'), icon: 'grid', onClick: convertSelection });
      }

      // "Add input": give a widget-param a connectable input dot (or remove it).
      // The widget stays; toggling only exposes/hides its input handle. Submenu
      // lists each eligible param, checked when its input dot is showing.
      const meta = wn.type ? (objectInfo[wn.type] || wn.node_info || null) : (wn.node_info || null);
      const promotable = getPromotableParamKeys(meta, wn.params || {});
      const promotedSet = new Set(ui.promotedInputs ?? []);
      if (promotable.length > 0) {
        const storedAll = promotable.every(k => promotedSet.has(k));
        items.push({
          key: 'addInput', label: t('canvas.menu.addInput'), icon: 'link',
          children: [
            {
              // "All": toggle every param's input dot at once.
              key: 'promote:__all__',
              label: t('canvas.menu.addInputAll'),
              checked: allParamInputs || storedAll,
              disabled: allParamInputs,
              onClick: () => actions.setPromotedInputs(m.nodeId!, storedAll ? [] : promotable),
            },
            { key: 'promote:__sep__', separator: true },
            ...promotable.map(key => {
              const spec = meta?.input_types?.required?.[key] || meta?.input_types?.optional?.[key];
              return {
                key: `promote:${key}`,
                label: spec?.label || key,
                checked: allParamInputs || promotedSet.has(key),
                disabled: allParamInputs,
                onClick: () => actions.togglePromotedInput(m.nodeId!, key),
              };
            }),
          ],
        });
      }
      items.push({ key: 'sep1', separator: true });
      items.push(
        { key: 'mute', label: t('canvas.menu.muteNode'), icon: 'mute', checked: Boolean(ui.muted), onClick: () => actions.toggleFlag(m.nodeId!, 'muted') },
        { key: 'bypass', label: t('canvas.menu.bypassNode'), icon: 'bypass', checked: Boolean(ui.bypassed), onClick: () => actions.toggleFlag(m.nodeId!, 'bypassed') },
        { key: 'pin', label: t('canvas.menu.pinNode'), icon: 'lock', checked: Boolean(ui.pinned), onClick: () => actions.toggleFlag(m.nodeId!, 'pinned') },
        { key: 'output', label: t('canvas.menu.setOutput'), icon: 'target', checked: Boolean(ui.output), onClick: () => actions.toggleFlag(m.nodeId!, 'output') },
        { key: 'collapse', label: collapsed ? t('canvas.menu.expand') : t('canvas.menu.collapse'), icon: collapsed ? 'chevronDown' : 'chevronUp', onClick: () => actions.toggleCollapse(m.nodeId!) },
        { key: 'sep2', separator: true },
        { key: 'delete', label: t('canvas.menu.delete'), icon: 'trash', danger: true, disabled: Boolean(ui.pinned), onClick: () => actions.remove(m.nodeId!) },
      );
      return items;
    }
    // Pane menu.
    return [
      ...(onOpenNodeLibrary ? [{ key: 'add', label: t('canvas.menu.addNode'), icon: 'plus', onClick: onOpenNodeLibrary }] : []),
      { key: 'reroute', label: t('canvas.menu.addReroute'), icon: 'reroute', onClick: () => addRerouteAt(m.flow) },
      { key: 'sep1', separator: true },
      { key: 'fit', label: t('canvas.menu.fitView'), icon: 'fit', onClick: fitView },
      { key: 'selectAll', label: t('canvas.menu.selectAll'), icon: 'grid', onClick: selectAll },
      { key: 'arrange', label: t('canvas.menu.arrangeNodes'), icon: 'layout', onClick: autoLayout },
      { key: 'sep2', separator: true },
      { key: 'thumb', label: t('canvas.menu.exportThumbnail'), icon: 'image', onClick: () => { void exportThumbnail(); } },
    ];
  }, [t, actions, edgeActions, insertRerouteOnEdge, objectInfo, allParamInputs, onAddComment, onOpenNodeLibrary, addRerouteAt, fitView, selectAll, autoLayout, exportThumbnail, enterSubgraphNode, unpackSubgraphNode, convertSelection]);

  const propsNode = propsNodeId ? nodesRef.current.find(n => n.id === propsNodeId) ?? null : null;

  return (
    <BioNodeActionsContext.Provider value={actions}>
    <BioEdgeActionsContext.Provider value={edgeActions}>
    <MultiSelectContext.Provider value={selectedIds.length > 1}>
      <div
        ref={hostRef}
        className={`workflow-canvas-host ${nodeShadow ? '' : 'bio-no-node-shadow'}`}
        style={hostStyle}
        onMouseMove={collabSessionActive ? onPaneMouseMove : undefined}
        onMouseLeave={collabSessionActive ? onPaneMouseLeave : undefined}
      >
      <ReactFlow
        nodes={rfNodes}
        edges={rfEdges}
        nodeTypes={NODE_TYPES}
        edgeTypes={EDGE_TYPES}
        onNodesChange={handleNodesChange}
        onEdgesChange={handleEdgesChange}
        onNodeDragStart={onNodeDragStart}
        onNodeDragStop={onNodeDragStop}
        onConnect={onConnect}
        edgesReconnectable={edgeReconnectable}
        onReconnectStart={edgeReconnectable ? onReconnectStart : undefined}
        onReconnect={edgeReconnectable ? onReconnect : undefined}
        onReconnectEnd={edgeReconnectable ? onReconnectEnd : undefined}
        isValidConnection={isValidConnection}
        onDelete={onDelete}
        onBeforeDelete={onBeforeDelete}
        onSelectionChange={handleSelectionChange}
        onNodeContextMenu={openNodeMenu}
        onNodeDoubleClick={onNodeDoubleClick}
        onPaneContextMenu={openPaneMenu}
        onEdgeContextMenu={openEdgeMenu}
        onError={onError}
        defaultEdgeOptions={DEFAULT_EDGE_OPTIONS}
        snapToGrid={snapToGrid}
        snapGrid={snapGridValue}
        deleteKeyCode={DELETE_KEYS}
        multiSelectionKeyCode={MULTISELECT_KEYS}
        connectionLineType={connectionLineType}
        connectionRadius={connectionRadius}
        elevateEdgesOnSelect
        elevateNodesOnSelect
        selectionOnDrag
        selectionMode={SelectionMode.Partial}
        panOnDrag={PAN_ON_DRAG}
        panActivationKeyCode="Space"
        panOnScroll={panOnScroll}
        zoomOnScroll={!panOnScroll}
        zoomOnDoubleClick={zoomOnDoubleClick}
        fitView
        fitViewOptions={FIT_VIEW_OPTIONS}
        minZoom={0.1}
        maxZoom={4}
        colorMode={colorMode}
        proOptions={PRO_OPTIONS}
      >
        {showBackground && <Background variant={bgVariant} gap={bgVariant === BackgroundVariant.Dots ? gridSize : gridSize * 2} size={1} />}
        {showControls && (
          <Controls>
            <ControlButton onClick={autoLayout} title={t('canvas.autoArrangeNodes')} aria-label={t('canvas.autoArrangeNodes')}>
              <span aria-hidden style={{ fontSize: 14, lineHeight: 1 }}>⤨</span>
            </ControlButton>
          </Controls>
        )}
        {showMinimap && (
          <MiniMap
            className="bio-minimap"
            pannable
            zoomable
            nodeColor={MINIMAP_NODE_COLOR}
          />
        )}
        {/* Native multi-select toolbar: React Flow positions a <NodeToolbar>
            bound to several node ids above the selection's bounding box. Replaces
            the old custom SelectionToolbox. */}
        <NodeToolbar nodeId={selectedIds} isVisible={selectedIds.length > 1} position={Position.Top} className="bio-node-toolbar">
          <button type="button" title={t('canvas.group.create')} aria-label={t('canvas.group.create')} onClick={createGroupFromSelection}><span aria-hidden>▣</span></button>
          <button type="button" title={t('canvas.subgraphConvertSelection')} aria-label={t('canvas.subgraphConvertSelection')} onClick={convertSelection}><span aria-hidden>⧠</span></button>
          <button type="button" title={t('canvas.menu.run')} aria-label={t('canvas.menu.run')} onClick={() => onExecuteSelected?.(pathRef.current.length > 0 ? [pathRef.current[0]] : selectedIds)}><span aria-hidden>▶</span></button>
          <button type="button" className="danger" title={t('canvas.menu.delete')} aria-label={t('canvas.menu.delete')} onClick={deleteSelected}><span aria-hidden>✕</span></button>
        </NodeToolbar>
        {(helperLines.horizontal !== undefined || helperLines.vertical !== undefined) && (
          <HelperLines horizontal={helperLines.horizontal} vertical={helperLines.vertical} />
        )}
        {/* Multiplayer: remote cursors + on-node comment pins/threads, both drawn
            in flow coords via <ViewportPortal> so they pan/zoom with the graph. */}
        {collabSessionActive && collabUsers && (
          <CollabCursors users={collabUsers} currentUserId={currentUserId} />
        )}
        {showComments && onAddComment && onResolveComment && onDeleteComment && (
          <NodeComments
            comments={nodeComments ?? EMPTY_COMMENTS}
            currentUserId={currentUserId}
            currentUserName={currentUserName}
            currentUserColor={currentUserColor}
            openNodeId={commentOpenNodeId}
            onOpenChange={setCommentOpenNodeId}
            onAddComment={onAddComment}
            onResolveComment={onResolveComment}
            onDeleteComment={onDeleteComment}
            onHideComments={() => set('bionodulo.canvas.showComments', false)}
          />
        )}
        {showDebugOverlay && <Devtools />}
      </ReactFlow>
      {/* Subgraph drill-down breadcrumb — only visible inside a subgraph. */}
      <SubgraphBreadcrumb
        rootTitle={workflowName || t('canvas.subgraphWorkflowFallbackName')}
        stack={stack.slice(0, derived.path.length)}
        onJump={jumpToNavDepth}
      />
      {menu && (
        <ContextMenu x={menu.x} y={menu.y} items={buildMenuItems(menu)} onClose={() => setMenu(null)} />
      )}
      {logsNode && (
        <NodeLogsPopover
          nodeId={logsNode.id}
          title={
            nodesRef.current.find(n => n.id === logsNode.id)?.ui?.title
            ?? nodesRef.current.find(n => n.id === logsNode.id)?.type
          }
          x={logsNode.x}
          y={logsNode.y}
          onClose={() => setLogsNode(null)}
        />
      )}
      {propsNode && (
        <NodePropertiesDialog
          node={propsNode}
          objectInfo={objectInfo}
          onRename={(id, title) => { emitNodes(nodesRef.current.map(n => n.id === id ? { ...n, ui: { ...n.ui, title } } : n)); onPushHistory(); }}
          onParamChange={(id, key, value) => actions.setParam(id, key, value)}
          onClose={() => setPropsNodeId(null)}
        />
      )}
      </div>
    </MultiSelectContext.Provider>
    </BioEdgeActionsContext.Provider>
    </BioNodeActionsContext.Provider>
  );
});

function WorkflowCanvas(props: WorkflowCanvasProps, ref: React.Ref<WorkflowCanvasRef>) {
  return (
    <ReactFlowProvider>
      <WorkflowCanvasInner {...props} ref={ref} />
    </ReactFlowProvider>
  );
}

export default forwardRef<WorkflowCanvasRef, WorkflowCanvasProps>(WorkflowCanvas);
