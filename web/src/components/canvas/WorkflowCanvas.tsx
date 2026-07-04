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
  MarkerType,
  ConnectionLineType,
  applyNodeChanges,
  getOutgoers,
  useReactFlow,
  type Node as RFNode,
  type Edge as RFEdge,
  type NodeChange,
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
import { selectedNodeIdAtom } from '../../state/uiAtoms';
import BioNode, { type BioNodeData } from './BioNode';
import { BioNodeActionsContext, type BioNodeActions } from './bioNodeActions';

export type { GraphNode, WorkflowCanvasRef };

const NODE_TYPES = { bio: BioNode };

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

  // Latest props for callbacks that must read fresh values without re-binding.
  const nodesRef = useRef(nodes); nodesRef.current = nodes;
  const edgesRef = useRef(edges); edgesRef.current = edges;
  const objectInfoRef = useRef(objectInfo); objectInfoRef.current = objectInfo;
  const isDraggingRef = useRef(false);
  const selectedIdsRef = useRef<Set<string>>(new Set());

  const [rfNodes, setRfNodes] = useState<RFNode<BioNodeData>[]>([]);

  // Reconcile React Flow node state from props. Skipped mid-drag so a status
  // tick or parent re-render never stomps the in-flight drag position (React
  // Flow owns positions during a drag; we commit them on drag stop).
  useEffect(() => {
    if (isDraggingRef.current) return;
    setRfNodes(prev => {
      const prevSel = new Map(prev.map(n => [n.id, n.selected]));
      return nodes.map(wn => {
        const g = toGraphNode(wn, edges, objectInfo, nodeStatusMap?.get(wn.id), tRef.current);
        const selected = prevSel.get(wn.id) ?? false;
        g.selected = selected;
        return {
          id: g.id,
          type: 'bio',
          position: { x: g.x, y: g.y },
          selected,
          width: g.width,
          height: g.height,
          style: { width: g.width, height: g.height },
          data: {
            g,
            categoryLabel: nodeCategoryDisplayLabel(g.category, tRef.current, tRef.current('nodeLibrary.otherCategory')),
            missingDependency: missingDependencyNodeIds?.has(g.id) ?? false,
            running: g.status === 'running',
          },
        } satisfies RFNode<BioNodeData>;
      });
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
    setRfNodes(prev => applyNodeChanges(changes, prev) as RFNode<BioNodeData>[]);
  }, []);

  const onNodeDragStart = useCallback(() => { isDraggingRef.current = true; }, []);

  const onNodeDragStop = useCallback(() => {
    isDraggingRef.current = false;
    // Commit live React Flow positions (honouring snap) as a single history step.
    const rfPos = new Map(rf.getNodes().map(n => [n.id, n.position]));
    const updated = nodesRef.current.map(wn => {
      const pos = rfPos.get(wn.id);
      if (!pos) return wn;
      const x = dragCoordinate(pos.x, 0, snapToGrid, gridSize);
      const y = dragCoordinate(pos.y, 0, snapToGrid, gridSize);
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

  const handleSelectionChange = useCallback((params: OnSelectionChangeParams) => {
    const ids = new Set(params.nodes.map(n => n.id));
    selectedIdsRef.current = ids;
    setSelectedNodeId(ids.size === 1 ? Array.from(ids)[0] : null);
  }, [setSelectedNodeId]);

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
  }), [onExecuteSelected, onNodesChange, onEdgesChange, onPushHistory]);

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

  useImperativeHandle(ref, () => ({
    fitView, focusNode, setViewport, getViewport, getSelectedNodeIds, executeSelected, autoLayout,
  }), [fitView, focusNode, setViewport, getViewport, getSelectedNodeIds, executeSelected, autoLayout]);

  return (
    <BioNodeActionsContext.Provider value={actions}>
      <div className="workflow-canvas-host">
      <ReactFlow
        nodes={rfNodes}
        edges={rfEdges}
        nodeTypes={NODE_TYPES}
        onNodesChange={handleNodesChange}
        onNodeDragStart={onNodeDragStart}
        onNodeDragStop={onNodeDragStop}
        onConnect={onConnect}
        onReconnect={onReconnect}
        isValidConnection={isValidConnection}
        onEdgesDelete={onEdgesDelete}
        onNodesDelete={onNodesDelete}
        onSelectionChange={handleSelectionChange}
        snapToGrid={snapToGrid}
        snapGrid={[gridSize, gridSize]}
        deleteKeyCode={['Backspace', 'Delete']}
        multiSelectionKeyCode={['Shift', 'Meta', 'Control']}
        connectionLineType={ConnectionLineType.Bezier}
        elevateEdgesOnSelect
        elevateNodesOnSelect
        onlyRenderVisibleElements
        selectionOnDrag
        panOnScroll
        fitView
        minZoom={0.1}
        maxZoom={4}
        colorMode="system"
        proOptions={{ hideAttribution: true }}
      >
        {showGrid && <Background variant={BackgroundVariant.Dots} gap={gridSize} size={1} />}
        <Controls>
          <ControlButton onClick={autoLayout} title={t('canvas.autoArrangeNodes')} aria-label={t('canvas.autoArrangeNodes')}>
            <span aria-hidden style={{ fontSize: 14, lineHeight: 1 }}>⤨</span>
          </ControlButton>
        </Controls>
        {showMinimap && (
          <MiniMap
            pannable
            zoomable
            nodeColor={(n) => (n.data as BioNodeData | undefined)?.g?.color ?? '#64748b'}
          />
        )}
        <Panel position="top-left" className="canvas-hint">{t('canvas.dragToConnect', 'Drag from a port to connect')}</Panel>
      </ReactFlow>
      </div>
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
