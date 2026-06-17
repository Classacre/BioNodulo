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
  onWorkflowParametersChange?: (parameters: WorkflowParameter[]) => void;
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

const WORKFLOW_PARAMETER_TYPES = ['STRING', 'INTEGER', 'FLOAT', 'BOOLEAN', 'JSON'];

function nextParameterName(parameters: WorkflowParameter[]): string {
  const names = new Set(parameters.map(parameter => parameter.name));
  if (!names.has('parameter')) return 'parameter';
  let index = 2;
  while (names.has(`parameter_${index}`)) index += 1;
  return `parameter_${index}`;
}

function patchParameter(
  parameters: WorkflowParameter[],
  index: number,
  patch: Partial<WorkflowParameter>,
): WorkflowParameter[] {
  return parameters.map((parameter, parameterIndex) => (
    parameterIndex === index ? { ...parameter, ...patch } : parameter
  ));
}

function optionalText(value: string): string | undefined {
  const trimmed = value.trim();
  return trimmed === '' ? undefined : value;
}

function WorkflowParameterSummary({
  parameters,
  onParametersChange,
}: {
  parameters: WorkflowParameter[];
  onParametersChange?: (parameters: WorkflowParameter[]) => void;
}) {
  const { t } = useTranslation();
  const editable = Boolean(onParametersChange);

  if (parameters.length === 0 && !editable) return null;

  return (
    <div style={{ marginTop: 14 }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8, marginBottom: 8 }}>
        <div style={{ fontSize: 10, fontWeight: 700, textTransform: 'uppercase', color: 'var(--muted)', letterSpacing: 0 }}>
          {t('inspector.workflowParametersTitle')}
        </div>
        {editable && (
          <button
            type="button"
            className="btn btn-sm"
            onClick={() => onParametersChange?.([
              ...parameters,
              { name: nextParameterName(parameters), type: 'STRING', required: false },
            ])}
          >
            {t('inspector.workflowParameterAdd')}
          </button>
        )}
      </div>
      <div style={{ display: 'grid', gap: 10 }}>
        {parameters.map((parameter, index) => {
          const initialValue = workflowParameterInitialValue(parameter);
          return (
            <div
              key={`${parameter.name}-${index}`}
              style={{
                border: '1px solid var(--border)',
                borderRadius: 6,
                padding: '8px 10px',
                background: 'var(--surface-2)',
              }}
            >
              {editable ? (
                <div style={{ display: 'grid', gap: 8 }}>
                  <label className="param-row" style={{ marginBottom: 0 }}>
                    <span className="param-label">{t('inspector.workflowParameterNameLabel')}</span>
                    <input
                      className="text-input param-input"
                      type="text"
                      value={parameter.name}
                      onChange={event => onParametersChange?.(patchParameter(parameters, index, { name: event.target.value }))}
                    />
                  </label>
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr auto', gap: 8, alignItems: 'end' }}>
                    <label className="param-row" style={{ marginBottom: 0 }}>
                      <span className="param-label">{t('inspector.workflowParameterTypeLabel')}</span>
                      <select
                        className="select-input param-input"
                        value={parameterType(parameter)}
                        onChange={event => onParametersChange?.(patchParameter(parameters, index, { type: event.target.value }))}
                      >
                        {WORKFLOW_PARAMETER_TYPES.map(type => <option key={type} value={type}>{type}</option>)}
                      </select>
                    </label>
                    <label style={{ display: 'flex', alignItems: 'center', gap: 6, minHeight: 31, fontSize: 11, color: 'var(--text-2)' }}>
                      <input
                        type="checkbox"
                        checked={Boolean(parameter.required)}
                        onChange={event => onParametersChange?.(patchParameter(parameters, index, { required: event.target.checked }))}
                      />
                      {t('inspector.workflowParameterRequiredLabel')}
                    </label>
                  </div>
                  <label className="param-row" style={{ marginBottom: 0 }}>
                    <span className="param-label">{t('inspector.workflowParameterDefaultLabel')}</span>
                    <input
                      className="text-input param-input"
                      type="text"
                      value={initialValue}
                      onChange={event => onParametersChange?.(patchParameter(parameters, index, { default: optionalText(event.target.value) }))}
                    />
                  </label>
                  <label className="param-row" style={{ marginBottom: 0 }}>
                    <span className="param-label">{t('inspector.workflowParameterDescriptionLabel')}</span>
                    <textarea
                      className="text-input param-input"
                      style={{ minHeight: 52, resize: 'vertical' }}
                      value={parameter.description ?? ''}
                      onChange={event => onParametersChange?.(patchParameter(parameters, index, { description: optionalText(event.target.value) }))}
                    />
                  </label>
                  <button
                    type="button"
                    className="btn btn-sm btn-ghost"
                    style={{ justifySelf: 'start' }}
                    onClick={() => onParametersChange?.(parameters.filter((_, parameterIndex) => parameterIndex !== index))}
                    aria-label={t('inspector.workflowParameterRemoveAria', { name: parameter.name })}
                  >
                    {t('common.remove')}
                  </button>
                </div>
              ) : (
                <>
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
                </>
              )}
            </div>
          );
        })}
        {parameters.length === 0 && editable && (
          <div style={{ color: 'var(--muted)', fontSize: 11, lineHeight: 1.4 }}>
            {t('inspector.workflowParametersEmpty')}
          </div>
        )}
      </div>
    </div>
  );
}

export default function InspectorPanel({
  selectedNode,
  objectInfo,
  workflowParameters = [],
  onWorkflowParametersChange,
  onParamChange,
  onClose,
}: InspectorPanelProps) {
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
              <WorkflowParameterSummary
                parameters={workflowParameters}
                onParametersChange={onWorkflowParametersChange}
              />
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
              inlinePreview: Boolean(meta?.inline_preview),
              previewCollapsed: selectedNode.ui?.previewCollapsed ?? false,
            };
            return (
              <NodeEditor
                node={synthetic}
                workflowParameters={workflowParameters}
                onParamChange={onParamChange}
                onClose={onClose}
              />
            );
          })()}
      </div>
    </div>
  );
}
