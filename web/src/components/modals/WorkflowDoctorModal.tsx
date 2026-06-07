// Workflow doctor: scans the current workflow for common problems and
// presents a fix-it list. Findings are derived client-side from the graph
// + objectInfo (no backend dependency) so they appear instantly and stay
// useful offline.
//
// Each finding has a category (error / warning / info) and an optional
// node id that the canvas can focus when the user clicks "Jump".

import { useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import { Dialog } from '../ui/Dialog';
import type { Workflow, ObjectInfo } from '../../types';

interface WorkflowDoctorModalProps {
  workflow: Workflow;
  objectInfo: ObjectInfo;
  onClose: () => void;
  onJumpToNode: (nodeId: string) => void;
}

type Severity = 'error' | 'warning' | 'info';

interface Finding {
  id: string;
  severity: Severity;
  titleKey: string;
  titleValues?: Record<string, string>;
  detailKey?: string;
  nodeId?: string;
}

const WORKFLOW_PARAMETER_REFERENCE_RE = /\{\{\s*([A-Za-z_][A-Za-z0-9_.-]*)\s*\}\}/g;
const NODE_LOCAL_TEMPLATE_FIELDS = new Set([
  'custom_prompt',
  'custom_script',
  'prompt',
  'system_prompt',
  'template',
  'workflow_template',
]);

function diagnose(workflow: Workflow, objectInfo: ObjectInfo): Finding[] {
  const findings: Finding[] = [];
  const nodes = workflow.nodes || [];
  const edges = workflow.edges || [];
  const parameterNames = new Set((workflow.parameters || []).map(parameter => parameter.name));
  const nodeIds = new Set(nodes.map(node => node.id));
  const seenNodeIds = new Set<string>();
  const duplicateNodeIds = new Set<string>();

  for (const node of nodes) {
    if (seenNodeIds.has(node.id)) duplicateNodeIds.add(node.id);
    seenNodeIds.add(node.id);
  }

  for (const nodeId of duplicateNodeIds) {
    findings.push({
      id: `duplicate-node-${nodeId}`,
      severity: 'error',
      titleKey: 'duplicateNodeIdTitle',
      titleValues: { nodeId },
      detailKey: 'duplicateNodeIdDetail',
      nodeId,
    });
  }

  // Per-node checks.
  const incomingByNode = new Map<string, Set<string>>();
  const outgoingByNode = new Map<string, number>();
  for (const edge of edges) {
    if (!nodeIds.has(edge.from.node)) {
      findings.push({
        id: `dangling-edge-source-${edge.id}`,
        severity: 'error',
        titleKey: 'danglingSourceEdgeTitle',
        titleValues: { edge: edge.id, node: edge.from.node },
        detailKey: 'danglingEdgeDetail',
        nodeId: nodeIds.has(edge.to.node) ? edge.to.node : undefined,
      });
    }
    if (!nodeIds.has(edge.to.node)) {
      findings.push({
        id: `dangling-edge-target-${edge.id}`,
        severity: 'error',
        titleKey: 'danglingTargetEdgeTitle',
        titleValues: { edge: edge.id, node: edge.to.node },
        detailKey: 'danglingEdgeDetail',
        nodeId: nodeIds.has(edge.from.node) ? edge.from.node : undefined,
      });
    }
    let set = incomingByNode.get(edge.to.node);
    if (!set) { set = new Set(); incomingByNode.set(edge.to.node, set); }
    set.add(edge.to.input);
    outgoingByNode.set(edge.from.node, (outgoingByNode.get(edge.from.node) || 0) + 1);
  }

  const isVisualOnly = (nodeType: string): boolean => {
    if (nodeType === 'note' || nodeType === 'reroute') return true;
    return Boolean(objectInfo[nodeType]?.visual_only);
  };

  for (const node of nodes) {
    if (isVisualOnly(node.type)) continue;
    const meta = objectInfo[node.type];
    if (!meta) {
      findings.push({
        id: `unknown-node-type-${node.id}`,
        severity: 'error',
        titleKey: 'unknownNodeTypeTitle',
        titleValues: { type: node.type },
        detailKey: 'unknownNodeTypeDetail',
        nodeId: node.id,
      });
    }
    const required = meta?.input_types?.required || {};
    const connected = incomingByNode.get(node.id) || new Set();
    for (const key of Object.keys(required)) {
      const value = node.params?.[key];
      const hasValue = value !== undefined && value !== null && value !== '';
      if (!connected.has(key) && !hasValue) {
        findings.push({
          id: `missing-${node.id}-${key}`,
          severity: 'error',
          titleKey: 'missingRequiredTitle',
          titleValues: { node: node.ui?.title || node.type, input: key },
          detailKey: 'missingRequiredDetail',
          nodeId: node.id,
        });
      }
    }
    // Orphaned output node: no outgoing edges from a non-terminal node type
    // is usually a sign the user forgot to connect downstream. We skip the
    // last layer (nodes that look like sinks — output_node flag).
    const isSink = Boolean(meta?.output_node);
    const outgoing = outgoingByNode.get(node.id) || 0;
    if (outgoing === 0 && !isSink && (meta?.return_types?.length ?? 0) > 0) {
      findings.push({
        id: `orphan-${node.id}`,
        severity: 'warning',
        titleKey: 'unusedOutputsTitle',
        titleValues: { node: node.ui?.title || node.type },
        detailKey: 'unusedOutputsDetail',
        nodeId: node.id,
      });
    }
    // Missing external tool that the node declares as required.
    const requires = meta?.requires_external_tools || [];
    if (requires.length > 0 && !meta?.experimental) {
      // We can't probe the host here — that's the HostPrerequisitesBanner's
      // job — but we surface the dependency so users see what they'll need.
      findings.push({
        id: `tools-${node.id}`,
        severity: 'info',
        titleKey: 'externalToolsTitle',
        titleValues: { node: node.ui?.title || node.type, tools: requires.join(', ') },
        nodeId: node.id,
      });
    }

    const executionValues = node as typeof node & { inputs?: unknown; widgets?: unknown };
    for (const [path, parameter] of iterWorkflowParameterReferences(executionValues.params, 'params')) {
      if (!parameterNames.has(parameter)) {
        findings.push({
          id: `unknown-parameter-${node.id}-${path}-${parameter}`,
          severity: 'error',
          titleKey: 'unknownWorkflowParameterTitle',
          titleValues: {
            node: node.ui?.title || node.type,
            parameter,
            path,
          },
          detailKey: 'unknownWorkflowParameterDetail',
          nodeId: node.id,
        });
      }
    }
    for (const [path, parameter] of iterWorkflowParameterReferences(executionValues.inputs, 'inputs')) {
      if (!parameterNames.has(parameter)) {
        findings.push({
          id: `unknown-parameter-${node.id}-${path}-${parameter}`,
          severity: 'error',
          titleKey: 'unknownWorkflowParameterTitle',
          titleValues: {
            node: node.ui?.title || node.type,
            parameter,
            path,
          },
          detailKey: 'unknownWorkflowParameterDetail',
          nodeId: node.id,
        });
      }
    }
    for (const [path, parameter] of iterWorkflowParameterReferences(executionValues.widgets, 'widgets')) {
      if (!parameterNames.has(parameter)) {
        findings.push({
          id: `unknown-parameter-${node.id}-${path}-${parameter}`,
          severity: 'error',
          titleKey: 'unknownWorkflowParameterTitle',
          titleValues: {
            node: node.ui?.title || node.type,
            parameter,
            path,
          },
          detailKey: 'unknownWorkflowParameterDetail',
          nodeId: node.id,
        });
      }
    }
  }

  // Graph-level checks.
  if (nodes.length === 0) {
    findings.push({
      id: 'empty-graph',
      severity: 'info',
      titleKey: 'emptyGraphTitle',
      detailKey: 'emptyGraphDetail',
    });
  }
  if (edges.length === 0 && nodes.length > 1) {
    findings.push({
      id: 'no-edges',
      severity: 'warning',
      titleKey: 'noEdgesTitle',
      detailKey: 'noEdgesDetail',
    });
  }

  // Sort errors first, then warnings, then info.
  const order: Record<Severity, number> = { error: 0, warning: 1, info: 2 };
  return findings.sort((a, b) => order[a.severity] - order[b.severity]);
}

function iterWorkflowParameterReferences(value: unknown, path: string): Array<[string, string]> {
  const references: Array<[string, string]> = [];
  if (value === null || value === undefined) return references;
  if (Array.isArray(value)) {
    value.forEach((item, index) => {
      references.push(...iterWorkflowParameterReferences(item, `${path}[${index}]`));
    });
    return references;
  }
  if (typeof value === 'object') {
    Object.entries(value as Record<string, unknown>).forEach(([key, item]) => {
      if (NODE_LOCAL_TEMPLATE_FIELDS.has(key)) return;
      references.push(...iterWorkflowParameterReferences(item, `${path}.${key}`));
    });
    return references;
  }
  if (typeof value !== 'string') return references;

  for (const match of value.matchAll(WORKFLOW_PARAMETER_REFERENCE_RE)) {
    references.push([path, match[1]]);
  }
  return references;
}

function severityIcon(s: Severity): string {
  return s === 'error' ? '⛔' : s === 'warning' ? '⚠' : 'ℹ';
}

function severityColor(s: Severity): string {
  return s === 'error' ? 'var(--danger, #ef4444)' : s === 'warning' ? 'var(--warning, #f59e0b)' : 'var(--accent, #2dd4bf)';
}

export default function WorkflowDoctorModal({ workflow, objectInfo, onClose, onJumpToNode }: WorkflowDoctorModalProps) {
  const { t } = useTranslation();
  const findings = useMemo(() => diagnose(workflow, objectInfo), [workflow, objectInfo]);
  const counts = useMemo(() => {
    const c = { error: 0, warning: 0, info: 0 };
    for (const f of findings) c[f.severity] += 1;
    return c;
  }, [findings]);

  const footer = (
    <button className="btn" type="button" onClick={onClose}>{t('common.close')}</button>
  );

  return (
    <Dialog
      title={t('doctor.title')}
      width={680}
      maxHeight="80vh"
      onClose={onClose}
      footer={footer}
      header={(
        <span>
          {counts.error > 0 && <span style={{ color: 'var(--danger, #ef4444)', marginRight: 12 }}>{t('doctor.countError', { count: counts.error })}</span>}
          {counts.warning > 0 && <span style={{ color: 'var(--warning, #f59e0b)', marginRight: 12 }}>{t('doctor.countWarning', { count: counts.warning })}</span>}
          {counts.info > 0 && <span style={{ color: 'var(--muted)' }}>{t('doctor.countInfo', { count: counts.info })}</span>}
          {findings.length === 0 && <span style={{ color: 'var(--success, #22c55e)' }}>{t('doctor.healthy')}</span>}
        </span>
      )}
    >
      {findings.length === 0 ? (
        <div style={{ color: 'var(--muted)', fontSize: 12, padding: '12px 0' }}>
          {t('doctor.noIssues')}
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          {findings.map(f => {
            const title = t(`doctor.findings.${f.titleKey}`, f.titleValues);
            const detail = f.detailKey ? t(`doctor.findings.${f.detailKey}`) : null;
            return (
              <div
                key={f.id}
                style={{
                  display: 'flex',
                  alignItems: 'flex-start',
                  gap: 10,
                  padding: 10,
                  background: 'var(--surface-2)',
                  border: '1px solid var(--border)',
                  borderLeft: `3px solid ${severityColor(f.severity)}`,
                  borderRadius: 6,
                }}
              >
                <span aria-hidden="true">{severityIcon(f.severity)}</span>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text)' }}>{title}</div>
                  {detail && <div style={{ fontSize: 11, color: 'var(--muted)', marginTop: 2 }}>{detail}</div>}
                </div>
                {f.nodeId && (
                  <button
                    type="button"
                    className="btn btn-sm"
                    onClick={() => onJumpToNode(f.nodeId!)}
                    title={t('doctor.jumpTitle')}
                  >
                    {t('doctor.jump')}
                  </button>
                )}
              </div>
            );
          })}
        </div>
      )}
    </Dialog>
  );
}
