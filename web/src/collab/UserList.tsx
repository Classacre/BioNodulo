import React, { useCallback, useEffect, useMemo, useState } from 'react';
import Icon from '../components/ui/Icon';
import { getToken } from './auth';
import type { CollabRole, LivePresenceUser } from './types';

interface ShareRecord {
  id: string;
  workflow_id: string;
  user_id: string;
  role: CollabRole;
}

interface UserListProps {
  users: LivePresenceUser[];
  currentUserId?: string;
  currentSessionId?: string;
  currentWorkflowId: string;
  workflowNames?: Record<string, string>;
  isOpen: boolean;
  onClose: () => void;
  embedded?: boolean;
}

function getInitials(name: string): string {
  return name.split(' ').map(word => word[0]).join('').toUpperCase().slice(0, 2);
}

function roleLabel(role: CollabRole): string {
  return role === 'owner' ? 'Admin' : `${role[0].toUpperCase()}${role.slice(1)}`;
}

const roleChipColors: Record<CollabRole, string> = {
  owner: '#0f766e',
  editor: '#2563eb',
  commenter: '#7c3aed',
  viewer: '#64748b',
};

const UserList: React.FC<UserListProps> = ({
  users,
  currentUserId,
  currentSessionId,
  currentWorkflowId,
  workflowNames = {},
  isOpen,
  onClose,
  embedded = false,
}) => {
  const [shares, setShares] = useState<Record<string, ShareRecord[]>>({});
  const [menuFor, setMenuFor] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const workflows = useMemo(() => Array.from(new Set(users.map(user => user.workflow_id))), [users]);

  const fetchShares = useCallback(async () => {
    const token = getToken();
    if (!token) return;
    const entries = await Promise.all(workflows.map(async workflowId => {
      const response = await fetch(`/api/collab/shares/${workflowId}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!response.ok) return [workflowId, []] as const;
      const data = await response.json() as { shares?: ShareRecord[] };
      return [workflowId, data.shares ?? []] as const;
    }));
    setShares(Object.fromEntries(entries));
  }, [workflows]);

  useEffect(() => {
    if (!isOpen) return;
    void fetchShares();
  }, [fetchShares, isOpen]);

  const currentRoles = useMemo(() => {
    const entries = Object.entries(shares).map(([workflowId, records]) => [
      workflowId,
      records.find(share => share.user_id === currentUserId)?.role,
    ]);
    return Object.fromEntries(entries) as Record<string, CollabRole | undefined>;
  }, [currentUserId, shares]);

  const mutateRole = async (user: LivePresenceUser, role: Exclude<CollabRole, 'owner'>) => {
    const token = getToken();
    if (!token) return;
    setError(null);
    const response = await fetch('/api/collab/share', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
      body: JSON.stringify({ workflow_id: user.workflow_id, user_id: user.user_id, role }),
    });
    if (!response.ok) {
      setError(`Could not change ${user.name}'s role.`);
      return;
    }
    setMenuFor(null);
    void fetchShares();
  };

  const kickUser = async (user: LivePresenceUser) => {
    const token = getToken();
    const share = shares[user.workflow_id]?.find(record => record.user_id === user.user_id);
    if (!token || !share) return;
    setError(null);
    const response = await fetch(`/api/collab/share/${share.id}`, {
      method: 'DELETE',
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!response.ok) {
      setError(`Could not remove ${user.name}.`);
      return;
    }
    setMenuFor(null);
    void fetchShares();
  };

  if (!isOpen) return null;

  return (
    <div className="collab-user-list" style={{
      position: embedded ? 'relative' : 'fixed',
      right: embedded ? undefined : 0,
      top: embedded ? undefined : 0,
      width: embedded ? '100%' : 340,
      maxWidth: embedded ? undefined : 'calc(100vw - 48px)',
      height: embedded ? 'min(360px, calc(100vh - 220px))' : '100vh',
      overflow: 'hidden',
      background: 'var(--surface)',
      border: embedded ? '1px solid var(--border)' : undefined,
      borderLeft: embedded ? '1px solid var(--border)' : '1px solid var(--border)',
      borderRadius: embedded ? 8 : 0,
      zIndex: embedded ? 1 : 265,
      boxShadow: embedded ? 'none' : '-10px 0 32px rgba(0,0,0,0.18)',
      display: 'flex',
      flexDirection: 'column',
    }}>
      <div style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        padding: '12px 14px',
        borderBottom: '1px solid var(--border)',
        flexShrink: 0,
      }}>
        <strong style={{ fontSize: 13 }}>Active Users</strong>
        <button className="btn btn-icon btn-xs" onClick={onClose} title="Close">
          <Icon name="close" size={12} />
        </button>
      </div>
      <div style={{ padding: 12, overflowY: 'auto', flex: 1 }}>
      {error ? <div style={{ color: 'var(--danger)', fontSize: 11, marginBottom: 8 }}>{error}</div> : null}
      {users.length === 0 ? (
        <div style={{ fontSize: 12, color: 'var(--muted)', padding: '8px 0' }}>No live collaboration sessions</div>
      ) : null}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        {users.map(user => {
          const itemKey = `${user.workflow_id}:${user.session_id}`;
          const workflowRole = shares[user.workflow_id]?.find(share => share.user_id === user.user_id)?.role ?? user.role;
          const canAdmin = currentRoles[user.workflow_id] === 'owner'
            && user.user_id !== currentUserId
            && workflowRole !== 'owner';
          return (
            <div key={itemKey} style={{ position: 'relative', display: 'flex', alignItems: 'center', gap: 8, padding: 6, borderRadius: 7, background: user.workflow_id === currentWorkflowId ? 'var(--surface-2)' : 'transparent' }}>
              <div style={{
                width: 28,
                height: 28,
                borderRadius: '50%',
                backgroundColor: user.color,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontSize: 10,
                fontWeight: 700,
                color: '#fff',
                flexShrink: 0,
              }}>{getInitials(user.name)}</div>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
                  <span style={{ fontSize: 12, fontWeight: 600, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                    {user.name}{user.session_id === currentSessionId || (!currentSessionId && user.user_id === currentUserId) ? ' (You)' : ''}
                  </span>
                  <span style={{ fontSize: 9, padding: '2px 5px', borderRadius: 10, background: `${roleChipColors[workflowRole]}20`, color: roleChipColors[workflowRole], fontWeight: 700 }}>
                    {roleLabel(workflowRole)}
                  </span>
                </div>
                <div title={user.workflow_id} style={{ fontSize: 10, color: 'var(--muted)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                  {workflowNames[user.workflow_id] || `Workflow ${user.workflow_id.slice(0, 12)}`}
                </div>
              </div>
              {canAdmin ? (
                <button className="btn btn-icon btn-xs" title="Manage access" onClick={() => setMenuFor(menuFor === itemKey ? null : itemKey)}>
                  <Icon name="menu" size={13} />
                </button>
              ) : null}
              {menuFor === itemKey ? (
                <div style={{
                  position: 'absolute',
                  top: 38,
                  right: 4,
                  width: 144,
                  zIndex: 2,
                  border: '1px solid var(--border)',
                  borderRadius: 7,
                  background: 'var(--surface)',
                  boxShadow: '0 8px 20px rgba(0,0,0,0.2)',
                  padding: 5,
                  display: 'grid',
                  gap: 2,
                }}>
                  {(['editor', 'commenter', 'viewer'] as const).map(role => (
                    <button key={role} className="btn btn-xs" onClick={() => void mutateRole(user, role)} style={{ justifyContent: 'flex-start' }}>
                      Make {roleLabel(role)}
                    </button>
                  ))}
                  <button className="btn btn-xs" onClick={() => void kickUser(user)} style={{ justifyContent: 'flex-start', color: 'var(--danger)' }}>
                    Kick user
                  </button>
                </div>
              ) : null}
            </div>
          );
        })}
      </div>
      </div>
    </div>
  );
};

export default UserList;
