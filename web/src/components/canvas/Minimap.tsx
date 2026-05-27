import { useRef, useCallback, useMemo } from 'react';
import type { GraphNode } from './LiteGraphCanvas';
import type { WorkflowGroup, WorkflowEdge } from '../../types';

interface MinimapProps {
  graphNodes: GraphNode[];
  groups: WorkflowGroup[];
  edges: WorkflowEdge[];
  offset: { x: number; y: number };
  scale: number;
  canvasSize: { w: number; h: number };
  onOffsetChange: (offset: { x: number; y: number }) => void;
  onScaleChange: (scale: number | ((prev: number) => number)) => void;
}

const MINIMAP_W = 220;
const MINIMAP_H = 176;

function clamp(v: number, min: number, max: number) {
  return Math.max(min, Math.min(max, v));
}

export default function Minimap({ graphNodes, groups, edges, offset, scale, canvasSize, onOffsetChange, onScaleChange }: MinimapProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const isDragging = useRef(false);

  const bounds = useMemo(() => {
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
    // Pad small graphs so they don't fill the whole minimap
    const padX = Math.max(0, 2500 - (maxX - minX)) / 2;
    const padY = Math.max(0, 2000 - (maxY - minY)) / 2;
    return {
      minX: minX - padX,
      minY: minY - padY,
      maxX: maxX + padX,
      maxY: maxY + padY,
    };
  }, [graphNodes, groups]);

  const mmScale = useMemo(() => {
    const bw = bounds.maxX - bounds.minX || 1;
    const bh = bounds.maxY - bounds.minY || 1;
    return Math.min(MINIMAP_W / bw, MINIMAP_H / bh) * 0.9;
  }, [bounds]);

  const centerOffset = useMemo(() => {
    const bw = bounds.maxX - bounds.minX || 1;
    const bh = bounds.maxY - bounds.minY || 1;
    return {
      x: (MINIMAP_W - bw * mmScale) / 2,
      y: (MINIMAP_H - bh * mmScale) / 2,
    };
  }, [bounds, mmScale]);

  const viewportStyle = useMemo(() => {
    const viewportW = canvasSize.w / scale;
    const viewportH = canvasSize.h / scale;
    const worldX = -offset.x / scale;
    const worldY = -offset.y / scale;
    const x = (worldX - bounds.minX) * mmScale + centerOffset.x;
    const y = (worldY - bounds.minY) * mmScale + centerOffset.y;
    const w = viewportW * mmScale;
    const h = viewportH * mmScale;
    return {
      transform: `translate(${x}px, ${y}px)`,
      width: `${w}px`,
      height: `${h}px`,
    };
  }, [canvasSize, offset, scale, bounds, mmScale, centerOffset]);

  const handlePointerDown = useCallback((e: React.PointerEvent) => {
    isDragging.current = true;
    (e.target as HTMLElement).setPointerCapture(e.pointerId);
    handlePointerMove(e);
  }, []);

  const handlePointerMove = useCallback((e: React.PointerEvent) => {
    if (!isDragging.current || !containerRef.current) return;
    const rect = containerRef.current.getBoundingClientRect();
    const mx = e.clientX - rect.left;
    const my = e.clientY - rect.top;
    const worldX = (mx - centerOffset.x) / mmScale + bounds.minX;
    const worldY = (my - centerOffset.y) / mmScale + bounds.minY;
    const { w, h } = canvasSize;
    onOffsetChange({ x: w / 2 - worldX * scale, y: h / 2 - worldY * scale });
  }, [centerOffset, mmScale, bounds, canvasSize, scale, onOffsetChange]);

  const handlePointerUp = useCallback(() => {
    isDragging.current = false;
  }, []);

  const handleWheel = useCallback((e: React.WheelEvent) => {
    e.preventDefault();
    const rect = containerRef.current?.getBoundingClientRect();
    if (!rect) return;
    const mx = e.clientX - rect.left;
    const my = e.clientY - rect.top;
    const worldX = (mx - centerOffset.x) / mmScale + bounds.minX;
    const worldY = (my - centerOffset.y) / mmScale + bounds.minY;
    const newScale = clamp(scale * (e.deltaY < 0 ? 1.1 : 0.9), 0.1, 5);
    const { w, h } = canvasSize;
    onScaleChange(newScale);
    onOffsetChange({ x: w / 2 - worldX * newScale, y: h / 2 - worldY * newScale });
  }, [centerOffset, mmScale, bounds, canvasSize, scale, onScaleChange, onOffsetChange]);

  const { groupRects, linkLines, nodeRects } = useMemo(() => {
    const bw = bounds.maxX - bounds.minX || 1;
    const bh = bounds.maxY - bounds.minY || 1;

    const groupsSvg = groups.map(g => {
      const nx = ((g.position[0] - bounds.minX) / bw) * MINIMAP_W;
      const ny = ((g.position[1] - bounds.minY) / bh) * MINIMAP_H;
      const nw = Math.max((g.width / bw) * MINIMAP_W, 3);
      const nh = Math.max((g.height / bh) * MINIMAP_H, 3);
      return { key: g.id, x: nx, y: ny, w: nw, h: nh, fill: g.color };
    });

    const nodeMap = new Map(graphNodes.map(n => [n.id, n]));
    const linksSvg = edges.map(e => {
      const fromNode = nodeMap.get(e.from.node);
      const toNode = nodeMap.get(e.to.node);
      if (!fromNode || !toNode) return null;
      const fx = ((fromNode.x + fromNode.width - bounds.minX) / bw) * MINIMAP_W;
      const fy = ((fromNode.y + (fromNode.collapsed ? 16 : 32) - bounds.minY) / bh) * MINIMAP_H;
      const tx = ((toNode.x - bounds.minX) / bw) * MINIMAP_W;
      const ty = ((toNode.y + (toNode.collapsed ? 16 : 32) - bounds.minY) / bh) * MINIMAP_H;
      return { key: e.id, x1: fx, y1: fy, x2: tx, y2: ty };
    }).filter(Boolean) as Array<{ key: string; x1: number; y1: number; x2: number; y2: number }>;

    // Status colors override the node's nominal tint so the minimap acts as
    // an at-a-glance run health indicator. Selection still wins so the user
    // can find what they just clicked on a tall workflow.
    const statusFill = (n: GraphNode): string => {
      if (n.selected) return '#2dd4bf';
      switch (n.status) {
        case 'running': return '#3b82f6';
        case 'error': return '#ef4444';
        case 'completed': return '#22c55e';
        case 'cached': return '#a855f7';
        case 'skipped': return '#94a3b8';
        default: return n.color || '#64748b';
      }
    };
    const nodesSvg = graphNodes.map(n => {
      const nx = ((n.x - bounds.minX) / bw) * MINIMAP_W;
      const ny = ((n.y - bounds.minY) / bh) * MINIMAP_H;
      const nw = Math.max((n.width / bw) * MINIMAP_W, 3);
      const nh = Math.max(((n.collapsed ? 32 : n.height) / bh) * MINIMAP_H, 3);
      return { key: n.id, x: nx, y: ny, w: nw, h: nh, fill: statusFill(n) };
    });

    return { groupRects: groupsSvg, linkLines: linksSvg, nodeRects: nodesSvg };
  }, [graphNodes, groups, edges, bounds]);

  return (
    <div className="minimap" ref={containerRef}>
      <svg viewBox={`0 0 ${MINIMAP_W} ${MINIMAP_H}`} style={{ width: '100%', height: '100%', pointerEvents: 'none' }}>
        {/* Groups rendered first (background layer) */}
        {groupRects.map(r => (
          <rect key={r.key} x={r.x} y={r.y} width={r.w} height={r.h} rx="2" fill={r.fill} opacity="0.35" />
        ))}
        {/* Links */}
        {linkLines.map(l => (
          <line key={l.key} x1={l.x1} y1={l.y1} x2={l.x2} y2={l.y2} stroke="#94a3b8" strokeWidth="0.5" opacity="0.5" />
        ))}
        {/* Nodes */}
        {nodeRects.map(r => (
          <rect key={r.key} x={r.x} y={r.y} width={r.w} height={r.h} rx="2" fill={r.fill} opacity="0.85" />
        ))}
      </svg>
      <div className="minimap-viewport" style={viewportStyle} />
      <div
        className="minimap-overlay"
        onPointerDown={handlePointerDown}
        onPointerMove={handlePointerMove}
        onPointerUp={handlePointerUp}
        onPointerLeave={handlePointerUp}
        onWheel={handleWheel}
      />
    </div>
  );
}
