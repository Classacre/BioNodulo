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

  return (
    <div style={{ position: 'absolute', inset: 0, pointerEvents: 'none', zIndex: 100, overflow: 'hidden' }}>
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

    </div>
  );
};

export default ForeignCursors;
