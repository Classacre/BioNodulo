import React from 'react';
import { useTranslation } from 'react-i18next';
import type { VersionDiffResult } from './types';
import Icon from '../components/ui/Icon';

interface VersionDiffProps {
  versionA: { id: string; name: string };
  versionB: { id: string; name: string };
  diff: VersionDiffResult;
  isOpen: boolean;
  onClose: () => void;
}

/**
 * Side-by-side diff view of two workflow versions.
 * Shows added nodes in green, removed in red, modified in yellow.
 */
const VersionDiff: React.FC<VersionDiffProps> = ({ versionA, versionB, diff, isOpen, onClose }) => {
  const { t } = useTranslation();

  if (!isOpen) return null;

  const addedNodes = diff.nodes?.added ?? [];
  const removedNodes = diff.nodes?.removed ?? [];
  const modifiedNodes = diff.nodes?.modified ?? [];
  const addedEdges = diff.edges?.added ?? [];
  const removedEdges = diff.edges?.removed ?? [];
  const modifiedEdges = diff.edges?.modified ?? [];
  const addedGroups = diff.groups?.added ?? [];
  const removedGroups = diff.groups?.removed ?? [];
  const modifiedGroups = diff.groups?.modified ?? [];
  const metaChanges = Object.entries(diff.meta_changes ?? {});
  const addedCount = addedNodes.length + addedEdges.length + addedGroups.length;
  const removedCount = removedNodes.length + removedEdges.length + removedGroups.length;
  const modifiedCount = modifiedNodes.length + modifiedEdges.length + modifiedGroups.length + metaChanges.length;
  const hasChanges = addedCount > 0 || removedCount > 0 || modifiedCount > 0;
  const groupChanges = [
    { type: 'added', items: addedGroups, label: t('collab.versionDiffAddedGroup'), side: 'right' as const, color: '#22c55e' },
    { type: 'removed', items: removedGroups, label: t('collab.versionDiffRemovedGroup'), side: 'left' as const, color: '#ef4444' },
    { type: 'modified', items: modifiedGroups, label: t('collab.versionDiffModifiedGroup'), side: 'both' as const, color: '#f59e0b' },
  ].flatMap(group => group.items.map(id => ({
    id,
    key: `${group.type}-group-${id}`,
    label: group.label,
    side: group.side,
    color: group.color,
  })));

  return (
    <div style={{
      position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
      background: 'rgba(0,0,0,0.6)', zIndex: 60,
      display: 'flex', alignItems: 'center', justifyContent: 'center',
    }} onClick={onClose}>
      <div style={{
        width: 700, maxWidth: '90vw', height: '80vh',
        background: 'var(--surface)', borderRadius: 10,
        border: '1px solid var(--border)', display: 'flex', flexDirection: 'column',
        overflow: 'hidden', boxShadow: '0 8px 32px rgba(0,0,0,0.3)',
      }} onClick={e => e.stopPropagation()}>
        {/* Header */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '12px 16px', borderBottom: '1px solid var(--border)' }}>
          <strong style={{ fontSize: 14 }}>{t('collab.versionDiffTitle')}</strong>
          <button className="btn btn-icon btn-xs" onClick={onClose} title={t('common.close')}><Icon name="close" size={12} /></button>
        </div>

        {/* Column headers */}
        <div style={{ display: 'flex', borderBottom: '1px solid var(--border)', background: 'var(--surface-2)' }}>
          <div style={{ flex: 1, padding: '8px 12px', fontSize: 11, fontWeight: 600, color: 'var(--muted)', borderRight: '1px solid var(--border)' }}>
            {versionA.name} <span style={{ fontWeight: 400 }}>{t('collab.versionDiffChangedCount', { count: removedCount + modifiedCount })}</span>
          </div>
          <div style={{ flex: 1, padding: '8px 12px', fontSize: 11, fontWeight: 600, color: 'var(--muted)' }}>
            {versionB.name} <span style={{ fontWeight: 400 }}>{t('collab.versionDiffChangedCount', { count: addedCount + modifiedCount })}</span>
          </div>
        </div>

        {/* Diff content */}
        <div style={{ flex: 1, overflowY: 'auto', padding: '8px 0' }}>
          {!hasChanges && (
            <div style={{ padding: 40, textAlign: 'center', fontSize: 13, color: 'var(--muted)' }}>
              {t('collab.versionDiffNoDifferences')}
            </div>
          )}

          {addedNodes.map(nodeId => (
            <div key={`added-node-${nodeId}`} style={{ display: 'flex', marginBottom: 4 }}>
              <div style={{ flex: 1, padding: '8px 12px', borderRight: '1px solid var(--border)' }} />
              <div style={{ flex: 1, padding: '8px 12px', background: '#22c55e10', borderLeft: '3px solid #22c55e' }}>
                <div style={{ fontSize: 11, fontWeight: 600, color: '#22c55e' }}>{t('collab.versionDiffAddedNode')}</div>
                <code style={{ fontSize: 10, color: 'var(--text)' }}>{nodeId}</code>
              </div>
            </div>
          ))}

          {removedNodes.map(nodeId => (
            <div key={`removed-node-${nodeId}`} style={{ display: 'flex', marginBottom: 4 }}>
              <div style={{ flex: 1, padding: '8px 12px', background: '#ef444410', borderLeft: '3px solid #ef4444', borderRight: '1px solid var(--border)' }}>
                <div style={{ fontSize: 11, fontWeight: 600, color: '#ef4444', textDecoration: 'line-through' }}>{t('collab.versionDiffRemovedNode')}</div>
                <code style={{ fontSize: 10, color: 'var(--text)', textDecoration: 'line-through', opacity: 0.7 }}>{nodeId}</code>
              </div>
              <div style={{ flex: 1, padding: '8px 12px' }} />
            </div>
          ))}

          {modifiedNodes.map(nodeId => (
            <div key={`modified-node-${nodeId}`} style={{ display: 'flex', marginBottom: 4 }}>
              <div style={{ flex: 1, padding: '8px 12px', background: '#f59e0b08', borderRight: '1px solid var(--border)', borderLeft: '3px solid #f59e0b' }}>
                <div style={{ fontSize: 11, fontWeight: 600, color: '#f59e0b' }}>{t('collab.versionDiffModifiedNode')}</div>
                <code style={{ fontSize: 10, color: 'var(--text)' }}>{nodeId}</code>
              </div>
              <div style={{ flex: 1, padding: '8px 12px', background: '#f59e0b08', borderLeft: '3px solid #f59e0b' }}>
                <div style={{ fontSize: 11, fontWeight: 600, color: '#f59e0b' }}>{t('collab.versionDiffModifiedNode')}</div>
                <code style={{ fontSize: 10, color: 'var(--text)' }}>{nodeId}</code>
              </div>
            </div>
          ))}

          {addedEdges.map(edge => (
            <div key={`added-edge-${edge}`} style={{ display: 'flex', marginBottom: 4 }}>
              <div style={{ flex: 1, padding: '8px 12px', borderRight: '1px solid var(--border)' }} />
              <div style={{ flex: 1, padding: '8px 12px', background: '#22c55e10', borderLeft: '3px solid #22c55e' }}>
                <div style={{ fontSize: 11, fontWeight: 600, color: '#22c55e' }}>{t('collab.versionDiffAddedEdge')}</div>
                <code style={{ fontSize: 10, color: 'var(--text)', wordBreak: 'break-all' }}>{edge}</code>
              </div>
            </div>
          ))}

          {removedEdges.map(edge => (
            <div key={`removed-edge-${edge}`} style={{ display: 'flex', marginBottom: 4 }}>
              <div style={{ flex: 1, padding: '8px 12px', background: '#ef444410', borderLeft: '3px solid #ef4444', borderRight: '1px solid var(--border)' }}>
                <div style={{ fontSize: 11, fontWeight: 600, color: '#ef4444', textDecoration: 'line-through' }}>{t('collab.versionDiffRemovedEdge')}</div>
                <code style={{ fontSize: 10, color: 'var(--text)', wordBreak: 'break-all', textDecoration: 'line-through', opacity: 0.7 }}>{edge}</code>
              </div>
              <div style={{ flex: 1, padding: '8px 12px' }} />
            </div>
          ))}

          {modifiedEdges.map(edge => (
            <div key={`modified-edge-${edge}`} style={{ display: 'flex', marginBottom: 4 }}>
              <div style={{ flex: 1, padding: '8px 12px', background: '#f59e0b08', borderRight: '1px solid var(--border)', borderLeft: '3px solid #f59e0b' }}>
                <div style={{ fontSize: 11, fontWeight: 600, color: '#f59e0b' }}>{t('collab.versionDiffModifiedEdge')}</div>
                <code style={{ fontSize: 10, color: 'var(--text)', wordBreak: 'break-all' }}>{edge}</code>
              </div>
              <div style={{ flex: 1, padding: '8px 12px', background: '#f59e0b08', borderLeft: '3px solid #f59e0b' }}>
                <div style={{ fontSize: 11, fontWeight: 600, color: '#f59e0b' }}>{t('collab.versionDiffModifiedEdge')}</div>
                <code style={{ fontSize: 10, color: 'var(--text)', wordBreak: 'break-all' }}>{edge}</code>
              </div>
            </div>
          ))}

          {groupChanges.map(group => (
            <div key={group.key} style={{ display: 'flex', marginBottom: 4 }}>
              {(group.side === 'left' || group.side === 'both') ? (
                <div style={{ flex: 1, padding: '8px 12px', background: `${group.color}10`, borderLeft: `3px solid ${group.color}`, borderRight: '1px solid var(--border)' }}>
                  <div style={{ fontSize: 11, fontWeight: 600, color: group.color }}>{group.label}</div>
                  <code style={{ fontSize: 10, color: 'var(--text)' }}>{group.id}</code>
                </div>
              ) : <div style={{ flex: 1, padding: '8px 12px', borderRight: '1px solid var(--border)' }} />}
              {(group.side === 'right' || group.side === 'both') ? (
                <div style={{ flex: 1, padding: '8px 12px', background: `${group.color}10`, borderLeft: `3px solid ${group.color}` }}>
                  <div style={{ fontSize: 11, fontWeight: 600, color: group.color }}>{group.label}</div>
                  <code style={{ fontSize: 10, color: 'var(--text)' }}>{group.id}</code>
                </div>
              ) : <div style={{ flex: 1, padding: '8px 12px' }} />}
            </div>
          ))}

          {metaChanges.map(([key, change]) => (
            <div key={`meta-${key}`} style={{ display: 'flex', marginBottom: 4 }}>
              <div style={{ flex: 1, padding: '8px 12px', background: '#f59e0b08', borderRight: '1px solid var(--border)', borderLeft: '3px solid #f59e0b' }}>
                <div style={{ fontSize: 11, fontWeight: 600, color: '#f59e0b' }}>{t('collab.versionDiffMetaBefore', { key })}</div>
                <pre style={{ fontSize: 10, color: 'var(--text)', margin: '4px 0 0', whiteSpace: 'pre-wrap', wordBreak: 'break-all' }}>
                  {JSON.stringify(change.before, null, 2)}
                </pre>
              </div>
              <div style={{ flex: 1, padding: '8px 12px', background: '#f59e0b08', borderLeft: '3px solid #f59e0b' }}>
                <div style={{ fontSize: 11, fontWeight: 600, color: '#f59e0b' }}>{t('collab.versionDiffMetaAfter', { key })}</div>
                <pre style={{ fontSize: 10, color: 'var(--text)', margin: '4px 0 0', whiteSpace: 'pre-wrap', wordBreak: 'break-all' }}>
                  {JSON.stringify(change.after, null, 2)}
                </pre>
              </div>
            </div>
          ))}
        </div>

        {/* Footer summary */}
        <div style={{ padding: '8px 16px', borderTop: '1px solid var(--border)', fontSize: 11, color: 'var(--muted)', display: 'flex', gap: 16 }}>
          <span style={{ color: '#22c55e' }}>{t('collab.versionDiffAddedCount', { count: addedCount })}</span>
          <span style={{ color: '#ef4444' }}>{t('collab.versionDiffRemovedCount', { count: removedCount })}</span>
          <span style={{ color: '#f59e0b' }}>{t('collab.versionDiffModifiedCount', { count: modifiedCount })}</span>
        </div>
      </div>
    </div>
  );
};

export default VersionDiff;
