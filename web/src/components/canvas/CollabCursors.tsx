// Live multiplayer cursors, rendered the React Flow way: inside a <ViewportPortal>
// using FLOW (world) coordinates, so each remote cursor pans and zooms with the
// graph instead of being pinned to a screen pixel. Positions come from the collab
// awareness state (cursor.worldX / worldY), published by the local client on
// pointer move (see WorkflowCanvas.onPaneMouseMove).
import { ViewportPortal, useReactFlow } from '@xyflow/react';
import type { AwarenessState } from '../../collab/types';

interface CollabCursorsProps {
  users: AwarenessState[];
  currentUserId: string;
}

// Not memoized: reads live node positions via rf.getNode() (for selection rings),
// so it must re-render with the canvas as nodes move.
export default function CollabCursors({ users, currentUserId }: CollabCursorsProps) {
  const rf = useReactFlow();
  // Guard against partial awareness states: a peer can broadcast a cursor before
  // its `user` identity has propagated, so `u.user` may be undefined.
  const others = users.filter(u => u.user && u.user.id !== currentUserId);
  const cursors = others.filter(u =>
    u.cursor?.visible && Number.isFinite(u.cursor.worldX) && Number.isFinite(u.cursor.worldY),
  );
  // Remote node selections: outline each node a collaborator has selected, in
  // their colour, at the node's live position.
  const selectionRings = others.flatMap(u =>
    (u.selection?.nodeIds ?? []).map(nodeId => {
      const node = rf.getNode(nodeId);
      if (!node) return null;
      const w = node.measured?.width ?? node.width ?? 0;
      const h = node.measured?.height ?? node.height ?? 0;
      return { key: `${u.user.sessionId || u.user.id}-${nodeId}`, x: node.position.x, y: node.position.y, w, h, color: u.user.color };
    }).filter(Boolean),
  ) as Array<{ key: string; x: number; y: number; w: number; h: number; color: string }>;

  if (cursors.length === 0 && selectionRings.length === 0) return null;
  return (
    <ViewportPortal>
      {selectionRings.map(r => (
        <div
          key={`sel-${r.key}`}
          className="collab-selection-ring"
          style={{ transform: `translate(${r.x - 2}px, ${r.y - 2}px)`, width: r.w + 4, height: r.h + 4, ['--collab-sel-color' as string]: r.color }}
        />
      ))}
      {cursors.map(u => (
        <div
          key={`cursor-${u.user.sessionId || u.user.id}`}
          className="collab-cursor"
          style={{ transform: `translate(${u.cursor!.worldX}px, ${u.cursor!.worldY}px)` }}
        >
          <svg width="18" height="18" viewBox="0 0 18 18" aria-hidden style={{ display: 'block' }}>
            <path
              d="M2 2 L2 14 L5.5 10.5 L8 15.5 L10 14.5 L7.5 9.5 L12 9.5 Z"
              fill={u.user.color}
              stroke="#fff"
              strokeWidth="1"
            />
          </svg>
          <span className="collab-cursor-label" style={{ background: u.user.color }}>{u.user.name}</span>
        </div>
      ))}
    </ViewportPortal>
  );
}
