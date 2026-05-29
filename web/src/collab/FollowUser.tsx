import React, { useState, useRef, useEffect } from 'react';
import type { AwarenessState } from './types';
import Icon from '../components/ui/Icon';

interface FollowUserProps {
  users: AwarenessState[];
  followingUserId: string | null;
  onFollow: (userId: string | null) => void;
}

function getInitials(name: string): string {
  return name.split(' ').map(w => w[0]).join('').toUpperCase().slice(0, 2);
}

/**
 * Follow User dropdown button.
 * Shows active users with "Follow" buttons.
 * When following, displays the followed user's name with an unfollow button.
 * Smooth viewport animation is triggered externally via the onFollow callback.
 */
const FollowUser: React.FC<FollowUserProps> = ({ users, followingUserId, onFollow }) => {
  const [open, setOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  // Close dropdown on outside click
  useEffect(() => {
    if (!open) return;
    const handler = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [open]);

  const followedUser = followingUserId ? users.find(u => u.user.id === followingUserId) : null;

  return (
    <div ref={dropdownRef} style={{ position: 'relative', display: 'inline-flex' }}>
      {followedUser ? (
        <button
          className="btn btn-sm"
          onClick={() => setOpen(v => !v)}
          title={`Following ${followedUser.user.name}. Click to unfollow.`}
          style={{
            display: 'flex', alignItems: 'center', gap: 5,
            border: `1px solid ${followedUser.user.color}40`,
            background: `${followedUser.user.color}15`,
            color: followedUser.user.color, fontSize: 11, fontWeight: 600,
          }}
        >
          <span style={{
            width: 14, height: 14, borderRadius: '50%', backgroundColor: followedUser.user.color,
            display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 7, fontWeight: 700, color: '#fff',
          }}>{getInitials(followedUser.user.name)}</span>
          <span>Following {followedUser.user.name}</span>
          <span onClick={e => { e.stopPropagation(); onFollow(null); }} style={{ cursor: 'pointer', marginLeft: 2, display: 'inline-flex' }}><Icon name="close" size={10} /></span>
        </button>
      ) : (
        <button
          className="btn btn-sm"
          onClick={() => setOpen(v => !v)}
          title="Follow a user's viewport"
          style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 11 }}
        >
          <Icon name="eye" size={12} />
          <span>Follow</span>
          {users.length > 0 && (
            <span style={{ fontSize: 9, fontWeight: 700, background: 'var(--accent, #3b82f6)', color: '#fff', padding: '0 5px', borderRadius: 8 }}>
              {users.length}
            </span>
          )}
        </button>
      )}

      {/* Dropdown */}
      {open && (
        <div style={{
          position: 'absolute', top: '100%', right: 0, marginTop: 6,
          minWidth: 200, background: 'var(--surface)',
          border: '1px solid var(--border)', borderRadius: 8,
          boxShadow: '0 4px 12px rgba(0,0,0,0.15)', zIndex: 200,
          padding: 8, display: 'flex', flexDirection: 'column', gap: 4,
        }}>
          <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--muted)', padding: '2px 6px 4px' }}>
            Active Users
          </div>
          {users.length === 0 && (
            <div style={{ fontSize: 11, color: 'var(--muted)', padding: '6px' }}>No active users</div>
          )}
          {users.map(u => (
            <div key={u.user.id} style={{
              display: 'flex', alignItems: 'center', gap: 8, padding: '5px 6px',
              borderRadius: 4, cursor: 'pointer',
              background: followingUserId === u.user.id ? 'var(--accent, #3b82f6)15' : 'transparent',
            }} onClick={() => { onFollow(u.user.id); setOpen(false); }}>
              <div style={{
                width: 20, height: 20, borderRadius: '50%', backgroundColor: u.user.color,
                display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 8, fontWeight: 700, color: '#fff', flexShrink: 0,
              }}>{getInitials(u.user.name)}</div>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontSize: 11, fontWeight: 600, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                  {u.user.name}
                </div>
                <div style={{ fontSize: 9, color: 'var(--muted)' }}>
                  {u.activity === 'active' ? 'Active' : u.activity === 'idle' ? 'Idle' : u.activity === 'dragging' ? 'Dragging' : 'Typing'}
                </div>
              </div>
              <button className="btn btn-xs" style={{ fontSize: 9, padding: '2px 8px', flexShrink: 0 }}>
                {followingUserId === u.user.id ? 'Unfollow' : 'Follow'}
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default FollowUser;
