import React, { useMemo } from 'react';
import type { AwarenessState } from './types';

interface ForeignCursorsProps {
  activeUsers: AwarenessState[];
  currentUserId: string;
}

const ForeignCursors: React.FC<ForeignCursorsProps> = ({ activeUsers, currentUserId }) => {
  const otherUsers = useMemo(() => {
    return activeUsers.filter(u => u.user.id !== currentUserId);
  }, [activeUsers, currentUserId]);

  const cursors = useMemo(() => {
    return otherUsers.filter(u => u.cursor?.visible);
  }, [otherUsers]);

  const selections = useMemo(() => {
    return otherUsers.filter(u => u.selection?.nodeIds?.length > 0);
  }, [otherUsers]);

  return (
    <div style={{ position: 'absolute', inset: 0, pointerEvents: 'none', zIndex: 100, overflow: 'hidden' }}>
      {/* Foreign selections (translucent boxes around selected nodes) */}
      {selections.map(u => (
        <React.Fragment key={`sel-${u.user.id}`}>
          {u.selection.nodeIds.map((nodeId, idx) => (
            <div
              key={`${u.user.id}-${nodeId}-${idx}`}
              style={{
                position: 'absolute',
                left: u.cursor?.x ?? 0,
                top: u.cursor?.y ?? 0,
                width: 120,
                height: 60,
                border: `2px solid ${u.user.color}`,
                background: `${u.user.color}20`,
                borderRadius: 4,
                pointerEvents: 'none',
                zIndex: 101,
              }}
            />
          ))}
        </React.Fragment>
      ))}

      {/* Foreign cursors */}
      {cursors.map(u => (
        <div
          key={`cursor-${u.user.id}`}
          style={{
            position: 'absolute',
            left: u.cursor!.x,
            top: u.cursor!.y,
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
              backgroundColor: u.user.color,
              boxShadow: `0 0 4px ${u.user.color}`,
            }}
          />
          <span
            style={{
              position: 'absolute',
              left: 10,
              top: -4,
              fontSize: 11,
              color: u.user.color,
              background: 'rgba(0,0,0,0.7)',
              padding: '1px 4px',
              borderRadius: 3,
              whiteSpace: 'nowrap',
            }}
          >
            {u.user.name}
          </span>
        </div>
      ))}

      {/* Drag ownership indicators */}
      {otherUsers
        .filter(u => u.dragOwnership?.nodeId)
        .map(u => (
          <div
            key={`lock-${u.user.id}`}
            style={{
              position: 'absolute',
              left: u.cursor?.x ?? 0,
              top: (u.cursor?.y ?? 0) - 20,
              fontSize: 11,
              color: u.user.color,
              background: 'rgba(0,0,0,0.8)',
              padding: '2px 6px',
              borderRadius: 4,
              whiteSpace: 'nowrap',
              zIndex: 103,
            }}
          >
            Locked by {u.user.name}
          </div>
        ))}
    </div>
  );
};

export default ForeignCursors;
