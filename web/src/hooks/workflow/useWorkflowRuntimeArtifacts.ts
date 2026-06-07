import { useCallback, useEffect, useState } from 'react';
import { apiGet, apiPost } from '../../api/client';
import { logError } from '../../state/logging';
import {
  safeValidateCheckpointManifestResponse,
  safeValidatePauseRequestsResponse,
  safeValidateResolveCheckpointResponse,
  safeValidateResolvePauseRequestResponse,
  safeValidateWorkflowTriggerEvaluationResponse,
  safeValidateWorkflowTriggersResponse,
  type ValidationResult,
} from '../../api/validators';

export interface CheckpointManifestResponse {
  exists: boolean;
  manifest_path: string;
  manifest: Record<string, unknown>;
  resume_manifest_supported?: boolean;
  resume_supported?: boolean;
  resume_note?: string;
}

export interface CheckpointRecord {
  checkpoint_name?: string;
  checkpoint_path?: string;
  run_id?: string;
  node_id?: string;
  node_type?: string;
  timestamp?: number;
  timestamp_iso?: string;
  compressed?: boolean;
  size_bytes?: number;
  resume_manifest_supported?: boolean;
  resume_supported?: boolean;
  note?: string;
  [key: string]: unknown;
}

export interface ResolveCheckpointInput {
  run_id?: string;
  node_id?: string;
  checkpoint_name?: string;
}

export interface ResolveCheckpointResponse {
  found: boolean;
  manifest_path: string;
  checkpoint: CheckpointRecord | null;
  resume_manifest_supported?: boolean;
  resume_supported?: boolean;
  resume_note?: string;
}

export interface PauseRequestRecord {
  pause_file?: string;
  run_id?: string;
  node_id?: string;
  message?: string;
  status?: string;
  approved?: boolean;
  resolved_by?: string;
  resolution_comment?: string;
  review_decision_supported?: boolean;
  engine_pause_supported?: boolean;
  note?: string;
  [key: string]: unknown;
}

export interface PauseRequestsResponse {
  pause_requests_dir: string;
  pause_requests: PauseRequestRecord[];
  count: number;
  errors: Array<Record<string, string>>;
  review_decision_supported?: boolean;
  engine_pause_supported?: boolean;
  pause_note?: string;
}

export interface WorkflowTriggerRecord {
  trigger_file?: string;
  trigger_type?: string;
  target_workflow?: string;
  status?: string;
  payload?: Record<string, unknown>;
  events?: Array<Record<string, string>>;
  [key: string]: unknown;
}

export interface SubmittedWorkflowTriggerRun {
  trigger_file?: string;
  status?: string;
  run_id?: string;
  target_workflow?: string;
  reason?: string;
  due_at?: string;
  [key: string]: unknown;
}

export interface WorkflowTriggersResponse {
  trigger_dir: string;
  triggers: WorkflowTriggerRecord[];
  count: number;
  errors: Array<Record<string, string>>;
  scheduler_runner_contract_supported?: boolean;
  file_watch_runner_contract_supported?: boolean;
  durable_scheduler_supported?: boolean;
  polling_file_watcher_supported?: boolean;
  run_submission_supported?: boolean;
  workflow_trigger_note?: string;
}

export interface WorkflowTriggerEvaluationResponse {
  trigger_dir?: string;
  due_schedule_triggers: WorkflowTriggerRecord[];
  due_schedule_count: number;
  due_file_watch_triggers: WorkflowTriggerRecord[];
  due_file_watch_count: number;
  submitted_runs: SubmittedWorkflowTriggerRun[];
  submitted_run_count: number;
  errors: Array<Record<string, string>>;
  scheduler_runner_contract_supported?: boolean;
  file_watch_runner_contract_supported?: boolean;
  durable_scheduler_supported?: boolean;
  polling_file_watcher_supported?: boolean;
  run_submission_supported?: boolean;
  workflow_trigger_note?: string;
}

export interface WorkflowTriggerEvaluationOptions {
  submitRuns?: boolean;
}

export interface ResolvePauseRequestInput {
  action: 'approve' | 'reject';
  node_id?: string;
  pause_file?: string;
  reviewer?: string;
  comment?: string;
}

export interface ResolvePauseRequestResponse {
  pause_request: PauseRequestRecord;
}

function unwrapValidated<T>(result: ValidationResult<T>): T {
  if (result.ok) return result.value;
  throw result.error;
}

export function useWorkflowRuntimeArtifacts() {
  const [checkpointManifest, setCheckpointManifest] = useState<CheckpointManifestResponse | null>(null);
  const [pauseRequests, setPauseRequests] = useState<PauseRequestsResponse | null>(null);
  const [workflowTriggers, setWorkflowTriggers] = useState<WorkflowTriggersResponse | null>(null);
  const [triggerEvaluation, setTriggerEvaluation] = useState<WorkflowTriggerEvaluationResponse | null>(null);
  const [lastResolvedCheckpoint, setLastResolvedCheckpoint] = useState<ResolveCheckpointResponse | null>(null);
  const [lastResolvedPauseRequest, setLastResolvedPauseRequest] = useState<PauseRequestRecord | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [checkpointData, pauseData, triggerData] = await Promise.all([
        apiGet<unknown>('/checkpoints/manifest'),
        apiGet<unknown>('/pause_requests'),
        apiGet<unknown>('/workflow_triggers'),
      ]);
      setCheckpointManifest(unwrapValidated(safeValidateCheckpointManifestResponse(checkpointData)));
      setPauseRequests(unwrapValidated(safeValidatePauseRequestsResponse(pauseData)));
      setWorkflowTriggers(unwrapValidated(safeValidateWorkflowTriggersResponse(triggerData)));
    } catch (err) {
      const error = err instanceof Error ? err : new Error(String(err));
      logError('runtimeArtifacts.refresh', error);
      setError(error);
    } finally {
      setLoading(false);
    }
  }, []);

  const evaluateWorkflowTriggers = useCallback(async (now?: string, options?: WorkflowTriggerEvaluationOptions) => {
    const body: Record<string, unknown> = {};
    if (now) body.now = now;
    if (options?.submitRuns) body.submit_runs = true;
    const rawData = await apiPost<unknown>('/workflow_triggers/evaluate', body);
    const data = unwrapValidated(safeValidateWorkflowTriggerEvaluationResponse(rawData));
    setTriggerEvaluation(data);
    return data;
  }, []);

  const resolveCheckpoint = useCallback(async (input: ResolveCheckpointInput) => {
    const params = new URLSearchParams();
    if (input.run_id) params.set('run_id', input.run_id);
    if (input.node_id) params.set('node_id', input.node_id);
    if (input.checkpoint_name) params.set('checkpoint_name', input.checkpoint_name);
    const query = params.toString();
    const rawData = await apiGet<unknown>(`/checkpoints/resolve${query ? `?${query}` : ''}`);
    const data = unwrapValidated(safeValidateResolveCheckpointResponse(rawData));
    setLastResolvedCheckpoint(data);
    return data;
  }, []);

  const resolvePauseRequest = useCallback(async (input: ResolvePauseRequestInput) => {
    const rawData = await apiPost<unknown>('/pause_requests/resolve', input);
    const data = unwrapValidated(safeValidateResolvePauseRequestResponse(rawData));
    setLastResolvedPauseRequest(data.pause_request);
    await refresh();
    return data.pause_request;
  }, [refresh]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  return {
    checkpointManifest,
    pauseRequests,
    workflowTriggers,
    triggerEvaluation,
    lastResolvedCheckpoint,
    lastResolvedPauseRequest,
    loading,
    error,
    refresh,
    evaluateWorkflowTriggers,
    resolveCheckpoint,
    resolvePauseRequest,
  };
}
