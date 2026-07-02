import { useEffect, useRef, useCallback, useMemo, useState, forwardRef, useImperativeHandle, memo } from 'react';
import {
  ReactFlow,
  ReactFlowProvider,
  Background,
  BackgroundVariant,
  useReactFlow,
  useViewport,
  type Node as RFNode,
  type Edge as RFEdge,
  type NodeChange,
  type Connection,
  type OnSelectionChangeParams,
  type FinalConnectionState,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { useSetAtom } from 'jotai';
import { useTranslation } from 'react-i18next';
import type { Workflow, WorkflowNode, WorkflowEdge, WorkflowGroup, ObjectInfo, NodeMetadata, NodeStatus, WorkflowParameter } from '../../types';
import { edgeColorForSource, defaultsFor } from '../../utils';
import { nodeCategoryDisplayLabel } from '../../utils/nodeCategories';
import { getVisibleInputSpecs } from '../../utils/nodeInputVisibility';
import { resolveNodeOutputs } from '../../utils/nodeOutputs';
import { dragCoordinate } from '../../utils/snap';
import {
  NODE_HEADER_H,
  NODE_PIN_H,
  NODE_WIDGET_ROW_H,
  getInteractiveWidgetEntries,
  getWidgetBlockTop,
  isColorParam,
  toHexColor,
} from '../../utils/nodeLayout';
import { resolveOverlaps } from '../../utils/autoLayout';
import { useSettings } from '../../hooks/settings';
import { hasOpenOverlay } from '../../state/overlays';
import Icon from '../ui/Icon';
import { promptDialog, toast } from '../ui';
import { saveBlueprint } from '../../state/subgraphLibrary';
import { apiPost } from '../../api/client';
import { logError } from '../../state/logging';
import NodePalette from '../nodes/NodePalette';
import NodeContextMenu from '../nodes/NodeContextMenu';
import NodeEditor from '../nodes/NodeEditor';
import NodeInfoPanel from '../nodes/NodeInfoPanel';
import Minimap from './Minimap';
import SelectionToolbox from './SelectionToolbox';
import GroupContextMenu from './GroupContextMenu';
import { selectedNodeIdAtom } from '../../state/uiAtoms';
import CommentPin from '../../collab/CommentPin';
import NodeCommentPopover from '../../collab/NodeCommentPopover';
import {
  getCommentPinPosition,
  getCommentPinSize,
  getNodeCommentPopoverPosition,
  type OverlayBounds,
  type OverlayRect,
} from '../../collab/commentLayout';
import type { AwarenessState, CollabUser, Comment } from '../../collab/types';
import BioNode, { type BioNodeData } from './BioNode';
import {
  type GraphNode,
  type NodeCommentSummary,
  type WorkflowCanvasRef,
  NODE_WIDTH,
  NODE_NOTE_WIDTH,
  INLINE_PREVIEW_TOGGLE_H,
  INLINE_PREVIEW_BAND_H,
  PREVIEW_SINK_TYPES,
  nodeColor,
  calcNodeHeight,
  arrangeNodesLayout,
  createGroupFromNodes,
  exportThumbnailDataURL,
  groupContainingPoint,
} from './canvasModel';

// Re-export the model types the sub-components (NodeEditor, NodeInfoPanel,
// SelectionToolbox, Minimap, InspectorPanel) and App import from this module so
// their existing import paths keep working after the React Flow migration.
export type { GraphNode, WorkflowCanvasRef };

interface WorkflowCanvasProps {
  nodes: WorkflowNode[];
  edges: WorkflowEdge[];
  groups: WorkflowGroup[];
  objectInfo: ObjectInfo;
  workflowParameters?: WorkflowParameter[];
  onNodesChange: (nodes: WorkflowNode[]) => void;
  onEdgesChange: (edges: WorkflowEdge[]) => void;
  onGroupsChange: (groups: WorkflowGroup[]) => void;
  onPushHistory: () => void;
  onUndo: () => void;
  onRedo: () => void;
  snapToGrid: boolean;
  showMinimap: boolean;
  viewportLocked: boolean;
  linksHidden: boolean;
  onToggleMinimap: () => void;
  onToggleLinksHidden: () => void;
  nodeStatusMap?: Map<string, NodeStatus['status']>;
  nodeErrorsMap?: Map<string, string>;
  nodePreviewsMap?: Map<string, string>;
  nodeHtmlPreviewsMap?: Map<string, string>;
  missingDependencyNodeIds?: Set<string>;
  nodeCommentsMap?: Map<string, NodeCommentSummary>;
  nodeComments?: Comment[];
  collabWorkflowId?: string;
  currentCollabUser?: CollabUser;
  onAddComment?: (content: string, nodeId: string | null, parentId: string | null) => void;
  onResolveComment?: (id: string) => void;
  collabUsers?: AwarenessState[];
  onCollabCursor?: (cursor: AwarenessState['cursor']) => void;
  onCollabSelection?: (selection: AwarenessState['selection']) => void;
  onCollabNodeMove?: (nodeId: string, position: [number, number]) => void;
  onCollabDragStart?: (nodeId: string) => void;
  onCollabDragEnd?: () => void;
  onViewportChange?: (offset: { x: number; y: number }, scale: number) => void;
  onExecuteSelected?: (nodeIds: string[]) => void;
  onCreateSubgraph?: (nodeIds: string[]) => void;
  onEnterSubgraph?: (nodeId: string) => void;
  onPromoteWidgets?: (innerNodeId: string) => void;
}

const NODE_TYPES = { bio: BioNode };

function clamp(n: number, min: number, max: number) { return Math.min(max, Math.max(min, n)); }

const WorkflowCanvasInner = forwardRef<WorkflowCanvasRef, WorkflowCanvasProps>(function WorkflowCanvasInner({
  nodes, edges, groups, objectInfo,
  workflowParameters = [],
  onNodesChange, onEdgesChange, onGroupsChange, onPushHistory, onUndo, onRedo,
  snapToGrid, showMinimap, viewportLocked, linksHidden,
  onToggleMinimap, onToggleLinksHidden,
  nodeStatusMap,
  nodeErrorsMap,
  nodePreviewsMap,
  nodeHtmlPreviewsMap,
  missingDependencyNodeIds,
  nodeCommentsMap,
  nodeComments = [],
  currentCollabUser,
  onAddComment,
  onResolveComment,
  collabUsers = [],
  onCollabCursor,
  onCollabSelection,
  onCollabNodeMove,
  onCollabDragStart,
  onCollabDragEnd,
  onViewportChange,
  onExecuteSelected,
  onCreateSubgraph,
  onEnterSubgraph,
  onPromoteWidgets,
}, ref) {
  const { t } = useTranslation();
  const tRef = useRef(t);
  tRef.current = t;
  const rf = useReactFlow();
  const rfViewport = useViewport();
  const offset = useMemo(() => ({ x: rfViewport.x, y: rfViewport.y }), [rfViewport.x, rfViewport.y]);
  const scale = rfViewport.zoom;

  const setSelectedNodeId = useSetAtom(selectedNodeIdAtom);
  const hostRef = useRef<HTMLDivElement>(null);

  const { getBool, getNumber } = useSettings();
  const showGrid = getBool('bionodulo.canvas.showGrid', true);
  const gridSize = Math.min(200, Math.max(4, getNumber('bionodulo.canvas.gridSize', 20)));

  const [graphNodes, setGraphNodes] = useState<GraphNode[]>([]);
  const [canvasSize, setCanvasSize] = useState({ w: 800, h: 600 });
  const [contextMenu, setContextMenu] = useState<{ x: number; y: number; nodeId: string | null } | null>(null);
  const [palettePos, setPalettePos] = useState<{ x: number; y: number } | null>(null);
  const [pendingLinkPickup, setPendingLinkPickup] = useState<{ fromNodeId: string; fromOutputName: string; fromOutputType: string } | null>(null);
  const [editingNode, setEditingNode] = useState<string | null>(null);
  const [renamingNode, setRenamingNode] = useState<{ id: string; value: string } | null>(null);
  const [showNodeInfo, setShowNodeInfo] = useState<string | null>(null);
  const [editingZoom, setEditingZoom] = useState(false);
  const [actionFeedback, setActionFeedback] = useState<{ label: string; key: number } | null>(null);
  const actionFeedbackTimer = useRef<number | null>(null);
  const [canvasMenu, setCanvasMenu] = useState<{
    x: number; y: number; canvasX: number; canvasY: number; worldX: number; worldY: number;
  } | null>(null);
  const [nodeCommentTarget, setNodeCommentTarget] = useState<{ nodeId: string; compose: boolean } | null>(null);
  const [groupContextMenu, setGroupContextMenu] = useState<{ x: number; y: number; groupId: string } | null>(null);
  const [linkContextMenu, setLinkContextMenu] = useState<{ x: number; y: number; edgeId: string; worldX: number; worldY: number } | null>(null);
  const [hoveredNodeId, setHoveredNodeId] = useState<string | null>(null);
  const [dragging, setDragging] = useState<string | null>(null);

  const flashAction = useCallback((label: string) => {
    if (actionFeedbackTimer.current) window.clearTimeout(actionFeedbackTimer.current);
    setActionFeedback({ label, key: Date.now() });
    actionFeedbackTimer.current = window.setTimeout(() => setActionFeedback(null), 900);
  }, []);
  useEffect(() => () => {
    if (actionFeedbackTimer.current) window.clearTimeout(actionFeedbackTimer.current);
  }, []);

  // High-frequency refs so window listeners and RF callbacks read current data
  // without re-subscribing.
  const graphNodesRef = useRef(graphNodes);
  const nodesRef = useRef(nodes);
  const edgesRef = useRef(edges);
  const groupsRef = useRef(groups);
  const onNodesChangeRef = useRef(onNodesChange);
  const onEdgesChangeRef = useRef(onEdgesChange);
  const onGroupsChangeRef = useRef(onGroupsChange);
  const onPushHistoryRef = useRef(onPushHistory);
  const onUndoRef = useRef(onUndo);
  const onRedoRef = useRef(onRedo);
  const onCollabSelectionRef = useRef(onCollabSelection);
  const onExecuteSelectedRef = useRef(onExecuteSelected);
  const onCreateSubgraphRef = useRef(onCreateSubgraph);
  const onEnterSubgraphRef = useRef(onEnterSubgraph);
  const onPromoteWidgetsRef = useRef(onPromoteWidgets);
  const pendingSelectionRef = useRef<Set<string> | null>(null);
  const isDraggingRef = useRef(false);

  useEffect(() => { if (!isDraggingRef.current) graphNodesRef.current = graphNodes; }, [graphNodes]);
  useEffect(() => { nodesRef.current = nodes; }, [nodes]);
  useEffect(() => { edgesRef.current = edges; }, [edges]);
  useEffect(() => { if (!isDraggingRef.current) groupsRef.current = groups; }, [groups]);
  useEffect(() => { onNodesChangeRef.current = onNodesChange; }, [onNodesChange]);
  useEffect(() => { onEdgesChangeRef.current = onEdgesChange; }, [onEdgesChange]);
  useEffect(() => { onGroupsChangeRef.current = onGroupsChange; }, [onGroupsChange]);
  useEffect(() => { onPushHistoryRef.current = onPushHistory; }, [onPushHistory]);
  useEffect(() => { onUndoRef.current = onUndo; }, [onUndo]);
  useEffect(() => { onRedoRef.current = onRedo; }, [onRedo]);
  useEffect(() => { onCollabSelectionRef.current = onCollabSelection; }, [onCollabSelection]);
  useEffect(() => { onExecuteSelectedRef.current = onExecuteSelected; }, [onExecuteSelected]);
  useEffect(() => { onCreateSubgraphRef.current = onCreateSubgraph; }, [onCreateSubgraph]);
  useEffect(() => { onEnterSubgraphRef.current = onEnterSubgraph; }, [onEnterSubgraph]);
  useEffect(() => { onPromoteWidgetsRef.current = onPromoteWidgets; }, [onPromoteWidgets]);

  const publishCollabSelection = useCallback((selection: AwarenessState['selection']) => {
    setSelectedNodeId(selection.nodeIds[0] ?? null);
    onCollabSelectionRef.current?.(selection);
  }, [setSelectedNodeId]);

  // Broadcast viewport changes to collaborators.
  useEffect(() => {
    onViewportChange?.({ x: rfViewport.x, y: rfViewport.y }, rfViewport.zoom);
  }, [rfViewport.x, rfViewport.y, rfViewport.zoom, onViewportChange]);

  // Convert workflow nodes to graph nodes (positions, structure, connectivity)
  useEffect(() => {
    setGraphNodes(prev => {
      const map = new Map(prev.map(n => [n.id, n]));
      const pending = pendingSelectionRef.current;
      if (pending) pendingSelectionRef.current = null;
      return nodes.map(wn => {
        const existing = map.get(wn.id);
        const meta = wn.type ? (objectInfo[wn.type] || wn.node_info || null) : (wn.node_info || null);
        const collapsed = wn.ui?.collapsed ?? existing?.collapsed ?? false;
        const isNote = meta?.id === 'note';
        const isReroute = meta?.id === 'reroute';
        const visualOnly = meta?.visual_only ?? isNote;
        const inlinePreview = Boolean(meta?.inline_preview);
        const previewCollapsed = wn.ui?.previewCollapsed ?? existing?.previewCollapsed ?? false;
        const nodeWidth = isNote
          ? (wn.ui?.width ?? existing?.width ?? NODE_NOTE_WIDTH)
          : (isReroute ? 20 : (wn.ui?.width ?? existing?.width ?? NODE_WIDTH));
        let nodeHeight: number;
        if (isReroute) {
          nodeHeight = 20;
        } else if (collapsed) {
          nodeHeight = calcNodeHeight(meta, true, wn.params);
        } else {
          const minHeight = calcNodeHeight(meta, false, wn.params, isNote ? nodeWidth : undefined, previewCollapsed);
          const storedHeight = wn.ui?.height ?? existing?.height;
          nodeHeight = (storedHeight && !inlinePreview) ? Math.max(storedHeight, minHeight) : minHeight;
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
            connected: edges.some(e => e.from.node === wn.id),
          })) : [],
          params: wn.params || {},
          meta,
          color: wn.ui?.color || nodeColor(meta),
          muted: wn.ui?.muted ?? false,
          bypassed: wn.ui?.bypassed ?? false,
          selected: pending?.has(wn.id) ? true : (existing?.selected || false),
          collapsed,
          pinned: wn.ui?.pinned || false,
          shape: wn.ui?.shape || (isNote ? 'card' : 'round'),
          title: wn.ui?.title || meta?.display_name || wn.type || t('canvas.nodeFallbackTitle'),
          status: existing?.status,
          visualOnly,
          inlinePreview,
          previewCollapsed,
          showingPreview: existing?.showingPreview ?? false,
        };
      });
    });
  }, [nodes, edges, objectInfo, t]);

  // Update node statuses separately so parent re-renders don't stomp drag positions
  useEffect(() => {
    if (!nodeStatusMap) return;
    setGraphNodes(prev => {
      let changed = false;
      const next = prev.map(n => {
        const status = nodeStatusMap.get(n.id);
        if (n.status === status) return n;
        changed = true;
        return { ...n, status };
      });
      return changed ? next : prev;
    });
  }, [nodeStatusMap]);

  const inlinePreviewsOn = getBool('bionodulo.canvas.inlinePreviews', true);
  const autoArrangeOn = getBool('bionodulo.canvas.autoArrangePreviews', true);

  const livePreviewSig = useMemo(() => {
    const ids: string[] = [];
    nodePreviewsMap?.forEach((_v, k) => ids.push(k));
    nodeHtmlPreviewsMap?.forEach((_v, k) => ids.push(k));
    return ids.sort().join('|');
  }, [nodePreviewsMap, nodeHtmlPreviewsMap]);
  const baseLayoutSig = useMemo(
    () => nodes.map(n => `${n.id}:${n.position[0]},${n.position[1]}`).join('|'),
    [nodes],
  );
  const previewCollapseSig = useMemo(
    () => nodes.filter(n => n.ui?.previewCollapsed).map(n => n.id).sort().join('|'),
    [nodes],
  );

  // Run-reactive inline-preview body + anti-overlap auto-layout.
  useEffect(() => {
    setGraphNodes(prev => {
      const hasLive = (id: string) => Boolean(nodePreviewsMap?.has(id) || nodeHtmlPreviewsMap?.has(id));
      let changed = false;
      const sized = prev.map(n => {
        const isSink = PREVIEW_SINK_TYPES.has(n.type);
        const showing = inlinePreviewsOn && !isSink && !n.collapsed && !n.visualOnly && hasLive(n.id);
        const base = calcNodeHeight(n.meta, n.collapsed, n.params);
        const band = INLINE_PREVIEW_TOGGLE_H + (n.previewCollapsed ? 0 : INLINE_PREVIEW_BAND_H);
        let height = n.height;
        if (showing) height = base + band;
        else if (n.showingPreview) height = base;
        if (n.showingPreview !== showing || n.height !== height) {
          changed = true;
          return { ...n, showingPreview: showing, height };
        }
        return n;
      });

      const basePos = new Map(nodesRef.current.map(n => [n.id, n.position] as const));
      let out = sized;
      if (autoArrangeOn && !isDraggingRef.current) {
        const moves = resolveOverlaps(
          sized.map(n => {
            const bp = basePos.get(n.id);
            return { id: n.id, x: bp ? bp[0] : n.x, y: bp ? bp[1] : n.y, width: n.width, height: n.height, pinned: n.pinned };
          }),
          { gap: 22 },
        );
        out = sized.map(n => {
          const bp = basePos.get(n.id);
          const mv = moves.get(n.id);
          const nx = mv ? mv.x : (bp ? bp[0] : n.x);
          const ny = mv ? mv.y : (bp ? bp[1] : n.y);
          if (n.x !== nx || n.y !== ny) { changed = true; return { ...n, x: nx, y: ny }; }
          return n;
        });
      }
      return changed ? out : prev;
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [livePreviewSig, baseLayoutSig, previewCollapseSig, inlinePreviewsOn, autoArrangeOn]);

  const toWorld = useCallback((cx: number, cy: number) => ({
    x: (cx - offset.x) / scale,
    y: (cy - offset.y) / scale,
  }), [offset, scale]);

  const getSelectedNodeIds = useCallback(() => (
    graphNodesRef.current.filter(n => n.selected).map(n => n.id)
  ), []);

  const canvasBounds = useMemo<OverlayBounds>(() => ({
    width: Math.max(1, canvasSize.w),
    height: Math.max(1, canvasSize.h),
  }), [canvasSize.h, canvasSize.w]);

  const toScreenNodeRect = useCallback((node: GraphNode): OverlayRect => ({
    x: node.x * scale + offset.x,
    y: node.y * scale + offset.y,
    width: node.width * scale,
    height: node.height * scale,
  }), [offset.x, offset.y, scale]);

  const addNode = useCallback((meta: NodeMetadata, cx: number, cy: number): WorkflowNode => {
    const world = toWorld(cx, cy);
    const x = dragCoordinate(world.x, 0, snapToGrid, gridSize);
    const y = dragCoordinate(world.y, 0, snapToGrid, gridSize);
    const isNote = meta.id === 'note';
    const newNode: WorkflowNode = {
      id: `${meta.id}_${Date.now()}`,
      type: meta.id,
      position: [x, y],
      params: defaultsFor(meta),
      node_info: meta,
      ui: { title: meta.display_name, color: isNote ? '#f59e0b' : nodeColor(meta) },
    };
    onNodesChange([...nodes, newNode]);
    onPushHistory();
    return newNode;
  }, [nodes, onNodesChange, onPushHistory, toWorld, snapToGrid, gridSize]);

  // ---- Viewport helpers backed by the React Flow instance ----
  const animateViewport = useCallback((targetOffset: { x: number; y: number }, targetScale: number, duration = 220) => {
    rf.setViewport({ x: targetOffset.x, y: targetOffset.y, zoom: targetScale }, { duration });
  }, [rf]);

  const fitView = useCallback((onlySelected?: boolean) => {
    if (onlySelected) {
      const selected = graphNodesRef.current.filter(n => n.selected).map(n => ({ id: n.id }));
      if (selected.length === 0) return;
      rf.fitView({ nodes: selected, padding: 0.2, duration: 220 });
    } else {
      rf.fitView({ padding: 0.2, duration: 220 });
    }
  }, [rf]);

  const focusNode = useCallback((nodeId: string) => {
    const node = graphNodesRef.current.find(candidate => candidate.id === nodeId);
    if (!node) return;
    pendingSelectionRef.current = new Set([nodeId]);
    setGraphNodes(prev => prev.map(candidate => ({ ...candidate, selected: candidate.id === nodeId })));
    publishCollabSelection({ nodeIds: [nodeId], box: null });
    rf.setCenter(node.x + node.width / 2, node.y + node.height / 2, { zoom: scale, duration: 220 });
  }, [rf, publishCollabSelection, scale]);

  const setViewportFromAwareness = useCallback((viewport: { x: number; y: number; scale: number }) => {
    animateViewport({ x: viewport.x, y: viewport.y }, clamp(viewport.scale, 0.1, 5), 280);
  }, [animateViewport]);

  const animateZoom = useCallback((factor: number) => {
    const targetScale = clamp(scale * factor, 0.1, 5);
    if (Math.abs(targetScale - scale) < 1e-3) return;
    const { w, h } = { w: canvasBounds.width, h: canvasBounds.height };
    const cx = w / 2;
    const cy = h / 2;
    const worldX = (cx - offset.x) / scale;
    const worldY = (cy - offset.y) / scale;
    animateViewport({ x: cx - worldX * targetScale, y: cy - worldY * targetScale }, targetScale, 160);
  }, [animateViewport, offset, scale, canvasBounds]);

  const autoLayout = useCallback(() => {
    const COL_W = 280;
    const ROW_GAP = 40;
    const selectedIds = new Set(graphNodesRef.current.filter(n => n.selected).map(n => n.id));
    const workingSet = selectedIds.size > 0
      ? graphNodesRef.current.filter(n => selectedIds.has(n.id))
      : graphNodesRef.current.slice();
    if (workingSet.length === 0) return;

    const inSet = new Set(workingSet.map(n => n.id));
    const inEdges = new Map<string, string[]>();
    for (const edge of edgesRef.current) {
      if (!inSet.has(edge.from.node) || !inSet.has(edge.to.node)) continue;
      const list = inEdges.get(edge.to.node) ?? [];
      list.push(edge.from.node);
      inEdges.set(edge.to.node, list);
    }

    const depths = new Map<string, number>();
    const visiting = new Set<string>();
    const depthOf = (id: string): number => {
      if (depths.has(id)) return depths.get(id)!;
      if (visiting.has(id)) return 0;
      visiting.add(id);
      const parents = inEdges.get(id) ?? [];
      const depth = parents.length === 0 ? 0 : Math.max(...parents.map(depthOf)) + 1;
      visiting.delete(id);
      depths.set(id, depth);
      return depth;
    };
    for (const node of workingSet) depthOf(node.id);

    const columns = new Map<number, typeof workingSet>();
    for (const node of workingSet) {
      const d = depths.get(node.id) ?? 0;
      const list = columns.get(d) ?? [];
      list.push(node);
      columns.set(d, list);
    }

    const anchorX = Math.min(...workingSet.map(n => n.x));
    const anchorY = Math.min(...workingSet.map(n => n.y));

    const positions = new Map<string, [number, number]>();
    Array.from(columns.entries()).sort(([a], [b]) => a - b).forEach(([depth, nodesInCol]) => {
      nodesInCol.sort((a, b) => a.y - b.y || a.id.localeCompare(b.id));
      let y = anchorY;
      nodesInCol.forEach((node) => {
        positions.set(node.id, [anchorX + depth * COL_W, y]);
        y += Math.max(node.height, calcNodeHeight(node.meta, node.collapsed, node.params, node.width)) + ROW_GAP;
      });
    });

    const updated = nodesRef.current.map(wn => {
      const next = positions.get(wn.id);
      if (!next) return wn;
      return { ...wn, position: next };
    });
    onNodesChangeRef.current(updated);
    onPushHistoryRef.current();
    flashAction(t('canvas.flashAutoLayout'));
  }, [flashAction, t]);

  useImperativeHandle(ref, () => ({
    fitView,
    focusNode,
    setViewport: setViewportFromAwareness,
    getViewport: () => ({ x: rf.getViewport().x, y: rf.getViewport().y, scale: rf.getViewport().zoom }),
    getSelectedNodeIds,
    executeSelected: () => {
      const ids = getSelectedNodeIds();
      if (ids.length > 0) onExecuteSelectedRef.current?.(ids);
    },
    createSubgraphFromSelection: () => {
      const ids = getSelectedNodeIds();
      if (ids.length > 0) onCreateSubgraphRef.current?.(ids);
    },
    autoLayout,
  }), [fitView, focusNode, getSelectedNodeIds, rf, setViewportFromAwareness, autoLayout]);

  const handleContextAction = useCallback(async (action: string, nodeId: string, extra?: string) => {
    setContextMenu(null);
    if (action === 'delete') {
      onNodesChange(nodes.filter(n => n.id !== nodeId));
      onEdgesChange(edges.filter(e => e.from.node !== nodeId && e.to.node !== nodeId));
    } else if (action === 'duplicate') {
      const orig = nodes.find(n => n.id === nodeId);
      if (orig) {
        const dup = { ...orig, id: `${orig.type}_${Date.now()}`, position: [orig.position[0] + 40, orig.position[1] + 40] as [number, number] };
        onNodesChange([...nodes, dup]);
      }
    } else if (action === 'edit') {
      setEditingNode(nodeId);
    } else if (action === 'rename') {
      const node = graphNodes.find(n => n.id === nodeId);
      if (node) {
        const newTitle = await promptDialog({
          title: t('canvas.renameNodeTitle'),
          message: t('canvas.renameNodeMessage'),
          inputLabel: t('canvas.nodeNameInput'),
          defaultValue: node.title,
        });
        if (newTitle !== null && newTitle.trim() !== '') {
          const trimmed = newTitle.trim();
          setGraphNodes(prev => prev.map(n => n.id === nodeId ? { ...n, title: trimmed } : n));
          onNodesChange(nodes.map(n => n.id === nodeId ? { ...n, ui: { ...n.ui, title: trimmed } } : n));
        }
      }
    } else if (action === 'info') {
      setShowNodeInfo(nodeId);
    } else if (action === 'comment') {
      setNodeCommentTarget({ nodeId, compose: true });
    } else if (action === 'mute') {
      const newMuted = !graphNodes.find(n => n.id === nodeId)?.muted;
      setGraphNodes(prev => prev.map(n => n.id === nodeId ? { ...n, muted: newMuted } : n));
      onNodesChange(nodes.map(n => n.id === nodeId ? { ...n, ui: { ...n.ui, muted: newMuted } } : n));
    } else if (action === 'bypass') {
      const newBypassed = !graphNodes.find(n => n.id === nodeId)?.bypassed;
      setGraphNodes(prev => prev.map(n => n.id === nodeId ? { ...n, bypassed: newBypassed } : n));
      onNodesChange(nodes.map(n => n.id === nodeId ? { ...n, ui: { ...n.ui, bypassed: newBypassed } } : n));
    } else if (action === 'pin') {
      const newPinned = !graphNodes.find(n => n.id === nodeId)?.pinned;
      setGraphNodes(prev => prev.map(n => n.id === nodeId ? { ...n, pinned: newPinned } : n));
      onNodesChange(nodes.map(n => n.id === nodeId ? { ...n, ui: { ...n.ui, pinned: newPinned } } : n));
    } else if (action === 'shape' && extra) {
      const shape = (extra === 'box' || extra === 'card') ? extra : 'round';
      setGraphNodes(prev => prev.map(n => n.id === nodeId ? { ...n, shape } : n));
      onNodesChange(nodes.map(n => n.id === nodeId ? { ...n, ui: { ...n.ui, shape } } : n));
    } else if (action === 'color' && extra) {
      setGraphNodes(prev => prev.map(n => n.id === nodeId ? { ...n, color: extra } : n));
      onNodesChange(nodes.map(n => n.id === nodeId ? { ...n, ui: { ...n.ui, color: extra } } : n));
    } else if (action === 'collapse') {
      setGraphNodes(prev => prev.map(n => {
        if (n.id !== nodeId) return n;
        const newCollapsed = !n.collapsed;
        return { ...n, collapsed: newCollapsed, height: calcNodeHeight(n.meta, newCollapsed, n.params) };
      }));
      const updatedNodes = nodes.map(n => n.id === nodeId ? { ...n, ui: { ...n.ui, collapsed: !(n.ui?.collapsed ?? false) } } : n);
      onNodesChange(updatedNodes);
    } else if (action === 'group') {
      const selectedIds = graphNodes.filter(n => n.selected).map(n => n.id);
      const idsToGroup = selectedIds.length > 0 ? selectedIds : [nodeId];
      const nodesToGroup = graphNodes.filter(n => idsToGroup.includes(n.id));
      if (nodesToGroup.length > 0) {
        const newGroup = createGroupFromNodes(nodesToGroup, t('canvas.groupFallbackName'));
        onGroupsChange([...groups, newGroup]);
      }
    } else if (action === 'subgraph') {
      const selectedIds = graphNodes.filter(n => n.selected).map(n => n.id);
      onCreateSubgraphRef.current?.(selectedIds.length > 0 ? selectedIds : [nodeId]);
    } else if (action === 'saveSubgraphBlueprint') {
      const node = nodes.find(n => n.id === nodeId);
      if (!node || node.type !== 'subgraph') {
        toast.warning(t('canvas.saveSubgraphLibraryOnlySubgraph'));
      } else {
        const innerWorkflow = node.params?.workflow as Workflow | undefined;
        const inputPorts = (node.params?.input_ports as unknown[] | undefined) ?? [];
        const outputPorts = (node.params?.output_ports as unknown[] | undefined) ?? [];
        if (!innerWorkflow) {
          toast.error(t('canvas.subgraphMissingEmbeddedWorkflow'));
        } else {
          const name = node.ui?.title || node.node_info?.display_name || t('canvas.subgraphFallbackName');
          saveBlueprint({
            name: String(name),
            workflow: innerWorkflow,
            inputPorts: inputPorts as never,
            outputPorts: outputPorts as never,
          });
          toast.success(t('canvas.subgraphLibrarySaved'), { message: String(name) });
        }
      }
    } else if (action === 'promoteWidgets') {
      onPromoteWidgetsRef.current?.(nodeId);
    } else if (action === 'savePreset') {
      const node = nodes.find(n => n.id === nodeId);
      if (node) {
        const { savePreset } = await import('../../state/nodePresets');
        const defaultName = t('canvas.presetDefaultName', { name: node.ui?.title || node.type });
        const name = await promptDialog({
          title: t('canvas.savePresetTitle'),
          message: t('canvas.savePresetMessage'),
          inputLabel: t('canvas.presetNameInput'),
          defaultValue: defaultName,
        });
        if (name) {
          savePreset(node.type, name, node.params || {});
          toast.success(t('canvas.presetSaved'), { message: name });
        }
      }
    } else if (action === 'applyPreset') {
      const node = nodes.find(n => n.id === nodeId);
      if (node) {
        const { listPresetsForType } = await import('../../state/nodePresets');
        const presets = listPresetsForType(node.type);
        if (presets.length === 0) {
          toast.info(t('canvas.noPresetsForNodeType'));
        } else {
          const labels = presets.map((p, i) => `${i + 1}. ${p.name}`).join('\n');
          const choice = await promptDialog({
            title: t('canvas.applyPresetTitle'),
            message: t('canvas.applyPresetMessage', { labels }),
            inputLabel: t('canvas.presetNumberInput'),
            defaultValue: '1',
          });
          const index = Math.max(1, Math.min(presets.length, parseInt(choice || '1', 10))) - 1;
          if (!Number.isNaN(index)) {
            const preset = presets[index];
            const nextParams = { ...node.params };
            for (const [key, value] of Object.entries(preset.params)) {
              if (Object.prototype.hasOwnProperty.call(nextParams, key)) {
                nextParams[key] = value;
              }
            }
            onNodesChange(nodes.map(n => n.id === nodeId ? { ...n, params: nextParams } : n));
            toast.success(t('canvas.presetApplied'), { message: preset.name });
          }
        }
      }
    } else if (action === 'executeSelected') {
      const selectedIds = graphNodes.filter(n => n.selected).map(n => n.id);
      onExecuteSelectedRef.current?.(selectedIds.length > 0 ? selectedIds : [nodeId]);
    }
    onPushHistory();
  }, [nodes, edges, graphNodes, groups, onNodesChange, onEdgesChange, onGroupsChange, onPushHistory, t]);

  const handleNodeParamChange = useCallback((nodeId: string, key: string, value: unknown) => {
    onNodesChange(nodes.map(n =>
      n.id === nodeId ? { ...n, params: { ...n.params, [key]: value } } : n
    ));
  }, [nodes, onNodesChange]);

  const toggleInlinePreview = useCallback((nodeId: string) => {
    const next = !(nodesRef.current.find(n => n.id === nodeId)?.ui?.previewCollapsed ?? false);
    setGraphNodes(prev => prev.map(n => {
      if (n.id !== nodeId) return n;
      const base = calcNodeHeight(n.meta, n.collapsed, n.params);
      const height = base + INLINE_PREVIEW_TOGGLE_H + (next ? 0 : INLINE_PREVIEW_BAND_H);
      return { ...n, previewCollapsed: next, height };
    }));
    onNodesChangeRef.current(nodesRef.current.map(wn =>
      wn.id === nodeId ? { ...wn, ui: { ...wn.ui, previewCollapsed: next } } : wn,
    ));
    onPushHistoryRef.current();
  }, []);

  const copyParamToSelection = useCallback((sourceId: string, key: string) => {
    const source = nodesRef.current.find(n => n.id === sourceId);
    if (!source) return;
    const value = source.params?.[key];
    const selectedIds = graphNodesRef.current.filter(n => n.selected && n.id !== sourceId).map(n => n.id);
    if (selectedIds.length === 0) {
      flashAction(t('canvas.flashSelectOtherNodesFirst'));
      return;
    }
    const targets = nodesRef.current.filter(n => selectedIds.includes(n.id) && Object.prototype.hasOwnProperty.call(n.params || {}, key));
    if (targets.length === 0) {
      flashAction(t('canvas.flashNoSelectedNodeHasParam', { param: key }));
      return;
    }
    const targetIds = new Set(targets.map(n => n.id));
    onNodesChange(nodesRef.current.map(n =>
      targetIds.has(n.id) ? { ...n, params: { ...n.params, [key]: value } } : n
    ));
    onPushHistory();
    flashAction(t('canvas.flashCopiedParamToNodes', { param: key, count: targets.length }));
  }, [flashAction, onNodesChange, onPushHistory, t]);

  const handleToolboxAction = useCallback((action: string, extra?: string) => {
    const selectedId = graphNodes.find(n => n.selected)?.id;
    if (!selectedId) return;
    if (action === 'delete') {
      handleContextAction('delete', selectedId);
    } else if (action === 'duplicate') {
      handleContextAction('duplicate', selectedId);
    } else if (action === 'mute') {
      handleContextAction('mute', selectedId);
    } else if (action === 'bypass') {
      handleContextAction('bypass', selectedId);
    } else if (action === 'collapse') {
      const selectedIds = new Set(graphNodes.filter(n => n.selected).map(n => n.id));
      const anyExpanded = graphNodes.some(n => n.selected && !n.collapsed && !n.visualOnly && n.type !== 'reroute');
      const targetCollapsed = anyExpanded;
      setGraphNodes(prev => prev.map(n => {
        if (!selectedIds.has(n.id) || n.visualOnly || n.type === 'reroute') return n;
        return { ...n, collapsed: targetCollapsed, height: calcNodeHeight(n.meta, targetCollapsed, n.params) };
      }));
      const updatedNodes = nodes.map(n => {
        const isVisualOnly = n.node_info?.visual_only ?? n.type === 'note';
        if (!selectedIds.has(n.id) || isVisualOnly) return n;
        return { ...n, ui: { ...n.ui, collapsed: targetCollapsed } };
      });
      onNodesChange(updatedNodes);
      onPushHistory();
    } else if (action === 'color') {
      setGraphNodes(prev => prev.map(n => n.selected ? { ...n, color: extra || n.color } : n));
      onGroupsChange(groups.map(g => g.selected ? { ...g, color: extra || g.color } : g));
      const updatedNodes = nodes.map(wn => {
        const gn = graphNodes.find(g => g.id === wn.id);
        if (!gn || !gn.selected) return wn;
        return { ...wn, ui: { ...wn.ui, color: extra } };
      });
      onNodesChange(updatedNodes);
      onPushHistory();
    } else if (action === 'alignLeft' || action === 'alignRight' || action === 'alignTop' || action === 'alignBottom' || action === 'alignCenterH' || action === 'alignCenterV' || action === 'distributeH' || action === 'distributeV') {
      const selected = graphNodes.filter(n => n.selected);
      if (selected.length < 2) return;
      const positions = new Map<string, [number, number]>();
      if (action === 'alignLeft') {
        const minX = Math.min(...selected.map(n => n.x));
        for (const n of selected) positions.set(n.id, [minX, n.y]);
      } else if (action === 'alignRight') {
        const maxRight = Math.max(...selected.map(n => n.x + n.width));
        for (const n of selected) positions.set(n.id, [maxRight - n.width, n.y]);
      } else if (action === 'alignTop') {
        const minY = Math.min(...selected.map(n => n.y));
        for (const n of selected) positions.set(n.id, [n.x, minY]);
      } else if (action === 'alignBottom') {
        const maxBottom = Math.max(...selected.map(n => n.y + n.height));
        for (const n of selected) positions.set(n.id, [n.x, maxBottom - n.height]);
      } else if (action === 'alignCenterH') {
        const centers = selected.map(n => n.x + n.width / 2);
        const avg = centers.reduce((a, b) => a + b, 0) / centers.length;
        for (const n of selected) positions.set(n.id, [avg - n.width / 2, n.y]);
      } else if (action === 'alignCenterV') {
        const centers = selected.map(n => n.y + n.height / 2);
        const avg = centers.reduce((a, b) => a + b, 0) / centers.length;
        for (const n of selected) positions.set(n.id, [n.x, avg - n.height / 2]);
      } else if (action === 'distributeH') {
        if (selected.length < 3) return;
        const sorted = [...selected].sort((a, b) => a.x - b.x);
        const minX = sorted[0].x;
        const maxRight = sorted[sorted.length - 1].x + sorted[sorted.length - 1].width;
        const totalWidth = sorted.reduce((sum, n) => sum + n.width, 0);
        const span = maxRight - minX;
        const gap = (span - totalWidth) / Math.max(1, sorted.length - 1);
        let cursor = minX;
        for (const n of sorted) {
          positions.set(n.id, [cursor, n.y]);
          cursor += n.width + gap;
        }
      } else {
        if (selected.length < 3) return;
        const sorted = [...selected].sort((a, b) => a.y - b.y);
        const minY = sorted[0].y;
        const maxBottom = sorted[sorted.length - 1].y + sorted[sorted.length - 1].height;
        const totalHeight = sorted.reduce((sum, n) => sum + n.height, 0);
        const span = maxBottom - minY;
        const gap = (span - totalHeight) / Math.max(1, sorted.length - 1);
        let cursor = minY;
        for (const n of sorted) {
          positions.set(n.id, [n.x, cursor]);
          cursor += n.height + gap;
        }
      }
      setGraphNodes(prev => prev.map(n => {
        const pos = positions.get(n.id);
        return pos ? { ...n, x: pos[0], y: pos[1] } : n;
      }));
      const updatedNodes = nodes.map(wn => {
        const pos = positions.get(wn.id);
        return pos ? { ...wn, position: pos } : wn;
      });
      onNodesChange(updatedNodes);
      onPushHistory();
    }
  }, [graphNodes, nodes, groups, handleContextAction, onNodesChange, onGroupsChange, onPushHistory]);

  const insertRerouteOnEdge = useCallback((edgeId: string, atWorld?: { x: number; y: number }) => {
    const edge = edges.find(candidate => candidate.id === edgeId);
    if (!edge) return;
    const fromNode = graphNodes.find(candidate => candidate.id === edge.from.node);
    const toNode = graphNodes.find(candidate => candidate.id === edge.to.node);
    const rerouteMeta = objectInfo.reroute;
    if (!fromNode || !toNode || !rerouteMeta) return;

    const fromOutIndex = fromNode.outputs.findIndex(output => output.name === edge.from.output);
    const toInIndex = toNode.inputs.findIndex(input => input.name === edge.to.input);
    const fy = fromNode.collapsed
      ? fromNode.y + NODE_HEADER_H / 2
      : fromNode.y + NODE_HEADER_H + NODE_PIN_H / 2 + (fromOutIndex >= 0 ? fromOutIndex : 0) * NODE_PIN_H;
    const ty = toNode.collapsed
      ? toNode.y + NODE_HEADER_H / 2
      : toNode.y + NODE_HEADER_H + NODE_PIN_H / 2 + (toInIndex >= 0 ? toInIndex : 0) * NODE_PIN_H;
    const fx = fromNode.x + fromNode.width;
    const tx = toNode.x;
    const id = `reroute_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`;
    const px = atWorld ? Math.round(atWorld.x - 10) : Math.round((fx + tx) / 2 - 10);
    const py = atWorld ? Math.round(atWorld.y - 10) : Math.round((fy + ty) / 2 - 10);
    const parent = groupContainingPoint(groups, px + 10, py + 10);
    const rerouteNode: WorkflowNode = {
      id,
      type: 'reroute',
      position: [px, py],
      params: defaultsFor(rerouteMeta),
      node_info: rerouteMeta,
      ...(parent ? { parentId: parent.id } : {}),
      ui: { title: t('canvas.rerouteFallbackName'), color: nodeColor(rerouteMeta), shape: 'round' },
    };
    const nextEdges: WorkflowEdge[] = edges
      .filter(candidate => candidate.id !== edgeId)
      .concat([
        { id: `e_${Date.now()}_a_${Math.random().toString(36).slice(2, 6)}`, from: edge.from, to: { node: id, input: 'input' } },
        { id: `e_${Date.now()}_b_${Math.random().toString(36).slice(2, 6)}`, from: { node: id, output: 'output' }, to: edge.to },
      ]);
    onNodesChange([...nodes, rerouteNode]);
    onEdgesChange(nextEdges);
    pendingSelectionRef.current = new Set([id]);
    onPushHistory();
    setLinkContextMenu(null);
  }, [edges, graphNodes, groups, nodes, objectInfo, onEdgesChange, onNodesChange, onPushHistory, t]);

  // ---- Keyboard shortcuts (copy / paste / media paste / cut / delete /
  // select-all / undo / redo / collapse / rename / group). Ported verbatim from
  // the legacy canvas so behaviour and i18n copy are unchanged. ----
  useEffect(() => {
    const handleKeyDown = async (e: KeyboardEvent) => {
      const target = e.target as HTMLElement;
      if (target instanceof HTMLInputElement || target instanceof HTMLTextAreaElement || target.isContentEditable) return;
      if (hasOpenOverlay()) return;

      const host = hostRef.current;
      const focused = document.activeElement;
      const isCanvasFocus =
        !focused
        || focused === document.body
        || focused === host
        || (host && host.contains(focused));
      if (!isCanvasFocus) return;

      const isCtrl = e.ctrlKey || e.metaKey;
      const key = e.key.toLowerCase();

      if (isCtrl && key === 'c') {
        e.preventDefault();
        const currentGraphNodes = graphNodesRef.current;
        const currentNodes = nodesRef.current;
        const selectedIds = new Set(currentGraphNodes.filter(n => n.selected).map(n => n.id));
        if (selectedIds.size === 0) return;
        const nodesToCopy = currentNodes.filter(n => selectedIds.has(n.id));
        const edgesToCopy = edgesRef.current.filter(e => selectedIds.has(e.from.node) && selectedIds.has(e.to.node));
        const incomingEdges = edgesRef.current.filter(e => !selectedIds.has(e.from.node) && selectedIds.has(e.to.node));
        const outgoingEdges = edgesRef.current.filter(e => selectedIds.has(e.from.node) && !selectedIds.has(e.to.node));
        const payload = JSON.stringify({ nodes: nodesToCopy, edges: edgesToCopy, externalIncoming: incomingEdges, externalOutgoing: outgoingEdges });
        const text = `bionodulo_clipboard:${payload}`;
        try {
          if (navigator.clipboard && navigator.clipboard.writeText) {
            await navigator.clipboard.writeText(text);
          } else {
            const ta = document.createElement('textarea');
            ta.value = text;
            ta.style.position = 'fixed';
            ta.style.opacity = '0';
            ta.style.left = '-9999px';
            document.body.appendChild(ta);
            ta.select();
            document.execCommand('copy');
            document.body.removeChild(ta);
          }
        } catch { /* ignore */ }
        return;
      }

      if (isCtrl && key === 'v') {
        e.preventDefault();
        const includeExternal = e.shiftKey;

        try {
          if (typeof navigator.clipboard?.read === 'function') {
            const items = await navigator.clipboard.read();
            const mediaBlobs: { blob: Blob; name: string }[] = [];
            for (const item of items) {
              for (const type of item.types) {
                if (type.startsWith('image/') || type.startsWith('audio/') || type.startsWith('video/')) {
                  try {
                    const blob = await item.getType(type);
                    const ext = type.split('/')[1]?.split(';')[0] || 'bin';
                    mediaBlobs.push({ blob, name: `pasted_${Date.now()}.${ext}` });
                  } catch { /* ignore type read failure */ }
                }
              }
            }
            if (mediaBlobs.length > 0) {
              const translate = tRef.current;
              const meta = objectInfo.input_file;
              if (!meta) {
                toast.error(translate('canvas.mediaPasteFailed'), { message: translate('canvas.mediaPasteInputFileMissing') });
                return;
              }
              const rect = hostRef.current?.getBoundingClientRect();
              const cx = (rect?.width ?? 800) / 2;
              const cy = (rect?.height ?? 600) / 2;
              for (let i = 0; i < mediaBlobs.length; i++) {
                const { blob, name } = mediaBlobs[i];
                const fd = new FormData();
                fd.append('file', blob, name);
                fd.append('subdir', 'uploads');
                try {
                  const resp = await apiPost<{ path: string; original_name?: string }>('/workspace/upload', { body: fd });
                  const created = addNode(meta, cx + i * 30, cy + i * 30);
                  const path = resp.path;
                  const updated = nodesRef.current.map(n =>
                    n.id === created.id ? { ...n, params: { ...(n.params || {}), file_path: path, path } } : n,
                  );
                  onNodesChangeRef.current(updated);
                  toast.success(translate('canvas.mediaPasteImported'), { message: name });
                } catch (err) {
                  logError('workflow.canvas.uploadMedia', err);
                  const message = err instanceof Error ? err.message : translate('workspace.uploadFailed');
                  toast.error(translate('workspace.uploadFailed'), { message });
                }
              }
              onPushHistoryRef.current();
              return;
            }
          }
        } catch { /* clipboard.read() unavailable or denied — fall through */ }

        try {
          if (!navigator.clipboard || !navigator.clipboard.readText) return;
          const text = await navigator.clipboard.readText();
          if (!text) return;

          let payload: {
            nodes?: WorkflowNode[];
            edges?: WorkflowEdge[];
            externalIncoming?: WorkflowEdge[];
            externalOutgoing?: WorkflowEdge[];
          } | null = null;

          if (text.startsWith('bionodulo_clipboard:')) {
            payload = JSON.parse(text.slice('bionodulo_clipboard:'.length));
          } else if (text.trim().startsWith('{')) {
            const raw = JSON.parse(text);
            if (raw.nodes && Array.isArray(raw.nodes)) {
              payload = { nodes: raw.nodes, edges: raw.edges || [] };
            }
          } else if (text.trim().startsWith('[')) {
            const raw = JSON.parse(text);
            if (Array.isArray(raw) && raw.length > 0 && raw[0].type) {
              payload = { nodes: raw, edges: [] };
            }
          }

          if (!payload || !payload.nodes || !Array.isArray(payload.nodes)) return;

          const currentNodes = nodesRef.current;
          const currentNodeIds = new Set(currentNodes.map(n => n.id));
          const timestamp = Date.now();
          const oldToNew = new Map<string, string>();
          const pastedNodes: WorkflowNode[] = payload.nodes.map((n: WorkflowNode, i: number) => {
            const newId = `${n.id}_${timestamp}_${i}`;
            oldToNew.set(n.id, newId);
            return { ...n, id: newId, position: [n.position[0] + 40, n.position[1] + 40] as [number, number] };
          });
          const pastedEdges: WorkflowEdge[] = (payload.edges || []).map((e: WorkflowEdge, i: number) => ({
            ...e,
            id: `${e.id}_${timestamp}_${i}`,
            from: { ...e.from, node: oldToNew.get(e.from.node) || e.from.node },
            to: { ...e.to, node: oldToNew.get(e.to.node) || e.to.node },
          }));

          const externalEdges: WorkflowEdge[] = [];
          if (includeExternal) {
            const incoming = payload.externalIncoming || [];
            const outgoing = payload.externalOutgoing || [];
            incoming.forEach((edge, i) => {
              if (!currentNodeIds.has(edge.from.node)) return;
              const remappedTo = oldToNew.get(edge.to.node);
              if (!remappedTo) return;
              externalEdges.push({ ...edge, id: `${edge.id}_${timestamp}_inc${i}`, from: { ...edge.from }, to: { ...edge.to, node: remappedTo } });
            });
            outgoing.forEach((edge, i) => {
              if (!currentNodeIds.has(edge.to.node)) return;
              const remappedFrom = oldToNew.get(edge.from.node);
              if (!remappedFrom) return;
              externalEdges.push({ ...edge, id: `${edge.id}_${timestamp}_out${i}`, from: { ...edge.from, node: remappedFrom }, to: { ...edge.to } });
            });
          }

          pendingSelectionRef.current = new Set(pastedNodes.map(n => n.id));
          onNodesChangeRef.current([...currentNodes, ...pastedNodes]);
          onEdgesChangeRef.current([...edgesRef.current, ...pastedEdges, ...externalEdges]);
          onPushHistoryRef.current();
        } catch { /* ignore */ }
        return;
      }

      if (isCtrl && key === 'x') {
        e.preventDefault();
        const currentGraphNodes = graphNodesRef.current;
        const currentNodes = nodesRef.current;
        const selectedIds = new Set(currentGraphNodes.filter(n => n.selected).map(n => n.id));
        if (selectedIds.size === 0) return;
        const nodesToCopy = currentNodes.filter(n => selectedIds.has(n.id));
        const edgesToCopy = edgesRef.current.filter(e => selectedIds.has(e.from.node) && selectedIds.has(e.to.node));
        const payload = JSON.stringify({ nodes: nodesToCopy, edges: edgesToCopy });
        const text = `bionodulo_clipboard:${payload}`;
        try {
          if (navigator.clipboard && navigator.clipboard.writeText) {
            await navigator.clipboard.writeText(text);
          } else {
            const ta = document.createElement('textarea');
            ta.value = text;
            ta.style.position = 'fixed';
            ta.style.opacity = '0';
            ta.style.left = '-9999px';
            document.body.appendChild(ta);
            ta.select();
            document.execCommand('copy');
            document.body.removeChild(ta);
          }
        } catch { /* ignore */ }
        const nextNodes = currentNodes.filter(n => !selectedIds.has(n.id));
        const nextEdges = edgesRef.current.filter(e => !selectedIds.has(e.from.node) && !selectedIds.has(e.to.node));
        onNodesChangeRef.current(nextNodes);
        onEdgesChangeRef.current(nextEdges);
        onPushHistoryRef.current();
        return;
      }

      if (key === 'delete' || key === 'backspace') {
        e.preventDefault();
        const currentGraphNodes = graphNodesRef.current;
        const currentNodes = nodesRef.current;
        const selectedIds = new Set(currentGraphNodes.filter(n => n.selected).map(n => n.id));
        if (selectedIds.size === 0) return;
        const nextNodes = currentNodes.filter(n => !selectedIds.has(n.id));
        const nextEdges = edgesRef.current.filter(e => !selectedIds.has(e.from.node) && !selectedIds.has(e.to.node));
        onNodesChangeRef.current(nextNodes);
        onEdgesChangeRef.current(nextEdges);
        onPushHistoryRef.current();
        return;
      }

      if (isCtrl && key === 'a') {
        e.preventDefault();
        setGraphNodes(prev => prev.map(n => ({ ...n, selected: true })));
        return;
      }

      if (isCtrl && key === 'z' && !e.shiftKey) {
        e.preventDefault();
        onUndoRef.current();
        flashAction(tRef.current('canvas.flashUndo'));
        return;
      }

      if ((isCtrl && key === 'y') || (isCtrl && key === 'z' && e.shiftKey)) {
        e.preventDefault();
        onRedoRef.current();
        flashAction(tRef.current('canvas.flashRedo'));
        return;
      }

      if (e.altKey && key === 'c') {
        e.preventDefault();
        const currentGraphNodes = graphNodesRef.current;
        const currentNodes = nodesRef.current;
        const selectedIds = currentGraphNodes.filter(n => n.selected).map(n => n.id);
        if (selectedIds.length === 0) return;
        const idsSet = new Set(selectedIds);
        const nextGraphNodes = currentGraphNodes.map(n => {
          if (!idsSet.has(n.id)) return n;
          const newCollapsed = !n.collapsed;
          return { ...n, collapsed: newCollapsed, height: calcNodeHeight(n.meta, newCollapsed, n.params) };
        });
        const nextNodes = currentNodes.map(wn => {
          if (!idsSet.has(wn.id)) return wn;
          return { ...wn, ui: { ...wn.ui, collapsed: !(wn.ui?.collapsed ?? false) } };
        });
        setGraphNodes(nextGraphNodes);
        onNodesChangeRef.current(nextNodes);
        onPushHistoryRef.current();
      }

      if (e.key === 'F2') {
        const selected = graphNodesRef.current.filter(n => n.selected);
        if (selected.length !== 1) return;
        const targetNode = selected[0];
        if (targetNode.type === 'reroute') return;
        e.preventDefault();
        setRenamingNode({ id: targetNode.id, value: targetNode.title || '' });
        return;
      }

      if (isCtrl && key === 'g') {
        e.preventDefault();
        const currentGraphNodes = graphNodesRef.current;
        const currentGroups = groupsRef.current;
        const selected = currentGraphNodes.filter(n => n.selected);
        if (selected.length > 0) {
          const newGroup = createGroupFromNodes(selected, tRef.current('canvas.groupFallbackName'));
          onGroupsChangeRef.current([...currentGroups, newGroup]);
          onPushHistoryRef.current();
        }
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [addNode, flashAction, objectInfo]);

  // Track host size for overlay clamping / comment layout.
  useEffect(() => {
    const host = hostRef.current;
    if (!host) return;
    const measure = () => {
      const next = { w: host.clientWidth, h: host.clientHeight };
      setCanvasSize(prev => (prev.w === next.w && prev.h === next.h ? prev : next));
    };
    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(host);
    window.addEventListener('resize', measure);
    return () => {
      observer.disconnect();
      window.removeEventListener('resize', measure);
    };
  }, []);

  // ---- React Flow node / edge derivation ----
  const rfNodes = useMemo<RFNode<BioNodeData>[]>(() => graphNodes.map(g => ({
    id: g.id,
    type: 'bio',
    position: { x: g.x, y: g.y },
    selected: g.selected,
    draggable: !viewportLocked,
    selectable: !viewportLocked,
    width: g.width,
    height: g.height,
    style: { width: g.width, height: g.height },
    data: {
      g,
      categoryLabel: nodeCategoryDisplayLabel(g.category, t, t('nodeLibrary.otherCategory')),
      missingDependency: missingDependencyNodeIds?.has(g.id) ?? false,
      running: g.status === 'running',
    },
  })), [graphNodes, viewportLocked, missingDependencyNodeIds, t]);

  const rfEdges = useMemo<RFEdge[]>(() => {
    if (linksHidden) return [];
    return edges.map(edge => {
      const fromNode = graphNodes.find(n => n.id === edge.from.node);
      const outType = fromNode?.outputs.find(o => o.name === edge.from.output)?.type || '';
      const stroke = edgeColorForSource(outType);
      return {
        id: edge.id,
        source: edge.from.node,
        target: edge.to.node,
        sourceHandle: edge.from.output,
        targetHandle: edge.to.input,
        style: { stroke, strokeWidth: 2 },
      } satisfies RFEdge;
    });
  }, [edges, graphNodes, linksHidden]);

  // Live position updates while dragging so overlays (widgets / previews /
  // errors / comments) follow the node; commit + snap happen on drag stop.
  const onRfNodesChange = useCallback((changes: NodeChange[]) => {
    let posChanged = false;
    for (const change of changes) {
      if (change.type === 'position' && change.position) posChanged = true;
    }
    if (!posChanged) return;
    setGraphNodes(prev => {
      const map = new Map(prev.map(n => [n.id, n]));
      for (const change of changes) {
        if (change.type === 'position' && change.position) {
          const n = map.get(change.id);
          if (n) map.set(change.id, { ...n, x: change.position.x, y: change.position.y });
        }
      }
      return Array.from(map.values());
    });
  }, []);

  const handleSelectionChange = useCallback((params: OnSelectionChangeParams) => {
    const ids = new Set(params.nodes.map(n => n.id));
    setGraphNodes(prev => {
      let changed = false;
      const next = prev.map(n => {
        const sel = ids.has(n.id);
        if (n.selected === sel) return n;
        changed = true;
        return { ...n, selected: sel };
      });
      return changed ? next : prev;
    });
    publishCollabSelection({ nodeIds: Array.from(ids), box: null });
  }, [publishCollabSelection]);

  const onNodeDragStart = useCallback((_e: MouseEvent | TouchEvent, node: RFNode) => {
    isDraggingRef.current = true;
    setDragging(node.id);
    onCollabDragStart?.(node.id);
  }, [onCollabDragStart]);

  const onNodeDragStop = useCallback(() => {
    isDraggingRef.current = false;
    setDragging(null);
    // Commit current graph positions (already snapped by React Flow) to the
    // workflow, honouring snap-to-grid, and push a single history entry.
    const current = graphNodesRef.current;
    const updated = nodesRef.current.map(wn => {
      const gn = current.find(n => n.id === wn.id);
      if (!gn) return wn;
      const x = dragCoordinate(gn.x, 0, snapToGrid, gridSize);
      const y = dragCoordinate(gn.y, 0, snapToGrid, gridSize);
      if (wn.position[0] === x && wn.position[1] === y) return wn;
      onCollabNodeMove?.(wn.id, [x, y]);
      return { ...wn, position: [x, y] as [number, number] };
    });
    onNodesChange(updated);
    onPushHistory();
    onCollabDragEnd?.();
  }, [onNodesChange, onPushHistory, snapToGrid, gridSize, onCollabNodeMove, onCollabDragEnd]);

  const onConnect = useCallback((connection: Connection) => {
    if (!connection.source || !connection.target || !connection.sourceHandle || !connection.targetHandle) return;
    if (connection.source === connection.target) return;
    const newEdge: WorkflowEdge = {
      id: `e_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`,
      from: { node: connection.source, output: connection.sourceHandle },
      to: { node: connection.target, input: connection.targetHandle },
    };
    // Single connection per input: drop any existing edge into the same slot.
    const filtered = edges.filter(e => !(e.to.node === connection.target && e.to.input === connection.targetHandle));
    onEdgesChange([...filtered, newEdge]);
    onPushHistory();
  }, [edges, onEdgesChange, onPushHistory]);

  // Drop a link on empty canvas: open the palette filtered to the source type
  // and remember the pickup so the chosen node auto-connects.
  const onConnectEnd = useCallback((event: MouseEvent | TouchEvent, connectionState: FinalConnectionState) => {
    if (connectionState.isValid) return;
    const fromHandle = connectionState.fromHandle;
    const fromNode = connectionState.fromNode;
    if (!fromHandle || !fromNode || fromHandle.type !== 'source') return;
    const gn = graphNodesRef.current.find(n => n.id === fromNode.id);
    const outputName = fromHandle.id || '';
    const outputType = gn?.outputs.find(o => o.name === outputName)?.type || '';
    const host = hostRef.current?.getBoundingClientRect();
    const clientX = 'changedTouches' in event ? event.changedTouches[0]?.clientX ?? 0 : event.clientX;
    const clientY = 'changedTouches' in event ? event.changedTouches[0]?.clientY ?? 0 : event.clientY;
    setPendingLinkPickup({ fromNodeId: fromNode.id, fromOutputName: outputName, fromOutputType: outputType });
    setPalettePos({ x: clientX - (host?.left ?? 0), y: clientY - (host?.top ?? 0) });
  }, []);

  const onNodeContextMenu = useCallback((event: React.MouseEvent, node: RFNode) => {
    event.preventDefault();
    const host = hostRef.current?.getBoundingClientRect();
    setContextMenu({ x: event.clientX - (host?.left ?? 0), y: event.clientY - (host?.top ?? 0), nodeId: node.id });
  }, []);

  const onNodeDoubleClick = useCallback((event: React.MouseEvent, node: RFNode) => {
    const gn = graphNodesRef.current.find(n => n.id === node.id);
    if (gn?.type === 'reroute') return;
    if (event.altKey && gn) {
      setRenamingNode({ id: gn.id, value: gn.title || '' });
      return;
    }
    if (gn?.type === 'subgraph') {
      onEnterSubgraphRef.current?.(node.id);
      return;
    }
    setEditingNode(node.id);
  }, []);

  const onPaneContextMenu = useCallback((event: MouseEvent | React.MouseEvent) => {
    event.preventDefault();
    const host = hostRef.current?.getBoundingClientRect();
    const canvasX = ('clientX' in event ? event.clientX : 0) - (host?.left ?? 0);
    const canvasY = ('clientY' in event ? event.clientY : 0) - (host?.top ?? 0);
    const world = toWorld(canvasX, canvasY);
    setCanvasMenu({ x: canvasX, y: canvasY, canvasX, canvasY, worldX: world.x, worldY: world.y });
  }, [toWorld]);

  const onEdgeContextMenu = useCallback((event: React.MouseEvent, edge: RFEdge) => {
    event.preventDefault();
    const host = hostRef.current?.getBoundingClientRect();
    const canvasX = event.clientX - (host?.left ?? 0);
    const canvasY = event.clientY - (host?.top ?? 0);
    const world = toWorld(canvasX, canvasY);
    setLinkContextMenu({ x: canvasX, y: canvasY, edgeId: edge.id, worldX: world.x, worldY: world.y });
  }, [toWorld]);

  const closeMenus = useCallback(() => {
    setContextMenu(null);
    setCanvasMenu(null);
    setGroupContextMenu(null);
    setLinkContextMenu(null);
    setPalettePos(null);
    setPendingLinkPickup(null);
  }, []);

  const onPaneMouseMove = useCallback((event: React.MouseEvent) => {
    if (!onCollabCursor) return;
    const host = hostRef.current?.getBoundingClientRect();
    const cx = event.clientX - (host?.left ?? 0);
    const cy = event.clientY - (host?.top ?? 0);
    const world = toWorld(cx, cy);
    onCollabCursor({ x: cx, y: cy, worldX: world.x, worldY: world.y, visible: true });
  }, [onCollabCursor, toWorld]);

  return (
    <div
      ref={hostRef}
      className="workflow-canvas-host"
      style={{ position: 'relative', overflow: 'hidden', width: '100%', height: '100%' }}
      onMouseMove={onPaneMouseMove}
      onMouseLeave={() => onCollabCursor?.(null)}
    >
      <ReactFlow
        nodes={rfNodes}
        edges={rfEdges}
        nodeTypes={NODE_TYPES}
        onNodesChange={onRfNodesChange}
        onConnect={onConnect}
        onConnectEnd={onConnectEnd}
        onSelectionChange={handleSelectionChange}
        onNodeDragStart={onNodeDragStart}
        onNodeDragStop={onNodeDragStop}
        onNodeContextMenu={onNodeContextMenu}
        onNodeDoubleClick={onNodeDoubleClick}
        onNodeMouseEnter={(_e, node) => setHoveredNodeId(node.id)}
        onNodeMouseLeave={() => setHoveredNodeId(null)}
        onEdgeContextMenu={onEdgeContextMenu}
        onPaneContextMenu={onPaneContextMenu}
        onPaneClick={closeMenus}
        onMoveStart={closeMenus}
        snapToGrid={snapToGrid}
        snapGrid={[gridSize, gridSize]}
        deleteKeyCode={null}
        multiSelectionKeyCode="Shift"
        selectionOnDrag={!viewportLocked}
        panOnDrag={viewportLocked ? false : [1, 2]}
        panOnScroll={false}
        zoomOnScroll={!viewportLocked}
        zoomOnDoubleClick={false}
        nodesDraggable={!viewportLocked}
        nodesConnectable={!viewportLocked}
        elementsSelectable={!viewportLocked}
        minZoom={0.1}
        maxZoom={5}
        proOptions={{ hideAttribution: true }}
        defaultViewport={{ x: 0, y: 0, zoom: 1 }}
      >
        {showGrid && <Background variant={BackgroundVariant.Dots} gap={gridSize} size={1} />}
      </ReactFlow>

      {actionFeedback && (
        <div key={actionFeedback.key} className="canvas-action-feedback" role="status" aria-live="polite">
          {actionFeedback.label}
        </div>
      )}

      {collabUsers.filter(user => user.cursor?.visible).map(user => {
        const cursor = user.cursor!;
        const hasWorld = Number.isFinite(cursor.worldX) && Number.isFinite(cursor.worldY);
        const x = hasWorld ? cursor.worldX! * scale + offset.x : cursor.x;
        const y = hasWorld ? cursor.worldY! * scale + offset.y : cursor.y;
        return (
          <div
            key={`cursor-${user.user.sessionId || user.user.id}`}
            style={{ position: 'absolute', left: x, top: y, pointerEvents: 'none', zIndex: 102, transform: 'translate(-50%, -50%)' }}
          >
            <div style={{ width: 8, height: 8, borderRadius: '50%', backgroundColor: user.user.color, boxShadow: `0 0 4px ${user.user.color}` }} />
            <span style={{ position: 'absolute', left: 10, top: -4, fontSize: 11, color: user.user.color, background: 'rgba(0,0,0,0.7)', padding: '1px 4px', borderRadius: 3, whiteSpace: 'nowrap' }}>
              {user.user.name}
            </span>
          </div>
        );
      })}

      {/* Image preview DOM overlays. */}
      {nodePreviewsMap && graphNodes.filter(n => {
        if (!nodePreviewsMap.has(n.id) || n.collapsed) return false;
        const isSink = PREVIEW_SINK_TYPES.has(n.type);
        return isSink || (n.showingPreview && !n.previewCollapsed);
      }).map(node => {
        const previewUrl = nodePreviewsMap.get(node.id)!;
        const isSink = PREVIEW_SINK_TYPES.has(node.type);
        const ioHeight = Math.max(node.inputs.length, node.outputs.length, 1) * NODE_PIN_H;
        const pad = 4 * scale;
        const left = node.x * scale + offset.x + pad;
        const top = isSink
          ? node.y * scale + offset.y + (NODE_HEADER_H + ioHeight + 4) * scale
          : node.y * scale + offset.y + (node.height - INLINE_PREVIEW_BAND_H) * scale;
        const width = (node.width - 8) * scale;
        const height = isSink
          ? (node.height - NODE_HEADER_H - ioHeight - 8) * scale
          : INLINE_PREVIEW_BAND_H * scale;
        if (width <= 0 || height <= 0) return null;
        return (
          <div
            key={node.id}
            style={{ position: 'absolute', left, top, width, height, zIndex: 5, pointerEvents: 'none', borderRadius: Math.max(2, 4 * scale), overflow: 'hidden', background: 'var(--surface)' }}
          >
            <img
              src={previewUrl}
              alt={t('common.preview')}
              style={{ width: '100%', height: '100%', objectFit: 'contain', display: 'block' }}
              onError={e => { (e.target as HTMLImageElement).style.display = 'none'; }}
            />
          </div>
        );
      })}

      {/* HTML preview DOM overlays. */}
      {nodeHtmlPreviewsMap && graphNodes.filter(n => {
        if (!nodeHtmlPreviewsMap.has(n.id) || n.collapsed) return false;
        const isSink = PREVIEW_SINK_TYPES.has(n.type);
        return isSink || (n.showingPreview && !n.previewCollapsed);
      }).map(node => {
        const previewUrl = nodeHtmlPreviewsMap.get(node.id)!;
        const isSink = PREVIEW_SINK_TYPES.has(node.type);
        const ioHeight = Math.max(node.inputs.length, node.outputs.length, 1) * NODE_PIN_H;
        const pad = 4 * scale;
        const left = node.x * scale + offset.x + pad;
        const top = isSink
          ? node.y * scale + offset.y + (NODE_HEADER_H + ioHeight + 4) * scale
          : node.y * scale + offset.y + (node.height - INLINE_PREVIEW_BAND_H) * scale;
        const width = (node.width - 8) * scale;
        const height = isSink
          ? (node.height - NODE_HEADER_H - ioHeight - 8) * scale
          : INLINE_PREVIEW_BAND_H * scale;
        if (width <= 0 || height <= 0) return null;
        return (
          <div
            key={`html-${node.id}`}
            style={{ position: 'absolute', left, top, width, height, zIndex: 5, borderRadius: Math.max(2, 4 * scale), overflow: 'hidden', background: '#ffffff' }}
          >
            <iframe
              src={previewUrl}
              title={t('canvas.htmlPreviewTitle', { id: node.id })}
              sandbox="allow-scripts"
              referrerPolicy="no-referrer"
              loading="lazy"
              style={{ width: '100%', height: '100%', border: 'none' }}
            />
          </div>
        );
      })}

      {/* Inline-preview collapse toggles on producer nodes. */}
      {graphNodes.filter(n => n.showingPreview).map(node => {
        const pad = 4 * scale;
        const bandH = node.previewCollapsed ? 0 : INLINE_PREVIEW_BAND_H;
        const left = node.x * scale + offset.x + pad;
        const top = node.y * scale + offset.y + (node.height - bandH - INLINE_PREVIEW_TOGGLE_H) * scale;
        const width = (node.width - 8) * scale;
        const height = INLINE_PREVIEW_TOGGLE_H * scale;
        if (width <= 0) return null;
        return (
          <div
            key={`pvtoggle-${node.id}`}
            className="node-inline-preview-toggle"
            onMouseDown={e => { e.stopPropagation(); }}
            onClick={e => { e.stopPropagation(); toggleInlinePreview(node.id); }}
            title={node.previewCollapsed ? t('canvas.showPreview', { defaultValue: 'Show preview' }) : t('canvas.hidePreview', { defaultValue: 'Hide preview' })}
            style={{ position: 'absolute', left, top, width, height, zIndex: 6, fontSize: Math.max(8, 10 * scale) }}
          >
            <span>{node.previewCollapsed ? '▸' : '▾'}</span>
            <span>{t('canvas.previewLabel', { defaultValue: 'Preview' })}</span>
          </div>
        );
      })}

      {/* Full DOM widget overlays for node controls, clipped to each node. */}
      {graphNodes.filter(node => (
        !node.collapsed && !node.visualOnly && node.type !== 'reroute'
      )).map(node => {
        const widgetEntries = getInteractiveWidgetEntries(node.meta, node.params);
        if (widgetEntries.length === 0) return null;
        const rect = toScreenNodeRect(node);
        const widgetTop = getWidgetBlockTop(node.inputs.length, node.outputs.length);
        const layoutWidth = node.width - 16;
        const isThisDragging = dragging === node.id || (dragging !== null && node.selected);
        const widgetZ = isThisDragging ? 1 : 12;
        const widgetPointer: 'auto' | 'none' = dragging !== null ? 'none' : 'auto';
        const widgetOpacity = isThisDragging ? 0.35 : 1;

        return (
          <div
            key={`widgets-${node.id}`}
            className="node-dom-widget-layer"
            style={{
              position: 'absolute',
              left: rect.x,
              top: rect.y,
              width: node.width,
              height: node.height,
              zIndex: widgetZ,
              transform: `scale(${scale})`,
              transformOrigin: 'top left',
              overflow: 'hidden',
              pointerEvents: 'none',
              opacity: widgetOpacity,
            }}
          >
            <div style={{ position: 'absolute', left: 8, top: widgetTop, width: layoutWidth, pointerEvents: 'none' }}>
              {widgetEntries.map(({ key, spec: rawSpec }) => {
                const spec = rawSpec as Record<string, unknown> & { type?: string; label?: string; options?: string[]; min?: number; max?: number; step?: number; display?: string; forceInput?: boolean; default?: unknown; tooltip?: string; description?: string };
                const value = node.params[key] ?? spec.default ?? '';
                const common = { height: NODE_WIDGET_ROW_H, pointerEvents: widgetPointer };
                const commit = (nextValue: unknown, push = true) => {
                  handleNodeParamChange(node.id, key, nextValue);
                  if (push) onPushHistory();
                };
                const onWidgetContextMenu = (event: React.MouseEvent) => {
                  event.preventDefault();
                  event.stopPropagation();
                  copyParamToSelection(node.id, key);
                };
                const tooltipText = (spec?.tooltip || spec?.description || '').toString().trim();
                const copyWidgetValueHint = t('canvas.copyWidgetValueHint');
                const labelTitle = tooltipText
                  ? t('canvas.widgetTooltipWithCopyHint', { tooltip: tooltipText, hint: copyWidgetValueHint })
                  : copyWidgetValueHint;
                const labelProps = { style: common, onContextMenu: onWidgetContextMenu, title: labelTitle };
                if (spec?.type === 'BOOLEAN') {
                  return (
                    <label key={`${node.id}-${key}`} className="node-dom-widget node-dom-widget-boolean" {...labelProps}>
                      <span>{spec.label || key}</span>
                      <input type="checkbox" checked={Boolean(value)} onChange={event => commit(event.target.checked)} />
                    </label>
                  );
                }
                if (spec?.options?.length) {
                  return (
                    <label key={`${node.id}-${key}`} className="node-dom-widget" {...labelProps}>
                      <span>{spec.label || key}</span>
                      <select value={String(value)} onChange={event => commit(event.target.value)}>
                        {spec.options.map((option: string) => <option key={option} value={option}>{option}</option>)}
                      </select>
                    </label>
                  );
                }
                if ((spec?.type === 'INT' || spec?.type === 'FLOAT') && spec?.display === 'slider') {
                  const min = Number(spec.min ?? 0);
                  const max = Number(spec.max ?? 100);
                  const step = Number(spec.step ?? (spec.type === 'FLOAT' ? 0.01 : 1));
                  return (
                    <label key={`${node.id}-${key}`} className="node-dom-widget node-dom-widget-slider" {...labelProps}>
                      <span>{spec.label || key}</span>
                      <input
                        type="range"
                        min={min}
                        max={max}
                        step={step}
                        value={Number(value)}
                        onChange={event => handleNodeParamChange(node.id, key, spec.type === 'INT' ? parseInt(event.target.value, 10) : parseFloat(event.target.value))}
                        onMouseUp={() => onPushHistory()}
                      />
                      <output>{String(value)}</output>
                    </label>
                  );
                }
                if (spec?.type === 'INT' || spec?.type === 'FLOAT') {
                  return (
                    <label key={`${node.id}-${key}`} className="node-dom-widget" {...labelProps}>
                      <span>{spec.label || key}</span>
                      <input
                        type="number"
                        value={Number(value)}
                        min={spec.min}
                        max={spec.max}
                        step={spec.step ?? (spec.type === 'FLOAT' ? 0.01 : 1)}
                        onChange={event => handleNodeParamChange(node.id, key, spec.type === 'INT' ? parseInt(event.target.value, 10) : parseFloat(event.target.value))}
                        onBlur={() => onPushHistory()}
                      />
                    </label>
                  );
                }
                if (isColorParam(key, spec)) {
                  return (
                    <label key={`${node.id}-${key}`} className="node-dom-widget node-dom-widget-color" {...labelProps}>
                      <span>{spec.label || key}</span>
                      <span className="node-dom-color-controls">
                        <input type="color" value={toHexColor(value)} onChange={event => commit(event.target.value, false)} onBlur={() => onPushHistory()} />
                        <input type="text" value={String(value)} spellCheck={false} onChange={event => commit(event.target.value, false)} onBlur={() => onPushHistory()} />
                      </span>
                    </label>
                  );
                }
                if (spec?.type === 'STRING' && !spec?.forceInput) {
                  return (
                    <label key={`${node.id}-${key}`} className="node-dom-widget" {...labelProps}>
                      <span>{spec.label || key}</span>
                      <input type="text" value={String(value)} onChange={event => handleNodeParamChange(node.id, key, event.target.value)} onBlur={() => onPushHistory()} />
                    </label>
                  );
                }
                return null;
              }).filter(Boolean)}
            </div>
          </div>
        );
      })}

      {/* Per-node error overlays. */}
      {nodeErrorsMap && nodeErrorsMap.size > 0 && graphNodes
        .filter(node => nodeErrorsMap.has(node.id))
        .map(node => {
          const message = nodeErrorsMap.get(node.id)!;
          const rect = toScreenNodeRect(node);
          return (
            <div key={`error-${node.id}`} className="node-error-overlay" style={{ left: rect.x + rect.width - 14, top: rect.y - 6 }}>
              <button
                type="button"
                className="node-error-badge"
                title={message}
                aria-label={t('canvas.nodeErrorAria', { message: message.slice(0, 80) })}
              >
                !
              </button>
              <div className="node-error-popover">
                <div className="node-error-popover-title">{t('canvas.nodeErrorTitle')}</div>
                <pre className="node-error-popover-message">{message}</pre>
                <div className="node-error-popover-hint">{t('canvas.nodeErrorDismissHint')}</div>
              </div>
            </div>
          );
        })}

      {nodeCommentsMap && graphNodes.filter(node => nodeCommentsMap.has(node.id)).map(node => {
        const summary = nodeCommentsMap.get(node.id)!;
        const point = getCommentPinPosition(toScreenNodeRect(node), canvasBounds, summary.count);
        return (
          <CommentPin
            key={`comment-${node.id}`}
            commentCount={summary.count}
            hasUnresolved={summary.unresolved}
            x={point.x}
            y={point.y}
            onClick={() => setNodeCommentTarget({ nodeId: node.id, compose: false })}
          />
        );
      })}
      {nodeCommentTarget && currentCollabUser && onAddComment && onResolveComment && (() => {
        const node = graphNodes.find(candidate => candidate.id === nodeCommentTarget.nodeId);
        if (!node) return null;
        const nodeRect = toScreenNodeRect(node);
        const summary = nodeCommentsMap?.get(node.id);
        const pinSize = summary ? getCommentPinSize(summary.count) : undefined;
        const pinPoint = summary ? getCommentPinPosition(nodeRect, canvasBounds, summary.count) : undefined;
        const point = getNodeCommentPopoverPosition(nodeRect, canvasBounds, pinPoint, pinSize);
        return (
          <NodeCommentPopover
            nodeId={node.id}
            currentUser={currentCollabUser}
            comments={nodeComments}
            x={point.x}
            y={point.y}
            compose={nodeCommentTarget.compose}
            onAddComment={onAddComment}
            onResolveComment={onResolveComment}
            onClose={() => setNodeCommentTarget(null)}
          />
        );
      })()}

      {hoveredNodeId && !dragging && (() => {
        const node = graphNodes.find(candidate => candidate.id === hoveredNodeId);
        if (!node || !node.meta || node.type === 'reroute') return null;
        const rect = toScreenNodeRect(node);
        const left = Math.min(canvasBounds.width - 292, Math.max(12, rect.x + rect.width + 12));
        const top = Math.min(canvasBounds.height - 180, Math.max(12, rect.y));
        return (
          <div className="node-hover-card" style={{ left, top }}>
            <div className="node-hover-card-title">
              <span className="node-hover-card-swatch" style={{ background: node.color }} />
              <strong>{node.title}</strong>
            </div>
            <div className="node-hover-card-meta">{nodeCategoryDisplayLabel(node.category, t, t('nodeLibrary.otherCategory'))}</div>
            {node.meta.description && <p>{node.meta.description}</p>}
            <div className="node-hover-card-grid">
              <span>{t('canvas.hoverInputs')}</span><strong>{node.inputs.length}</strong>
              <span>{t('canvas.hoverOutputs')}</span><strong>{node.outputs.length}</strong>
              {node.meta.version && <><span>{t('canvas.hoverVersion')}</span><strong>{node.meta.version}</strong></>}
            </div>
          </div>
        );
      })()}

      <SelectionToolbox
        graphNodes={graphNodes}
        groups={groups}
        offset={offset}
        scale={scale}
        isDragging={!!dragging}
        onAction={handleToolboxAction}
        hostRef={hostRef}
      />

      {/* Zoom controls */}
      <div className="canvas-controls">
        <button className="btn btn-icon btn-sm" onClick={() => fitView()} title={t('canvas.fitToView')} aria-label={t('canvas.fitToView')}><Icon name="maximize" size={14} /></button>
        <button className="btn btn-icon btn-sm" onClick={() => fitView(true)} title={t('canvas.fitSelection')} aria-label={t('canvas.fitSelection')}><Icon name="target" size={14} /></button>
        <button className="btn btn-icon btn-sm" onClick={() => animateZoom(1.2)} title={t('canvas.zoomIn')} aria-label={t('canvas.zoomIn')}><Icon name="plus" size={14} /></button>
        {editingZoom ? (
          <input
            type="text"
            autoFocus
            defaultValue={Math.round(scale * 100)}
            onBlur={(e) => {
              const val = parseInt(e.target.value, 10);
              if (!isNaN(val)) animateViewport(offset, clamp(val / 100, 0.1, 5), 0);
              setEditingZoom(false);
            }}
            onKeyDown={(e) => {
              if (e.key === 'Enter') {
                const val = parseInt((e.target as HTMLInputElement).value, 10);
                if (!isNaN(val)) animateViewport(offset, clamp(val / 100, 0.1, 5), 0);
                setEditingZoom(false);
              } else if (e.key === 'Escape') {
                setEditingZoom(false);
              }
            }}
            style={{ width: 36, fontSize: 11, textAlign: 'center', background: 'transparent', border: '1px solid var(--border)', borderRadius: 4, color: 'var(--text)', padding: '1px 2px' }}
          />
        ) : (
          <span
            onClick={() => setEditingZoom(true)}
            style={{ fontSize: 11, color: 'var(--muted)', minWidth: 40, textAlign: 'center', cursor: 'text', userSelect: 'none' }}
          >{Math.round(scale * 100)}%</span>
        )}
        <button className="btn btn-icon btn-sm" onClick={() => animateZoom(1 / 1.2)} title={t('canvas.zoomOut')} aria-label={t('canvas.zoomOut')}><Icon name="minus" size={14} /></button>
        <div style={{ width: 1, height: 20, background: 'var(--border)', margin: '0 4px' }} />
        <button className={`btn btn-icon btn-sm ${showMinimap ? 'active' : ''}`} onClick={onToggleMinimap} title={t('canvas.toggleMinimap')}><Icon name="map" size={14} /></button>
        <button className={`btn btn-icon btn-sm ${!linksHidden ? 'active' : ''}`} onClick={onToggleLinksHidden} title={t('canvas.toggleLinks')}><Icon name="link" size={14} /></button>
        <div style={{ width: 1, height: 20, background: 'var(--border)', margin: '0 4px' }} />
        <button className="btn btn-icon btn-sm" onClick={() => {
          const layout = arrangeNodesLayout(graphNodes, edges);
          setGraphNodes(prev => prev.map(n => {
            const pos = layout.find(l => l.id === n.id);
            return pos ? { ...n, x: pos.x, y: pos.y } : n;
          }));
          const updatedNodes = nodes.map(wn => {
            const pos = layout.find(l => l.id === wn.id);
            return pos ? { ...wn, position: [pos.x, pos.y] as [number, number] } : wn;
          });
          onNodesChange(updatedNodes);
          onPushHistory();
        }} title={t('canvas.autoArrangeNodes')}><Icon name="layout" size={14} /></button>
      </div>

      {/* Minimap */}
      {showMinimap && graphNodes.length > 0 && (
        <Minimap
          graphNodes={graphNodes}
          groups={groups}
          edges={edges}
          offset={offset}
          scale={scale}
          canvasSize={{ w: canvasBounds.width, h: canvasBounds.height }}
          onOffsetChange={next => animateViewport(next, scale, 0)}
          onScaleChange={next => {
            const target = typeof next === 'function' ? next(scale) : next;
            animateViewport(offset, target, 0);
          }}
        />
      )}

      {/* Node Palette (right-click canvas or link-drop on empty space) */}
      {palettePos && (
        <NodePalette
          objectInfo={objectInfo}
          requireInputType={pendingLinkPickup?.fromOutputType}
          onSelect={(meta) => {
            const created = addNode(meta, palettePos.x, palettePos.y);
            if (pendingLinkPickup && created) {
              const visibleInputs = getVisibleInputSpecs(meta, defaultsFor(meta));
              const inputs = { ...visibleInputs.required, ...visibleInputs.optional };
              const entries = Object.entries(inputs);
              const match = entries.find(([, spec]) => (spec as { type?: string }).type === pendingLinkPickup.fromOutputType)
                ?? entries.find(([, spec]) => {
                  const ty = (spec as { type?: string }).type;
                  return ty === '*' || ty === 'ANY';
                })
                ?? entries[0];
              if (match) {
                const [inputName] = match;
                const newEdge: WorkflowEdge = {
                  id: `e_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`,
                  from: { node: pendingLinkPickup.fromNodeId, output: pendingLinkPickup.fromOutputName },
                  to: { node: created.id, input: inputName },
                };
                onEdgesChangeRef.current([...edgesRef.current, newEdge]);
                onPushHistoryRef.current();
              }
            }
            setPendingLinkPickup(null);
            setPalettePos(null);
          }}
          onClose={() => { setPendingLinkPickup(null); setPalettePos(null); }}
          style={{ position: 'absolute', left: palettePos.x + 10, top: palettePos.y, zIndex: 150 }}
        />
      )}

      {/* Canvas Context Menu */}
      {canvasMenu && (
        <div className="context-menu" style={{ left: canvasMenu.x, top: canvasMenu.y, zIndex: 200 }}>
          <div className="context-menu-body">
            <div className="context-menu-item" onClick={() => { setPalettePos({ x: canvasMenu.canvasX, y: canvasMenu.canvasY }); setCanvasMenu(null); }}>{t('canvas.addNode')}</div>
            <div className="context-menu-item" onClick={() => {
              const rerouteMeta = objectInfo.reroute;
              if (rerouteMeta) {
                const id = `reroute_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`;
                const parent = groupContainingPoint(groups, canvasMenu.worldX, canvasMenu.worldY);
                const newNode: WorkflowNode = {
                  id,
                  type: 'reroute',
                  position: [Math.round(canvasMenu.worldX - 10), Math.round(canvasMenu.worldY - 10)],
                  params: defaultsFor(rerouteMeta),
                  node_info: rerouteMeta,
                  ...(parent ? { parentId: parent.id } : {}),
                  ui: { title: t('canvas.rerouteFallbackName'), color: nodeColor(rerouteMeta), shape: 'round' },
                };
                onNodesChange([...nodes, newNode]);
                pendingSelectionRef.current = new Set([id]);
                onPushHistory();
              }
              setCanvasMenu(null);
            }}>{t('canvas.addRerouteHere')}</div>
            <div className="context-menu-item" onClick={() => { fitView(); setCanvasMenu(null); }}>{t('canvas.fitView')}</div>
            <div className="context-menu-sep" />
            <div className="context-menu-item" onClick={() => {
              const selected = graphNodes.filter(n => n.selected);
              if (selected.length > 0) {
                const newGroup = createGroupFromNodes(selected, t('canvas.groupFallbackName'));
                onGroupsChange([...groups, newGroup]);
                onPushHistory();
              }
              setCanvasMenu(null);
            }}>{t('canvas.groupSelectedNodes')}</div>
            <div className="context-menu-sep" />
            <div className="context-menu-item" onClick={() => { onNodesChange(nodes.map(n => ({ ...n }))); setGraphNodes(prev => prev.map(n => ({ ...n, selected: true }))); setCanvasMenu(null); }}>{t('canvas.selectAll')}</div>
            <div className="context-menu-sep" />
            <div className="context-menu-item" onClick={() => {
              const selected = graphNodes.filter(n => n.selected);
              if (selected.length > 1) {
                const minX = Math.min(...selected.map(n => n.x));
                onNodesChange(nodes.map(wn => {
                  const gn = graphNodes.find(g => g.id === wn.id);
                  if (!gn || !gn.selected) return wn;
                  return { ...wn, position: [minX, wn.position[1]] as [number, number] };
                }));
                onPushHistory();
              }
              setCanvasMenu(null);
            }}>{t('canvas.alignLeft')}</div>
            <div className="context-menu-item" onClick={() => {
              const selected = graphNodes.filter(n => n.selected);
              if (selected.length > 1) {
                const minY = Math.min(...selected.map(n => n.y));
                onNodesChange(nodes.map(wn => {
                  const gn = graphNodes.find(g => g.id === wn.id);
                  if (!gn || !gn.selected) return wn;
                  return { ...wn, position: [wn.position[0], minY] as [number, number] };
                }));
                onPushHistory();
              }
              setCanvasMenu(null);
            }}>{t('canvas.alignTop')}</div>
            <div className="context-menu-item" onClick={() => {
              const selected = graphNodes.filter(n => n.selected);
              if (selected.length > 1) {
                const sorted = [...selected].sort((a, b) => a.x - b.x);
                const minX = sorted[0].x;
                const maxX = sorted[sorted.length - 1].x;
                const spacing = sorted.length > 1 ? (maxX - minX) / (sorted.length - 1) : 0;
                onNodesChange(nodes.map(wn => {
                  const idx = sorted.findIndex(s => s.id === wn.id);
                  if (idx < 0) return wn;
                  return { ...wn, position: [minX + spacing * idx, wn.position[1]] as [number, number] };
                }));
                onPushHistory();
              }
              setCanvasMenu(null);
            }}>{t('canvas.distributeHorizontal')}</div>
            <div className="context-menu-item" onClick={() => {
              const selected = graphNodes.filter(n => n.selected);
              if (selected.length > 1) {
                const sorted = [...selected].sort((a, b) => a.y - b.y);
                const minY = sorted[0].y;
                const maxY = sorted[sorted.length - 1].y;
                const spacing = sorted.length > 1 ? (maxY - minY) / (sorted.length - 1) : 0;
                onNodesChange(nodes.map(wn => {
                  const idx = sorted.findIndex(s => s.id === wn.id);
                  if (idx < 0) return wn;
                  return { ...wn, position: [wn.position[0], minY + spacing * idx] as [number, number] };
                }));
                onPushHistory();
              }
              setCanvasMenu(null);
            }}>{t('canvas.distributeVertical')}</div>
            <div className="context-menu-item" onClick={() => {
              const layout = arrangeNodesLayout(graphNodes, edges);
              setGraphNodes(prev => prev.map(n => {
                const pos = layout.find(l => l.id === n.id);
                return pos ? { ...n, x: pos.x, y: pos.y } : n;
              }));
              const updatedNodes = nodes.map(wn => {
                const pos = layout.find(l => l.id === wn.id);
                return pos ? { ...wn, position: [pos.x, pos.y] as [number, number] } : wn;
              });
              onNodesChange(updatedNodes);
              onPushHistory();
              setCanvasMenu(null);
            }}>{t('canvas.arrangeNodes')}</div>
            <div className="context-menu-item" onClick={() => {
              const dataUrl = exportThumbnailDataURL(graphNodes, edges, groups);
              const a = document.createElement('a');
              a.href = dataUrl;
              a.download = 'workflow_thumbnail.png';
              a.click();
              setCanvasMenu(null);
            }}>{t('canvas.exportThumbnail')}</div>
            <div className="context-menu-sep" />
            <div className="context-menu-item" onClick={() => { onNodesChange([]); onEdgesChange([]); onPushHistory(); setCanvasMenu(null); }}>{t('canvas.clearWorkflow')}</div>
          </div>
        </div>
      )}

      {/* Group Context Menu */}
      {groupContextMenu && (
        <GroupContextMenu
          x={groupContextMenu.x}
          y={groupContextMenu.y}
          groupId={groupContextMenu.groupId}
          groups={groups}
          nodes={nodes}
          onGroupsChange={onGroupsChange}
          onNodesChange={onNodesChange}
          onClose={() => setGroupContextMenu(null)}
        />
      )}

      {/* Link Context Menu */}
      {linkContextMenu && (
        <div className="context-menu" style={{ left: linkContextMenu.x, top: linkContextMenu.y, zIndex: 200 }}>
          <div className="context-menu-body">
            <div className="context-menu-item" onClick={() => insertRerouteOnEdge(linkContextMenu.edgeId, { x: linkContextMenu.worldX, y: linkContextMenu.worldY })}>{t('canvas.insertReroute')}</div>
            <div className="context-menu-item" onClick={() => {
              onEdgesChange(edges.filter(e => e.id !== linkContextMenu.edgeId));
              onPushHistory();
              setLinkContextMenu(null);
            }}>{t('canvas.deleteLink')}</div>
          </div>
        </div>
      )}

      {/* Node Context Menu */}
      {contextMenu && (
        <NodeContextMenu x={contextMenu.x} y={contextMenu.y} nodeId={contextMenu.nodeId} onAction={handleContextAction} onClose={() => setContextMenu(null)} />
      )}

      {/* Node Editor */}
      {editingNode && (
        <NodeEditor node={graphNodes.find(n => n.id === editingNode)} workflowParameters={workflowParameters} onParamChange={handleNodeParamChange} onClose={() => setEditingNode(null)} />
      )}

      {/* Node Info Panel */}
      {showNodeInfo && (
        <div style={{ position: 'absolute', right: 12, top: 12, zIndex: 150, maxWidth: 380, width: '100%' }}>
          <NodeInfoPanel node={graphNodes.find(n => n.id === showNodeInfo)} onClose={() => setShowNodeInfo(null)} />
        </div>
      )}

      {/* Inline rename overlay. */}
      {renamingNode && (() => {
        const targetNode = graphNodes.find(n => n.id === renamingNode.id);
        if (!targetNode) return null;
        const left = targetNode.x * scale + offset.x + 6 * scale;
        const top = targetNode.y * scale + offset.y + 6 * scale;
        const width = (targetNode.width - 12) * scale;
        const height = (NODE_HEADER_H - 12) * scale;
        const commit = () => {
          const value = renamingNode.value.trim();
          if (value !== (targetNode.title || '').trim()) {
            const updated = nodes.map(wn => wn.id === targetNode.id ? { ...wn, ui: { ...wn.ui, title: value || targetNode.type } } : wn);
            onNodesChange(updated);
            onPushHistory();
          }
          setRenamingNode(null);
        };
        return (
          <input
            autoFocus
            value={renamingNode.value}
            onChange={e => setRenamingNode({ id: renamingNode.id, value: e.target.value })}
            onBlur={commit}
            onKeyDown={e => {
              e.stopPropagation();
              if (e.key === 'Enter') { e.preventDefault(); commit(); }
              else if (e.key === 'Escape') { e.preventDefault(); setRenamingNode(null); }
            }}
            style={{
              position: 'absolute',
              left,
              top,
              width: Math.max(60, width),
              height: Math.max(18, height),
              fontSize: Math.max(11, 13 * scale),
              fontWeight: 600,
              padding: '0 6px',
              border: '1px solid var(--accent, #2dd4bf)',
              borderRadius: 4,
              background: 'var(--surface)',
              color: 'var(--text)',
              zIndex: 90,
              outline: 'none',
              boxShadow: '0 2px 8px rgba(0,0,0,0.25)',
            }}
            aria-label={t('canvas.renameNodeTitle')}
          />
        );
      })()}
    </div>
  );
});

const WorkflowCanvas = forwardRef<WorkflowCanvasRef, WorkflowCanvasProps>(function WorkflowCanvas(props, ref) {
  return (
    <ReactFlowProvider>
      <WorkflowCanvasInner {...props} ref={ref} />
    </ReactFlowProvider>
  );
});

// Memoized: App re-renders frequently (logs, run progress, collab presence).
export default memo(WorkflowCanvas);
