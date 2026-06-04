import React, { useEffect, useMemo, useRef, useState } from 'react';
import { useSetAtom } from 'jotai';
import { useTranslation } from 'react-i18next';
import Icon from '../components/ui/Icon';
import type { AwarenessState, LivePresenceUser } from './types';
import UserList from './UserList';
import {
  showAuditAtom,
  showCommentsAtom,
  showShareDialogAtom,
  showVersionsAtom,
} from '../state/uiAtoms';

interface CollabBadgeProps {
  enabled: boolean;
  connected: boolean;
  connecting: boolean;
  activeUsers: AwarenessState[];
  liveUsers?: LivePresenceUser[];
  currentUserId?: string;
  currentSessionId?: string;
  currentWorkflowId: string;
  workflowNames?: Record<string, string>;
  followingUserId: string | null;
  isShared: boolean;
  onFollow: (userId: string | null) => void;
  onOpenSettings: () => void;
  onCreateSession: () => void;
  onJoinSession: () => void;
  onLeaveSession: () => void;
  hasJoinLink?: boolean;
  shareLink?: string;
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
  currentUserId,
  currentSessionId,
  currentWorkflowId,
  workflowNames = {},
  followingUserId,
  isShared,
  onFollow,
  onOpenSettings,
  onCreateSession,
  onJoinSession,
  onLeaveSession,
  hasJoinLink = false,
  shareLink = '',
  reconnectAttempt = 0,
  error = null,
  offline = false,
}) => {
  const { t } = useTranslation();
  const setShowShareDialog = useSetAtom(showShareDialogAtom);
  const setShowComments = useSetAtom(showCommentsAtom);
  const setShowVersions = useSetAtom(showVersionsAtom);
  const setShowAudit = useSetAtom(showAuditAtom);
  const [open, setOpen] = useState(false);
  const [usersOpen, setUsersOpen] = useState(false);
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
      if (hasJoinLink) {
        return { color: '#0d9488', text: t('collab.badgeJoin'), label: t('collab.badgeLinkReady') };
      }
      return { color: '#64748b', text: t('collab.badgeOffline'), label: t('collab.badgeDisabled') };
    }
    if (offline && !connected) {
      return { color: '#6366f1', text: t('collab.badgeLocal'), label: t('collab.badgeLocalChangesSaved') };
    }
    if (connected) {
      return connecting
        ? { color: '#f59e0b', text: t('collab.badgeSyncing'), label: t('collab.badgeSynchronizing') }
        : { color: '#22c55e', text: t('collab.badgeLive'), label: t('collab.badgeConnected') };
    }
    if (connecting || reconnectAttempt > 0) {
      return {
        color: '#f97316',
        text: reconnectAttempt > 0
          ? t('collab.badgeReconnectingWithAttempt', { count: reconnectAttempt })
          : t('collab.badgeReconnecting'),
        label: t('collab.badgeReconnectingAttempt', { count: reconnectAttempt }),
      };
    }
    return { color: '#ef4444', text: t('collab.badgeOffline'), label: error || t('collab.badgeDisconnected') };
  }, [enabled, hasJoinLink, offline, connected, connecting, reconnectAttempt, error, t]);

  const liveOtherUsers = liveUsers.filter(user => (
    currentSessionId ? user.session_id !== currentSessionId : user.user_id !== currentUserId
  ));
  const followUsers = liveUsers.length > 0
    ? liveOtherUsers
    : activeUsers.map(user => ({
        session_id: user.user.sessionId || user.user.id,
        user_id: user.user.id,
        name: user.user.name,
        color: user.user.color,
        role: user.user.role || 'editor',
        workflow_id: user.user.workflowId || '',
      })).filter(user => (
        currentSessionId ? user.session_id !== currentSessionId : user.user_id !== currentUserId
      ));
  const userCount = liveUsers.length > 0 ? liveUsers.length : activeUsers.length + 1;
  const followedUser = followingUserId
    ? [...liveUsers, ...followUsers].find(user => user.session_id === followingUserId || user.user_id === followingUserId)
    : null;

  const closeThen = (action: () => void) => {
    action();
    setOpen(false);
  };

  return (
    <div ref={dropdownRef} style={{ position: 'relative', display: 'inline-flex' }}>
      <button
        className="collab-badge btn btn-sm"
        onClick={() => setOpen(value => !value)}
        title={isShared ? t('collab.badgeTitleShared', { status: status.label }) : t('collab.badgeTitle', { status: status.label })}
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
            {userCount}
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
                {t('collab.badgeOfflineNotice')}
              </div>
            )}
            {!enabled && (
              <>
                <button style={menuButtonStyle} onClick={() => closeThen(onCreateSession)}>
                  <Icon name="link" size={14} /> {t('collab.badgeCreateLink')}
                </button>
                <button style={menuButtonStyle} onClick={() => closeThen(onJoinSession)}>
                  <Icon name="users" size={14} /> {t('collab.badgeJoinCollaboration')}
                </button>
              </>
            )}
            {enabled && (
              <>
                <button style={menuButtonStyle} onClick={() => closeThen(() => setShowShareDialog(true))}>
                  <Icon name="link" size={14} /> {t('collab.shareDialogTitle')}
                </button>
                <button style={menuButtonStyle} onClick={() => setUsersOpen(value => !value)}>
                  <Icon name="users" size={14} /> {t('collab.badgeActiveUsers')}
                  <span style={{ marginLeft: 'auto', color: 'var(--muted)' }}>{userCount}</span>
                  <Icon name={usersOpen ? 'chevronUp' : 'chevronDown'} size={12} />
                </button>
              </>
            )}
            {usersOpen && enabled && (
              <UserList
                users={liveUsers}
                currentUserId={currentUserId}
                currentSessionId={currentSessionId}
                currentWorkflowId={currentWorkflowId}
                workflowNames={workflowNames}
                isOpen
                embedded
                onClose={() => setUsersOpen(false)}
              />
            )}
            <button style={enabled ? menuButtonStyle : disabledMenuButtonStyle} onClick={() => closeThen(() => setShowComments(value => !value))} disabled={!enabled}>
              <Icon name="comment" size={14} /> {t('collab.commentsTitle')}
            </button>
            <button style={enabled ? menuButtonStyle : disabledMenuButtonStyle} onClick={() => closeThen(() => setShowVersions(value => !value))} disabled={!enabled}>
              <Icon name="clock" size={14} /> {t('collab.versionHistoryTitle')}
            </button>
            <button style={enabled ? menuButtonStyle : disabledMenuButtonStyle} onClick={() => closeThen(() => setShowAudit(value => !value))} disabled={!enabled}>
              <Icon name="activity" size={14} /> {t('collab.badgeAuditLog')}
            </button>
            {enabled && (
              <button style={menuButtonStyle} onClick={() => closeThen(onLeaveSession)}>
                <Icon name="circle" size={14} /> {t('collab.badgeStopCollaboration')}
              </button>
            )}
            <button style={menuButtonStyle} onClick={() => closeThen(onOpenSettings)}>
              <Icon name="settings" size={14} /> {t('collab.badgeSettings')}
            </button>
          </div>

          {enabled && shareLink && (
            <div style={{ borderTop: '1px solid var(--border)', padding: '8px 6px', fontSize: 10, color: 'var(--muted)', wordBreak: 'break-all' }}>
              {shareLink}
            </div>
          )}

          {enabled && (
            <div style={{ borderTop: '1px solid var(--border)', paddingTop: 8 }}>
              <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--muted)', padding: '0 6px 6px' }}>
                {t('collab.badgeFollowViewport')}
              </div>
              {followedUser && (
                <button style={menuButtonStyle} onClick={() => onFollow(null)}>
                  <Icon name="eye" size={14} /> {t('collab.badgeStopFollowing', { name: followedUser.name })}
                </button>
              )}
              {followUsers.length === 0 && (
                <div style={{ fontSize: 11, color: 'var(--muted)', padding: '6px' }}>{t('collab.badgeNoOtherUsersActive')}</div>
              )}
              {followUsers.map(user => (
                <button
                  key={`${user.workflow_id}:${user.session_id}`}
                  style={{
                    ...menuButtonStyle,
                    background: followingUserId === user.session_id ? 'var(--accent-soft, rgba(59, 130, 246, 0.15))' : 'transparent',
                  }}
                  onClick={() => closeThen(() => onFollow(user.session_id))}
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
                        {workflowNames[user.workflow_id] || t('collab.badgeWorkflowFallback', { id: user.workflow_id.slice(0, 10) })}
                      </span>
                    ) : null}
                  </span>
                </button>
              ))}
            </div>
          )}
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
