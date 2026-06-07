// Persistent right-rail wrapper around `NodeEditor`. The floating modal
// editor (double-click on a node) keeps working; this panel always shows the
// currently selected node so users can keep params visible while editing the
// graph.
//
// We synthesise a minimal `GraphNode`-shaped object from the workflow node +
// metadata. NodeEditor only reads `id`, `title`, `color`, `meta`, `params` —
// the rest is filled with sensible defaults.

import type { ReactNode } from 'react';
import { useTranslation } from 'react-i18next';
import type { ObjectInfo, WorkflowNode, WorkflowParameter } from '../../types';
import { workflowParameterInitialValue } from '../../utils/workflowParameters';
import type { GraphNode } from '../canvas/WorkflowCanvas';
import NodeEditor from '../nodes/NodeEditor';
import Icon from '../ui/Icon';

interface InspectorPanelProps {
  selectedNode: WorkflowNode | null;
  objectInfo: ObjectInfo;
  workflowParameters?: WorkflowParameter[];
  onParamChange: (nodeId: string, key: string, value: unknown) => void;
  onClose: () => void;
}

function emptyState(message: string, hint?: ReactNode): ReactNode {
  return (
    <div className="rail-panel-empty" style={{ padding: 16, fontSize: 12, color: 'var(--muted)' }}>
      <div style={{ fontWeight: 600, marginBottom: 6 }}>{message}</div>
      {hint && <div style={{ fontSize: 11, lineHeight: 1.5 }}>{hint}</div>}
    </div>
  );
}

function parameterType(parameter: WorkflowParameter): string {
  return String(parameter.type || 'STRING').trim().toUpperCase();
}

function WorkflowParameterSummary({ parameters }: { parameters: WorkflowParameter[] }) {
  const { t } = useTranslation();
  if (parameters.length === 0) return null;

  return (
    <div style={{ marginTop: 14 }}>
      <div style={{ fontSize: 10, fontWeight: 700, textTransform: 'uppercase', color: 'var(--muted)', marginBottom: 8, letterSpacing: 0 }}>
        {t('inspector.workflowParametersTitle')}
      </div>
      <div style={{ display: 'grid', gap: 8 }}>
        {parameters.map(parameter => {
          const initialValue = workflowParameterInitialValue(parameter);
          return (
            <div
              key={parameter.name}
              style={{
                border: '1px solid var(--border)',
                borderRadius: 6,
                padding: '8px 10px',
                background: 'var(--surface-2)',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
                <span style={{ fontWeight: 700, color: 'var(--text)' }}>{parameter.name}</span>
                <span style={{ fontSize: 10, color: 'var(--muted)', border: '1px solid var(--border)', borderRadius: 4, padding: '1px 5px' }}>
                  {parameterType(parameter)}
                </span>
                <span style={{ fontSize: 10, color: parameter.required ? 'var(--danger)' : 'var(--muted)' }}>
                  {parameter.required ? t('inspector.workflowParameterRequired') : t('inspector.workflowParameterOptional')}
                </span>
              </div>
              {initialValue && (
                <div style={{ marginTop: 5, fontSize: 11, color: 'var(--muted)', wordBreak: 'break-word' }}>
                  {t('inspector.workflowParameterDefault', { value: initialValue })}
                </div>
              )}
              {parameter.description && (
                <div style={{ marginTop: 5, fontSize: 11, color: 'var(--muted)', lineHeight: 1.4 }}>
                  {parameter.description}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

export default function InspectorPanel({ selectedNode, objectInfo, workflowParameters = [], onParamChange, onClose }: InspectorPanelProps) {
  const { t } = useTranslation();

  return (
    <div className="rail-panel inspector-panel">
      <div className="rail-panel-header">
        <span>{t('inspector.title')}</span>
        <button className="btn btn-icon btn-sm" onClick={onClose} title={t('inspector.closeTitle')}>
          <Icon name="close" size={14} />
        </button>
      </div>
      <div className="rail-panel-body" style={{ overflow: 'auto' }}>
        {!selectedNode
          ? emptyState(
            t('inspector.emptyTitle'),
            <>
              <div>{t('inspector.emptyHint')}</div>
              <WorkflowParameterSummary parameters={workflowParameters} />
            </>,
          )
          : (() => {
            const meta = objectInfo[selectedNode.type] ?? selectedNode.node_info ?? null;
            const synthetic: GraphNode = {
              id: selectedNode.id,
              type: selectedNode.type,
              display_name: meta?.display_name || selectedNode.type,
              category: meta?.category || '',
              x: selectedNode.position?.[0] ?? 0,
              y: selectedNode.position?.[1] ?? 0,
              width: 240,
              height: 80,
              inputs: [],
              outputs: [],
              params: selectedNode.params || {},
              meta,
              color: selectedNode.ui?.color || 'var(--accent)',
              muted: false,
              bypassed: false,
              selected: true,
              collapsed: false,
              pinned: false,
              shape: 'card',
              title: selectedNode.ui?.title || meta?.display_name || selectedNode.type,
              visualOnly: false,
            };
            return (
              <NodeEditor
                node={synthetic}
                onParamChange={onParamChange}
                onClose={onClose}
              />
            );
          })()}
      </div>
    </div>
  );
}
