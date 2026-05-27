import { useEffect, useRef, useCallback, useMemo, useState, forwardRef, useImperativeHandle } from 'react';
import type { Workflow, WorkflowNode, WorkflowEdge, WorkflowGroup, ObjectInfo, NodeMetadata, NodeStatus } from '../../types';
import { edgeColorForSource, defaultsFor } from '../../utils';
import { useSettings } from '../../hooks/useSettings';
import { hasOpenOverlay } from '../../state/overlays';
import Icon from '../ui/Icon';
import { promptDialog, toast } from '../ui';
import { saveBlueprint } from '../../state/subgraphLibrary';
import NodePalette from '../nodes/NodePalette';
import NodeContextMenu from '../nodes/NodeContextMenu';
import NodeEditor from '../nodes/NodeEditor';
import NodeInfoPanel from '../nodes/NodeInfoPanel';
import Minimap from './Minimap';
import SelectionToolbox from './SelectionToolbox';
import GroupContextMenu from './GroupContextMenu';

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

export interface NodeCommentSummary {
  count: number;
  unresolved: boolean;
}

interface LiteGraphCanvasProps {
  nodes: WorkflowNode[];
  edges: WorkflowEdge[];
  groups: WorkflowGroup[];
  objectInfo: ObjectInfo;
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
  nodeProgressMap?: Map<string, { current: number; total: number; startedAt: number }>;
  nodePreviewsMap?: Map<string, string>;
  missingDependencyNodeIds?: Set<string>;
  nodeCommentsMap?: Map<string, NodeCommentSummary>;
  nodeComments?: Comment[];
  collabWorkflowId?: string;
  currentCollabUser?: CollabUser;
  onNodeCommentsChange?: () => void;
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

export interface GraphNode {
  id: string;
  type: string;
  display_name: string;
  category: string;
  x: number;
  y: number;
  width: number;
  height: number;
  inputs: { name: string; type: string; connected: boolean }[];
  outputs: { name: string; type: string; connected: boolean }[];
  params: Record<string, unknown>;
  meta: NodeMetadata | null;
  color: string;
  muted: boolean;
  bypassed: boolean;
  selected: boolean;
  collapsed: boolean;
  pinned: boolean;
  shape: 'round' | 'box' | 'card';
  title: string;
  status?: NodeStatus['status'];
  visualOnly: boolean;
}

const NODE_WIDTH = 220;
const NODE_NOTE_WIDTH = 260;
const NODE_HEADER_H = 32;
const NODE_PIN_H = 22;
const COLORS: Record<string, string> = {
  Input: '#0d9488', 'Quality Control': '#ec4899', 'Read Preprocessing': '#f59e0b',
  Alignment: '#3b82f6', 'SAM/BAM Processing': '#60a5fa', 'Variant Calling': '#ef4444',
  Assembly: '#22c55e', Annotation: '#a855f7', Phylogenetics: '#14b8a6',
  'RNA-Seq': '#f97316', Metagenomics: '#8b5cf6', 'ChIP-Seq': '#06b6d4',
  'Single Cell': '#d946ef', HPC: '#6366f1', Utility: '#64748b',
};

// The Python registry emits lowercase categories like 'trimming', 'samtools',
// 'metagenomics' — these don't match the COLORS keys above, so before falling
// back to slate gray we run a substring search on category + id + display name.
// Order matters: first match wins, so put more specific keywords earlier.
const COLOR_KEYWORD_RULES: Array<[string, string]> = [
  ['input', '#0d9488'],
  ['qc', '#ec4899'],
  ['quality', '#ec4899'],
  ['preprocess', '#f59e0b'],
  ['trim', '#f59e0b'],
  ['cutadapt', '#f59e0b'],
  ['fastp', '#f59e0b'],
  ['samtools', '#60a5fa'],
  ['sam/bam', '#60a5fa'],
  ['align', '#3b82f6'],
  ['hisat', '#3b82f6'],
  ['bowtie', '#3b82f6'],
  ['bwa', '#3b82f6'],
  ['minimap', '#3b82f6'],
  ['star', '#3b82f6'],
  ['variant', '#ef4444'],
  ['gatk', '#ef4444'],
  ['bcftools', '#ef4444'],
  ['freebayes', '#ef4444'],
  ['vcftools', '#ef4444'],
  ['assembly', '#22c55e'],
  ['spades', '#22c55e'],
  ['canu', '#22c55e'],
  ['flye', '#22c55e'],
  ['unicycler', '#22c55e'],
  ['megahit', '#22c55e'],
  ['quast', '#22c55e'],
  ['annotation', '#a855f7'],
  ['prokka', '#a855f7'],
  ['bakta', '#a855f7'],
  ['eggnog', '#a855f7'],
  ['phylo', '#14b8a6'],
  ['mafft', '#14b8a6'],
  ['iqtree', '#14b8a6'],
  ['fasttree', '#14b8a6'],
  ['raxml', '#14b8a6'],
  ['clustalo', '#14b8a6'],
  ['single', '#d946ef'],
  ['cellranger', '#d946ef'],
  ['metag', '#8b5cf6'],
  ['kraken', '#8b5cf6'],
  ['bracken', '#8b5cf6'],
  ['metaphlan', '#8b5cf6'],
  ['humann', '#8b5cf6'],
  ['checkm', '#8b5cf6'],
  ['maxbin', '#8b5cf6'],
  ['quantif', '#a855f7'],
  ['count', '#a855f7'],
  ['featurecounts', '#a855f7'],
  ['kallisto', '#a855f7'],
  ['salmon', '#a855f7'],
  ['stringtie', '#a855f7'],
  ['differential', '#ef4444'],
  ['deseq', '#ef4444'],
  ['expression', '#a855f7'],
  ['peak', '#06b6d4'],
  ['macs', '#06b6d4'],
  ['chip', '#06b6d4'],
  ['deeptools', '#3b82f6'],
  ['bedtools', '#60a5fa'],
  ['hpc', '#6366f1'],
  ['biopython', '#a855f7'],
  ['biostrings', '#a855f7'],
  ['blast', '#a855f7'],
  ['plot', '#ec4899'],
  ['heatmap', '#ec4899'],
  ['viz', '#ec4899'],
  ['note', '#f59e0b'],
];

function nodeColor(meta: NodeMetadata | null): string {
  if (!meta) return '#64748b';
  const category = meta.category || '';
  if (COLORS[category]) return COLORS[category];
  const haystack = `${category} ${meta.id || ''} ${meta.display_name || ''}`.toLowerCase();
  for (const [keyword, color] of COLOR_KEYWORD_RULES) {
    if (haystack.includes(keyword)) return color;
  }
  return '#64748b';
}

function calcNoteHeight(text: string, width: number): number {
  const maxCharsPerLine = Math.floor((width - 20) / 6.5);
  const lines = text.split('\n').reduce((total, line) => {
    return total + Math.max(1, Math.ceil(line.length / maxCharsPerLine));
  }, 0);
  return NODE_HEADER_H + Math.max(40, lines * 15 + 20);
}

function isInteractiveWidgetSpec(spec: unknown): boolean {
  const s = spec as { type?: string; options?: unknown[]; forceInput?: boolean } | null | undefined;
  if (!s) return false;
  if (s.type === 'BOOLEAN') return true;
  if (Array.isArray(s.options) && s.options.length > 0) return true;
  if (s.type === 'INT' || s.type === 'FLOAT') return true;
  if (s.type === 'STRING' && !s.forceInput) return true;
  return false;
}

function countInteractiveWidgets(meta: NodeMetadata | null): number {
  const all = { ...meta?.input_types?.required, ...meta?.input_types?.optional };
  let count = 0;
  for (const [, spec] of Object.entries(all)) {
    if (isInteractiveWidgetSpec(spec)) count += 1;
  }
  return count;
}

const WIDGET_ROW_H = 24;
const WIDGET_BLOCK_PAD = 8;

function calcNodeHeight(meta: NodeMetadata | null, collapsed: boolean, params?: Record<string, unknown>, width?: number): number {
  if (collapsed) return NODE_HEADER_H;
  if (meta?.id === 'note') {
    const text = String(params?.text || '');
    return calcNoteHeight(text, width || NODE_NOTE_WIDTH);
  }
  const ins = Object.keys(meta?.input_types?.required || {}).length + Object.keys(meta?.input_types?.optional || {}).length;
  const outs = (meta?.return_types || []).length;
  const ioHeight = Math.max(ins, outs, 1) * NODE_PIN_H;
  const widgetCount = countInteractiveWidgets(meta);
  const widgetHeight = widgetCount > 0 ? widgetCount * WIDGET_ROW_H + WIDGET_BLOCK_PAD : 0;
  const visibleParamCount = Object.keys(params || {}).filter(key => key !== 'text').length;
  const summaryHeight = widgetCount === 0 && visibleParamCount > 0 ? Math.min(3, visibleParamCount) * 15 + 10 : 0;
  const descriptionHeight = widgetCount === 0 && visibleParamCount === 0 && meta?.description ? 28 : 0;
  const base = NODE_HEADER_H + ioHeight + widgetHeight + summaryHeight + descriptionHeight + 12;
  if (meta?.id === 'image_preview') return base + 120;
  return base;
}

function formatNodeParamValue(value: unknown): string {
  if (value === null || value === undefined || value === '') return '-';
  if (typeof value === 'boolean') return value ? 'true' : 'false';
  if (typeof value === 'number') return Number.isInteger(value) ? String(value) : value.toFixed(3).replace(/\.?0+$/, '');
  if (Array.isArray(value)) return `${value.length} items`;
  if (typeof value === 'object') return '{...}';
  const text = String(value);
  return text.length > 24 ? `${text.slice(0, 21)}...` : text;
}

function getNodesInGroup(group: WorkflowGroup, graphNodes: GraphNode[]): string[] {
  const gx1 = group.position[0];
  const gy1 = group.position[1];
  const gx2 = gx1 + group.width;
  const gy2 = gy1 + group.height;
  return graphNodes
    .filter(n => {
      const ncx = n.x + n.width / 2;
      const ncy = n.y + n.height / 2;
      return ncx >= gx1 && ncx <= gx2 && ncy >= gy1 && ncy <= gy2;
    })
    .map(n => n.id);
}

function arrangeNodesLayout(graphNodes: GraphNode[], edges: WorkflowEdge[]): Array<{ id: string; x: number; y: number }> {
  const adj = new Map<string, string[]>();
  const inDegree = new Map<string, number>();
  for (const n of graphNodes) {
    adj.set(n.id, []);
    inDegree.set(n.id, 0);
  }
  for (const e of edges) {
    adj.get(e.from.node)?.push(e.to.node);
    inDegree.set(e.to.node, (inDegree.get(e.to.node) || 0) + 1);
  }
  const queue: string[] = [];
  for (const [id, deg] of inDegree) {
    if (deg === 0) queue.push(id);
  }
  const topo: string[] = [];
  while (queue.length > 0) {
    const id = queue.shift()!;
    topo.push(id);
    for (const next of adj.get(id) || []) {
      const newDeg = (inDegree.get(next) || 0) - 1;
      inDegree.set(next, newDeg);
      if (newDeg === 0) queue.push(next);
    }
  }
  const layer = new Map<string, number>();
  for (const id of topo) {
    let maxLayer = 0;
    for (const e of edges) {
      if (e.to.node === id) {
        maxLayer = Math.max(maxLayer, (layer.get(e.from.node) || 0) + 1);
      }
    }
    layer.set(id, maxLayer);
  }
  const layerMap = new Map<number, GraphNode[]>();
  for (const n of graphNodes) {
    const l = layer.get(n.id) || 0;
    if (!layerMap.has(l)) layerMap.set(l, []);
    layerMap.get(l)!.push(n);
  }
  const colWidth = 280;
  const rowHeight = 140;
  const result: Array<{ id: string; x: number; y: number }> = [];
  for (const n of graphNodes) {
    const l = layer.get(n.id) || 0;
    const nodesInLayer = layerMap.get(l)!;
    const idx = nodesInLayer.findIndex(nn => nn.id === n.id);
    result.push({ id: n.id, x: l * colWidth + 60, y: idx * rowHeight + 60 });
  }
  return result;
}

function exportThumbnailDataURL(graphNodes: GraphNode[], edges: WorkflowEdge[], groups: WorkflowGroup[]): string {
  const c = document.createElement('canvas');
  c.width = 480;
  c.height = 360;
  const ctx = c.getContext('2d')!;
  ctx.fillStyle = '#0f172a';
  ctx.fillRect(0, 0, c.width, c.height);

  let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
  for (const n of graphNodes) {
    minX = Math.min(minX, n.x);
    minY = Math.min(minY, n.y);
    maxX = Math.max(maxX, n.x + n.width);
    maxY = Math.max(maxY, n.y + n.height);
  }
  for (const g of groups) {
    minX = Math.min(minX, g.position[0]);
    minY = Math.min(minY, g.position[1]);
    maxX = Math.max(maxX, g.position[0] + g.width);
    maxY = Math.max(maxY, g.position[1] + g.height);
  }
  if (!isFinite(minX)) { minX = 0; minY = 0; maxX = c.width; maxY = c.height; }

  const pad = 30;
  const bw = maxX - minX + pad * 2;
  const bh = maxY - minY + pad * 2;
  const s = Math.min(c.width / bw, c.height / bh);
  const ox = (c.width - bw * s) / 2 + pad * s - minX * s;
  const oy = (c.height - bh * s) / 2 + pad * s - minY * s;
  ctx.setTransform(s, 0, 0, s, ox, oy);

  for (const g of groups) {
    ctx.fillStyle = g.color + '18';
    ctx.fillRect(g.position[0], g.position[1], g.width, g.height);
    ctx.strokeStyle = g.color + '40';
    ctx.lineWidth = 1 / s;
    ctx.strokeRect(g.position[0], g.position[1], g.width, g.height);
  }

  for (const edge of edges) {
    const fromNode = graphNodes.find(n => n.id === edge.from.node);
    const toNode = graphNodes.find(n => n.id === edge.to.node);
    if (!fromNode || !toNode) continue;
    const fromOutIndex = fromNode.outputs.findIndex(o => o.name === edge.from.output);
    const toInIndex = toNode.inputs.findIndex(i => i.name === edge.to.input);
    const fy = fromNode.y + NODE_HEADER_H + NODE_PIN_H / 2 + (fromOutIndex >= 0 ? fromOutIndex : 0) * NODE_PIN_H;
    const ty = toNode.y + NODE_HEADER_H + NODE_PIN_H / 2 + (toInIndex >= 0 ? toInIndex : 0) * NODE_PIN_H;
    const fx = fromNode.x + fromNode.width;
    const tx = toNode.x;
    const dist = Math.hypot(tx - fx, ty - fy);
    const cd = Math.max(30, dist * 0.25);
    ctx.strokeStyle = '#94a3b8';
    ctx.lineWidth = 1.5 / s;
    ctx.beginPath();
    ctx.moveTo(fx, fy);
    ctx.bezierCurveTo(fx + cd, fy, tx - cd, ty, tx, ty);
    ctx.stroke();
  }

  for (const node of graphNodes) {
    ctx.fillStyle = node.color;
    roundRect(ctx, node.x, node.y, node.width, node.height, 8);
    ctx.fill();
    ctx.fillStyle = 'rgba(0,0,0,0.35)';
    ctx.fillRect(node.x, node.y, node.width, NODE_HEADER_H);
    ctx.fillStyle = '#ffffff';
    ctx.font = `${11 / s}px Inter, sans-serif`;
    ctx.textAlign = 'left';
    ctx.fillText(node.display_name, node.x + 10, node.y + 21);
  }

  ctx.setTransform(1, 0, 0, 1, 0, 0);
  return c.toDataURL('image/png');
}

function createGroupFromNodes(nodes: GraphNode[]): WorkflowGroup {
  const minX = Math.min(...nodes.map(n => n.x));
  const minY = Math.min(...nodes.map(n => n.y));
  const maxX = Math.max(...nodes.map(n => n.x + n.width));
  const maxY = Math.max(...nodes.map(n => n.y + n.height));
  const padding = 20;
  return {
    id: typeof crypto !== 'undefined' && crypto.randomUUID ? crypto.randomUUID() : `group_${Date.now()}`,
    name: 'Group',
    position: [minX - padding, minY - padding] as [number, number],
    width: maxX - minX + padding * 2,
    height: maxY - minY + padding * 2,
    color: '#6366f1',
    collapsed: false,
  };
}

export interface LiteGraphCanvasRef {
  fitView: () => void;
  focusNode: (nodeId: string) => void;
  setViewport: (viewport: { x: number; y: number; scale: number }) => void;
  getViewport: () => { x: number; y: number; scale: number };
  getSelectedNodeIds: () => string[];
  executeSelected: () => void;
  createSubgraphFromSelection: () => void;
}

const LiteGraphCanvas = forwardRef<LiteGraphCanvasRef, LiteGraphCanvasProps>(function LiteGraphCanvas({
  nodes, edges, groups, objectInfo,
  onNodesChange, onEdgesChange, onGroupsChange, onPushHistory, onUndo, onRedo,
  snapToGrid, showMinimap, viewportLocked, linksHidden,
  onToggleMinimap, onToggleLinksHidden,
  nodeStatusMap,
  nodeProgressMap,
  nodePreviewsMap,
  missingDependencyNodeIds,
  nodeCommentsMap,
  nodeComments = [],
  collabWorkflowId,
  currentCollabUser,
  onNodeCommentsChange,
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
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const hostRef = useRef<HTMLDivElement>(null);
  const [offset, setOffset] = useState({ x: 0, y: 0 });
  const [scale, setScale] = useState(1);

  // Render quality preferences (auto/high/low + shadow + smoothing toggles).
  // Read on every render so settings changes propagate immediately. The
  // values are forwarded into the draw loop via a ref to avoid invalidating
  // the memoised `draw` callback on every settings change.
  const { get, getBool } = useSettings();
  const qualityModeSetting = String(get('bionodulo.canvas.quality') || 'auto') as 'auto' | 'high' | 'low';
  const shadowsEnabled = getBool('bionodulo.canvas.shadows', true);
  const smoothLinksEnabled = getBool('bionodulo.canvas.smoothLinks', true);
  const qualityPrefsRef = useRef({ qualityModeSetting, shadowsEnabled, smoothLinksEnabled });
  qualityPrefsRef.current = { qualityModeSetting, shadowsEnabled, smoothLinksEnabled };

  useEffect(() => {
    onViewportChange?.(offset, scale);
  }, [offset, scale, onViewportChange]);

  const [graphNodes, setGraphNodes] = useState<GraphNode[]>([]);
  const [dragging, setDragging] = useState<string | null>(null);
  const [dragStart, setDragStart] = useState({ x: 0, y: 0 });
  const [panning, setPanning] = useState(false);
  const [selectBox, setSelectBox] = useState<{ x: number; y: number; w: number; h: number } | null>(null);
  const [contextMenu, setContextMenu] = useState<{ x: number; y: number; nodeId: string | null } | null>(null);
  const [palettePos, setPalettePos] = useState<{ x: number; y: number } | null>(null);
  const [pendingLinkPickup, setPendingLinkPickup] = useState<{ fromNodeId: string; fromOutputName: string; fromOutputType: string } | null>(null);
  const [editingNode, setEditingNode] = useState<string | null>(null);
  const [showNodeInfo, setShowNodeInfo] = useState<string | null>(null);
  const [editingZoom, setEditingZoom] = useState(false);
  const [actionFeedback, setActionFeedback] = useState<{ label: string; key: number } | null>(null);
  const actionFeedbackTimer = useRef<number | null>(null);
  const flashAction = useCallback((label: string) => {
    if (actionFeedbackTimer.current) window.clearTimeout(actionFeedbackTimer.current);
    setActionFeedback({ label, key: Date.now() });
    actionFeedbackTimer.current = window.setTimeout(() => setActionFeedback(null), 900);
  }, []);
  useEffect(() => () => {
    if (actionFeedbackTimer.current) window.clearTimeout(actionFeedbackTimer.current);
  }, []);
  const [canvasMenu, setCanvasMenu] = useState<{ x: number; y: number; worldX: number; worldY: number } | null>(null);
  const [nodeCommentTarget, setNodeCommentTarget] = useState<{ nodeId: string; compose: boolean } | null>(null);
  const [groupContextMenu, setGroupContextMenu] = useState<{ x: number; y: number; groupId: string } | null>(null);
  const [groupDragging, setGroupDragging] = useState<string | null>(null);
  const groupDragNodesRef = useRef<string[]>([]);
  const groupDragStartRef = useRef<{ groupId: string; startPos: [number, number]; nodeStarts: Map<string, [number, number]> } | null>(null);
  const [groupResizing, setGroupResizing] = useState<string | null>(null);
  // Link drag & slot hover
  const [linkDrag, setLinkDrag] = useState<{ fromNodeId: string; fromOutputIndex: number; fromOutputName: string; fromOutputType: string } | null>(null);
  const [mouseWorld, setMouseWorld] = useState({ x: 0, y: 0 });
  const [hoveredSlot, setHoveredSlot] = useState<{ nodeId: string; type: 'input' | 'output'; index: number } | null>(null);
  const [hoveredLink, setHoveredLink] = useState<string | null>(null);
  const [hoveredNodeId, setHoveredNodeId] = useState<string | null>(null);
  const [linkContextMenu, setLinkContextMenu] = useState<{ x: number; y: number; edgeId: string; worldX: number; worldY: number } | null>(null);
  const [resizingNode, setResizingNode] = useState<string | null>(null);
  const [activeWidget, setActiveWidget] = useState<{ nodeId: string; name: string } | null>(null);
  const activeWidgetRef = useRef(activeWidget);
  useEffect(() => { activeWidgetRef.current = activeWidget; }, [activeWidget]);
  const sizeRef = useRef({ w: 800, h: 600 });
  const [canvasSize, setCanvasSize] = useState({ w: 800, h: 600 });
  const widgetsRef = useRef<Map<string, Array<{ name: string; type: string; x: number; y: number; w: number; h: number }>>>(new Map());
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
  const dragMovedRef = useRef(false);
  const dragCommitNeededRef = useRef(false);
  const dragOwnershipStartedRef = useRef(false);
  // Snapshot of each dragged node's original rect so we can render faint
  // "ghost" outlines at the origin during a node drag.
  const dragGhostsRef = useRef<Array<{ id: string; x: number; y: number; w: number; h: number; radius: number; isReroute: boolean }>>([]);
  // Refs for high-frequency values to avoid recreating draw callback
  const linkDragRef = useRef(linkDrag);
  const mouseWorldRef = useRef(mouseWorld);
  const hoveredSlotRef = useRef(hoveredSlot);
  const hoveredLinkRef = useRef(hoveredLink);
  const resizingNodeRef = useRef(resizingNode);
  const collabUsersRef = useRef(collabUsers);
  const missingDependencyNodeIdsRef = useRef(missingDependencyNodeIds);
  const nodeProgressMapRef = useRef(nodeProgressMap);
  const isDraggingRef = useRef(false);
  const drawRef = useRef<() => void>(() => {});

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
  useEffect(() => { linkDragRef.current = linkDrag; }, [linkDrag]);
  useEffect(() => { mouseWorldRef.current = mouseWorld; }, [mouseWorld]);
  useEffect(() => { hoveredSlotRef.current = hoveredSlot; }, [hoveredSlot]);
  useEffect(() => { hoveredLinkRef.current = hoveredLink; }, [hoveredLink]);
  useEffect(() => { resizingNodeRef.current = resizingNode; }, [resizingNode]);
  useEffect(() => { collabUsersRef.current = collabUsers; }, [collabUsers]);
  useEffect(() => { missingDependencyNodeIdsRef.current = missingDependencyNodeIds; }, [missingDependencyNodeIds]);
  useEffect(() => { nodeProgressMapRef.current = nodeProgressMap; }, [nodeProgressMap]);
  useEffect(() => { widgetsRef.current.clear(); }, [graphNodes]);

  const publishCollabSelection = useCallback((selection: AwarenessState['selection']) => {
    onCollabSelectionRef.current?.(selection);
  }, []);

  const startDragOwnership = useCallback((nodeId: string) => {
    if (dragOwnershipStartedRef.current) return;
    dragOwnershipStartedRef.current = true;
    onCollabDragStart?.(nodeId);
  }, [onCollabDragStart]);

  // Convert workflow nodes to graph nodes (positions, structure, connectivity)
  useEffect(() => {
    setGraphNodes(prev => {
      const map = new Map(prev.map(n => [n.id, n]));
      const pending = pendingSelectionRef.current;
      if (pending) pendingSelectionRef.current = null;
      return nodes.map(wn => {
        const existing = map.get(wn.id);
        // Subgraph nodes carry their port shape on `wn.node_info` directly
        // since they're synthesized client-side and don't exist in the
        // registry-derived objectInfo map.
        const meta = wn.type ? (objectInfo[wn.type] || wn.node_info || null) : (wn.node_info || null);
        const collapsed = wn.ui?.collapsed ?? existing?.collapsed ?? false;
        const isNote = meta?.id === 'note';
        const isReroute = meta?.id === 'reroute';
        const visualOnly = meta?.visual_only ?? isNote;
        const nodeWidth = isNote
          ? (wn.ui?.width ?? existing?.width ?? NODE_NOTE_WIDTH)
          : (isReroute ? 20 : (wn.ui?.width ?? existing?.width ?? NODE_WIDTH));
        let nodeHeight: number;
        if (isReroute) {
          nodeHeight = 20;
        } else if (collapsed) {
          nodeHeight = calcNodeHeight(meta, true, wn.params);
        } else {
          const minHeight = calcNodeHeight(meta, false, wn.params, isNote ? nodeWidth : undefined);
          const storedHeight = wn.ui?.height ?? existing?.height;
          // Stored heights may have been computed by an older version that
          // undersized widget rows; honour user-resized growth but never let
          // the node clip its DOM-widget overlays.
          nodeHeight = storedHeight ? Math.max(storedHeight, minHeight) : minHeight;
        }
        return {
          id: wn.id,
          type: wn.type,
          display_name: meta?.display_name || wn.type || 'Unknown',
          category: meta?.category || 'Utility',
          x: wn.position[0],
          y: wn.position[1],
          width: nodeWidth,
          height: nodeHeight,
          inputs: (meta && !visualOnly) ? [
            ...Object.entries(meta.input_types?.required || {}).map(([name, spec]) => ({
              name, type: spec.type || 'STRING', connected: edges.some(e => e.to.node === wn.id && e.to.input === name),
            })),
            ...Object.entries(meta.input_types?.optional || {}).map(([name, spec]) => ({
              name, type: spec.type || 'STRING', connected: edges.some(e => e.to.node === wn.id && e.to.input === name),
            })),
          ] : [],
          outputs: (meta && !visualOnly) ? (meta.return_types || []).map((t, i) => ({
            name: meta.return_names?.[i] || t, type: t,
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
          title: wn.ui?.title || meta?.display_name || wn.type || 'Node',
          status: existing?.status,
          visualOnly,
        };
      });
    });
  }, [nodes, edges, objectInfo]);

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

  const toWorld = useCallback((cx: number, cy: number) => ({
    x: (cx - offset.x) / scale,
    y: (cy - offset.y) / scale,
  }), [offset, scale]);

  const fromWorld = useCallback((wx: number, wy: number) => ({
    x: wx * scale + offset.x,
    y: wy * scale + offset.y,
  }), [offset, scale]);

  const getSelectedNodeIds = useCallback(() => (
    graphNodesRef.current.filter(n => n.selected).map(n => n.id)
  ), []);

  const nodeRadius = useCallback((node: GraphNode) => {
    if (node.shape === 'box') return 2;
    if (node.shape === 'card') return 12;
    return 8;
  }, []);

  const draw = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    const w = Math.max(1, sizeRef.current.w);
    const h = Math.max(1, sizeRef.current.h);
    const dpr = window.devicePixelRatio || 1;
    const targetWidth = Math.round(w * dpr);
    const targetHeight = Math.round(h * dpr);
    if (canvas.width !== targetWidth || canvas.height !== targetHeight) {
      canvas.width = targetWidth;
      canvas.height = targetHeight;
      canvas.style.width = w + 'px';
      canvas.style.height = h + 'px';
    }

    const isDark = document.documentElement.classList.contains('dark');
    const currentLinkDrag = linkDragRef.current;
    const currentMouseWorld = mouseWorldRef.current;
    const currentHoveredSlot = hoveredSlotRef.current;
    const qualityPrefs = qualityPrefsRef.current;
    const interacting = isDraggingRef.current || panning || groupDragging || groupResizing || resizingNode || Boolean(activeWidgetRef.current);
    // `auto` honours the interaction heuristic; `high` always renders rich;
    // `low` always renders cheap (best for huge graphs on weak hardware).
    const lowQuality =
      qualityPrefs.qualityModeSetting === 'low'
        ? true
        : qualityPrefs.qualityModeSetting === 'high'
        ? false
        : interacting;
    const allowShadows = qualityPrefs.shadowsEnabled && !lowQuality;
    ctx.imageSmoothingEnabled = qualityPrefs.smoothLinksEnabled && !lowQuality;
    ctx.imageSmoothingQuality = lowQuality ? 'low' : 'high';

    // Resolve palette tokens once per frame so the canvas follows the active
    // theme (`bionodulo`, `clinical`, `field`, `contrast`, custom) instead of
    // hard-coding teal everywhere. Each token has a sensible fallback.
    const rootStyle = getComputedStyle(document.documentElement);
    const token = (name: string, fallback: string): string => {
      const value = rootStyle.getPropertyValue(name).trim();
      return value || fallback;
    };
    const palette = {
      canvas: token('--canvas', isDark ? '#0f172a' : '#eef3f4'),
      accent: token('--accent', '#2dd4bf'),
      surface: token('--surface', isDark ? '#1e293b' : '#ffffff'),
      surface2: token('--surface-2', isDark ? '#334155' : '#f3f6f7'),
      border: token('--border', isDark ? '#334155' : '#cbd5e1'),
      border2: token('--border-2', isDark ? '#475569' : '#cbd5e1'),
      muted: token('--muted', isDark ? '#94a3b8' : '#64748b'),
      text: token('--text', isDark ? '#cbd5e1' : '#475569'),
    };
    const gridStroke = isDark ? 'rgba(255,255,255,0.04)' : 'rgba(0,0,0,0.05)';

    // Clear
    ctx.fillStyle = palette.canvas;
    ctx.fillRect(0, 0, w * dpr, h * dpr);

    // Apply world transform
    ctx.save();
    ctx.setTransform(dpr * scale, 0, 0, dpr * scale, offset.x * dpr, offset.y * dpr);

    // Grid
    const gridSize = 20;
    const minX = -offset.x / scale;
    const minY = -offset.y / scale;
    const maxX = minX + w / scale;
    const maxY = minY + h / scale;
    const visibleMargin = 240;
    const visibleNodes = graphNodesRef.current.filter(node => (
      node.x + node.width >= minX - visibleMargin
      && node.x <= maxX + visibleMargin
      && node.y + node.height >= minY - visibleMargin
      && node.y <= maxY + visibleMargin
    ));
    const visibleNodeIds = new Set(visibleNodes.map(node => node.id));
    const nodeById = new Map(graphNodesRef.current.map(node => [node.id, node]));
    const startX = Math.floor(minX / gridSize) * gridSize;
    const startY = Math.floor(minY / gridSize) * gridSize;
    ctx.strokeStyle = gridStroke;
    ctx.lineWidth = 1;
    for (let x = startX; x <= maxX; x += gridSize) {
      ctx.beginPath(); ctx.moveTo(x, startY); ctx.lineTo(x, maxY); ctx.stroke();
    }
    for (let y = startY; y <= maxY; y += gridSize) {
      ctx.beginPath(); ctx.moveTo(startX, y); ctx.lineTo(maxX, y); ctx.stroke();
    }

    // Edges
    if (!linksHidden) {
      // Reroute geometry: anchors at the reroute centre and control-point
      // tangents borrowed from the neighbour on the other side of the
      // reroute so chains draw as a single smooth curve.
      const REROUTE_HALF = 10; // half of the 20px reroute footprint
      const rerouteCentre = (node: GraphNode) => ({
        x: node.x + REROUTE_HALF,
        y: node.y + REROUTE_HALF,
      });
      const slotPoint = (node: GraphNode, side: 'output' | 'input', slotIndex: number): { x: number; y: number } => {
        if (node.type === 'reroute') return rerouteCentre(node);
        const slotY = node.collapsed
          ? node.y + NODE_HEADER_H / 2
          : node.y + NODE_HEADER_H + NODE_PIN_H / 2 + Math.max(0, slotIndex) * NODE_PIN_H;
        return { x: side === 'output' ? node.x + node.width : node.x, y: slotY };
      };
      // Look up the neighbour endpoint that continues past a reroute, so its
      // bezier control point keeps the chain tangent.
      const neighbourThroughReroute = (rerouteId: string, side: 'output' | 'input'): { x: number; y: number } | null => {
        // 'output' side means we are drawing an edge whose SOURCE is the
        // reroute, so we want the previous link feeding INTO the reroute.
        const target = side === 'output'
          ? edges.find(e => e.to.node === rerouteId)
          : edges.find(e => e.from.node === rerouteId);
        if (!target) return null;
        const otherNode = side === 'output'
          ? nodeById.get(target.from.node)
          : nodeById.get(target.to.node);
        if (!otherNode) return null;
        const slotIndex = side === 'output'
          ? otherNode.outputs.findIndex(o => o.name === target.from.output)
          : otherNode.inputs.findIndex(i => i.name === target.to.input);
        return slotPoint(otherNode, side === 'output' ? 'output' : 'input', slotIndex);
      };

      for (const edge of edges) {
        if (!visibleNodeIds.has(edge.from.node) && !visibleNodeIds.has(edge.to.node)) continue;
        const fromNode = nodeById.get(edge.from.node);
        const toNode = nodeById.get(edge.to.node);
        if (!fromNode || !toNode) continue;
        const fromOutIndex = fromNode.outputs.findIndex(o => o.name === edge.from.output);
        const toInIndex = toNode.inputs.findIndex(i => i.name === edge.to.input);
        const from = slotPoint(fromNode, 'output', fromOutIndex);
        const to = slotPoint(toNode, 'input', toInIndex);
        const dist = Math.hypot(to.x - from.x, to.y - from.y);
        const cd = Math.max(30, dist * 0.25);
        const isHovered = hoveredLinkRef.current === edge.id;
        // Color resolves from the original source's slot type so the colour
        // propagates faithfully across a reroute chain.
        let originType = fromNode.outputs[fromOutIndex]?.type || '';
        if (fromNode.type === 'reroute') {
          let cursor: GraphNode | undefined = fromNode;
          let guard = 0;
          while (cursor && cursor.type === 'reroute' && guard < 16) {
            const incoming = edges.find(e => e.to.node === cursor!.id);
            if (!incoming) break;
            const upstream = nodeById.get(incoming.from.node);
            if (!upstream) break;
            if (upstream.type !== 'reroute') {
              const sIdx = upstream.outputs.findIndex(o => o.name === incoming.from.output);
              originType = upstream.outputs[sIdx]?.type || originType;
              break;
            }
            cursor = upstream;
            guard += 1;
          }
        }
        const linkColor = edgeColorForSource(originType);
        ctx.strokeStyle = linkColor;
        ctx.lineWidth = lowQuality ? 1.5 : isHovered ? 3.5 : 2;
        if (isHovered) {
          ctx.shadowColor = linkColor + '88';
          ctx.shadowBlur = 10;
        }
        // Control points. For a normal node end the control point juts out
        // horizontally by cd. For a reroute end, mirror the neighbour around
        // the reroute centre so adjacent segments share a tangent.
        let c1: { x: number; y: number };
        let c2: { x: number; y: number };
        if (fromNode.type === 'reroute') {
          const neighbour = neighbourThroughReroute(fromNode.id, 'output');
          if (neighbour) {
            const dx = from.x - neighbour.x;
            const dy = from.y - neighbour.y;
            const len = Math.hypot(dx, dy) || 1;
            c1 = { x: from.x + (dx / len) * cd, y: from.y + (dy / len) * cd };
          } else {
            c1 = { x: from.x + cd, y: from.y };
          }
        } else {
          c1 = { x: from.x + cd, y: from.y };
        }
        if (toNode.type === 'reroute') {
          const neighbour = neighbourThroughReroute(toNode.id, 'input');
          if (neighbour) {
            const dx = to.x - neighbour.x;
            const dy = to.y - neighbour.y;
            const len = Math.hypot(dx, dy) || 1;
            c2 = { x: to.x + (dx / len) * cd, y: to.y + (dy / len) * cd };
          } else {
            c2 = { x: to.x - cd, y: to.y };
          }
        } else {
          c2 = { x: to.x - cd, y: to.y };
        }
        ctx.beginPath();
        ctx.moveTo(from.x, from.y);
        ctx.bezierCurveTo(c1.x, c1.y, c2.x, c2.y, to.x, to.y);
        ctx.stroke();
        ctx.shadowColor = 'transparent';
        ctx.shadowBlur = 0;
      }
    }

    // Temp link while dragging from an output
    if (currentLinkDrag) {
      const fromNode = graphNodesRef.current.find(n => n.id === currentLinkDrag.fromNodeId);
      if (fromNode) {
        const fy = fromNode.collapsed
          ? fromNode.y + NODE_HEADER_H / 2
          : fromNode.y + NODE_HEADER_H + NODE_PIN_H / 2 + currentLinkDrag.fromOutputIndex * NODE_PIN_H;
        const fx = fromNode.x + fromNode.width;
        const tx = currentMouseWorld.x;
        const ty = currentMouseWorld.y;
        const dist = Math.hypot(tx - fx, ty - fy);
        const cd = Math.max(30, dist * 0.25);
        ctx.strokeStyle = palette.accent;
        ctx.lineWidth = 2;
        ctx.setLineDash([5, 5]);
        ctx.beginPath();
        ctx.moveTo(fx, fy);
        ctx.bezierCurveTo(fx + cd, fy, tx - cd, ty, tx, ty);
        ctx.stroke();
        ctx.setLineDash([]);
        // Target cursor dot
        ctx.fillStyle = palette.accent;
        ctx.beginPath();
        ctx.arc(tx, ty, 4, 0, Math.PI * 2);
        ctx.fill();
      }
    }

    // Groups
    for (const g of groupsRef.current) {
      ctx.fillStyle = g.color + '33';
      roundRect(ctx, g.position[0], g.position[1], g.width, g.height, 6);
      ctx.fill();
      ctx.strokeStyle = g.selected ? g.color : (g.color + '66');
      ctx.lineWidth = g.selected ? 2.5 : 1.5;
      roundRect(ctx, g.position[0], g.position[1], g.width, g.height, 6);
      ctx.stroke();
      // Title bar
      ctx.fillStyle = g.color + '55';
      ctx.fillRect(g.position[0], g.position[1], g.width, 24);
      ctx.fillStyle = '#ffffff';
      ctx.font = '600 12px Inter, sans-serif';
      ctx.fillText(g.name, g.position[0] + 8, g.position[1] + 17);
      // Resize handle
      const hs = 8;
      ctx.fillStyle = g.color + 'cc';
      ctx.beginPath();
      ctx.moveTo(g.position[0] + g.width, g.position[1] + g.height);
      ctx.lineTo(g.position[0] + g.width - hs, g.position[1] + g.height);
      ctx.lineTo(g.position[0] + g.width, g.position[1] + g.height - hs);
      ctx.fill();
    }

    // Ghost outlines: where the dragged nodes started. Drawn under the live
    // nodes so users can compare the new position with the origin during a
    // drag. Only renders when the drag has actually moved.
    if (dragGhostsRef.current.length && dragMovedRef.current) {
      ctx.save();
      ctx.globalAlpha = 0.4;
      ctx.strokeStyle = palette.muted;
      ctx.setLineDash([5, 4]);
      ctx.lineWidth = 1.25;
      for (const ghost of dragGhostsRef.current) {
        if (ghost.isReroute) {
          const r = 10;
          const cx = ghost.x + ghost.w / 2;
          const cy = ghost.y + ghost.h / 2;
          ctx.beginPath();
          ctx.arc(cx, cy, r, 0, Math.PI * 2);
          ctx.stroke();
        } else {
          roundRect(ctx, ghost.x, ghost.y, ghost.w, ghost.h, ghost.radius);
          ctx.stroke();
        }
      }
      ctx.setLineDash([]);
      ctx.restore();
    }

    // Nodes
    for (const node of visibleNodes) {
      const isNote = node.type === 'note';
      const isVisualOnly = node.visualOnly;
      const isReroute = node.type === 'reroute';
      const nw = node.width;
      const nh = node.height;

      if (isReroute) {
        // Reroute: small circle with overlapping input/output
        const cx = node.x + nw / 2;
        const cy = node.y + nh / 2;
        const r = 10;
        if (allowShadows) {
          ctx.shadowColor = 'rgba(0,0,0,0.2)';
          ctx.shadowBlur = 6;
        }
        ctx.fillStyle = node.selected ? node.color : palette.border2;
        ctx.beginPath();
        ctx.arc(cx, cy, r, 0, Math.PI * 2);
        ctx.fill();
        ctx.shadowColor = 'transparent';
        ctx.shadowBlur = 0;
        ctx.strokeStyle = node.selected ? palette.accent : palette.muted;
        ctx.lineWidth = node.selected ? 2.5 : 1.5;
        ctx.beginPath();
        ctx.arc(cx, cy, r, 0, Math.PI * 2);
        ctx.stroke();
        // Inner dot
        ctx.fillStyle = node.color;
        ctx.beginPath();
        ctx.arc(cx, cy, 4, 0, Math.PI * 2);
        ctx.fill();
        continue;
      }

      const radius = nodeRadius(node);
      const isCard = node.shape === 'card';
      const isBox = node.shape === 'box';

      // Shadow
      if (allowShadows) {
        ctx.shadowColor = isCard ? 'rgba(0,0,0,0.22)' : (isBox ? 'rgba(0,0,0,0.08)' : 'rgba(0,0,0,0.15)');
        ctx.shadowBlur = isCard ? 14 : (isBox ? 3 : 8);
        ctx.shadowOffsetY = isCard ? 4 : (isBox ? 1 : 3);
      }

      // Body
      if (isNote) {
        ctx.fillStyle = isDark ? '#3f3820' : '#fef9c3';
      } else if (isCard) {
        ctx.fillStyle = palette.canvas;
      } else {
        ctx.fillStyle = palette.surface;
      }
      if (node.selected) ctx.fillStyle = palette.surface2;
      if (node.muted) ctx.globalAlpha = 0.5;
      roundRect(ctx, node.x, node.y, nw, nh, radius);
      ctx.fill();

      ctx.shadowColor = 'transparent';
      ctx.shadowBlur = 0;
      ctx.shadowOffsetY = 0;
      ctx.globalAlpha = 1;

      // Card shape: vertical colored stripe on the left edge (visible below the header)
      if (isCard && !isNote && !node.collapsed) {
        ctx.fillStyle = node.color;
        ctx.fillRect(node.x, node.y + NODE_HEADER_H, 3, nh - NODE_HEADER_H);
      }

      // Box shape: thin sharp border
      if (isBox && !isNote) {
        ctx.strokeStyle = palette.border;
        ctx.lineWidth = 1;
        roundRect(ctx, node.x + 0.5, node.y + 0.5, nw - 1, nh - 1, radius);
        ctx.stroke();
      }

      // Header
      ctx.fillStyle = isNote ? '#f59e0b' : node.color;
      if (node.collapsed) {
        roundRect(ctx, node.x, node.y, nw, NODE_HEADER_H, radius);
      } else {
        roundRect(ctx, node.x, node.y, nw, NODE_HEADER_H, { tl: radius, tr: radius, bl: 0, br: 0 });
      }
      ctx.fill();

      // Collapse indicator
      if (!isReroute) {
        ctx.fillStyle = 'rgba(255,255,255,0.85)';
        ctx.font = '11px Inter, sans-serif';
        ctx.fillText(node.collapsed ? '▸' : '▾', node.x + 6, node.y + 20);
      }

      // Title
      ctx.fillStyle = '#ffffff';
      ctx.font = '600 12px Inter, sans-serif';
      const title = node.title;
      const maxTitleChars = node.collapsed ? 20 : Math.floor((nw - (isNote ? 20 : 36)) / 7);
      ctx.fillText(title.length > maxTitleChars ? title.slice(0, maxTitleChars) + '...' : title, node.x + (isNote ? 10 : 22), node.y + 20);

      // Compact metadata badges in the title bar.
      if (!isNote && !lowQuality) {
        const badges: string[] = [];
        if (node.pinned) badges.push('L');
        if (node.meta?.version) badges.push(String(node.meta.version).slice(0, 8));
        if (node.meta?.experimental) badges.push('EXP');
        let badgeX = node.x + nw - 12;
        ctx.font = '700 8px Inter, sans-serif';
        for (const badge of badges.reverse()) {
          const bw = Math.min(48, ctx.measureText(badge).width + 8);
          badgeX -= bw;
          ctx.fillStyle = 'rgba(255,255,255,0.22)';
          roundRect(ctx, badgeX, node.y + 8, bw, 14, 7);
          ctx.fill();
          ctx.fillStyle = '#ffffff';
          ctx.fillText(badge, badgeX + 4, node.y + 18);
          badgeX -= 4;
        }
      }

      if (node.collapsed && !isVisualOnly) {
        // Collapsed: show first connected input on left, first connected output on right
        const firstConnectedIn = node.inputs.findIndex(i => i.connected);
        const firstConnectedOut = node.outputs.findIndex(o => o.connected);
        const slotY = node.y + NODE_HEADER_H / 2;
        if (firstConnectedIn >= 0) {
          const inp = node.inputs[firstConnectedIn];
          ctx.fillStyle = edgeColorForSource(inp.type);
          ctx.beginPath();
          ctx.arc(node.x, slotY, 5, 0, Math.PI * 2);
          ctx.fill();
        }
        if (firstConnectedOut >= 0) {
          const out = node.outputs[firstConnectedOut];
          ctx.fillStyle = edgeColorForSource(out.type);
          ctx.beginPath();
          ctx.arc(node.x + nw, slotY, 5, 0, Math.PI * 2);
          ctx.fill();
        }
      }

      if (!node.collapsed) {
        if (isNote) {
          // Note body text
          const text = String(node.params?.text || '');
          ctx.fillStyle = palette.text;
          ctx.font = '11px Inter, sans-serif';
          const maxCharsPerLine = Math.floor((nw - 20) / 6.5);
          const lines = text.split('\n').flatMap(line => {
            if (line.length <= maxCharsPerLine) return [line];
            const chunks: string[] = [];
            for (let i = 0; i < line.length; i += maxCharsPerLine) {
              chunks.push(line.slice(i, i + maxCharsPerLine));
            }
            return chunks;
          });
          const maxLines = Math.floor((nh - NODE_HEADER_H - 16) / 15);
          lines.slice(0, maxLines).forEach((line, i) => {
            ctx.fillText(line, node.x + 10, node.y + NODE_HEADER_H + 16 + i * 15);
          });
        } else {
          // Inputs
          node.inputs.forEach((inp, i) => {
            const py = node.y + NODE_HEADER_H + NODE_PIN_H / 2 + i * NODE_PIN_H;
            const isHovered = currentHoveredSlot?.nodeId === node.id && currentHoveredSlot?.type === 'input' && currentHoveredSlot?.index === i;
            const pinR = isHovered ? 6 : 5;
            ctx.fillStyle = inp.connected ? edgeColorForSource(inp.type) : palette.border2;
            if (isHovered) ctx.fillStyle = palette.accent;
            ctx.beginPath();
            ctx.arc(node.x, py, pinR, 0, Math.PI * 2);
            ctx.fill();
            ctx.fillStyle = palette.text;
            ctx.font = '10px Inter, sans-serif';
            ctx.fillText(inp.name, node.x + 10, py + 3);
          });

          // Outputs
          node.outputs.forEach((out, i) => {
            const py = node.y + NODE_HEADER_H + NODE_PIN_H / 2 + i * NODE_PIN_H;
            const isHovered = currentHoveredSlot?.nodeId === node.id && currentHoveredSlot?.type === 'output' && currentHoveredSlot?.index === i;
            const pinR = isHovered ? 6 : 5;
            ctx.fillStyle = out.connected ? edgeColorForSource(out.type) : palette.border2;
            if (isHovered) ctx.fillStyle = palette.accent;
            ctx.beginPath();
            ctx.arc(node.x + nw, py, pinR, 0, Math.PI * 2);
            ctx.fill();
            ctx.fillStyle = palette.text;
            ctx.font = '10px Inter, sans-serif';
            const tw = ctx.measureText(out.name).width;
            ctx.fillText(out.name, node.x + nw - tw - 10, py + 3);
          });

          // Track widget hit areas (kept for legacy slider/select drag handlers).
          // Visible rendering happens entirely via the DOM overlay below, so the
          // canvas itself no longer draws toggles/sliders/combos/etc.
          const nodeMeta = node.meta;
          const metaRequired = nodeMeta?.input_types?.required || {};
          const metaOptional = nodeMeta?.input_types?.optional || {};
          const allSpecs = { ...metaRequired, ...metaOptional };
          const widgetY0 = node.y + NODE_HEADER_H + Math.max(node.inputs.length, node.outputs.length, 1) * NODE_PIN_H + 6;
          let wy = widgetY0;
          const widgetH = 18;
          const widgetGap = 2;
          const wx = node.x + 8;
          const ww = nw - 16;
          const nodeWidgets: Array<{ name: string; type: string; x: number; y: number; w: number; h: number }> = [];

          for (const [key, spec] of Object.entries(allSpecs)) {
            const s = spec as any;
            let wtype = 'text';
            if (s?.type === 'BOOLEAN') wtype = 'toggle';
            else if (s?.options && s.options.length > 0) wtype = 'combo';
            else if ((s?.type === 'INT' || s?.type === 'FLOAT') && s?.display === 'slider') wtype = 'slider';
            else if (s?.type === 'INT' || s?.type === 'FLOAT') wtype = 'number';
            else if (s?.type === 'STRING' && !s?.forceInput) wtype = 'text';
            else continue;
            nodeWidgets.push({ name: key, type: wtype, x: wx, y: wy, w: ww, h: widgetH });
            wy += widgetH + widgetGap;
          }
          widgetsRef.current.set(node.id, nodeWidgets);
          if (nodeWidgets.length === 0) {
            const paramEntries = Object.entries(node.params || {})
              .filter(([key, value]) => key !== 'text' && value !== undefined && value !== null && value !== '')
              .slice(0, 3);
            let summaryY = widgetY0 + 2;
            if (paramEntries.length > 0) {
              ctx.font = '9px Inter, sans-serif';
              for (const [key, value] of paramEntries) {
                const label = key.replace(/_/g, ' ');
                const brief = `${label}: ${formatNodeParamValue(value)}`;
                ctx.fillStyle = isDark ? '#334155' : '#f1f5f9';
                roundRect(ctx, wx, summaryY - 2, ww, 13, 5);
                ctx.fill();
                ctx.fillStyle = isDark ? '#cbd5e1' : '#475569';
                ctx.fillText(brief.length > 34 ? `${brief.slice(0, 31)}...` : brief, wx + 5, summaryY + 8);
                summaryY += 15;
              }
            } else if (node.meta?.description) {
              const description = node.meta.description;
              ctx.fillStyle = isDark ? '#94a3b8' : '#64748b';
              ctx.font = '9px Inter, sans-serif';
              const maxChars = Math.max(24, Math.floor((ww - 4) / 5.3));
              const lineA = description.slice(0, maxChars);
              const lineB = description.slice(maxChars, maxChars * 2);
              ctx.fillText(lineA, wx + 2, summaryY + 8);
              if (lineB) ctx.fillText(`${lineB.slice(0, maxChars - 3)}...`, wx + 2, summaryY + 21);
            }
          }
        }
      }

      // Border
      const statusOutline = node.status === 'running'
        ? '#22c55e'
        : node.status === 'error'
          ? '#ef4444'
          : null;
      const missingDependency = missingDependencyNodeIdsRef.current?.has(node.id);
      ctx.strokeStyle = statusOutline
        || (missingDependency ? '#f97316' : node.selected ? node.color : (isDark ? '#334155' : '#e2e8f0'));
      ctx.lineWidth = statusOutline || missingDependency ? 3 : node.selected ? 2 : 1;
      roundRect(ctx, node.x, node.y, nw, nh, radius);
      ctx.stroke();

      const nodeCollaborators = collabUsersRef.current.filter(user =>
        user.selection?.nodeIds?.includes(node.id) || user.dragOwnership?.nodeId === node.id
      );
      nodeCollaborators.forEach((user, index) => {
        ctx.strokeStyle = user.user.color;
        ctx.lineWidth = user.dragOwnership?.nodeId === node.id ? 3 : 2;
        ctx.setLineDash(user.dragOwnership?.nodeId === node.id ? [] : [6, 3]);
        roundRect(ctx, node.x - 3 - index * 2, node.y - 3 - index * 2, nw + 6 + index * 4, nh + 6 + index * 4, 10);
        ctx.stroke();
        ctx.setLineDash([]);

        const label = user.user.name;
        ctx.font = '600 10px Inter, sans-serif';
        const labelWidth = Math.min(140, ctx.measureText(label).width + 23);
        const labelX = node.x + 6;
        const labelY = node.y - 22 - index * 21;
        ctx.fillStyle = user.user.color;
        roundRect(ctx, labelX, labelY, labelWidth, 17, 8);
        ctx.fill();
        ctx.fillStyle = '#ffffff';
        ctx.beginPath();
        ctx.arc(labelX + 8, labelY + 8.5, 3, 0, Math.PI * 2);
        ctx.fill();
        ctx.fillText(label.length > 18 ? `${label.slice(0, 18)}...` : label, labelX + 15, labelY + 12);
      });

      // Status badge
      if (node.status && !isVisualOnly) {
        const statusColors: Record<string, string> = {
          pending: '#94a3b8', running: '#22c55e', completed: '#22c55e',
          error: '#ef4444', cached: '#a855f7', skipped: '#f97316',
        };
        const sc = statusColors[node.status] || '#94a3b8';
        ctx.fillStyle = sc;
        ctx.beginPath();
        ctx.arc(node.x + nw - 8, node.y + 10, 5, 0, Math.PI * 2);
        ctx.fill();
        ctx.strokeStyle = isDark ? '#1e293b' : '#ffffff';
        ctx.lineWidth = 1.5;
        ctx.beginPath();
        ctx.arc(node.x + nw - 8, node.y + 10, 5, 0, Math.PI * 2);
        ctx.stroke();
      }

      // Inline progress bar for running nodes. We don't have per-node duration
      // estimates from the backend yet, so we render an indeterminate sweep —
      // a 30%-wide highlight bouncing back and forth on a 1.4s loop. The bar
      // sits just under the header so it doesn't fight with widgets.
      if (node.status === 'running' && !isVisualOnly && !isReroute && !isNote) {
        const barY = node.y + NODE_HEADER_H - 2;
        const barH = 2.5;
        const t = (performance.now() / 1400) % 1;
        const phase = t < 0.5 ? t * 2 : 2 - t * 2; // 0->1->0 ping-pong
        const knobW = nw * 0.3;
        const knobX = node.x + (nw - knobW) * phase;
        ctx.fillStyle = isDark ? 'rgba(34,197,94,0.18)' : 'rgba(34,197,94,0.22)';
        ctx.fillRect(node.x, barY, nw, barH);
        ctx.fillStyle = '#22c55e';
        ctx.fillRect(knobX, barY, knobW, barH);

        // "3/12 · 6s" caption rendered in the header strip so the user can see
        // queue position + how long the node has been running without scrolling
        // to the console.
        const progress = nodeProgressMapRef.current?.get(node.id);
        if (progress) {
          const parts: string[] = [];
          if (progress.total > 0) parts.push(`${progress.current}/${progress.total}`);
          if (progress.startedAt > 0) {
            const elapsed = Math.max(0, Math.floor((Date.now() - progress.startedAt) / 1000));
            parts.push(elapsed >= 60 ? `${Math.floor(elapsed / 60)}m ${elapsed % 60}s` : `${elapsed}s`);
          }
          if (parts.length) {
            ctx.font = '600 9px Inter, sans-serif';
            ctx.fillStyle = 'rgba(255,255,255,0.85)';
            const text = parts.join(' · ');
            const textWidth = ctx.measureText(text).width;
            ctx.fillText(text, node.x + nw - textWidth - 22, node.y + 20);
          }
        }
      }

      // Resize handle (bottom-right corner)
      if (!isReroute) {
        ctx.fillStyle = isDark ? '#475569' : '#cbd5e1';
        ctx.fillRect(node.x + nw - 6, node.y + nh - 6, 6, 6);
        ctx.fillStyle = isDark ? '#94a3b8' : '#64748b';
        ctx.fillRect(node.x + nw - 4, node.y + nh - 4, 4, 4);
      }
    }

    ctx.restore();

    // Selection box (screen coords)
    if (selectBox) {
      ctx.save();
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.strokeStyle = palette.accent;
      ctx.lineWidth = 1;
      ctx.setLineDash([4, 4]);
      ctx.strokeRect(selectBox.x, selectBox.y, selectBox.w, selectBox.h);
      ctx.fillStyle = palette.accent;
      ctx.globalAlpha = 0.08;
      ctx.fillRect(selectBox.x, selectBox.y, selectBox.w, selectBox.h);
      ctx.globalAlpha = 1;
      ctx.setLineDash([]);
      ctx.restore();
    }

    const remoteBoxes = collabUsersRef.current.filter(u => u.selection?.box);
    if (remoteBoxes.length > 0) {
      ctx.save();
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      for (const user of remoteBoxes) {
        const box = user.selection.box!;
        const x = box.x * scale + offset.x;
        const y = box.y * scale + offset.y;
        const bw = box.w * scale;
        const bh = box.h * scale;
        ctx.strokeStyle = user.user.color;
        ctx.lineWidth = 1.5;
        ctx.setLineDash([6, 4]);
        ctx.strokeRect(x, y, bw, bh);
        ctx.fillStyle = `${user.user.color}1a`;
        ctx.fillRect(x, y, bw, bh);
      }
      ctx.setLineDash([]);
      ctx.restore();
    }
  }, [edges, offset, scale, linksHidden, selectBox, panning, groupDragging, groupResizing, resizingNode, nodeRadius]);
  useEffect(() => { drawRef.current = draw; }, [draw]);

  // Keyboard shortcuts
  useEffect(() => {
    const handleKeyDown = async (e: KeyboardEvent) => {
      const target = e.target as HTMLElement;
      if (target instanceof HTMLInputElement || target instanceof HTMLTextAreaElement || target.isContentEditable) return;
      // Suppress every canvas shortcut while a modal/dropdown/popover is open
      // so Backspace inside a dialog cannot delete the user's selection and
      // Ctrl+A inside a settings search cannot select every node.
      if (hasOpenOverlay()) return;

      // Scope canvas shortcuts to the canvas host. If focus is on a panel,
      // top-bar button, or other UI chrome, Backspace/Ctrl+A/etc. should not
      // affect the graph. document.body == "nothing focused" counts as
      // canvas-eligible, matching how users typically interact with the
      // canvas (click background, then keyboard).
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

      // Copy
      if (isCtrl && key === 'c') {
        e.preventDefault();
        const currentGraphNodes = graphNodesRef.current;
        const currentNodes = nodesRef.current;
        const selectedIds = new Set(currentGraphNodes.filter(n => n.selected).map(n => n.id));
        if (selectedIds.size === 0) return;
        const nodesToCopy = currentNodes.filter(n => selectedIds.has(n.id));
        const edgesToCopy = edgesRef.current.filter(e => selectedIds.has(e.from.node) && selectedIds.has(e.to.node));
        // External edges: link the copied subgraph to nodes that did NOT make
        // it into the selection. Stored under their own key so plain Ctrl+V
        // ignores them and Ctrl+Shift+V can re-attach the originals.
        const incomingEdges = edgesRef.current.filter(e => !selectedIds.has(e.from.node) && selectedIds.has(e.to.node));
        const outgoingEdges = edgesRef.current.filter(e => selectedIds.has(e.from.node) && !selectedIds.has(e.to.node));
        const payload = JSON.stringify({
          nodes: nodesToCopy,
          edges: edgesToCopy,
          externalIncoming: incomingEdges,
          externalOutgoing: outgoingEdges,
        });
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

      // Paste (Ctrl+V replaces with copy, Ctrl+Shift+V keeps external links)
      if (isCtrl && key === 'v') {
        e.preventDefault();
        const includeExternal = e.shiftKey;
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
            // Try parsing as a raw workflow JSON object
            const raw = JSON.parse(text);
            if (raw.nodes && Array.isArray(raw.nodes)) {
              payload = { nodes: raw.nodes, edges: raw.edges || [] };
            }
          } else if (text.trim().startsWith('[')) {
            // Try parsing as a raw node array
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
            return {
              ...n,
              id: newId,
              position: [n.position[0] + 40, n.position[1] + 40] as [number, number],
            };
          });
          const pastedEdges: WorkflowEdge[] = (payload.edges || []).map((e: WorkflowEdge, i: number) => ({
            ...e,
            id: `${e.id}_${timestamp}_${i}`,
            from: { ...e.from, node: oldToNew.get(e.from.node) || e.from.node },
            to: { ...e.to, node: oldToNew.get(e.to.node) || e.to.node },
          }));

          // Ctrl+Shift+V: re-attach edges from/to the original neighbours when
          // those neighbours are still on the canvas. External edges to nodes
          // that no longer exist are silently dropped.
          const externalEdges: WorkflowEdge[] = [];
          if (includeExternal) {
            const incoming = payload.externalIncoming || [];
            const outgoing = payload.externalOutgoing || [];
            incoming.forEach((edge, i) => {
              if (!currentNodeIds.has(edge.from.node)) return;
              const remappedTo = oldToNew.get(edge.to.node);
              if (!remappedTo) return;
              externalEdges.push({
                ...edge,
                id: `${edge.id}_${timestamp}_inc${i}`,
                from: { ...edge.from },
                to: { ...edge.to, node: remappedTo },
              });
            });
            outgoing.forEach((edge, i) => {
              if (!currentNodeIds.has(edge.to.node)) return;
              const remappedFrom = oldToNew.get(edge.from.node);
              if (!remappedFrom) return;
              externalEdges.push({
                ...edge,
                id: `${edge.id}_${timestamp}_out${i}`,
                from: { ...edge.from, node: remappedFrom },
                to: { ...edge.to },
              });
            });
          }

          pendingSelectionRef.current = new Set(pastedNodes.map(n => n.id));
          onNodesChangeRef.current([...currentNodes, ...pastedNodes]);
          onEdgesChangeRef.current([...edgesRef.current, ...pastedEdges, ...externalEdges]);
          onPushHistoryRef.current();
        } catch { /* ignore */ }
        return;
      }

      // Cut
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

      // Delete / Backspace
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

      // Select All
      if (isCtrl && key === 'a') {
        e.preventDefault();
        setGraphNodes(prev => prev.map(n => ({ ...n, selected: true })));
        return;
      }

      // Undo
      if (isCtrl && key === 'z' && !e.shiftKey) {
        e.preventDefault();
        onUndoRef.current();
        flashAction('Undo');
        return;
      }

      // Redo
      if ((isCtrl && key === 'y') || (isCtrl && key === 'z' && e.shiftKey)) {
        e.preventDefault();
        onRedoRef.current();
        flashAction('Redo');
        return;
      }

      // Collapse selected nodes (Alt+C)
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

      // Group selected nodes (Ctrl+G)
      if (isCtrl && key === 'g') {
        e.preventDefault();
        const currentGraphNodes = graphNodesRef.current;
        const currentGroups = groupsRef.current;
        const selected = currentGraphNodes.filter(n => n.selected);
        if (selected.length > 0) {
          const newGroup = createGroupFromNodes(selected);
          onGroupsChangeRef.current([...currentGroups, newGroup]);
          onPushHistoryRef.current();
        }
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  // Animation loop
  useEffect(() => {
    let raf: number;
    const loop = () => { draw(); raf = requestAnimationFrame(loop); };
    raf = requestAnimationFrame(loop);
    return () => cancelAnimationFrame(raf);
  }, [draw]);

  // Resize
  useEffect(() => {
    const handleResize = () => {
      const canvas = canvasRef.current;
      if (!canvas) return;
      const parent = canvas.parentElement;
      if (!parent) return;
      const nextSize = { w: parent.clientWidth, h: parent.clientHeight };
      sizeRef.current = nextSize;
      setCanvasSize(prev => (prev.w === nextSize.w && prev.h === nextSize.h ? prev : nextSize));
    };
    handleResize();
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

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
    const x = snapToGrid ? Math.round(world.x / 20) * 20 : world.x;
    const y = snapToGrid ? Math.round(world.y / 20) * 20 : world.y;
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
  }, [nodes, onNodesChange, onPushHistory, toWorld, snapToGrid]);

  // Mouse handlers
  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    // Cancel link drag with any click
    if (linkDragRef.current && e.button === 0) {
      setLinkDrag(null);
      setHoveredSlot(null);
      return;
    }

    // If any menu is open, close it and don't start selection/panning
    if (contextMenu || canvasMenu || palettePos || groupContextMenu) {
      setContextMenu(null);
      setCanvasMenu(null);
      setPalettePos(null);
      setGroupContextMenu(null);
      return;
    }
    if (e.button === 1 || (e.button === 0 && e.altKey)) {
      dragMovedRef.current = false;
      dragCommitNeededRef.current = false;
      dragOwnershipStartedRef.current = false;
      setPanning(true);
      setDragStart({ x: e.clientX, y: e.clientY });
      return;
    }
    if (e.button !== 0) return;
    const rect = canvasRef.current!.getBoundingClientRect();
    const cx = e.clientX - rect.left;
    const cy = e.clientY - rect.top;
    const world = toWorld(cx, cy);

    // Check if clicked on a node
    const clicked = [...graphNodes].reverse().find(n => {
      if (n.type === 'reroute') {
        const cx = n.x + n.width / 2;
        const cy = n.y + n.height / 2;
        return Math.hypot(world.x - cx, world.y - cy) < 12;
      }
      return world.x >= n.x && world.x <= n.x + n.width &&
        world.y >= n.y && world.y <= n.y + n.height;
    });

    if (clicked) {
      // Shift+click on a connected input slot detaches the link and lets the
      // user re-route the source's output to a new target. Mirrors ComfyUI.
      if (e.shiftKey && clicked.inputs.length > 0 && !clicked.visualOnly && !clicked.collapsed) {
        for (let i = 0; i < clicked.inputs.length; i += 1) {
          if (!clicked.inputs[i].connected) continue;
          const slotY = clicked.y + NODE_HEADER_H + NODE_PIN_H / 2 + i * NODE_PIN_H;
          const dist = Math.hypot(world.x - clicked.x, world.y - slotY);
          if (dist > 12) continue;
          const existingEdge = edges.find(edge => edge.to.node === clicked.id && edge.to.input === clicked.inputs[i].name);
          if (!existingEdge) break;
          const sourceNode = graphNodes.find(n => n.id === existingEdge.from.node);
          if (!sourceNode) break;
          const sourceOutIdx = sourceNode.outputs.findIndex(o => o.name === existingEdge.from.output);
          if (sourceOutIdx < 0) break;
          onEdgesChange(edges.filter(edge => edge.id !== existingEdge.id));
          setLinkDrag({
            fromNodeId: sourceNode.id,
            fromOutputIndex: sourceOutIdx,
            fromOutputName: existingEdge.from.output,
            fromOutputType: sourceNode.outputs[sourceOutIdx].type,
          });
          return;
        }
      }
      // Check output slot hit (for link drag)
      if (clicked.outputs.length > 0 && !clicked.visualOnly) {
        if (clicked.collapsed) {
          const firstConnectedOut = clicked.outputs.findIndex(o => o.connected);
          const outIdx = firstConnectedOut >= 0 ? firstConnectedOut : 0;
          const slotY = clicked.y + NODE_HEADER_H / 2;
          const dist = Math.hypot(world.x - (clicked.x + clicked.width), world.y - slotY);
          if (dist < 12) {
            setLinkDrag({ fromNodeId: clicked.id, fromOutputIndex: outIdx, fromOutputName: clicked.outputs[outIdx].name, fromOutputType: clicked.outputs[outIdx].type });
            return;
          }
        } else {
          for (let i = 0; i < clicked.outputs.length; i++) {
            const slotY = clicked.y + NODE_HEADER_H + NODE_PIN_H / 2 + i * NODE_PIN_H;
            const dist = Math.hypot(world.x - (clicked.x + clicked.width), world.y - slotY);
            if (dist < 12) {
              setLinkDrag({ fromNodeId: clicked.id, fromOutputIndex: i, fromOutputName: clicked.outputs[i].name, fromOutputType: clicked.outputs[i].type });
              return;
            }
          }
        }
      }

      // Check widget hit
      const nodeWidgets = widgetsRef.current.get(clicked.id) || [];
      for (const w of nodeWidgets) {
        if (world.x >= w.x && world.x <= w.x + w.w && world.y >= w.y && world.y <= w.y + w.h) {
          if (w.type === 'toggle') {
            const newVal = !clicked.params[w.name];
            handleNodeParamChange(clicked.id, w.name, newVal);
            onPushHistory();
          } else if (w.type === 'combo') {
            const spec = clicked.meta?.input_types?.required?.[w.name] || clicked.meta?.input_types?.optional?.[w.name];
            const options = (spec as any)?.options || [];
            const currentIdx = options.indexOf(String(clicked.params[w.name] ?? options[0]));
            const nextIdx = (currentIdx + 1) % options.length;
            handleNodeParamChange(clicked.id, w.name, options[nextIdx]);
            onPushHistory();
          } else if (w.type === 'slider') {
            setActiveWidget({ nodeId: clicked.id, name: w.name });
            setDragStart({ x: e.clientX, y: e.clientY });
          }
          return;
        }
      }

      // Check node resize handle
      if (world.x >= clicked.x + clicked.width - 10 && world.y >= clicked.y + clicked.height - 10) {
        dragMovedRef.current = false;
        dragCommitNeededRef.current = false;
        dragOwnershipStartedRef.current = false;
        setResizingNode(clicked.id);
        setDragStart({ x: e.clientX, y: e.clientY });
        return;
      }

      const inCollapseArea = !clicked.visualOnly && world.x >= clicked.x && world.x <= clicked.x + 20 && world.y >= clicked.y && world.y <= clicked.y + NODE_HEADER_H;
      if (inCollapseArea) {
        dragMovedRef.current = false;
        dragCommitNeededRef.current = true;
        dragOwnershipStartedRef.current = false;
        setGraphNodes(prev => prev.map(n => {
          if (n.id !== clicked.id) return n;
          const newCollapsed = !n.collapsed;
          return { ...n, collapsed: newCollapsed, height: calcNodeHeight(n.meta, newCollapsed, n.params) };
        }));
        setDragging(clicked.id);
        isDraggingRef.current = true;
        setDragStart({ x: e.clientX, y: e.clientY });
        setContextMenu(null);
        setPalettePos(null);
        return;
      }
      let willBeSelectedIds: Set<string>;
      // Shift+click toggles, Ctrl/Cmd+click adds to selection. Plain click
      // replaces. Treating Cmd separately from Shift mirrors ComfyUI and lets
      // users grow a selection without un-selecting nodes they already had.
      const additive = e.shiftKey || e.ctrlKey || e.metaKey;
      if (additive) {
        const next = graphNodes.map(n => {
          if (n.id !== clicked.id) return n;
          // Shift toggles, Cmd/Ctrl additively selects (never de-selects).
          if (e.ctrlKey || e.metaKey) return { ...n, selected: true };
          return { ...n, selected: !n.selected };
        });
        setGraphNodes(next);
        willBeSelectedIds = new Set(next.filter(n => n.selected).map(n => n.id));
        publishCollabSelection({ nodeIds: Array.from(willBeSelectedIds), box: null });
      } else {
        setGraphNodes(prev => prev.map(n => ({ ...n, selected: n.id === clicked.id })));
        willBeSelectedIds = new Set([clicked.id]);
        publishCollabSelection({ nodeIds: [clicked.id], box: null });
      }
      dragMovedRef.current = false;
      dragCommitNeededRef.current = false;
      dragOwnershipStartedRef.current = false;
      // Capture origin rects for ghost outlines during the drag.
      dragGhostsRef.current = graphNodesRef.current
        .filter(n => willBeSelectedIds.has(n.id) && !n.pinned)
        .map(n => ({
          id: n.id,
          x: n.x,
          y: n.y,
          w: n.width,
          h: n.height,
          radius: nodeRadius(n),
          isReroute: n.type === 'reroute',
        }));
      setDragging(clicked.id);
      isDraggingRef.current = true;
      setDragStart({ x: e.clientX, y: e.clientY });
    } else {
      // Check group resize handle (in screen coords for easier grabbing)
      for (const g of [...groups].reverse()) {
        const p = fromWorld(g.position[0], g.position[1]);
        const gw = g.width * scale;
        const gh = g.height * scale;
        const hs = 8;
        if (cx >= p.x + gw - hs && cx <= p.x + gw && cy >= p.y + gh - hs && cy <= p.y + gh) {
          dragMovedRef.current = false;
          dragCommitNeededRef.current = false;
          dragOwnershipStartedRef.current = false;
          setGroupResizing(g.id);
          setDragStart({ x: e.clientX, y: e.clientY });
          setContextMenu(null);
          setPalettePos(null);
          return;
        }
      }
      // Check group title bar (only title bar is draggable, matching ComfyUI)
      const GROUP_TITLE_H = 24;
      for (const g of [...groups].reverse()) {
        if (world.x >= g.position[0] && world.x <= g.position[0] + g.width &&
            world.y >= g.position[1] && world.y <= g.position[1] + GROUP_TITLE_H) {
          if (e.shiftKey) {
            onGroupsChange(groups.map(gg => gg.id === g.id ? { ...gg, selected: !gg.selected } : gg));
          } else {
            onGroupsChange(groups.map(gg => ({ ...gg, selected: gg.id === g.id })));
            setGraphNodes(prev => prev.map(n => ({ ...n, selected: false })));
          }
          setGroupDragging(g.id);
          dragMovedRef.current = false;
          dragCommitNeededRef.current = false;
          dragOwnershipStartedRef.current = false;
          const containedIds = getNodesInGroup(g, graphNodes);
          groupDragNodesRef.current = containedIds;
          groupDragStartRef.current = {
            groupId: g.id,
            startPos: [...g.position] as [number, number],
            nodeStarts: new Map(graphNodes.filter(n => containedIds.includes(n.id)).map(n => [n.id, [n.x, n.y] as [number, number]])),
          };
          setDragStart({ x: e.clientX, y: e.clientY });
          setContextMenu(null);
          setPalettePos(null);
          return;
        }
      }
      // Check if click is inside any group body (not title bar) — deselect group and start marquee
      const clickedGroupBody = [...groups].reverse().find(g =>
        world.x >= g.position[0] && world.x <= g.position[0] + g.width &&
        world.y >= g.position[1] + 24 && world.y <= g.position[1] + g.height
      );
      if (clickedGroupBody && clickedGroupBody.selected) {
        onGroupsChange(groups.map(g => ({ ...g, selected: false })));
      }
      // Start selection box
      setGraphNodes(prev => prev.map(n => e.ctrlKey ? n : { ...n, selected: false }));
      if (!e.ctrlKey) {
        onGroupsChange(groups.map(g => ({ ...g, selected: false })));
        publishCollabSelection({ nodeIds: [], box: null });
      }
      setSelectBox({ x: cx, y: cy, w: 0, h: 0 });
      setDragStart({ x: cx, y: cy });
      const startWorld = toWorld(cx, cy);
      publishCollabSelection({ nodeIds: [], box: { x: startWorld.x, y: startWorld.y, w: 0, h: 0 } });
    }
    setContextMenu(null);
    setPalettePos(null);
  }, [graphNodes, toWorld, fromWorld, scale, contextMenu, canvasMenu, palettePos, groupContextMenu, groups, publishCollabSelection]);

  const handleMouseMove = useCallback((e: React.MouseEvent) => {
    const rect = canvasRef.current?.getBoundingClientRect();
    const cx = rect ? e.clientX - rect.left : e.clientX;
    const cy = rect ? e.clientY - rect.top : e.clientY;
    const world = toWorld(cx, cy);
    setMouseWorld(world);
    onCollabCursor?.({ x: cx, y: cy, worldX: world.x, worldY: world.y, visible: true });
    mouseWorldRef.current = world;

    const hoveredNode = [...graphNodes].reverse().find(n => {
      if (n.type === 'reroute') {
        const rx = n.x + n.width / 2;
        const ry = n.y + n.height / 2;
        return Math.hypot(world.x - rx, world.y - ry) < 12;
      }
      return world.x >= n.x && world.x <= n.x + n.width &&
        world.y >= n.y && world.y <= n.y + n.height;
    });
    setHoveredNodeId(hoveredNode?.id ?? null);

    // Slot hover detection
    let foundSlot: { nodeId: string; type: 'input' | 'output'; index: number } | null = null;
    const linkOutputType = linkDragRef.current?.fromOutputType;
    for (const node of graphNodes) {
      if (node.visualOnly) continue;
      if (node.collapsed) {
        // Collapsed: only first connected slot (or first slot) is visible at header center
        const firstConnectedIn = node.inputs.findIndex(i => i.connected);
        const inIdx = firstConnectedIn >= 0 ? firstConnectedIn : 0;
        const slotY = node.y + NODE_HEADER_H / 2;
        const inDist = Math.hypot(world.x - node.x, world.y - slotY);
        if (inDist < 12 && node.inputs.length > 0) {
          if (linkOutputType && node.inputs[inIdx].type !== linkOutputType && node.inputs[inIdx].type !== '*') {
            /* incompatible, skip */
          } else {
            foundSlot = { nodeId: node.id, type: 'input', index: inIdx };
            break;
          }
        }
        if (!linkDragRef.current) {
          const firstConnectedOut = node.outputs.findIndex(o => o.connected);
          const outIdx = firstConnectedOut >= 0 ? firstConnectedOut : 0;
          const outDist = Math.hypot(world.x - (node.x + node.width), world.y - slotY);
          if (outDist < 12 && node.outputs.length > 0) {
            foundSlot = { nodeId: node.id, type: 'output', index: outIdx };
            break;
          }
        }
        continue;
      }
      // Input slots
      for (let i = 0; i < node.inputs.length; i++) {
        const slotY = node.y + NODE_HEADER_H + NODE_PIN_H / 2 + i * NODE_PIN_H;
        const dist = Math.hypot(world.x - node.x, world.y - slotY);
        if (dist < 12) {
          // Type compatibility check during link drag
          if (linkOutputType && node.inputs[i].type !== linkOutputType && node.inputs[i].type !== '*') {
            continue;
          }
          foundSlot = { nodeId: node.id, type: 'input', index: i };
          break;
        }
      }
      if (foundSlot) break;
      // Output slots (only if not link dragging)
      if (!linkDragRef.current) {
        for (let i = 0; i < node.outputs.length; i++) {
          const slotY = node.y + NODE_HEADER_H + NODE_PIN_H / 2 + i * NODE_PIN_H;
          const dist = Math.hypot(world.x - (node.x + node.width), world.y - slotY);
          if (dist < 12) {
            foundSlot = { nodeId: node.id, type: 'output', index: i };
            break;
          }
        }
      }
      if (foundSlot) break;
    }
    setHoveredSlot(foundSlot);

    // Link hover detection
    let foundLink: string | null = null;
    for (const edge of edges) {
      const fromNode = graphNodes.find(n => n.id === edge.from.node);
      const toNode = graphNodes.find(n => n.id === edge.to.node);
      if (!fromNode || !toNode) continue;
      const fromOutIndex = fromNode.outputs.findIndex(o => o.name === edge.from.output);
      const toInIndex = toNode.inputs.findIndex(i => i.name === edge.to.input);
      const fy = fromNode.collapsed
        ? fromNode.y + NODE_HEADER_H / 2
        : fromNode.y + NODE_HEADER_H + NODE_PIN_H / 2 + (fromOutIndex >= 0 ? fromOutIndex : 0) * NODE_PIN_H;
      const ty = toNode.collapsed
        ? toNode.y + NODE_HEADER_H / 2
        : toNode.y + NODE_HEADER_H + NODE_PIN_H / 2 + (toInIndex >= 0 ? toInIndex : 0) * NODE_PIN_H;
      const fx = fromNode.x + fromNode.width;
      const tx = toNode.x;
      const dist = Math.hypot(tx - fx, ty - fy);
      const cd = Math.max(30, dist * 0.25);
      if (pointNearBezier(fx, fy, fx + cd, fy, tx - cd, ty, tx, ty, world.x, world.y, 8)) {
        foundLink = edge.id;
        break;
      }
    }
    setHoveredLink(foundLink);

    // If link dragging, just update mouse position (drawing handled in draw loop)
    if (linkDragRef.current) {
      return;
    }

    // Active widget drag (slider)
    if (activeWidgetRef.current) {
      const aw = activeWidgetRef.current;
      const node = graphNodes.find(n => n.id === aw.nodeId);
      if (!node) { setActiveWidget(null); return; }
      const widgets = widgetsRef.current.get(node.id) || [];
      const w = widgets.find(ww => ww.name === aw.name);
      if (!w || w.type !== 'slider') { setActiveWidget(null); return; }
      const metaRequired = node.meta?.input_types?.required || {};
      const metaOptional = node.meta?.input_types?.optional || {};
      const s = (metaRequired[aw.name] || metaOptional[aw.name]) as any;
      const min = s?.min ?? 0;
      const max = s?.max ?? 100;
      const step = s?.step ?? 1;
      const precision = s?.precision ?? (step < 1 ? 2 : 0);
      const t = Math.max(0, Math.min(1, (world.x - w.x) / w.w));
      let newVal = min + t * (max - min);
      newVal = Math.round(newVal / step) * step;
      newVal = Math.max(min, Math.min(max, newVal));
      if (precision > 0) newVal = Number(newVal.toFixed(precision));
      setGraphNodes(prev => prev.map(n => {
        if (n.id !== aw.nodeId) return n;
        return { ...n, params: { ...n.params, [aw.name]: newVal } };
      }));
      return;
    }

    if (panning) {
      const dx = e.clientX - dragStart.x;
      const dy = e.clientY - dragStart.y;
      setOffset(prev => ({ x: prev.x + dx, y: prev.y + dy }));
      setDragStart({ x: e.clientX, y: e.clientY });
      return;
    }
    if (groupResizing) {
      const dx = (e.clientX - dragStart.x) / scale;
      const dy = (e.clientY - dragStart.y) / scale;
      if (Math.abs(dx) > 0.01 || Math.abs(dy) > 0.01) dragMovedRef.current = true;
      setDragStart({ x: e.clientX, y: e.clientY });
      onGroupsChange(groups.map(g => {
        if (g.id !== groupResizing) return g;
        return { ...g, width: Math.max(60, g.width + dx), height: Math.max(40, g.height + dy) };
      }));
      return;
    }
    if (resizingNode) {
      const dx = (e.clientX - dragStart.x) / scale;
      const dy = (e.clientY - dragStart.y) / scale;
      if (Math.abs(dx) > 0.01 || Math.abs(dy) > 0.01) dragMovedRef.current = true;
      setDragStart({ x: e.clientX, y: e.clientY });
      setGraphNodes(prev => prev.map(n => {
        if (n.id !== resizingNode) return n;
        const newWidth = Math.max(140, n.width + dx);
        if (n.visualOnly) {
          const newHeight = calcNoteHeight(String(n.params?.text || ''), newWidth);
          return { ...n, width: newWidth, height: newHeight };
        }
        return { ...n, width: newWidth, height: Math.max(NODE_HEADER_H + 20, n.height + dy) };
      }));
      return;
    }
    if (groupDragging) {
      const dx = (e.clientX - dragStart.x) / scale;
      const dy = (e.clientY - dragStart.y) / scale;
      if (Math.abs(dx) > 0.01 || Math.abs(dy) > 0.01) dragMovedRef.current = true;
      const gs = groupDragStartRef.current;
      if (!gs) return;
      const containedIds = groupDragNodesRef.current;
      isDraggingRef.current = true;
      // Mutate refs directly — no React state churn during drag
      groupsRef.current = groupsRef.current.map(g => {
        if (g.id !== groupDragging) return g;
        return {
          ...g,
          position: [
            snapToGrid ? Math.round((gs.startPos[0] + dx) / 20) * 20 : gs.startPos[0] + dx,
            snapToGrid ? Math.round((gs.startPos[1] + dy) / 20) * 20 : gs.startPos[1] + dy,
          ] as [number, number],
        };
      });
      if (containedIds.length > 0) {
        graphNodesRef.current = graphNodesRef.current.map(n => {
          const start = gs.nodeStarts.get(n.id);
          if (!start) return n;
          const nx = start[0] + dx;
          const ny = start[1] + dy;
          return {
            ...n,
            x: snapToGrid ? Math.round(nx / 20) * 20 : nx,
            y: snapToGrid ? Math.round(ny / 20) * 20 : ny,
          };
        });
      }
      drawRef.current();
      return;
    }
    if (dragging) {
      isDraggingRef.current = true;
      const dx = (e.clientX - dragStart.x) / scale;
      const dy = (e.clientY - dragStart.y) / scale;
      if (Math.abs(dx) > 0.01 || Math.abs(dy) > 0.01) {
        dragMovedRef.current = true;
        startDragOwnership(dragging);
      }
      setDragStart({ x: e.clientX, y: e.clientY });
      setGraphNodes(prev => {
        const next = prev.map(n => {
          if (!n.selected) return n;
          if (n.pinned) return n;
          const nx = n.x + dx;
          const ny = n.y + dy;
          return {
            ...n,
            x: snapToGrid ? Math.round(nx / 20) * 20 : nx,
            y: snapToGrid ? Math.round(ny / 20) * 20 : ny,
          };
        });
        graphNodesRef.current = next;
        next
          .filter(n => n.selected)
          .forEach(n => onCollabNodeMove?.(n.id, [n.x, n.y]));
        return next;
      });
    } else if (selectBox) {
      const x = Math.min(dragStart.x, cx);
      const y = Math.min(dragStart.y, cy);
      setSelectBox({ x, y, w: Math.abs(cx - dragStart.x), h: Math.abs(cy - dragStart.y) });
      // Select nodes in box
      const w1 = toWorld(x, y);
      const w2 = toWorld(x + Math.abs(cx - dragStart.x), y + Math.abs(cy - dragStart.y));
      const isInSelectionBox = (n: GraphNode) => (
        n.x >= w1.x && n.x + n.width <= w2.x && n.y >= w1.y && n.y + n.height <= w2.y
      );
      const selectedIds = graphNodesRef.current.filter(isInSelectionBox).map(n => n.id);
      setGraphNodes(prev => prev.map(n => {
        const inBox = n.x >= w1.x && n.x + n.width <= w2.x && n.y >= w1.y && n.y + n.height <= w2.y;
        return { ...n, selected: inBox };
      }));
      publishCollabSelection({
        nodeIds: selectedIds,
        box: {
          x: w1.x,
          y: w1.y,
          w: Math.max(0, w2.x - w1.x),
          h: Math.max(0, w2.y - w1.y),
        },
      });
    }
  }, [panning, dragging, selectBox, dragStart, scale, snapToGrid, toWorld, groupDragging, groupResizing, groups, graphNodes, onGroupsChange, publishCollabSelection, startDragOwnership, onCollabNodeMove]);

  const handleMouseUp = useCallback(() => {
    // Check for link drop
    if (activeWidgetRef.current) {
      const aw = activeWidgetRef.current;
      const gn = graphNodesRef.current.find(n => n.id === aw.nodeId);
      if (gn) {
        const paramVal = gn.params[aw.name];
        onNodesChange(nodes.map(n => n.id === aw.nodeId ? { ...n, params: { ...n.params, [aw.name]: paramVal } } : n));
      }
      setActiveWidget(null);
      onPushHistory();
      return;
    }

    if (linkDragRef.current) {
      const ld = linkDragRef.current;
      const world = mouseWorldRef.current;
      let created = false;
      for (const node of graphNodesRef.current) {
        if (node.id === ld.fromNodeId) continue;
        if (node.visualOnly) continue;
        if (node.collapsed) {
          const firstConnectedIn = node.inputs.findIndex(inp => inp.connected);
          const i = firstConnectedIn >= 0 ? firstConnectedIn : 0;
          const slotY = node.y + NODE_HEADER_H / 2;
          const dist = Math.hypot(world.x - node.x, world.y - slotY);
          if (dist < 12 && node.inputs.length > 0) {
            if (node.inputs[i].type !== ld.fromOutputType && node.inputs[i].type !== '*') {
              continue;
            }
            const currentEdges = edgesRef.current;
            const alreadyConnected = currentEdges.some(e => e.to.node === node.id && e.to.input === node.inputs[i].name);
            if (!alreadyConnected) {
              const newEdge: WorkflowEdge = {
                id: `e_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`,
                from: { node: ld.fromNodeId, output: ld.fromOutputName },
                to: { node: node.id, input: node.inputs[i].name },
              };
              onEdgesChangeRef.current([...currentEdges, newEdge]);
              onPushHistoryRef.current();
              created = true;
            }
          }
          continue;
        }
        for (let i = 0; i < node.inputs.length; i++) {
          const slotY = node.y + NODE_HEADER_H + NODE_PIN_H / 2 + i * NODE_PIN_H;
          const dist = Math.hypot(world.x - node.x, world.y - slotY);
          if (dist < 12) {
            // Type compatibility check
            if (node.inputs[i].type !== ld.fromOutputType && node.inputs[i].type !== '*') {
              break;
            }
            const currentEdges2 = edgesRef.current;
            const alreadyConnected = currentEdges2.some(e => e.to.node === node.id && e.to.input === node.inputs[i].name);
            if (!alreadyConnected) {
              const newEdge: WorkflowEdge = {
                id: `e_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`,
                from: { node: ld.fromNodeId, output: ld.fromOutputName },
                to: { node: node.id, input: node.inputs[i].name },
              };
              onEdgesChangeRef.current([...currentEdges2, newEdge]);
              onPushHistoryRef.current();
              created = true;
            }
            break;
          }
        }
        if (created) break;
      }
      setLinkDrag(null);
      setHoveredSlot(null);
      if (!created) {
        // Dropped on empty canvas — open the node palette filtered to nodes
        // that have a compatible input slot, and remember the link source so
        // we can auto-connect when the user picks one.
        const screen = fromWorld(mouseWorldRef.current.x, mouseWorldRef.current.y);
        setPendingLinkPickup({
          fromNodeId: ld.fromNodeId,
          fromOutputName: ld.fromOutputName,
          fromOutputType: ld.fromOutputType,
        });
        setPalettePos({ x: screen.x, y: screen.y });
      }
      return;
    }

    isDraggingRef.current = false;
    const moved = dragMovedRef.current;
    const needsNodeCommit = moved || dragCommitNeededRef.current;
    if (groupDragging && moved) {
      onGroupsChangeRef.current(groupsRef.current);
    }
    if ((dragging && needsNodeCommit) || (groupDragging && moved)) {
      // Sync back to workflow nodes using ref to avoid stale closure
      const currentGraphNodes = graphNodesRef.current;
      const updatedNodes = nodes.map(wn => {
        const gn = currentGraphNodes.find(g => g.id === wn.id);
        if (!gn) return wn;
        return { ...wn, position: [gn.x, gn.y] as [number, number], ui: { ...wn.ui, title: gn.title, collapsed: gn.collapsed, color: gn.color, muted: gn.muted, bypassed: gn.bypassed } };
      });
      onNodesChange(updatedNodes);
    }
    if (resizingNode && moved) {
      const updatedNodes = nodes.map(wn => {
        const gn = graphNodesRef.current.find(g => g.id === wn.id);
        if (!gn) return wn;
        return { ...wn, ui: { ...wn.ui, width: gn.width, height: gn.height } };
      });
      onNodesChange(updatedNodes);
    }
    if ((dragging && needsNodeCommit) || (groupDragging && moved) || (groupResizing && moved) || (resizingNode && moved)) {
      onPushHistory();
    }
    if (selectBox) {
      publishCollabSelection({
        nodeIds: graphNodesRef.current.filter(n => n.selected).map(n => n.id),
        box: null,
      });
    }
    if (dragOwnershipStartedRef.current) {
      onCollabDragEnd?.();
    }
    dragMovedRef.current = false;
    dragCommitNeededRef.current = false;
    dragOwnershipStartedRef.current = false;
    dragGhostsRef.current = [];
    setDragging(null);
    setPanning(false);
    setSelectBox(null);
    setGroupDragging(null);
    groupDragNodesRef.current = [];
    groupDragStartRef.current = null;
    setGroupResizing(null);
    setResizingNode(null);
  }, [dragging, graphNodes, nodes, onNodesChange, groupDragging, groupResizing, resizingNode, onPushHistory, edges, onEdgesChange, publishCollabSelection, onCollabDragEnd]);

  const handleWheel = useCallback((e: React.WheelEvent) => {
    e.preventDefault();
    const rect = canvasRef.current!.getBoundingClientRect();
    const cx = e.clientX - rect.left;
    const cy = e.clientY - rect.top;
    const world = toWorld(cx, cy);
    const newScale = clamp(scale * (e.deltaY < 0 ? 1.1 : 0.9), 0.1, 5);
    setOffset({
      x: cx - world.x * newScale,
      y: cy - world.y * newScale,
    });
    setScale(newScale);
  }, [scale, offset, toWorld]);

  const handleContextMenu = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    // Cancel link drag on right-click
    if (linkDragRef.current) {
      setLinkDrag(null);
      setHoveredSlot(null);
      return;
    }
    const rect = canvasRef.current!.getBoundingClientRect();
    const cx = e.clientX - rect.left;
    const cy = e.clientY - rect.top;
    const world = toWorld(cx, cy);
    const clicked = [...graphNodes].reverse().find(n =>
      world.x >= n.x && world.x <= n.x + n.width &&
      world.y >= n.y && world.y <= n.y + n.height
    );
    if (clicked) {
      setContextMenu({ x: e.clientX, y: e.clientY, nodeId: clicked.id });
      setCanvasMenu(null);
      setGroupContextMenu(null);
      setLinkContextMenu(null);
    } else {
      // Check for link right-click
      let clickedLink: string | null = null;
      for (const edge of edges) {
        const fromNode = graphNodes.find(n => n.id === edge.from.node);
        const toNode = graphNodes.find(n => n.id === edge.to.node);
        if (!fromNode || !toNode) continue;
        const fromOutIndex = fromNode.outputs.findIndex(o => o.name === edge.from.output);
        const toInIndex = toNode.inputs.findIndex(i => i.name === edge.to.input);
        const fy = fromNode.collapsed
          ? fromNode.y + NODE_HEADER_H / 2
          : fromNode.y + NODE_HEADER_H + NODE_PIN_H / 2 + (fromOutIndex >= 0 ? fromOutIndex : 0) * NODE_PIN_H;
        const ty = toNode.collapsed
          ? toNode.y + NODE_HEADER_H / 2
          : toNode.y + NODE_HEADER_H + NODE_PIN_H / 2 + (toInIndex >= 0 ? toInIndex : 0) * NODE_PIN_H;
        const fx = fromNode.x + fromNode.width;
        const tx = toNode.x;
        const dist = Math.hypot(tx - fx, ty - fy);
        const cd = Math.max(30, dist * 0.25);
        if (pointNearBezier(fx, fy, fx + cd, fy, tx - cd, ty, tx, ty, world.x, world.y, 12)) {
          clickedLink = edge.id;
          break;
        }
      }
      if (clickedLink) {
        setLinkContextMenu({ x: e.clientX, y: e.clientY, edgeId: clickedLink, worldX: world.x, worldY: world.y });
        setCanvasMenu(null);
        setContextMenu(null);
        setGroupContextMenu(null);
      } else {
        const clickedGroup = [...groups].reverse().find(g =>
          world.x >= g.position[0] && world.x <= g.position[0] + g.width &&
          world.y >= g.position[1] && world.y <= g.position[1] + g.height
        );
        if (clickedGroup) {
          setGroupContextMenu({ x: e.clientX, y: e.clientY, groupId: clickedGroup.id });
          setCanvasMenu(null);
          setContextMenu(null);
          setLinkContextMenu(null);
        } else {
          setCanvasMenu({ x: e.clientX, y: e.clientY, worldX: world.x, worldY: world.y });
          setContextMenu(null);
          setGroupContextMenu(null);
          setLinkContextMenu(null);
        }
      }
    }
    setPalettePos(null);
  }, [graphNodes, toWorld, groups, edges]);

  const handleDoubleClick = useCallback((e: React.MouseEvent) => {
    // Cancel link drag on double-click
    if (linkDragRef.current) {
      setLinkDrag(null);
      setHoveredSlot(null);
      return;
    }
    const rect = canvasRef.current!.getBoundingClientRect();
    const cx = e.clientX - rect.left;
    const cy = e.clientY - rect.top;
    const world = toWorld(cx, cy);
    const clicked = [...graphNodes].reverse().find(n =>
      world.x >= n.x && world.x <= n.x + n.width &&
      world.y >= n.y && world.y <= n.y + n.height
    );
    if (clicked) {
      // Subgraph nodes — double-click enters the embedded workflow.
      if (clicked.type === 'subgraph' && onEnterSubgraphRef.current) {
        onEnterSubgraphRef.current(clicked.id);
        return;
      }
      // Double-click header to toggle collapse (ComfyUI behavior)
      const inHeader = world.y >= clicked.y && world.y <= clicked.y + NODE_HEADER_H;
      if (inHeader && !clicked.visualOnly) {
        setGraphNodes(prev => prev.map(n => {
          if (n.id !== clicked.id) return n;
          const newCollapsed = !n.collapsed;
          return { ...n, collapsed: newCollapsed, height: calcNodeHeight(n.meta, newCollapsed, n.params) };
        }));
        const updatedNodes = nodes.map(n => n.id === clicked.id ? { ...n, ui: { ...n.ui, collapsed: !(n.ui?.collapsed ?? false) } } : n);
        onNodesChange(updatedNodes);
        return;
      }
      setEditingNode(clicked.id);
    } else {
      setPalettePos({ x: cx, y: cy });
    }
  }, [graphNodes, toWorld, nodes, onNodesChange]);

  const animateViewport = useCallback((targetOffset: { x: number; y: number }, targetScale: number, duration = 220) => {
    const startOffset = { ...offset };
    const startScale = scale;
    const start = performance.now();
    const ease = (t: number) => 1 - Math.pow(1 - t, 3);
    const step = (now: number) => {
      const t = Math.min(1, (now - start) / duration);
      const k = ease(t);
      setScale(startScale + (targetScale - startScale) * k);
      setOffset({
        x: startOffset.x + (targetOffset.x - startOffset.x) * k,
        y: startOffset.y + (targetOffset.y - startOffset.y) * k,
      });
      if (t < 1) requestAnimationFrame(step);
    };
    requestAnimationFrame(step);
  }, [offset, scale]);

  const fitView = useCallback((onlySelected?: boolean) => {
    const targets = onlySelected ? graphNodes.filter(n => n.selected) : graphNodes;
    if (targets.length === 0) return;
    const xs = targets.map(n => n.x);
    const ys = targets.map(n => n.y);
    const minX = Math.min(...xs) - 50;
    const minY = Math.min(...ys) - 50;
    const maxX = Math.max(...targets.map(n => n.x + n.width)) + 50;
    const maxY = Math.max(...targets.map(n => n.y + n.height)) + 50;
    const { w, h } = sizeRef.current;
    const newScale = Math.min(w / (maxX - minX), h / (maxY - minY), 1);
    animateViewport({
      x: -minX * newScale + (w - (maxX - minX) * newScale) / 2,
      y: -minY * newScale + (h - (maxY - minY) * newScale) / 2,
    }, newScale);
  }, [animateViewport, graphNodes]);

  const focusNode = useCallback((nodeId: string) => {
    const node = graphNodesRef.current.find(candidate => candidate.id === nodeId);
    if (!node) return;
    pendingSelectionRef.current = new Set([nodeId]);
    setGraphNodes(prev => prev.map(candidate => ({ ...candidate, selected: candidate.id === nodeId })));
    publishCollabSelection({ nodeIds: [nodeId], box: null });
    animateViewport({
      x: sizeRef.current.w / 2 - (node.x + node.width / 2) * scale,
      y: sizeRef.current.h / 2 - (node.y + node.height / 2) * scale,
    }, scale);
  }, [animateViewport, publishCollabSelection, scale]);

  const setViewportFromAwareness = useCallback((viewport: { x: number; y: number; scale: number }) => {
    animateViewport({ x: viewport.x, y: viewport.y }, clamp(viewport.scale, 0.1, 5), 280);
  }, [animateViewport]);

  const animateZoom = useCallback((factor: number) => {
    const targetScale = clamp(scale * factor, 0.1, 5);
    if (Math.abs(targetScale - scale) < 1e-3) return;
    const { w, h } = sizeRef.current;
    const cx = w / 2;
    const cy = h / 2;
    const worldX = (cx - offset.x) / scale;
    const worldY = (cy - offset.y) / scale;
    animateViewport({ x: cx - worldX * targetScale, y: cy - worldY * targetScale }, targetScale, 160);
  }, [animateViewport, offset, scale]);

  useImperativeHandle(ref, () => ({
    fitView,
    focusNode,
    setViewport: setViewportFromAwareness,
    getViewport: () => ({ x: offset.x, y: offset.y, scale }),
    getSelectedNodeIds,
    executeSelected: () => {
      const ids = getSelectedNodeIds();
      if (ids.length > 0) onExecuteSelectedRef.current?.(ids);
    },
    createSubgraphFromSelection: () => {
      const ids = getSelectedNodeIds();
      if (ids.length > 0) onCreateSubgraphRef.current?.(ids);
    },
  }), [fitView, focusNode, getSelectedNodeIds, offset.x, offset.y, scale, setViewportFromAwareness]);

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
          title: 'Rename node',
          message: 'Choose a display name for this node.',
          inputLabel: 'Node name',
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
        const newGroup = createGroupFromNodes(nodesToGroup);
        onGroupsChange([...groups, newGroup]);
      }
    } else if (action === 'subgraph') {
      const selectedIds = graphNodes.filter(n => n.selected).map(n => n.id);
      onCreateSubgraphRef.current?.(selectedIds.length > 0 ? selectedIds : [nodeId]);
    } else if (action === 'saveSubgraphBlueprint') {
      const node = nodes.find(n => n.id === nodeId);
      if (!node || node.type !== 'subgraph') {
        toast.warning('Save to library only works on subgraph nodes');
      } else {
        const innerWorkflow = node.params?.workflow as Workflow | undefined;
        const inputPorts = (node.params?.input_ports as unknown[] | undefined) ?? [];
        const outputPorts = (node.params?.output_ports as unknown[] | undefined) ?? [];
        if (!innerWorkflow) {
          toast.error('Subgraph has no embedded workflow');
        } else {
          const name = node.ui?.title || node.node_info?.display_name || 'Subgraph';
          saveBlueprint({
            name: String(name),
            workflow: innerWorkflow,
            inputPorts: inputPorts as never,
            outputPorts: outputPorts as never,
          });
          toast.success('Saved to subgraph library', { message: String(name) });
        }
      }
    } else if (action === 'promoteWidgets') {
      // Mark the requested inner node's interactive widgets for promotion.
      // Actual promotion happens in App.tsx via onPromoteWidgets so it can
      // mutate the parent workflow that owns this subgraph view.
      onPromoteWidgetsRef.current?.(nodeId);
    } else if (action === 'executeSelected') {
      const selectedIds = graphNodes.filter(n => n.selected).map(n => n.id);
      onExecuteSelectedRef.current?.(selectedIds.length > 0 ? selectedIds : [nodeId]);
    }
    onPushHistory();
  }, [nodes, edges, graphNodes, groups, onNodesChange, onEdgesChange, onGroupsChange, onPushHistory]);

  const handleNodeParamChange = useCallback((nodeId: string, key: string, value: unknown) => {
    onNodesChange(nodes.map(n =>
      n.id === nodeId ? { ...n, params: { ...n.params, [key]: value } } : n
    ));
  }, [nodes, onNodesChange]);

  const cursorStyle = panning ? 'grabbing' : dragging || groupDragging || groupResizing ? 'grabbing' : resizingNode ? 'nwse-resize' : activeWidget ? 'ew-resize' : linkDrag ? 'crosshair' : hoveredLink ? 'pointer' : 'default';

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
      // Collapse/expand all selected nodes
      const selectedIds = new Set(graphNodes.filter(n => n.selected).map(n => n.id));
      const anyExpanded = graphNodes.some(n => n.selected && !n.collapsed && !n.visualOnly && n.type !== 'reroute');
      const targetCollapsed = anyExpanded; // if any selected is expanded, collapse all; else expand all
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
      // Compute target positions for the selection.
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
        // distributeV
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
    const rerouteNode: WorkflowNode = {
      id,
      type: 'reroute',
      position: [px, py],
      params: defaultsFor(rerouteMeta),
      node_info: rerouteMeta,
      ui: { title: 'Reroute', color: nodeColor(rerouteMeta), shape: 'round' },
    };
    const nextEdges: WorkflowEdge[] = edges
      .filter(candidate => candidate.id !== edgeId)
      .concat([
        {
          id: `e_${Date.now()}_a_${Math.random().toString(36).slice(2, 6)}`,
          from: edge.from,
          to: { node: id, input: 'input' },
        },
        {
          id: `e_${Date.now()}_b_${Math.random().toString(36).slice(2, 6)}`,
          from: { node: id, output: 'output' },
          to: edge.to,
        },
      ]);
    onNodesChange([...nodes, rerouteNode]);
    onEdgesChange(nextEdges);
    pendingSelectionRef.current = new Set([id]);
    onPushHistory();
    setLinkContextMenu(null);
  }, [edges, graphNodes, nodes, objectInfo, onEdgesChange, onNodesChange, onPushHistory]);

  return (
    <div ref={hostRef} className="litegraph-host" style={{ position: 'relative', overflow: 'hidden' }}>
      <canvas
        ref={canvasRef}
        style={{ position: 'absolute', inset: 0, cursor: cursorStyle }}
        onMouseDown={viewportLocked ? undefined : handleMouseDown}
        onMouseMove={viewportLocked ? undefined : handleMouseMove}
        onMouseUp={handleMouseUp}
        onMouseLeave={() => { onCollabCursor?.(null); handleMouseUp(); }}
        onWheel={handleWheel}
        onContextMenu={handleContextMenu}
        onDoubleClick={handleDoubleClick}
      />

      {actionFeedback && (
        <div
          key={actionFeedback.key}
          className="canvas-action-feedback"
          role="status"
          aria-live="polite"
        >
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
            style={{
              position: 'absolute',
              left: x,
              top: y,
              pointerEvents: 'none',
              zIndex: 102,
              transform: 'translate(-50%, -50%)',
            }}
          >
            <div
              style={{
                width: 8,
                height: 8,
                borderRadius: '50%',
                backgroundColor: user.user.color,
                boxShadow: `0 0 4px ${user.user.color}`,
              }}
            />
            <span
              style={{
                position: 'absolute',
                left: 10,
                top: -4,
                fontSize: 11,
                color: user.user.color,
                background: 'rgba(0,0,0,0.7)',
                padding: '1px 4px',
                borderRadius: 3,
                whiteSpace: 'nowrap',
              }}
            >
              {user.user.name}
            </span>
          </div>
        );
      })}

      {/* Image preview DOM overlays */}
      {nodePreviewsMap && graphNodes.filter(n => nodePreviewsMap.has(n.id) && !n.collapsed).map(node => {
        const previewUrl = nodePreviewsMap.get(node.id)!;
        const ioHeight = Math.max(node.inputs.length, node.outputs.length, 1) * NODE_PIN_H;
        const pad = 4 * scale;
        const left = node.x * scale + offset.x + pad;
        const top = node.y * scale + offset.y + (NODE_HEADER_H + ioHeight + 4) * scale;
        const width = (node.width - 8) * scale;
        const height = (node.height - NODE_HEADER_H - ioHeight - 8) * scale;
        if (width <= 0 || height <= 0) return null;
        return (
          <div
            key={node.id}
            style={{
              position: 'absolute',
              left,
              top,
              width,
              height,
              zIndex: 5,
              pointerEvents: 'none',
              borderRadius: Math.max(2, 4 * scale),
              overflow: 'hidden',
              background: 'var(--surface)',
            }}
          >
            <img
              src={previewUrl}
              alt="Preview"
              style={{ width: '100%', height: '100%', objectFit: 'contain', display: 'block' }}
              onError={e => { (e.target as HTMLImageElement).style.display = 'none'; }}
            />
          </div>
        );
      })}

      {/* Full DOM widget overlays for node controls. These mirror ComfyUI's
          portal-style widgets while preserving BioNodulo's custom canvas model.
          With `transform: scale(scale)` they now scale uniformly with the node
          so the previous zoom-out fallback to canvas-drawn widgets is gone. */}
      {graphNodes.filter(node => (
        !node.collapsed
        && !node.visualOnly
        && node.type !== 'reroute'
      )).flatMap(node => {
        const allSpecs = {
          ...(node.meta?.input_types?.required || {}),
          ...(node.meta?.input_types?.optional || {}),
        };
        const ioHeight = Math.max(node.inputs.length, node.outputs.length, 1) * NODE_PIN_H;
        let top = node.y * scale + offset.y + (NODE_HEADER_H + ioHeight + 6) * scale;
        const left = node.x * scale + offset.x + 8 * scale;
        // Lay widgets out in WORLD units (so child controls keep their natural
        // sizing) and use `transform: scale(scale)` to align with the canvas.
        // This makes widgets grow/shrink in lockstep with the node at any zoom
        // instead of clipping when scale > 1 or jittering when scale < 1.
        const layoutWidth = node.width - 16;
        const layoutHeight = 24;
        return Object.entries(allSpecs).map(([key, rawSpec]) => {
          const spec = rawSpec as any;
          const value = node.params[key] ?? spec.default ?? '';
          const rowTop = top;
          top += layoutHeight * scale;
          const common = {
            position: 'absolute' as const,
            left,
            top: rowTop,
            width: layoutWidth,
            height: layoutHeight,
            zIndex: 12,
            transform: `scale(${scale})`,
            transformOrigin: 'top left',
          };
          const commit = (nextValue: unknown, push = true) => {
            handleNodeParamChange(node.id, key, nextValue);
            if (push) onPushHistory();
          };
          if (spec?.type === 'BOOLEAN') {
            return (
              <label key={`${node.id}-${key}`} className="node-dom-widget node-dom-widget-boolean" style={common}>
                <span>{spec.label || key}</span>
                <input type="checkbox" checked={Boolean(value)} onChange={event => commit(event.target.checked)} />
              </label>
            );
          }
          if (spec?.options?.length) {
            return (
              <label key={`${node.id}-${key}`} className="node-dom-widget" style={common}>
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
              <label key={`${node.id}-${key}`} className="node-dom-widget node-dom-widget-slider" style={common}>
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
              <label key={`${node.id}-${key}`} className="node-dom-widget" style={common}>
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
          if (spec?.type === 'STRING' && !spec?.forceInput) {
            return (
              <label key={`${node.id}-${key}`} className="node-dom-widget" style={common}>
                <span>{spec.label || key}</span>
                <input
                  type="text"
                  value={String(value)}
                  onChange={event => handleNodeParamChange(node.id, key, event.target.value)}
                  onBlur={() => onPushHistory()}
                />
              </label>
            );
          }
          return null;
        }).filter(Boolean);
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
      {nodeCommentTarget && collabWorkflowId && currentCollabUser && (() => {
        const node = graphNodes.find(candidate => candidate.id === nodeCommentTarget.nodeId);
        if (!node) return null;
        const nodeRect = toScreenNodeRect(node);
        const summary = nodeCommentsMap?.get(node.id);
        const pinSize = summary ? getCommentPinSize(summary.count) : undefined;
        const pinPoint = summary ? getCommentPinPosition(nodeRect, canvasBounds, summary.count) : undefined;
        const point = getNodeCommentPopoverPosition(nodeRect, canvasBounds, pinPoint, pinSize);
        return (
          <NodeCommentPopover
            workflowId={collabWorkflowId}
            nodeId={node.id}
            currentUser={currentCollabUser}
            comments={nodeComments}
            x={point.x}
            y={point.y}
            compose={nodeCommentTarget.compose}
            onChanged={() => onNodeCommentsChange?.()}
            onClose={() => setNodeCommentTarget(null)}
          />
        );
      })()}

      {hoveredNodeId && !dragging && !panning && !linkDrag && (() => {
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
            <div className="node-hover-card-meta">{node.category}</div>
            {node.meta.description && <p>{node.meta.description}</p>}
            <div className="node-hover-card-grid">
              <span>Inputs</span><strong>{node.inputs.length}</strong>
              <span>Outputs</span><strong>{node.outputs.length}</strong>
              {node.meta.version && <><span>Version</span><strong>{node.meta.version}</strong></>}
            </div>
          </div>
        );
      })()}

      <SelectionToolbox
        graphNodes={graphNodes}
        groups={groups}
        offset={offset}
        scale={scale}
        isDragging={!!dragging || !!groupDragging || !!groupResizing || !!resizingNode || panning}
        onAction={handleToolboxAction}
        hostRef={hostRef}
      />

      {/* Zoom controls */}
      <div className="canvas-controls">
        <button className="btn btn-icon btn-sm" onClick={() => fitView()} title="Fit view" aria-label="Fit view"><Icon name="maximize" size={14} /></button>
        <button className="btn btn-icon btn-sm" onClick={() => fitView(true)} title="Fit selection" aria-label="Fit selection"><Icon name="target" size={14} /></button>
        <button className="btn btn-icon btn-sm" onClick={() => animateZoom(1.2)} title="Zoom in" aria-label="Zoom in"><Icon name="plus" size={14} /></button>
        {editingZoom ? (
          <input
            type="text"
            autoFocus
            defaultValue={Math.round(scale * 100)}
            onBlur={(e) => {
              const val = parseInt(e.target.value, 10);
              if (!isNaN(val)) setScale(clamp(val / 100, 0.1, 5));
              setEditingZoom(false);
            }}
            onKeyDown={(e) => {
              if (e.key === 'Enter') {
                const val = parseInt((e.target as HTMLInputElement).value, 10);
                if (!isNaN(val)) setScale(clamp(val / 100, 0.1, 5));
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
        <button className="btn btn-icon btn-sm" onClick={() => animateZoom(1 / 1.2)} title="Zoom out" aria-label="Zoom out"><Icon name="minus" size={14} /></button>
        <div style={{ width: 1, height: 20, background: 'var(--border)', margin: '0 4px' }} />
        <button className={`btn btn-icon btn-sm ${showMinimap ? 'active' : ''}`} onClick={onToggleMinimap} title="Toggle minimap"><Icon name="map" size={14} /></button>
        <button className={`btn btn-icon btn-sm ${!linksHidden ? 'active' : ''}`} onClick={onToggleLinksHidden} title="Toggle links"><Icon name="link" size={14} /></button>
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
        }} title="Auto-arrange nodes"><Icon name="layout" size={14} /></button>
      </div>

      {/* Minimap */}
      {showMinimap && graphNodes.length > 0 && (
        <Minimap
          graphNodes={graphNodes}
          groups={groups}
          edges={edges}
          offset={offset}
          scale={scale}
          canvasSize={sizeRef.current}
          onOffsetChange={setOffset}
          onScaleChange={setScale}
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
              const inputs = {
                ...(meta.input_types?.required || {}),
                ...(meta.input_types?.optional || {}),
              };
              // Prefer a slot whose type exactly matches the dragged link's
              // output type. Fall back to '*' / 'ANY', then the first input.
              const entries = Object.entries(inputs);
              const match = entries.find(([, spec]) => (
                (spec as { type?: string }).type === pendingLinkPickup.fromOutputType
              ))
                ?? entries.find(([, spec]) => {
                  const t = (spec as { type?: string }).type;
                  return t === '*' || t === 'ANY';
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
            <div className="context-menu-item" onClick={() => { setPalettePos({ x: canvasMenu.x, y: canvasMenu.y }); setCanvasMenu(null); }}>Add Node</div>
            <div className="context-menu-item" onClick={() => {
              const rerouteMeta = objectInfo.reroute;
              if (rerouteMeta) {
                const id = `reroute_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`;
                const newNode: WorkflowNode = {
                  id,
                  type: 'reroute',
                  position: [Math.round(canvasMenu.worldX - 10), Math.round(canvasMenu.worldY - 10)],
                  params: defaultsFor(rerouteMeta),
                  node_info: rerouteMeta,
                  ui: { title: 'Reroute', color: nodeColor(rerouteMeta), shape: 'round' },
                };
                onNodesChange([...nodes, newNode]);
                pendingSelectionRef.current = new Set([id]);
                onPushHistory();
              }
              setCanvasMenu(null);
            }}>Add Reroute Here</div>
            <div className="context-menu-item" onClick={() => { fitView(); setCanvasMenu(null); }}>Fit View</div>
            <div className="context-menu-sep" />
            <div className="context-menu-item" onClick={() => {
              const selected = graphNodes.filter(n => n.selected);
              if (selected.length > 0) {
                const newGroup = createGroupFromNodes(selected);
                onGroupsChange([...groups, newGroup]);
                onPushHistory();
              }
              setCanvasMenu(null);
            }}>Group Selected Nodes</div>
            <div className="context-menu-sep" />
            <div className="context-menu-item" onClick={() => { onNodesChange(nodes.map(n => ({ ...n, selected: true }))); setCanvasMenu(null); }}>Select All</div>
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
            }}>Align Left</div>
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
            }}>Align Top</div>
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
            }}>Distribute Horizontally</div>
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
            }}>Distribute Vertically</div>
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
            }}>Arrange Nodes</div>
            <div className="context-menu-item" onClick={() => {
              const dataUrl = exportThumbnailDataURL(graphNodes, edges, groups);
              const a = document.createElement('a');
              a.href = dataUrl;
              a.download = 'workflow_thumbnail.png';
              a.click();
              setCanvasMenu(null);
            }}>Export Thumbnail</div>
            <div className="context-menu-sep" />
            <div className="context-menu-item" onClick={() => { onNodesChange([]); onEdgesChange([]); onPushHistory(); setCanvasMenu(null); }}>Clear Workflow</div>
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
            <div className="context-menu-item" onClick={() => insertRerouteOnEdge(linkContextMenu.edgeId, { x: linkContextMenu.worldX, y: linkContextMenu.worldY })}>Insert Reroute</div>
            <div className="context-menu-item" onClick={() => {
              onEdgesChange(edges.filter(e => e.id !== linkContextMenu.edgeId));
              onPushHistory();
              setLinkContextMenu(null);
            }}>Delete Link</div>
          </div>
        </div>
      )}

      {/* Node Context Menu */}
      {contextMenu && (
        <NodeContextMenu
          x={contextMenu.x} y={contextMenu.y}
          nodeId={contextMenu.nodeId}
          onAction={handleContextAction}
          onClose={() => setContextMenu(null)}
        />
      )}

      {/* Node Editor */}
      {editingNode && (
        <NodeEditor
          node={graphNodes.find(n => n.id === editingNode)}
          onParamChange={handleNodeParamChange}
          onClose={() => setEditingNode(null)}
        />
      )}

      {/* Node Info Panel */}
      {showNodeInfo && (
        <div style={{ position: 'absolute', right: 12, top: 12, zIndex: 150, maxWidth: 380, width: '100%' }}>
          <NodeInfoPanel
            node={graphNodes.find(n => n.id === showNodeInfo)}
            onClose={() => setShowNodeInfo(null)}
          />
        </div>
      )}
    </div>
  );
});

export default LiteGraphCanvas;

function roundRect(ctx: CanvasRenderingContext2D, x: number, y: number, w: number, h: number, r: number | Record<string, number>) {
  if (typeof r === 'number') r = { tl: r, tr: r, br: r, bl: r };
  const rad = r as Record<string, number>;
  ctx.beginPath();
  ctx.moveTo(x + rad.tl, y);
  ctx.lineTo(x + w - rad.tr, y);
  ctx.quadraticCurveTo(x + w, y, x + w, y + rad.tr);
  ctx.lineTo(x + w, y + h - rad.br);
  ctx.quadraticCurveTo(x + w, y + h, x + w - rad.br, y + h);
  ctx.lineTo(x + rad.bl, y + h);
  ctx.quadraticCurveTo(x, y + h, x, y + h - rad.bl);
  ctx.lineTo(x, y + rad.tl);
  ctx.quadraticCurveTo(x, y, x + rad.tl, y);
  ctx.closePath();
}

function clamp(n: number, min: number, max: number) { return Math.min(max, Math.max(min, n)); }

function pointOnBezier(p0: number, p1: number, p2: number, p3: number, t: number): number {
  const mt = 1 - t;
  return mt * mt * mt * p0 + 3 * mt * mt * t * p1 + 3 * mt * t * t * p2 + t * t * t * p3;
}

function pointNearBezier(
  fx: number, fy: number,
  c1x: number, c1y: number,
  c2x: number, c2y: number,
  tx: number, ty: number,
  px: number, py: number,
  threshold: number
): boolean {
  for (let i = 0; i <= 20; i++) {
    const t = i / 20;
    const bx = pointOnBezier(fx, c1x, c2x, tx, t);
    const by = pointOnBezier(fy, c1y, c2y, ty, t);
    if (Math.hypot(bx - px, by - py) < threshold) return true;
  }
  return false;
}
