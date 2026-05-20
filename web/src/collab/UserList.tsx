import React, { useState } from 'react';
import type { AwarenessState } from './types';

interface UserListProps {
  users: AwarenessState[];
  currentUserId?: string;
  isOpen: boolean;
  onClose: () => void;
}

function getInitials(name: string): string {
  return name
    .split(' ')
    .map(w => w[0])
    .join('')
    .toUpperCase()
    .slice(0, 2);
}

const UserList: React.FC<UserListProps> = ({ users, currentUserId, isOpen, onClose }) => {
  const displayUsers = currentUserId ? users.filter(u => u.user.id !== currentUserId) : users;
  if (!isOpen) return null;
  return (
    <div className="collab-user-list" style={{
      position: 'absolute',
      right: 12,
      top: 48,
      width: 220,
      background: 'var(--surface)',
      border: '1px solid var(--border)',
      borderRadius: 8,
      padding: 12,
      zIndex: 120,
      boxShadow: '0 4px 12px rgba(0,0,0,0.15)',
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
        <strong style={{ fontSize: 13 }}>Active Users</strong>
        <button className="btn btn-icon btn-xs" onClick={onClose} title="Close">
          <span style={{ fontSize: 12 }}>×</span>
        </button>
      </div>
      {displayUsers.length === 0 && (
        <div style={{ fontSize: 12, color: 'var(--muted)', padding: '8px 0' }}>No other users in this room</div>
      )}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        {displayUsers.map(u => (
          <div key={u.user.id} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <div style={{
              width: 24,
              height: 24,
              borderRadius: '50%',
              backgroundColor: u.user.color,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontSize: 10,
              fontWeight: 700,
              color: '#fff',
              flexShrink: 0,
            }}>
              {getInitials(u.user.name)}
            </div>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontSize: 12, fontWeight: 600, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                {u.user.name}
              </div>
              <div style={{ fontSize: 10, color: 'var(--muted)' }}>
                {u.activity === 'active' ? 'Active' : u.activity === 'idle' ? 'Idle' : u.activity === 'dragging' ? 'Dragging' : 'Typing'}
              </div>
            </div>
            <div style={{
              width: 6,
              height: 6,
              borderRadius: '50%',
              backgroundColor: u.activity === 'active' || u.activity === 'dragging' ? '#22c55e' : '#94a3b8',
            }} />
          </div>
        ))}
      </div>
    </div>
  );
};

export default UserList;
