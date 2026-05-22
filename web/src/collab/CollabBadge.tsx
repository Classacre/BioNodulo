import React, { useEffect, useMemo, useRef, useState } from 'react';
import Icon from '../components/ui/Icon';
import type { AwarenessState, LivePresenceUser } from './types';

interface CollabBadgeProps {
  enabled: boolean;
  connected: boolean;
  connecting: boolean;
  activeUsers: AwarenessState[];
  liveUsers?: LivePresenceUser[];
  workflowNames?: Record<string, string>;
  followingUserId: string | null;
  isShared: boolean;
  onShare: () => void;
  onShowUsers: () => void;
  onFollow: (userId: string | null) => void;
  onOpenComments: () => void;
  onOpenVersions: () => void;
  onOpenAudit: () => void;
  onOpenSettings: () => void;
  reconnectAttempt?: number;
  error?: string | null;
  offline?: boolean;
}

function getInitials(name: string): string {
  return name.split(' ').map(w => w[0]).join('').toUpperCase().slice(0, 2);
}

const menuButtonStyle: React.CSSProperties = {
  width: '100%',
  display: 'flex',
  alignItems: 'center',
  gap: 8,
  padding: '7px 8px',
  border: 0,
  borderRadius: 6,
  background: 'transparent',
  color: 'var(--text)',
  fontSize: 12,
  textAlign: 'left',
  cursor: 'pointer',
};

const disabledMenuButtonStyle: React.CSSProperties = {
  ...menuButtonStyle,
  color: 'var(--muted)',
  opacity: 0.55,
  cursor: 'not-allowed',
};

const CollabBadge: React.FC<CollabBadgeProps> = ({
  enabled,
  connected,
  connecting,
  activeUsers,
  liveUsers = [],
  workflowNames = {},
  followingUserId,
  isShared,
  onShare,
  onShowUsers,
  onFollow,
  onOpenComments,
  onOpenVersions,
  onOpenAudit,
  onOpenSettings,
  reconnectAttempt = 0,
  error = null,
  offline = false,
}) => {
  const [open, setOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const handler = (event: MouseEvent) => {
      if (!dropdownRef.current?.contains(event.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [open]);

  const status = useMemo(() => {
    if (!enabled) {
      return { color: '#64748b', text: 'Offline', label: 'Collaboration disabled' };
    }
    if (offline && !connected) {
      return { color: '#6366f1', text: 'Local', label: 'Offline - changes saved locally' };
    }
    if (connected) {
      return connecting
        ? { color: '#f59e0b', text: 'Syncing', label: 'Synchronizing' }
        : { color: '#22c55e', text: 'Live', label: 'Connected' };
    }
    if (connecting || reconnectAttempt > 0) {
      return {
        color: '#f97316',
        text: `Reconnecting${reconnectAttempt > 0 ? ` (${reconnectAttempt})` : ''}`,
        label: `Reconnecting (attempt ${reconnectAttempt})`,
      };
    }
    return { color: '#ef4444', text: 'Offline', label: error || 'Disconnected' };
  }, [enabled, offline, connected, connecting, reconnectAttempt, error]);

  const followUsers = liveUsers.length > 0
    ? liveUsers
    : activeUsers.map(user => ({
        session_id: user.user.sessionId || user.user.id,
        user_id: user.user.id,
        name: user.user.name,
        color: user.user.color,
        role: user.user.role || 'editor',
        workflow_id: user.user.workflowId || '',
      }));
  const userCount = liveUsers.length > 0 ? liveUsers.length : activeUsers.length;
  const followedUser = followingUserId ? followUsers.find(user => user.user_id === followingUserId) : null;

  const closeThen = (action: () => void) => {
    action();
    setOpen(false);
  };

  return (
    <div ref={dropdownRef} style={{ position: 'relative', display: 'inline-flex' }}>
      <button
        className="collab-badge btn btn-sm"
        onClick={() => setOpen(value => !value)}
        title={`Collaboration: ${status.label}${isShared ? ' | Shared' : ''}`}
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 6,
          border: `1px solid ${status.color}40`,
          background: `${status.color}10`,
          color: status.color,
        }}
      >
        <span
          style={{
            width: 7,
            height: 7,
            borderRadius: '50%',
            backgroundColor: status.color,
            display: 'inline-block',
            boxShadow: `0 0 0 2px ${status.color}30`,
            animation: connecting && enabled && !connected ? 'pulse 1.5s infinite' : undefined,
          }}
        />
        <span style={{ fontSize: 11, fontWeight: 600 }}>{status.text}</span>
        {enabled && userCount > 0 && (
          <span style={{
            fontSize: 10,
            fontWeight: 700,
            background: `${status.color}20`,
            padding: '1px 5px',
            borderRadius: 8,
          }}>
            {userCount + 1}
          </span>
        )}
        <Icon name="chevronDown" size={12} />
      </button>

      {open && (
        <div
          style={{
            position: 'absolute',
            top: '100%',
            right: 0,
            marginTop: 8,
            width: 260,
            background: 'var(--surface)',
            border: '1px solid var(--border)',
            borderRadius: 8,
            boxShadow: '0 10px 30px rgba(0,0,0,0.25)',
            zIndex: 250,
            padding: 8,
          }}
        >
          <div style={{ padding: '4px 6px 8px', borderBottom: '1px solid var(--border)' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 12, fontWeight: 700 }}>
              <span style={{ width: 8, height: 8, borderRadius: '50%', background: status.color }} />
              {status.label}
            </div>
            {error && enabled && (
              <div style={{ fontSize: 11, color: 'var(--muted)', marginTop: 4 }}>{error}</div>
            )}
          </div>

          <div style={{ padding: '8px 0', display: 'grid', gap: 2 }}>
            {!enabled && (
              <div style={{ fontSize: 11, color: 'var(--muted)', padding: '4px 6px 8px' }}>
                Local mode is active. Enable collaboration in Settings to use sharing, comments, versions, and audit history.
              </div>
            )}
            <button style={enabled ? menuButtonStyle : disabledMenuButtonStyle} onClick={() => closeThen(onShare)} disabled={!enabled}>
              <Icon name="link" size={14} /> Share workflow
            </button>
            <button style={enabled ? menuButtonStyle : disabledMenuButtonStyle} onClick={onShowUsers} disabled={!enabled}>
              <Icon name="users" size={14} /> Active users
              {enabled && <span style={{ marginLeft: 'auto', color: 'var(--muted)' }}>{userCount + 1}</span>}
            </button>
            <button style={enabled ? menuButtonStyle : disabledMenuButtonStyle} onClick={() => closeThen(onOpenComments)} disabled={!enabled}>
              <Icon name="comment" size={14} /> Comments
            </button>
            <button style={enabled ? menuButtonStyle : disabledMenuButtonStyle} onClick={() => closeThen(onOpenVersions)} disabled={!enabled}>
              <Icon name="clock" size={14} /> Version history
            </button>
            <button style={enabled ? menuButtonStyle : disabledMenuButtonStyle} onClick={() => closeThen(onOpenAudit)} disabled={!enabled}>
              <Icon name="activity" size={14} /> Audit log
            </button>
            <button style={menuButtonStyle} onClick={() => closeThen(onOpenSettings)}>
              <Icon name="settings" size={14} /> Collaboration settings
            </button>
          </div>

          <div style={{ borderTop: '1px solid var(--border)', paddingTop: 8 }}>
            <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--muted)', padding: '0 6px 6px' }}>
              Follow Viewport
            </div>
            {followedUser && (
              <button style={menuButtonStyle} onClick={() => onFollow(null)}>
                <Icon name="eye" size={14} /> Stop following {followedUser.name}
              </button>
            )}
            {followUsers.length === 0 && (
              <div style={{ fontSize: 11, color: 'var(--muted)', padding: '6px' }}>No other users are active.</div>
            )}
            {followUsers.map(user => (
              <button
                key={`${user.workflow_id}:${user.session_id}`}
                style={{
                  ...menuButtonStyle,
                  background: followingUserId === user.user_id ? 'var(--accent-soft, rgba(59, 130, 246, 0.15))' : 'transparent',
                }}
                onClick={() => closeThen(() => onFollow(user.user_id))}
              >
                <span style={{
                  width: 20,
                  height: 20,
                  borderRadius: '50%',
                  background: user.color,
                  color: '#fff',
                  display: 'inline-flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontSize: 8,
                  fontWeight: 700,
                }}>
                  {getInitials(user.name)}
                </span>
                <span style={{ minWidth: 0, display: 'grid', overflow: 'hidden' }}>
                  <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {user.name}
                  </span>
                  {user.workflow_id ? (
                    <span style={{ fontSize: 10, color: 'var(--muted)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {workflowNames[user.workflow_id] || `Workflow ${user.workflow_id.slice(0, 10)}`}
                    </span>
                  ) : null}
                </span>
              </button>
            ))}
          </div>
        </div>
      )}

      <style>{`
        @keyframes pulse {
          0% { opacity: 1; }
          50% { opacity: 0.4; }
          100% { opacity: 1; }
        }
      `}</style>
    </div>
  );
};

export default CollabBadge;
