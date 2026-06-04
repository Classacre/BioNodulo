import { useState, useEffect, useRef } from 'react';
import { useTranslation } from 'react-i18next';

const PRESET_COLORS = [
  '#ef4444', '#f97316', '#f59e0b', '#84cc16', '#22c55e',
  '#10b981', '#14b8a6', '#06b6d4', '#0ea5e9', '#3b82f6',
  '#6366f1', '#8b5cf6', '#a855f7', '#d946ef', '#ec4899',
  '#f43f5e', '#64748b', '#94a3b8',
];

interface NodeContextMenuProps {
  x: number;
  y: number;
  nodeId: string | null;
  onAction: (action: string, nodeId: string, extra?: string) => void;
  onClose: () => void;
}

export default function NodeContextMenu({ x, y, nodeId, onAction, onClose }: NodeContextMenuProps) {
  const { t } = useTranslation();
  const ref = useRef<HTMLDivElement>(null);
  const [showColors, setShowColors] = useState(false);

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (!ref.current?.contains(e.target as Node)) onClose();
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [onClose]);

  if (showColors) {
    return (
      <div ref={ref} className="context-menu" style={{ left: x, top: y }}>
        <div className="context-menu-body">
          <div className="context-menu-item" onClick={() => setShowColors(false)}>{t('nodeContextMenu.back')}</div>
          <div className="context-menu-sep" />
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(6, 1fr)', gap: 4, padding: '4px 8px' }}>
            {PRESET_COLORS.map(c => (
              <div
                key={c}
                style={{ width: 20, height: 20, borderRadius: 4, background: c, cursor: 'pointer', border: '1px solid var(--border)' }}
                onClick={() => { onAction('color', nodeId || '', c); setShowColors(false); }}
              />
            ))}
          </div>
        </div>
      </div>
    );
  }

  const items = nodeId ? [
    { label: t('nodeContextMenu.editProperties'), action: 'edit' },
    { label: t('common.rename'), action: 'rename' },
    { label: t('nodeContextMenu.nodeInfo'), action: 'info' },
    { label: t('nodeContextMenu.addComment'), action: 'comment' },
    { label: t('common.duplicate'), action: 'duplicate' },
    null,
    { label: t('nodeContextMenu.muteNode'), action: 'mute' },
    { label: t('nodeContextMenu.bypassNode'), action: 'bypass' },
    { label: t('nodeContextMenu.pinLockNode'), action: 'pin' },
    { label: t('nodeContextMenu.collapseExpand'), action: 'collapse' },
    null,
    { label: t('nodeContextMenu.setAsOutput'), action: 'output' },
    { label: t('nodeContextMenu.setColor'), action: 'color', handler: () => setShowColors(true) },
    { label: t('nodeContextMenu.roundShape'), action: 'shape:round' },
    { label: t('nodeContextMenu.boxShape'), action: 'shape:box' },
    { label: t('nodeContextMenu.cardShape'), action: 'shape:card' },
    null,
    { label: t('nodeContextMenu.groupSelected'), action: 'group' },
    { label: t('nodeContextMenu.createSubgraph'), action: 'subgraph' },
    { label: t('nodeContextMenu.saveSubgraphToLibrary'), action: 'saveSubgraphBlueprint' },
    { label: t('nodeContextMenu.promoteWidgetsToParent'), action: 'promoteWidgets' },
    { label: t('nodeContextMenu.saveParamsAsPreset'), action: 'savePreset' },
    { label: t('nodeContextMenu.applyPreset'), action: 'applyPreset' },
    { label: t('nodeContextMenu.executeSelected'), action: 'executeSelected' },
    null,
    { label: t('common.delete'), action: 'delete' },
  ] : [
    { label: t('nodeContextMenu.addNode'), action: 'add' },
    { label: t('nodeContextMenu.addGroup'), action: 'addGroup' },
    null,
    { label: t('common.selectAll'), action: 'selectAll' },
    null,
    { label: t('common.paste'), action: 'paste' },
  ];

  return (
    <div ref={ref} className="context-menu" style={{ left: x, top: y }}>
      <div className="context-menu-body">
        {items.map((item, i) => (
          item === null
            ? <div key={i} className="context-menu-sep" />
            : (
              <div key={i} className="context-menu-item" onClick={() => {
                if ('handler' in item && item.handler) {
                  item.handler();
                } else {
                  if (nodeId && item.action.startsWith('shape:')) onAction('shape', nodeId, item.action.split(':')[1]);
                  else if (nodeId) onAction(item.action, nodeId);
                  else onAction(item.action, '');
                }
              }}>
                {item.label}
              </div>
            )
        ))}
      </div>
    </div>
  );
}
