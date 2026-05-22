import React from 'react';
import Icon from '../components/ui/Icon';

interface CommentPinProps {
  commentCount: number;
  hasUnresolved: boolean;
  onClick: () => void;
  x: number;
  y: number;
}

/**
 * Small comment pin rendered on canvas nodes.
 * Shows comment count with a colored circle.
 * Red dot indicator appears when there are unresolved comments.
 */
const CommentPin: React.FC<CommentPinProps> = ({
  commentCount,
  hasUnresolved,
  onClick,
  x,
  y,
}) => {
  if (commentCount === 0) return null;

  return (
    <div
      onClick={onClick}
      title={`${commentCount} comment${commentCount !== 1 ? 's' : ''}${hasUnresolved ? ` (${commentCount} unresolved)` : ''}`}
      style={{
        position: 'absolute',
        left: x + 8,
        top: y - 28,
        zIndex: 30,
        cursor: 'pointer',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        minWidth: 24,
        height: 24,
        borderRadius: 12,
        border: '1px solid var(--border)',
        background: 'var(--surface)',
        color: hasUnresolved ? '#ef4444' : 'var(--accent)',
        fontSize: 10,
        fontWeight: 700,
        gap: 2,
        padding: '0 5px',
        boxShadow: '0 2px 6px rgba(0,0,0,0.3)',
        transition: 'transform 0.15s ease',
        userSelect: 'none',
      }}
      onMouseEnter={e => { (e.currentTarget as HTMLDivElement).style.transform = 'scale(1.15)'; }}
      onMouseLeave={e => { (e.currentTarget as HTMLDivElement).style.transform = 'scale(1)'; }}
    >
      <Icon name="comment" size={13} />
      {commentCount}
      {/* Unresolved indicator pulse */}
      {hasUnresolved && (
        <span style={{
          position: 'absolute',
          top: -2,
          right: -2,
          width: 7,
          height: 7,
          borderRadius: '50%',
          background: '#fbbf24',
          border: '1.5px solid var(--surface)',
        }} />
      )}
    </div>
  );
};

export default CommentPin;
