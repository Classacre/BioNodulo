import { useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useWorkflowRuntimeArtifacts } from '../../hooks/workflow/useWorkflowRuntimeArtifacts';
import type {
  CheckpointManifestResponse,
  PauseRequestRecord,
  WorkflowTriggerRecord,
} from '../../hooks/workflow/useWorkflowRuntimeArtifacts';
import Icon from '../ui/Icon';

interface RuntimeArtifactsPanelProps {
  onClose: () => void;
}

interface CheckpointSummary {
  id: string;
  name: string;
  nodeId?: string;
}

function valueAsString(value: unknown): string | undefined {
  return typeof value === 'string' && value.trim() ? value : undefined;
}

function basename(path: string): string {
  return path.split(/[\\/]/).filter(Boolean).pop() || path;
}

function summarizeCheckpoints(manifestResponse: CheckpointManifestResponse | null): CheckpointSummary[] {
  const checkpoints = manifestResponse?.manifest?.checkpoints;
  if (!checkpoints || typeof checkpoints !== 'object' || Array.isArray(checkpoints)) return [];

  return Object.entries(checkpoints as Record<string, unknown>).map(([key, raw]) => {
    const record = raw && typeof raw === 'object' && !Array.isArray(raw)
      ? raw as Record<string, unknown>
      : {};
    const name = valueAsString(record.checkpoint_name)
      || valueAsString(record.name)
      || valueAsString(record.checkpoint_path)
      || basename(key);
    return {
      id: key,
      name: basename(name),
      nodeId: valueAsString(record.node_id),
    };
  });
}

function pauseStatus(record: PauseRequestRecord): string {
  if (typeof record.status === 'string' && record.status.trim()) return record.status;
  if (record.approved === true) return 'approved';
  if (record.approved === false) return 'rejected';
  return 'waiting';
}

function pauseTitle(record: PauseRequestRecord): string {
  return valueAsString(record.message) || valueAsString(record.node_id) || valueAsString(record.pause_file) || 'pause request';
}

function triggerTitle(record: WorkflowTriggerRecord): string {
  return valueAsString(record.target_workflow)
    || valueAsString(record.trigger_type)
    || valueAsString(record.trigger_file)
    || 'trigger';
}

export default function RuntimeArtifactsPanel({ onClose }: RuntimeArtifactsPanelProps) {
  const { t } = useTranslation();
  const {
    checkpointManifest,
    pauseRequests,
    workflowTriggers,
    triggerEvaluation,
    loading,
    error,
    refresh,
    evaluateWorkflowTriggers,
    resolvePauseRequest,
  } = useWorkflowRuntimeArtifacts();
  const [actionError, setActionError] = useState<string | null>(null);
  const [evaluating, setEvaluating] = useState(false);
  const [resolvingPauseKey, setResolvingPauseKey] = useState<string | null>(null);

  const checkpoints = useMemo(() => summarizeCheckpoints(checkpointManifest), [checkpointManifest]);
  const pauseRequestList = pauseRequests?.pause_requests ?? [];
  const triggerList = workflowTriggers?.triggers ?? [];
  const waitingPauseRequests = pauseRequestList.filter(request => pauseStatus(request) === 'waiting');

  const handleEvaluate = async () => {
    setActionError(null);
    setEvaluating(true);
    try {
      await evaluateWorkflowTriggers();
    } catch (err) {
      setActionError(err instanceof Error ? err.message : String(err));
    } finally {
      setEvaluating(false);
    }
  };

  const handleResolve = async (request: PauseRequestRecord, action: 'approve' | 'reject') => {
    const key = valueAsString(request.pause_file) || valueAsString(request.node_id) || action;
    setActionError(null);
    setResolvingPauseKey(`${key}:${action}`);
    try {
      await resolvePauseRequest({
        action,
        node_id: valueAsString(request.node_id),
        pause_file: valueAsString(request.pause_file),
      });
    } catch (err) {
      setActionError(err instanceof Error ? err.message : String(err));
    } finally {
      setResolvingPauseKey(null);
    }
  };

  return (
    <div className="rail-panel runtime-artifacts-panel">
      <div className="rail-panel-header">
        <span>{t('runtimeArtifacts.title')}</span>
        <button className="btn btn-icon btn-sm" onClick={onClose} title={t('common.close')} aria-label={t('common.close')} type="button">
          <Icon name="close" size={14} />
        </button>
      </div>

      <div className="rail-panel-body runtime-artifacts-body">
        <div className="runtime-artifacts-toolbar">
          <button className="btn btn-sm" onClick={() => void refresh()} type="button">
            {t('common.refresh')}
          </button>
          <button className="btn btn-sm btn-primary" onClick={() => void handleEvaluate()} disabled={evaluating} type="button">
            <Icon name={evaluating ? 'spinner' : 'activity'} size={14} />
            {evaluating ? t('runtimeArtifacts.evaluating') : t('runtimeArtifacts.evaluateTriggers')}
          </button>
        </div>

        {loading && <div className="runtime-artifacts-state">{t('common.loading')}</div>}
        {error && <div className="runtime-artifacts-error">{error.message}</div>}
        {actionError && <div className="runtime-artifacts-error">{actionError}</div>}

        <section className="runtime-artifacts-section" aria-labelledby="runtime-artifacts-checkpoints">
          <div className="runtime-artifacts-section-header">
            <h3 id="runtime-artifacts-checkpoints">{t('runtimeArtifacts.checkpoints')}</h3>
            <span>{t('runtimeArtifacts.checkpointCount', { count: checkpoints.length })}</span>
          </div>
          {checkpoints.length > 0 ? (
            <div className="runtime-artifacts-list">
              {checkpoints.slice(0, 5).map(checkpoint => (
                <div className="runtime-artifact-row" key={checkpoint.id}>
                  <Icon name="layers" size={14} />
                  <div>
                    <div className="runtime-artifact-title">{checkpoint.name}</div>
                    {checkpoint.nodeId && <div className="runtime-artifact-meta">{checkpoint.nodeId}</div>}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="runtime-artifacts-empty">
              {checkpointManifest?.exists ? t('runtimeArtifacts.noCheckpoints') : t('runtimeArtifacts.noCheckpointManifest')}
            </div>
          )}
        </section>

        <section className="runtime-artifacts-section" aria-labelledby="runtime-artifacts-pauses">
          <div className="runtime-artifacts-section-header">
            <h3 id="runtime-artifacts-pauses">{t('runtimeArtifacts.pauseRequests')}</h3>
            <span>{t('runtimeArtifacts.waitingPauseCount', { count: waitingPauseRequests.length })}</span>
          </div>
          {pauseRequestList.length > 0 ? (
            <div className="runtime-artifacts-list">
              {pauseRequestList.map((request, index) => {
                const status = pauseStatus(request);
                const nodeId = valueAsString(request.node_id) || valueAsString(request.pause_file) || String(index + 1);
                const key = valueAsString(request.pause_file) || `${nodeId}-${index}`;
                return (
                  <div className="runtime-artifact-row runtime-artifact-row-stacked" key={key}>
                    <div className="runtime-artifact-main">
                      <Icon name={status === 'waiting' ? 'clock' : 'check'} size={14} />
                      <div>
                        <div className="runtime-artifact-title">{pauseTitle(request)}</div>
                        <div className="runtime-artifact-meta">{nodeId} · {status}</div>
                      </div>
                    </div>
                    {status === 'waiting' && (
                      <div className="runtime-artifact-actions">
                        <button
                          className="btn btn-sm"
                          onClick={() => void handleResolve(request, 'approve')}
                          disabled={resolvingPauseKey === `${key}:approve`}
                          aria-label={t('runtimeArtifacts.approvePause', { nodeId })}
                          type="button"
                        >
                          {t('runtimeArtifacts.approve')}
                        </button>
                        <button
                          className="btn btn-sm"
                          onClick={() => void handleResolve(request, 'reject')}
                          disabled={resolvingPauseKey === `${key}:reject`}
                          aria-label={t('runtimeArtifacts.rejectPause', { nodeId })}
                          type="button"
                        >
                          {t('runtimeArtifacts.reject')}
                        </button>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          ) : (
            <div className="runtime-artifacts-empty">{t('runtimeArtifacts.noPauseRequests')}</div>
          )}
        </section>

        <section className="runtime-artifacts-section" aria-labelledby="runtime-artifacts-triggers">
          <div className="runtime-artifacts-section-header">
            <h3 id="runtime-artifacts-triggers">{t('runtimeArtifacts.workflowTriggers')}</h3>
            <span>{t('runtimeArtifacts.triggerCount', { count: triggerList.length })}</span>
          </div>
          {triggerEvaluation && (
            <div className="runtime-artifacts-evaluation">
              <span>{t('runtimeArtifacts.scheduleDueCount', { count: triggerEvaluation.due_schedule_count })}</span>
              <span>{t('runtimeArtifacts.fileWatchDueCount', { count: triggerEvaluation.due_file_watch_count })}</span>
            </div>
          )}
          {triggerList.length > 0 ? (
            <div className="runtime-artifacts-list">
              {triggerList.map((trigger, index) => {
                const key = valueAsString(trigger.trigger_file) || `${triggerTitle(trigger)}-${index}`;
                return (
                  <div className="runtime-artifact-row" key={key}>
                    <Icon name={trigger.trigger_type === 'schedule' ? 'clock' : 'target'} size={14} />
                    <div>
                      <div className="runtime-artifact-title">{triggerTitle(trigger)}</div>
                      <div className="runtime-artifact-meta">
                        {[trigger.trigger_type, trigger.status].filter(Boolean).join(' · ')}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          ) : (
            <div className="runtime-artifacts-empty">{t('runtimeArtifacts.noWorkflowTriggers')}</div>
          )}
        </section>
      </div>
    </div>
  );
}
