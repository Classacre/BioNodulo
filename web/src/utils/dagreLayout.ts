// Graph auto-layout via dagre — React Flow's officially recommended layouting
// approach (see reactflow.dev/learn/layouting). Replaces the old hand-rolled
// topological column layout. Given node sizes + directed edges it returns a
// top-left position per node (dagre lays out around node centers, React Flow
// positions by top-left, so we offset by half the size).
import Dagre from '@dagrejs/dagre';

export interface DagreItem {
  id: string;
  width: number;
  height: number;
}

export interface DagreEdge {
  from: string;
  to: string;
}

export interface DagreLayoutOptions {
  /** 'LR' left→right (default, matches data-flow), 'TB' top→bottom, etc. */
  direction?: 'LR' | 'TB' | 'RL' | 'BT';
  nodeSep?: number;
  rankSep?: number;
}

export function dagreLayout(
  items: DagreItem[],
  edges: DagreEdge[],
  options: DagreLayoutOptions = {},
): Map<string, { x: number; y: number }> {
  const g = new Dagre.graphlib.Graph().setDefaultEdgeLabel(() => ({}));
  g.setGraph({
    rankdir: options.direction ?? 'LR',
    nodesep: options.nodeSep ?? 40,
    ranksep: options.rankSep ?? 80,
  });

  const known = new Set(items.map(i => i.id));
  for (const item of items) {
    g.setNode(item.id, { width: item.width, height: item.height });
  }
  for (const edge of edges) {
    if (known.has(edge.from) && known.has(edge.to)) g.setEdge(edge.from, edge.to);
  }

  Dagre.layout(g);

  const result = new Map<string, { x: number; y: number }>();
  for (const item of items) {
    const pos = g.node(item.id);
    if (!pos) continue;
    // dagre gives the node center; React Flow wants top-left.
    result.set(item.id, {
      x: Math.round(pos.x - item.width / 2),
      y: Math.round(pos.y - item.height / 2),
    });
  }
  return result;
}
