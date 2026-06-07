import { useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useWorkflowRuntimeArtifacts } from '../../hooks/workflow/useWorkflowRuntimeArtifacts';
import type {
  CheckpointManifestResponse,
  CheckpointRecord,
  PauseRequestRecord,
  ResolveCheckpointInput,
  SubmittedWorkflowTriggerRun,
  WorkflowTriggerRecord,
} from '../../hooks/workflow/useWorkflowRuntimeArtifacts';
import Icon from '../ui/Icon';

interface RuntimeArtifactsPanelProps {
  onClose: () => void;
  onResumeCheckpointSelect?: (selection: { label: string; checkpoint: CheckpointRecord }) => void;
}

interface CheckpointSummary {
  id: string;
  name: string;
  checkpointName?: string;
  runId?: string;
  nodeId?: string;
  resumeManifestSupported?: boolean;
  resumeSupported?: boolean;
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
      checkpointName: valueAsString(record.checkpoint_name),
      runId: valueAsString(record.run_id),
      nodeId: valueAsString(record.node_id),
      resumeManifestSupported: typeof record.resume_manifest_supported === 'boolean'
        ? record.resume_manifest_supported
        : manifestResponse.resume_manifest_supported,
      resumeSupported: typeof record.resume_supported === 'boolean'
        ? record.resume_supported
        : manifestResponse.resume_supported,
    };
  });
}

function checkpointResumeBadges(
  t: (key: string) => string,
  resumeManifestSupported?: boolean,
  resumeSupported?: boolean,
): string[] {
  if (resumeSupported === true) return [t('runtimeArtifacts.executorResumeAvailable')];
  if (resumeManifestSupported === true && resumeSupported === false) {
    return [t('runtimeArtifacts.manifestOnly'), t('runtimeArtifacts.executorResumeUnavailable')];
  }
  if (resumeManifestSupported === true) return [t('runtimeArtifacts.manifestOnly')];
  return [];
}

function pauseRuntimeBadges(
  t: (key: string) => string,
  reviewDecisionSupported?: boolean,
  enginePauseSupported?: boolean,
): string[] {
  if (enginePauseSupported === true) return [t('runtimeArtifacts.blockingPauseAvailable')];
  if (reviewDecisionSupported === true && enginePauseSupported === false) {
    return [t('runtimeArtifacts.reviewOnly'), t('runtimeArtifacts.blockingPauseUnavailable')];
  }
  if (reviewDecisionSupported === true) return [t('runtimeArtifacts.reviewOnly')];
  return [];
}

function triggerRuntimeBadges(
  t: (key: string) => string,
  runSubmissionSupported?: boolean,
  durableSchedulerSupported?: boolean,
  pollingFileWatcherSupported?: boolean,
): string[] {
  const durableEvaluationSupported = durableSchedulerSupported === true || pollingFileWatcherSupported === true;
  if (runSubmissionSupported === true) return [t('runtimeArtifacts.durableTriggerEvaluationAvailable')];
  if (runSubmissionSupported === false && !durableEvaluationSupported) {
    return [
      t('runtimeArtifacts.pollableMetadataOnly'),
      t('runtimeArtifacts.runSubmissionUnavailable'),
      t('runtimeArtifacts.doesNotSubmitRuns'),
    ];
  }
  if (durableEvaluationSupported) return [t('runtimeArtifacts.durableTriggerEvaluationAvailable')];
  return [];
}

function pauseStatus(record: PauseRequestRecord): string {
  if (typeof record.status === 'string' && record.status.trim()) return record.status;
  if (record.approved === true) return 'approved';
  if (record.approved === false) return 'rejected';
  return 'waiting';
}

function pauseStatusLabel(status: string, t: (key: string) => string): string {
  if (status === 'approved') return t('runtimeArtifacts.status.approved');
  if (status === 'rejected') return t('runtimeArtifacts.status.rejected');
  if (status === 'waiting') return t('runtimeArtifacts.status.waiting');
  return status;
}

function pauseTitle(record: PauseRequestRecord, t: (key: string) => string): string {
  return valueAsString(record.message)
    || valueAsString(record.node_id)
    || valueAsString(record.pause_file)
    || t('runtimeArtifacts.pauseRequestFallback');
}

function triggerTitle(record: WorkflowTriggerRecord, t: (key: string) => string): string {
  return valueAsString(record.target_workflow)
    || valueAsString(record.trigger_type)
    || valueAsString(record.trigger_file)
    || t('runtimeArtifacts.triggerFallback');
}

function submittedRunTitle(record: SubmittedWorkflowTriggerRun, t: (key: string) => string): string {
  return valueAsString(record.run_id)
    || valueAsString(record.target_workflow)
    || valueAsString(record.trigger_file)
    || valueAsString(record.status)
    || t('runtimeArtifacts.workflowTriggerRunFallback');
}

function submittedRunMeta(record: SubmittedWorkflowTriggerRun): string {
  return [
    valueAsString(record.target_workflow),
    valueAsString(record.status),
    valueAsString(record.due_at),
  ].filter(Boolean).join(' · ');
}

function checkpointResolveInput(checkpoint: CheckpointSummary): ResolveCheckpointInput {
  if (checkpoint.checkpointName) return { checkpoint_name: checkpoint.checkpointName };
  if (checkpoint.runId && checkpoint.nodeId) return { run_id: checkpoint.runId, node_id: checkpoint.nodeId };
  return { checkpoint_name: checkpoint.name };
}

function resumeCheckpointLabel(checkpoint: CheckpointRecord, t: (key: string) => string): string {
  const name = valueAsString(checkpoint.checkpoint_name)
    || valueAsString(checkpoint.checkpoint_path)?.split(/[\\/]/).filter(Boolean).pop()
    || t('runtimeArtifacts.checkpointFallback');
  const nodeId = valueAsString(checkpoint.node_id);
  return nodeId ? `${name} / ${nodeId}` : name;
}

export default function RuntimeArtifactsPanel({ onClose, onResumeCheckpointSelect }: RuntimeArtifactsPanelProps) {
  const { t } = useTranslation();
  const {
    checkpointManifest,
    pauseRequests,
    workflowTriggers,
    triggerEvaluation,
    lastResolvedCheckpoint,
    loading,
    error,
    refresh,
    evaluateWorkflowTriggers,
    resolveCheckpoint,
    resolvePauseRequest,
  } = useWorkflowRuntimeArtifacts();
  const [actionError, setActionError] = useState<string | null>(null);
  const [evaluating, setEvaluating] = useState(false);
  const [submittingTriggers, setSubmittingTriggers] = useState(false);
  const [resolvingCheckpointKey, setResolvingCheckpointKey] = useState<string | null>(null);
  const [resolvingPauseKey, setResolvingPauseKey] = useState<string | null>(null);

  const checkpoints = useMemo(() => summarizeCheckpoints(checkpointManifest), [checkpointManifest]);
  const pauseRequestList = pauseRequests?.pause_requests ?? [];
  const triggerList = workflowTriggers?.triggers ?? [];
  const submittedRuns = triggerEvaluation?.submitted_runs ?? [];
  const waitingPauseRequests = pauseRequestList.filter(request => pauseStatus(request) === 'waiting');
  const triggerBadges = useMemo(
    () => triggerRuntimeBadges(
      t,
      typeof workflowTriggers?.run_submission_supported === 'boolean'
        ? workflowTriggers.run_submission_supported
        : triggerEvaluation?.run_submission_supported,
      typeof workflowTriggers?.durable_scheduler_supported === 'boolean'
        ? workflowTriggers.durable_scheduler_supported
        : triggerEvaluation?.durable_scheduler_supported,
      typeof workflowTriggers?.polling_file_watcher_supported === 'boolean'
        ? workflowTriggers.polling_file_watcher_supported
        : triggerEvaluation?.polling_file_watcher_supported,
    ),
    [
      t,
      triggerEvaluation?.durable_scheduler_supported,
      triggerEvaluation?.polling_file_watcher_supported,
      triggerEvaluation?.run_submission_supported,
      workflowTriggers?.durable_scheduler_supported,
      workflowTriggers?.polling_file_watcher_supported,
      workflowTriggers?.run_submission_supported,
    ],
  );

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

  const handleSubmitDueTriggers = async () => {
    setActionError(null);
    setSubmittingTriggers(true);
    try {
      await evaluateWorkflowTriggers(undefined, { submitRuns: true });
    } catch (err) {
      setActionError(err instanceof Error ? err.message : String(err));
    } finally {
      setSubmittingTriggers(false);
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

  const handleResolveCheckpoint = async (checkpoint: CheckpointSummary) => {
    setActionError(null);
    setResolvingCheckpointKey(checkpoint.id);
    try {
      const resolved = await resolveCheckpoint(checkpointResolveInput(checkpoint));
      if (resolved.checkpoint && onResumeCheckpointSelect) {
        onResumeCheckpointSelect({
          label: resumeCheckpointLabel(resolved.checkpoint, t),
          checkpoint: resolved.checkpoint,
        });
      }
    } catch (err) {
      setActionError(err instanceof Error ? err.message : String(err));
    } finally {
      setResolvingCheckpointKey(null);
    }
  };

  const resolvedCheckpoint = lastResolvedCheckpoint?.checkpoint;
  const resolvedResumeBadges = checkpointResumeBadges(
    t,
    typeof resolvedCheckpoint?.resume_manifest_supported === 'boolean'
      ? resolvedCheckpoint.resume_manifest_supported
      : lastResolvedCheckpoint?.resume_manifest_supported,
    typeof resolvedCheckpoint?.resume_supported === 'boolean'
      ? resolvedCheckpoint.resume_supported
      : lastResolvedCheckpoint?.resume_supported,
  ).filter(label => label !== t('runtimeArtifacts.manifestOnly'));

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
          <button className="btn btn-sm" onClick={() => void handleSubmitDueTriggers()} disabled={submittingTriggers} type="button">
            <Icon name={submittingTriggers ? 'spinner' : 'play'} size={14} />
            {submittingTriggers ? t('runtimeArtifacts.submittingTriggers') : t('runtimeArtifacts.submitDueTriggers')}
          </button>
        </div>

        {loading && <div className="runtime-artifacts-state">{t('common.loading')}</div>}
        {error && <div className="runtime-artifacts-error">{error.message}</div>}
        {actionError && <div className="runtime-artifacts-error">{actionError}</div>}
        {lastResolvedCheckpoint && (
          <div className="runtime-artifacts-resolution">
            <div className="runtime-artifact-meta">{t('runtimeArtifacts.resolvedCheckpoint')}</div>
            {resolvedCheckpoint ? (
              <>
                <div className="runtime-artifact-title">
                  {valueAsString(resolvedCheckpoint.checkpoint_name) || t('runtimeArtifacts.unnamedCheckpoint')}
                </div>
                {valueAsString(resolvedCheckpoint.checkpoint_path) && (
                  <div className="runtime-artifact-meta">{resolvedCheckpoint.checkpoint_path}</div>
                )}
                {resolvedResumeBadges.map(label => (
                  <div className="runtime-artifact-meta" key={label}>{label}</div>
                ))}
              </>
            ) : (
              <div className="runtime-artifact-title">{t('runtimeArtifacts.checkpointNotFound')}</div>
            )}
          </div>
        )}

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
                    {checkpointResumeBadges(t, checkpoint.resumeManifestSupported, checkpoint.resumeSupported).map(label => (
                      <div className="runtime-artifact-meta" key={label}>{label}</div>
                    ))}
                  </div>
                  <div className="runtime-artifact-actions runtime-artifact-actions-inline">
                    <button
                      className="btn btn-sm"
                      onClick={() => void handleResolveCheckpoint(checkpoint)}
                      disabled={resolvingCheckpointKey === checkpoint.id}
                      aria-label={t('runtimeArtifacts.resolveCheckpoint', { name: checkpoint.name })}
                      type="button"
                    >
                      {resolvingCheckpointKey === checkpoint.id ? t('runtimeArtifacts.resolving') : t('runtimeArtifacts.resolve')}
                    </button>
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
                        <div className="runtime-artifact-title">{pauseTitle(request, t)}</div>
                        <div className="runtime-artifact-meta">{nodeId} · {pauseStatusLabel(status, t)}</div>
                        {pauseRuntimeBadges(
                          t,
                          typeof request.review_decision_supported === 'boolean'
                            ? request.review_decision_supported
                            : pauseRequests?.review_decision_supported,
                          typeof request.engine_pause_supported === 'boolean'
                            ? request.engine_pause_supported
                            : pauseRequests?.engine_pause_supported,
                        ).map(label => (
                          <div className="runtime-artifact-meta" key={label}>{label}</div>
                        ))}
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
              <span>{t('runtimeArtifacts.submittedRunCount', { count: triggerEvaluation.submitted_run_count })}</span>
            </div>
          )}
          {submittedRuns.length > 0 && (
            <div className="runtime-artifacts-list">
              {submittedRuns.map((run, index) => {
                const key = valueAsString(run.run_id)
                  || valueAsString(run.trigger_file)
                  || `${submittedRunTitle(run, t)}-${index}`;
                const meta = submittedRunMeta(run);
                const reason = valueAsString(run.reason);
                return (
                  <div className="runtime-artifact-row" key={key}>
                    <Icon name={run.status === 'submitted' ? 'check' : 'clock'} size={14} />
                    <div>
                      <div className="runtime-artifact-title">{submittedRunTitle(run, t)}</div>
                      {meta && <div className="runtime-artifact-meta">{meta}</div>}
                      {reason && <div className="runtime-artifact-meta">{reason}</div>}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
          {triggerBadges.length > 0 && (
            <div className="runtime-artifacts-evaluation">
              {triggerBadges.map(label => (
                <span key={label}>{label}</span>
              ))}
            </div>
          )}
          {triggerList.length > 0 ? (
            <div className="runtime-artifacts-list">
              {triggerList.map((trigger, index) => {
                const key = valueAsString(trigger.trigger_file) || `${triggerTitle(trigger, t)}-${index}`;
                return (
                  <div className="runtime-artifact-row" key={key}>
                    <Icon name={trigger.trigger_type === 'schedule' ? 'clock' : 'target'} size={14} />
                    <div>
                      <div className="runtime-artifact-title">{triggerTitle(trigger, t)}</div>
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
