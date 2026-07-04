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
  Panel,
  NodeToolbar,
  Position,
  MarkerType,
  ConnectionLineType,
  SelectionMode,
  applyNodeChanges,
  getOutgoers,
  useReactFlow,
  useKeyPress,
  type Node as RFNode,
  type Edge as RFEdge,
  type NodeChange,
  type NodePositionChange,
  type Connection,
  type OnSelectionChangeParams,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { useSetAtom } from 'jotai';
import { useTranslation } from 'react-i18next';
import type { WorkflowNode, WorkflowEdge, ObjectInfo, NodeStatus, WorkflowParameter } from '../../types';
import { edgeColorForSource } from '../../utils';
import { nodeCategoryDisplayLabel } from '../../utils/nodeCategories';
import { getVisibleInputSpecs } from '../../utils/nodeInputVisibility';
import { resolveNodeOutputs } from '../../utils/nodeOutputs';
import { dragCoordinate } from '../../utils/snap';
import {
  NODE_WIDTH, NODE_NOTE_WIDTH, nodeColor, calcNodeHeight, arrangeNodesLayout,
  type GraphNode, type WorkflowCanvasRef,
} from './canvasModel';
import { useSettings } from '../../hooks/settings';
import { promptDialog } from '../ui';
import { logError } from '../../state/logging';
import { getResolvedPaletteMode } from '../../state/palettes';
import { selectedNodeIdAtom } from '../../state/uiAtoms';
import BioNode from './BioNode';
import BioEdge from './BioEdge';
import GroupNode from './GroupNode';
import Devtools from './Devtools';
import HelperLines from './HelperLines';
import { getHelperLines } from './helperLines';
import { BioNodeActionsContext, MultiSelectContext, type BioNodeActions } from './bioNodeActions';
import { BioEdgeActionsContext, type BioEdgeActions } from './bioEdgeActions';

export type { GraphNode, WorkflowCanvasRef };

const NODE_TYPES = { bio: BioNode, group: GroupNode };
const GROUP_DEFAULT_COLOR = '#6366f1';
const EDGE_TYPES = { bio: BioEdge };
const IS_DEV = import.meta.env.DEV;

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
}

// WorkflowNode -> GraphNode: resolve metadata, geometry, ports, colour. The
// GraphNode shape is shared with the inspector/editor panels, so we still fill
// every field (unused-in-canvas ones default to false).
function toGraphNode(
  wn: WorkflowNode,
  edges: WorkflowEdge[],
  objectInfo: ObjectInfo,
  status: NodeStatus['status'] | undefined,
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
  let nodeHeight: number;
  if (isReroute) nodeHeight = 20;
  else if (collapsed) nodeHeight = calcNodeHeight(meta, true, wn.params);
  else {
    const minHeight = calcNodeHeight(meta, false, wn.params, isNote ? nodeWidth : undefined);
    const storedHeight = wn.ui?.height;
    nodeHeight = storedHeight ? Math.max(storedHeight, minHeight) : minHeight;
  }
  const visibleInputs = getVisibleInputSpecs(meta, wn.params || {});
  return {
    id: wn.id,
    type: wn.type,
    display_name: meta?.display_name || wn.type || t('canvas.unknownNodeDisplayName'),
    category: meta?.category || 'Utility',
    x: wn.position[0],
    y: wn.position[1],
    width: nodeWidth,
    height: nodeHeight,
    inputs: (meta && !visualOnly) ? [
      ...Object.entries(visibleInputs.required).map(([name, spec]) => ({
        name, type: spec.type || 'STRING', connected: edges.some(e => e.to.node === wn.id && e.to.input === name),
      })),
      ...Object.entries(visibleInputs.optional).map(([name, spec]) => ({
        name, type: spec.type || 'STRING', connected: edges.some(e => e.to.node === wn.id && e.to.input === name),
      })),
    ] : [],
    outputs: (meta && !visualOnly) ? resolveNodeOutputs(meta, wn.params || {}).map(output => ({
      name: output.name, type: output.type,
      connected: edges.some(e => e.from.node === wn.id && e.from.output === output.name),
    })) : [],
    params: wn.params || {},
    meta,
    color: wn.ui?.color || nodeColor(meta),
    muted: wn.ui?.muted ?? false,
    bypassed: wn.ui?.bypassed ?? false,
    selected: false,
    collapsed,
    pinned: wn.ui?.pinned || false,
    shape: wn.ui?.shape || (isNote ? 'card' : 'round'),
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
}, ref) {
  const { t } = useTranslation();
  const tRef = useRef(t); tRef.current = t;
  const rf = useReactFlow();
  const setSelectedNodeId = useSetAtom(selectedNodeIdAtom);
  const { getBool, getNumber } = useSettings();
  const showGrid = getBool('bionodulo.canvas.showGrid', true);
  const gridSize = Math.min(200, Math.max(4, getNumber('bionodulo.canvas.gridSize', 20)));
  const { colorMode, pattern } = useCanvasChrome();
  const bgVariant = pattern === 'grid' ? BackgroundVariant.Lines
    : pattern === 'mesh' ? BackgroundVariant.Cross
    : BackgroundVariant.Dots;
  const showBackground = showGrid && pattern !== 'none';

  // Latest props for callbacks that must read fresh values without re-binding.
  const nodesRef = useRef(nodes); nodesRef.current = nodes;
  const edgesRef = useRef(edges); edgesRef.current = edges;
  const objectInfoRef = useRef(objectInfo); objectInfoRef.current = objectInfo;
  const isDraggingRef = useRef(false);
  const selectedIdsRef = useRef<Set<string>>(new Set());

  const [rfNodes, setRfNodes] = useState<RFNode[]>([]);
  const [helperLines, setHelperLines] = useState<{ horizontal?: number; vertical?: number }>({});
  // Reactive selection (for the multi-select toolbar); the ref mirror stays for
  // callbacks that need the latest value without re-binding.
  const [selectedIds, setSelectedIds] = useState<string[]>([]);

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
          return {
            id: wn.id, type: 'group', position, selected,
            width: w, height: h, style: { width: w, height: h },
            data: { title: wn.ui?.title ?? tRef.current('canvas.group.defaultName'), color: wn.ui?.color ?? GROUP_DEFAULT_COLOR },
          } satisfies RFNode;
        }

        const g = toGraphNode(wn, edges, objectInfo, nodeStatusMap?.get(wn.id), tRef.current);
        g.selected = selected;
        const node: RFNode = {
          id: g.id, type: 'bio', position, selected,
          width: g.width, height: g.height, style: { width: g.width, height: g.height },
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
  }, [nodes, edges, objectInfo, nodeStatusMap, missingDependencyNodeIds]);

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

  const rfEdges = useMemo<RFEdge[]>(() => edges.map(edge => {
    const outType = outTypeByNodeOutput.get(`${edge.from.node}:${edge.from.output}`) || '';
    const stroke = edgeColorForSource(outType);
    return {
      id: edge.id,
      type: 'bio',
      source: edge.from.node,
      target: edge.to.node,
      sourceHandle: edge.from.output,
      targetHandle: edge.to.input,
      style: { stroke, strokeWidth: 2 },
      // Native arrowhead so data-flow direction is obvious, colour-matched.
      markerEnd: { type: MarkerType.ArrowClosed, color: stroke, width: 18, height: 18 },
    } satisfies RFEdge;
  }), [edges, outTypeByNodeOutput]);

  const handleNodesChange = useCallback((changes: NodeChange[]) => {
    // Alignment helper lines: when a single node is being dragged (and grid-snap
    // is off), snap its position to the nearest other-node edge/center and show
    // the guide line. Grid-snap and helper-lines are mutually exclusive.
    setHelperLines({});
    if (!snapToGrid) {
      const posChanges = changes.filter(c => c.type === 'position' && c.dragging && c.position);
      if (posChanges.length === 1) {
        const change = posChanges[0] as NodePositionChange;
        const lines = getHelperLines(change, rf.getNodes());
        if (change.position) {
          change.position.x = lines.snapPosition.x ?? change.position.x;
          change.position.y = lines.snapPosition.y ?? change.position.y;
        }
        if (lines.horizontal !== undefined || lines.vertical !== undefined) {
          setHelperLines({ horizontal: lines.horizontal, vertical: lines.vertical });
        }
      }
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
  const isValidConnection = useCallback((conn: Connection | RFEdge): boolean => {
    const { source, target, sourceHandle, targetHandle } = conn;
    if (!source || !target || source === target) return false;
    const outType = outTypeByNodeOutput.get(`${source}:${sourceHandle}`) || '';
    const inType = inTypeByNodeInput.get(`${target}:${targetHandle}`) || '';
    if (!typesCompatible(outType, inType)) return false;
    const rfN = rf.getNodes();
    const rfE = rf.getEdges();
    const targetNode = rfN.find(n => n.id === target);
    if (!targetNode) return true;
    const hasCycle = (node: RFNode, seen = new Set<string>()): boolean => {
      if (seen.has(node.id)) return false;
      seen.add(node.id);
      for (const out of getOutgoers(node, rfN, rfE)) {
        if (out.id === source) return true;
        if (hasCycle(out, seen)) return true;
      }
      return false;
    };
    return !hasCycle(targetNode);
  }, [rf, outTypeByNodeOutput, inTypeByNodeInput]);

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

  const onEdgesDelete = useCallback((deleted: RFEdge[]) => {
    const gone = new Set(deleted.map(e => e.id));
    onEdgesChange(edgesRef.current.filter(e => !gone.has(e.id)));
    onPushHistory();
  }, [onEdgesChange, onPushHistory]);

  const onNodesDelete = useCallback((deleted: RFNode[]) => {
    const gone = new Set(deleted.map(n => n.id));
    onNodesChange(nodesRef.current.filter(n => !gone.has(n.id)));
    onEdgesChange(edgesRef.current.filter(e => !gone.has(e.from.node) && !gone.has(e.to.node)));
    onPushHistory();
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

  const handleSelectionChange = useCallback((params: OnSelectionChangeParams) => {
    const idList = params.nodes.map(n => n.id);
    const ids = new Set(idList);
    selectedIdsRef.current = ids;
    setSelectedIds(idList);
    setSelectedNodeId(ids.size === 1 ? idList[0] : null);
  }, [setSelectedNodeId]);

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
  }), [onExecuteSelected, onNodesChange, onEdgesChange, onPushHistory]);

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
    const graph = nodesRef.current.map(wn => toGraphNode(wn, edgesRef.current, objectInfoRef.current, undefined, tRef.current));
    const positions = arrangeNodesLayout(graph, edgesRef.current);
    const posById = new Map(positions.map(p => [p.id, p]));
    onNodesChange(nodesRef.current.map(wn => {
      const p = posById.get(wn.id);
      return p ? { ...wn, position: [p.x, p.y] as [number, number] } : wn;
    }));
    onPushHistory();
    requestAnimationFrame(() => rf.fitView({ padding: 0.2, duration: 240 }));
  }, [onNodesChange, onPushHistory, rf]);

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

  // Native keyboard shortcuts (React Flow's useKeyPress). Cmd/Ctrl+G groups the
  // selection; Cmd/Ctrl+Shift+G ungroups the selected group(s). Rising-edge
  // guards so holding the combo fires the action only once.
  const groupKey = useKeyPress(['Meta+g', 'Control+g'], { preventDefault: true });
  const ungroupKey = useKeyPress(['Meta+Shift+g', 'Control+Shift+g'], { preventDefault: true });
  const groupKeyRef = useRef(false);
  const ungroupKeyRef = useRef(false);
  useEffect(() => {
    if (groupKey && !groupKeyRef.current) createGroupFromSelection();
    groupKeyRef.current = groupKey;
  }, [groupKey, createGroupFromSelection]);
  useEffect(() => {
    if (ungroupKey && !ungroupKeyRef.current) {
      const groups = nodesRef.current.filter(n => n.type === 'group' && selectedIdsRef.current.has(n.id));
      if (groups.length) {
        const groupIds = new Set(groups.map(g => g.id));
        onNodesChange(nodesRef.current
          .filter(n => !groupIds.has(n.id))
          .map(n => n.parentId && groupIds.has(n.parentId) ? { ...n, parentId: undefined } : n));
        onPushHistory();
      }
    }
    ungroupKeyRef.current = ungroupKey;
  }, [ungroupKey, onNodesChange, onPushHistory]);

  useImperativeHandle(ref, () => ({
    fitView, focusNode, setViewport, getViewport, getSelectedNodeIds, executeSelected, screenToFlowPosition, createGroupFromSelection, autoLayout,
  }), [fitView, focusNode, setViewport, getViewport, getSelectedNodeIds, executeSelected, screenToFlowPosition, createGroupFromSelection, autoLayout]);

  return (
    <BioNodeActionsContext.Provider value={actions}>
    <BioEdgeActionsContext.Provider value={edgeActions}>
    <MultiSelectContext.Provider value={selectedIds.length > 1}>
      <div className="workflow-canvas-host">
      <ReactFlow
        nodes={rfNodes}
        edges={rfEdges}
        nodeTypes={NODE_TYPES}
        edgeTypes={EDGE_TYPES}
        onNodesChange={handleNodesChange}
        onNodeDragStart={onNodeDragStart}
        onNodeDragStop={onNodeDragStop}
        onConnect={onConnect}
        onReconnect={onReconnect}
        isValidConnection={isValidConnection}
        onEdgesDelete={onEdgesDelete}
        onNodesDelete={onNodesDelete}
        onBeforeDelete={onBeforeDelete}
        onSelectionChange={handleSelectionChange}
        onError={onError}
        snapToGrid={snapToGrid}
        snapGrid={[gridSize, gridSize]}
        deleteKeyCode={['Backspace', 'Delete']}
        multiSelectionKeyCode={['Shift', 'Meta', 'Control']}
        connectionLineType={ConnectionLineType.Bezier}
        connectionRadius={28}
        elevateEdgesOnSelect
        elevateNodesOnSelect
        onlyRenderVisibleElements
        selectionOnDrag
        selectionMode={SelectionMode.Partial}
        panOnDrag={[1, 2]}
        panActivationKeyCode="Space"
        panOnScroll
        zoomOnDoubleClick={false}
        fitView
        fitViewOptions={{ padding: 0.2, maxZoom: 1.5 }}
        minZoom={0.1}
        maxZoom={4}
        colorMode={colorMode}
        proOptions={{ hideAttribution: true }}
      >
        {showBackground && <Background variant={bgVariant} gap={bgVariant === BackgroundVariant.Dots ? gridSize : gridSize * 2} size={1} />}
        <Controls>
          <ControlButton onClick={autoLayout} title={t('canvas.autoArrangeNodes')} aria-label={t('canvas.autoArrangeNodes')}>
            <span aria-hidden style={{ fontSize: 14, lineHeight: 1 }}>⤨</span>
          </ControlButton>
        </Controls>
        {showMinimap && (
          <MiniMap
            className="bio-minimap"
            pannable
            zoomable
            nodeColor={(n) => {
              const d = n.data as { g?: { color?: string }; color?: string } | undefined;
              return d?.g?.color ?? d?.color ?? '#64748b';
            }}
          />
        )}
        {/* Native multi-select toolbar: React Flow positions a <NodeToolbar>
            bound to several node ids above the selection's bounding box. Replaces
            the old custom SelectionToolbox. */}
        <NodeToolbar nodeId={selectedIds} isVisible={selectedIds.length > 1} position={Position.Top} className="bio-node-toolbar">
          <button type="button" title={t('canvas.group.create')} onClick={createGroupFromSelection}>▣</button>
          <button type="button" title={t('canvas.menu.run')} onClick={() => onExecuteSelected?.(selectedIds)}>▶</button>
          <button type="button" className="danger" title={t('canvas.menu.delete')} onClick={deleteSelected}>✕</button>
        </NodeToolbar>
        <HelperLines horizontal={helperLines.horizontal} vertical={helperLines.vertical} />
        {IS_DEV && <Devtools />}
        <Panel position="top-left" className="canvas-hint">{t('canvas.dragToConnect', 'Drag from a port to connect')}</Panel>
      </ReactFlow>
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
