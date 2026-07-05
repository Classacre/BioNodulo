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
import { useSetAtom } from 'jotai';
import { useTranslation } from 'react-i18next';
import type { WorkflowNode, WorkflowEdge, ObjectInfo, NodeStatus, WorkflowParameter } from '../../types';
import type { AwarenessState, Comment } from '../../collab/types';
import { edgeColorForSource } from '../../utils';
import { nodeCategoryDisplayLabel } from '../../utils/nodeCategories';
import { getVisibleInputSpecs } from '../../utils/nodeInputVisibility';
import { resolveNodeOutputs } from '../../utils/nodeOutputs';
import { dragCoordinate } from '../../utils/snap';
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
import BioNode from './BioNode';
import BioEdge from './BioEdge';
import GroupNode from './GroupNode';
import Devtools from './Devtools';
import CollabCursors from './CollabCursors';
import NodeComments from './NodeComments';
import ContextMenu, { type MenuItem } from './ContextMenu';
import NodePropertiesDialog from './NodePropertiesDialog';
import { captureCanvasThumbnail } from '../../utils/canvasThumbnail';
import HelperLines from './HelperLines';
import { getHelperLines } from './helperLines';
import { BioNodeActionsContext, MultiSelectContext, type BioNodeActions } from './bioNodeActions';
import { BioEdgeActionsContext, type BioEdgeActions } from './bioEdgeActions';

export type { GraphNode, WorkflowCanvasRef };

const NODE_TYPES = { bio: BioNode, group: GroupNode };
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
  const promotedInputs = wn.ui?.promotedInputs ?? EMPTY_PROMOTED;
  const promotedSet = promotedInputs.length ? new Set(promotedInputs) : null;
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
    inputs: (meta && !visualOnly) ? [
      ...Object.entries(visibleInputs.required),
      ...Object.entries(visibleInputs.optional),
    ].filter(([name, spec]) => !isInteractiveWidgetSpec(spec) || promotedSet?.has(name)).map(([name, spec]) => ({
      name, type: spec.type || 'STRING', connected: connectedIn.has(`${wn.id}:${name}`),
    })) : [],
    outputs: (meta && !visualOnly) ? resolveNodeOutputs(meta, wn.params || {}).map(output => ({
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
    inlinePreview: false,
    previewCollapsed: false,
    showingPreview: false,
  };
}

const WorkflowCanvasInner = forwardRef<WorkflowCanvasRef, WorkflowCanvasProps>(function WorkflowCanvasInner({
  nodes, edges, objectInfo,
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
  const defaultNodeShape = getString('bionodulo.canvas.nodeShape', 'round');     // round|box|card
  const nodeRadius = Math.min(24, Math.max(0, getNumber('bionodulo.canvas.nodeRadius', 8)));
  const nodeShadow = getBool('bionodulo.canvas.nodeShadow', true);
  const connectionRadius = Math.min(80, Math.max(8, getNumber('bionodulo.canvas.connectionRadius', 28)));
  const bgPatternSetting = getString('bionodulo.canvas.backgroundPattern', 'auto'); // auto|dots|lines|cross|none
  const panOnScroll = getBool('bionodulo.canvas.panOnScroll', true);
  const zoomOnDoubleClick = getBool('bionodulo.canvas.zoomOnDoubleClick', false);
  const nodeFontSize = Math.min(18, Math.max(9, getNumber('bionodulo.canvas.nodeFontSize', 12)));
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
  const nodesRef = useRef(nodes); nodesRef.current = nodes;
  const edgesRef = useRef(edges); edgesRef.current = edges;
  const isDraggingRef = useRef(false);
  const selectedIdsRef = useRef<Set<string>>(new Set());

  const [rfNodes, setRfNodes] = useState<RFNode[]>([]);
  const [helperLines, setHelperLines] = useState<{ horizontal?: number; vertical?: number }>({});
  // Reactive selection (for the multi-select toolbar); the ref mirror stays for
  // callbacks that need the latest value without re-binding.
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [commentOpenNodeId, setCommentOpenNodeId] = useState<string | null>(null);
  const [propsNodeId, setPropsNodeId] = useState<string | null>(null);
  const [menu, setMenu] = useState<{ kind: 'node' | 'pane'; x: number; y: number; nodeId?: string; flow: { x: number; y: number } } | null>(null);
  const hostRef = useRef<HTMLDivElement>(null);

  // Precompute the connected input/output port keys once per edges change, so
  // the node reconcile is O(nodes) instead of scanning all edges per node.
  const connectedPorts = useMemo(() => {
    const cin = new Set<string>();
    const cout = new Set<string>();
    for (const e of edges) {
      cin.add(`${e.to.node}:${e.to.input}`);
      cout.add(`${e.from.node}:${e.from.output}`);
    }
    return { cin, cout };
  }, [edges]);

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
      for (const wn of nodes) {
        if (wn.type === 'group') groupAbs.set(wn.id, { x: wn.position[0], y: wn.position[1] });
      }
      const built: RFNode[] = nodes.map(wn => {
        const selected = prevSel.get(wn.id) ?? false;
        const parent = wn.parentId && groupAbs.has(wn.parentId) ? groupAbs.get(wn.parentId)! : null;
        const position = parent
          ? { x: wn.position[0] - parent.x, y: wn.position[1] - parent.y }
          : { x: wn.position[0], y: wn.position[1] };

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

        const g = toGraphNode(wn, connectedPorts.cin, connectedPorts.cout, objectInfo, nodeStatusMap?.get(wn.id), defaultNodeShape, tRef.current);
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
  }, [nodes, connectedPorts, objectInfo, nodeStatusMap, missingDependencyNodeIds, defaultNodeShape]);

  // Stable `${nodeId}:${outputName}` -> output type map for edge colour, keyed
  // on props (not node positions) so it does not churn during a drag.
  const outTypeByNodeOutput = useMemo(() => {
    const map = new Map<string, string>();
    for (const wn of nodes) {
      const meta = wn.type ? (objectInfo[wn.type] || wn.node_info || null) : (wn.node_info || null);
      if (!meta) continue;
      for (const output of resolveNodeOutputs(meta, wn.params || {})) {
        map.set(`${wn.id}:${output.name}`, output.type);
      }
    }
    return map;
  }, [nodes, objectInfo]);

  // Stable `${nodeId}:${inputName}` -> input type map, for connection validation.
  const inTypeByNodeInput = useMemo(() => {
    const map = new Map<string, string>();
    for (const wn of nodes) {
      const meta = wn.type ? (objectInfo[wn.type] || wn.node_info || null) : (wn.node_info || null);
      if (!meta) continue;
      const visible = getVisibleInputSpecs(meta, wn.params || {});
      for (const [name, spec] of [...Object.entries(visible.required), ...Object.entries(visible.optional)]) {
        map.set(`${wn.id}:${name}`, spec.type || '');
      }
    }
    return map;
  }, [nodes, objectInfo]);

  // Edges are local React Flow state (like nodes), reconciled from props but
  // carrying their own `selected` flag — a controlled flow only surfaces edge
  // select/remove via onEdgesChange, so a pure-derived array could never select
  // (which would break the BioEdge delete button + elevateEdgesOnSelect).
  const [rfEdges, setRfEdges] = useState<RFEdge[]>([]);
  useEffect(() => {
    setRfEdges(prev => {
      const prevSel = new Map(prev.map(e => [e.id, e.selected]));
      return edges.map(edge => {
        const outType = outTypeByNodeOutput.get(`${edge.from.node}:${edge.from.output}`) || '';
        const stroke = edgeColorForSource(outType);
        return {
          id: edge.id,
          source: edge.from.node,
          target: edge.to.node,
          sourceHandle: edge.from.output,
          targetHandle: edge.to.input,
          selected: prevSel.get(edge.id) ?? false,
          animated: edgeAnimated,
          ariaLabel: `${edge.from.node} → ${edge.to.node}`,
          style: { stroke, strokeWidth: edgeWidth },
          data: { pathType: edgeType },
          ...(edgeArrows ? { markerEnd: { type: MarkerType.ArrowClosed, color: stroke, width: 18, height: 18 } } : {}),
        } satisfies RFEdge;
      });
    });
  }, [edges, outTypeByNodeOutput, edgeType, edgeAnimated, edgeWidth, edgeArrows]);

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
      const x = dragCoordinate(ax, 0, snapToGrid, gridSize);
      const y = dragCoordinate(ay, 0, snapToGrid, gridSize);
      if (wn.position[0] === x && wn.position[1] === y) return wn;
      return { ...wn, position: [x, y] as [number, number] };
    });
    onNodesChange(updated);
    onPushHistory();
  }, [rf, onNodesChange, onPushHistory, snapToGrid, gridSize]);

  const onConnect = useCallback((connection: Connection) => {
    if (!connection.source || !connection.target || !connection.sourceHandle || !connection.targetHandle) return;
    if (connection.source === connection.target) return;
    const newEdge: WorkflowEdge = {
      id: `e_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`,
      from: { node: connection.source, output: connection.sourceHandle },
      to: { node: connection.target, input: connection.targetHandle },
    };
    // One connection per input slot: drop any edge already in that slot.
    const filtered = edgesRef.current.filter(e => !(e.to.node === connection.target && e.to.input === connection.targetHandle));
    onEdgesChange([...filtered, newEdge]);
    onPushHistory();
  }, [onEdgesChange, onPushHistory]);

  // Native connection gate: React Flow calls this while the user drags a link
  // and greys out ports it rejects. Block self-links, type-incompatible ports,
  // and any connection that would create a cycle (workflows must stay a DAG).
  // Adjacency (source node -> target nodes), memoized on edges so a connection
  // drag doesn't rebuild the graph for every hovered port.
  const adjacency = useMemo(() => {
    const map = new Map<string, string[]>();
    for (const e of edges) {
      const list = map.get(e.from.node);
      if (list) list.push(e.to.node); else map.set(e.from.node, [e.to.node]);
    }
    return map;
  }, [edges]);

  const isValidConnection = useCallback((conn: Connection | RFEdge): boolean => {
    const { source, target, sourceHandle, targetHandle } = conn;
    if (!source || !target || source === target) return false;
    const outType = outTypeByNodeOutput.get(`${source}:${sourceHandle}`) || '';
    const inType = inTypeByNodeInput.get(`${target}:${targetHandle}`) || '';
    if (!typesCompatible(outType, inType)) return false;
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
  }, [adjacency, outTypeByNodeOutput, inTypeByNodeInput]);

  // Native edge reconnection: drag an existing edge's end onto another port.
  const onReconnect = useCallback((oldEdge: RFEdge, newConn: Connection) => {
    if (!newConn.source || !newConn.target || !newConn.sourceHandle || !newConn.targetHandle) return;
    const filtered = edgesRef.current.filter(e =>
      e.id !== oldEdge.id && !(e.to.node === newConn.target && e.to.input === newConn.targetHandle));
    filtered.push({
      id: oldEdge.id,
      from: { node: newConn.source, output: newConn.sourceHandle },
      to: { node: newConn.target, input: newConn.targetHandle },
    });
    onEdgesChange(filtered);
    onPushHistory();
  }, [onEdgesChange, onPushHistory]);

  // Single native delete handler: React Flow passes the FULL cascade in one call
  // — the deleted nodes plus every edge removed as a consequence — so we commit
  // nodes + edges together with a single history push (using onNodesDelete +
  // onEdgesDelete separately double-fires off the same stale ref).
  const onDelete = useCallback(({ nodes: delNodes, edges: delEdges }: { nodes: RFNode[]; edges: RFEdge[] }) => {
    const goneNodes = new Set(delNodes.map(n => n.id));
    const goneEdges = new Set(delEdges.map(e => e.id));
    if (goneNodes.size) onNodesChange(nodesRef.current.filter(n => !goneNodes.has(n.id)));
    if (goneEdges.size) onEdgesChange(edgesRef.current.filter(e => !goneEdges.has(e.id)));
    if (goneNodes.size || goneEdges.size) onPushHistory();
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
    run: (id) => onExecuteSelected?.([id]),
    rename: async (id) => {
      const wn = nodesRef.current.find(n => n.id === id);
      if (!wn) return;
      const current = wn.ui?.title || wn.type || '';
      const next = await promptDialog({ title: tRef.current('canvas.menu.rename'), message: tRef.current('canvas.menu.renamePrompt', 'New node name'), defaultValue: current });
      if (typeof next !== 'string') return;
      onNodesChange(nodesRef.current.map(n => n.id === id ? { ...n, ui: { ...n.ui, title: next } } : n));
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
      onNodesChange([...nodesRef.current, clone]);
      onPushHistory();
    },
    toggleCollapse: (id) => {
      onNodesChange(nodesRef.current.map(n => n.id === id
        ? { ...n, ui: { ...n.ui, collapsed: !(n.ui?.collapsed ?? false) } }
        : n));
      onPushHistory();
    },
    remove: (id) => {
      onNodesChange(nodesRef.current.filter(n => n.id !== id));
      onEdgesChange(edgesRef.current.filter(e => e.from.node !== id && e.to.node !== id));
      onPushHistory();
    },
    resize: (id, width, height) => {
      onNodesChange(nodesRef.current.map(n => n.id === id ? { ...n, ui: { ...n.ui, width, height } } : n));
      onPushHistory();
    },
    setParam: (id, key, value, history = true) => {
      onNodesChange(nodesRef.current.map(n => n.id === id
        ? { ...n, params: { ...(n.params || {}), [key]: value } }
        : n));
      if (history) onPushHistory();
    },
    setColor: (id, color) => {
      onNodesChange(nodesRef.current.map(n => n.id === id ? { ...n, ui: { ...n.ui, color } } : n));
      onPushHistory();
    },
    ungroup: (groupId) => {
      onNodesChange(nodesRef.current
        .filter(n => n.id !== groupId)
        .map(n => n.parentId === groupId ? { ...n, parentId: undefined } : n));
      onPushHistory();
    },
    deleteGroup: (groupId) => {
      const childIds = new Set(nodesRef.current.filter(n => n.parentId === groupId).map(n => n.id));
      childIds.add(groupId);
      onNodesChange(nodesRef.current.filter(n => !childIds.has(n.id)));
      onEdgesChange(edgesRef.current.filter(e => !childIds.has(e.from.node) && !childIds.has(e.to.node)));
      onPushHistory();
    },
    comment: onAddComment ? (id) => setCommentOpenNodeId(prev => prev === id ? null : id) : undefined,
    toggleFlag: (id, flag) => {
      onNodesChange(nodesRef.current.map(n => n.id === id
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
      onNodesChange(nodesRef.current.map(n => n.id === id
        ? { ...n, ui: { ...n.ui, promotedInputs: next.length ? next : undefined } }
        : n));
      // Demoting a connected input back to a widget: drop the dangling edge(s).
      if (isPromoted) {
        onEdgesChange(edgesRef.current.filter(e => !(e.to.node === id && e.to.input === key)));
      }
      onPushHistory();
    },
  }), [onExecuteSelected, onNodesChange, onEdgesChange, onPushHistory, onAddComment]);

  const edgeActions = useMemo<BioEdgeActions>(() => ({
    removeEdge: (id) => {
      onEdgesChange(edgesRef.current.filter(e => e.id !== id));
      onPushHistory();
    },
  }), [onEdgesChange, onPushHistory]);

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
    if (ids.length) onExecuteSelected?.(ids);
  }, [onExecuteSelected]);
  const autoLayout = useCallback(() => {
    const all = nodesRef.current;
    // Lay out top-level, non-group nodes only, so grouped sub-flows are left
    // intact (dagre has no notion of parent/child). Uses live measured sizes.
    const layoutable = all.filter(n => !n.parentId && n.type !== 'group');
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
    onNodesChange(all.map(wn => {
      const p = posById.get(wn.id);
      return p ? { ...wn, position: [p.x, p.y] as [number, number] } : wn;
    }));
    onPushHistory();
    requestAnimationFrame(() => rf.fitView({ padding: 0.2, duration: 240 }));
  }, [rf, onNodesChange, onPushHistory]);

  // --- Right-click context menus (node + pane) ---
  const openNodeMenu = useCallback((e: React.MouseEvent, node: RFNode) => {
    e.preventDefault();
    setMenu({ kind: 'node', x: e.clientX, y: e.clientY, nodeId: node.id, flow: rf.screenToFlowPosition({ x: e.clientX, y: e.clientY }) });
  }, [rf]);
  const openPaneMenu = useCallback((e: React.MouseEvent | MouseEvent) => {
    e.preventDefault();
    setMenu({ kind: 'pane', x: e.clientX, y: e.clientY, flow: rf.screenToFlowPosition({ x: e.clientX, y: e.clientY }) });
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
    onNodesChange([...nodesRef.current, wn]);
    onPushHistory();
  }, [onNodesChange, onPushHistory]);

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
    onNodesChange([group, ...next]);
    onPushHistory();
  }, [rf, onNodesChange, onPushHistory]);

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
    onNodesChange(nodesRef.current.filter(n => !toDelete.has(n.id)));
    onEdgesChange(edgesRef.current.filter(e => !toDelete.has(e.from.node) && !toDelete.has(e.to.node)));
    onPushHistory();
  }, [onNodesChange, onEdgesChange, onPushHistory]);

  // Dissolve every selected group, keeping its children (clears their parentId).
  const ungroupSelection = useCallback(() => {
    const groupIds = new Set(
      nodesRef.current.filter(n => n.type === 'group' && selectedIdsRef.current.has(n.id)).map(n => n.id),
    );
    if (!groupIds.size) return;
    onNodesChange(nodesRef.current
      .filter(n => !groupIds.has(n.id))
      .map(n => n.parentId && groupIds.has(n.parentId) ? { ...n, parentId: undefined } : n));
    onPushHistory();
  }, [onNodesChange, onPushHistory]);

  // Native keyboard shortcuts via React Flow's useKeyPress; the rising-edge fire
  // (once per press, not held) is handled by useKeyPressAction below.
  // Cmd/Ctrl+G groups the selection; Cmd/Ctrl+Shift+G ungroups selected groups.
  useKeyPressAction(['Meta+g', 'Control+g'], createGroupFromSelection);
  useKeyPressAction(['Meta+Shift+g', 'Control+Shift+g'], ungroupSelection);

  useImperativeHandle(ref, () => ({
    fitView, focusNode, setViewport, getViewport, getSelectedNodeIds, executeSelected, screenToFlowPosition, createGroupFromSelection, autoLayout,
  }), [fitView, focusNode, setViewport, getViewport, getSelectedNodeIds, executeSelected, screenToFlowPosition, createGroupFromSelection, autoLayout]);

  // Build the right-click menu items lazily from the current target. Node items
  // toggle ui flags / collapse / comments; pane items act on the whole canvas.
  const buildMenuItems = useCallback((m: NonNullable<typeof menu>): MenuItem[] => {
    if (m.kind === 'node' && m.nodeId) {
      const wn = nodesRef.current.find(n => n.id === m.nodeId);
      if (!wn) return [];
      const ui = wn.ui ?? {};
      const collapsed = Boolean(ui.collapsed);
      const items: MenuItem[] = [
        { key: 'info', label: t('canvas.menu.nodeInfo'), icon: 'info', onClick: () => setPropsNodeId(m.nodeId!) },
        { key: 'edit', label: t('canvas.menu.editProperties'), icon: 'edit', onClick: () => setPropsNodeId(m.nodeId!) },
      ];
      if (onAddComment) items.push({ key: 'comment', label: t('canvas.menu.addComment'), icon: 'comment', onClick: () => setCommentOpenNodeId(m.nodeId!) });

      // "Connect to parameter": promote a widget-param to a connectable input
      // port (or demote it back). Submenu lists each promotable param, checked
      // when it's currently a port.
      const meta = wn.type ? (objectInfo[wn.type] || wn.node_info || null) : (wn.node_info || null);
      const promotable = getPromotableParamKeys(meta, wn.params || {});
      const promotedSet = new Set(ui.promotedInputs ?? []);
      if (promotable.length > 0) {
        items.push({
          key: 'connectParam', label: t('canvas.menu.connectParam'), icon: 'link',
          children: promotable.map(key => {
            const spec = meta?.input_types?.required?.[key] || meta?.input_types?.optional?.[key];
            return {
              key: `promote:${key}`,
              label: spec?.label || key,
              checked: promotedSet.has(key),
              onClick: () => actions.togglePromotedInput(m.nodeId!, key),
            };
          }),
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
  }, [t, actions, objectInfo, onAddComment, onOpenNodeLibrary, addRerouteAt, fitView, selectAll, autoLayout, exportThumbnail]);

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
        onReconnect={onReconnect}
        isValidConnection={isValidConnection}
        onDelete={onDelete}
        onBeforeDelete={onBeforeDelete}
        onSelectionChange={handleSelectionChange}
        onNodeContextMenu={openNodeMenu}
        onPaneContextMenu={openPaneMenu}
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
          <button type="button" title={t('canvas.menu.run')} aria-label={t('canvas.menu.run')} onClick={() => onExecuteSelected?.(selectedIds)}><span aria-hidden>▶</span></button>
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
      {menu && (
        <ContextMenu x={menu.x} y={menu.y} items={buildMenuItems(menu)} onClose={() => setMenu(null)} />
      )}
      {propsNode && (
        <NodePropertiesDialog
          node={propsNode}
          objectInfo={objectInfo}
          onRename={(id, title) => { onNodesChange(nodesRef.current.map(n => n.id === id ? { ...n, ui: { ...n.ui, title } } : n)); onPushHistory(); }}
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
