import { useCallback, useEffect, useState } from 'react';
import { apiGet, apiPost } from '../../api/client';

export interface CheckpointManifestResponse {
  exists: boolean;
  manifest_path: string;
  manifest: Record<string, unknown>;
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
  [key: string]: unknown;
}

export interface PauseRequestsResponse {
  pause_requests_dir: string;
  pause_requests: PauseRequestRecord[];
  count: number;
  errors: Array<Record<string, string>>;
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

export interface WorkflowTriggersResponse {
  trigger_dir: string;
  triggers: WorkflowTriggerRecord[];
  count: number;
  errors: Array<Record<string, string>>;
}

export interface WorkflowTriggerEvaluationResponse {
  trigger_dir?: string;
  due_schedule_triggers: WorkflowTriggerRecord[];
  due_schedule_count: number;
  due_file_watch_triggers: WorkflowTriggerRecord[];
  due_file_watch_count: number;
  errors: Array<Record<string, string>>;
  scheduler_runner_contract_supported?: boolean;
  file_watch_runner_contract_supported?: boolean;
  run_submission_supported?: boolean;
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

export function useWorkflowRuntimeArtifacts() {
  const [checkpointManifest, setCheckpointManifest] = useState<CheckpointManifestResponse | null>(null);
  const [pauseRequests, setPauseRequests] = useState<PauseRequestsResponse | null>(null);
  const [workflowTriggers, setWorkflowTriggers] = useState<WorkflowTriggersResponse | null>(null);
  const [triggerEvaluation, setTriggerEvaluation] = useState<WorkflowTriggerEvaluationResponse | null>(null);
  const [lastResolvedPauseRequest, setLastResolvedPauseRequest] = useState<PauseRequestRecord | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [checkpointData, pauseData, triggerData] = await Promise.all([
        apiGet<CheckpointManifestResponse>('/checkpoints/manifest'),
        apiGet<PauseRequestsResponse>('/pause_requests'),
        apiGet<WorkflowTriggersResponse>('/workflow_triggers'),
      ]);
      setCheckpointManifest(checkpointData);
      setPauseRequests(pauseData);
      setWorkflowTriggers(triggerData);
    } catch (err) {
      setError(err instanceof Error ? err : new Error(String(err)));
    } finally {
      setLoading(false);
    }
  }, []);

  const evaluateWorkflowTriggers = useCallback(async (now?: string) => {
    const data = await apiPost<WorkflowTriggerEvaluationResponse>('/workflow_triggers/evaluate', now ? { now } : {});
    setTriggerEvaluation(data);
    return data;
  }, []);

  const resolvePauseRequest = useCallback(async (input: ResolvePauseRequestInput) => {
    const data = await apiPost<ResolvePauseRequestResponse>('/pause_requests/resolve', input);
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
    lastResolvedPauseRequest,
    loading,
    error,
    refresh,
    evaluateWorkflowTriggers,
    resolvePauseRequest,
  };
}
