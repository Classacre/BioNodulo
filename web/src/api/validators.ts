// Hand-rolled runtime validators for the API responses we depend on most
// (run records, workflow JSON, template list). The goal is not to ship a
// full Zod-style DSL — the goal is to fail loudly with an actionable
// message when the backend returns something the client wasn't expecting,
// rather than letting the bad shape propagate as `undefined`s into the UI.
//
// We keep this dependency-free because Zod's bundle cost (~10kB min+gz) is
// hard to justify for ~5 endpoints. If validation coverage grows, swap to
// Zod and these functions become drop-in shims.
//
// Convention:
//   - `validateX(value)` throws `ApiValidationError` on shape mismatch.
//   - `safeValidateX(value)` returns `{ ok: true, value } | { ok: false, error }`.
//   - Validators are *permissive* about extra fields — we only enforce the
//     subset the UI relies on — so an additive backend change won't break
//     the frontend.

import type {
  CustomNodePackage,
  CustomNodeRegistryCompatibility,
  CustomNodeRegistryEntry,
  ManagerRegistryResponse,
} from '../types';

export class ApiValidationError extends Error {
  readonly path: string;
  readonly received: unknown;

  constructor(path: string, expected: string, received: unknown) {
    super(`API validation failed at ${path}: expected ${expected}, got ${describe(received)}`);
    this.name = 'ApiValidationError';
    this.path = path;
    this.received = received;
  }
}

function describe(value: unknown): string {
  if (value === null) return 'null';
  if (Array.isArray(value)) return `array(length=${value.length})`;
  return typeof value;
}

function isObject(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === 'object' && !Array.isArray(value);
}

function requireString(value: unknown, path: string): string {
  if (typeof value !== 'string') throw new ApiValidationError(path, 'string', value);
  return value;
}

function optionalString(value: unknown, path: string): string | undefined {
  if (value === undefined || value === null) return undefined;
  if (typeof value !== 'string') throw new ApiValidationError(path, 'string | undefined', value);
  return value;
}

function optionalTimestamp(value: unknown, path: string): string | undefined {
  if (value === undefined || value === null) return undefined;
  if (typeof value === 'string') return value;
  if (typeof value === 'number' && Number.isFinite(value)) {
    return new Date(value * 1000).toISOString();
  }
  throw new ApiValidationError(path, 'string | unix timestamp | undefined', value);
}

function requireObject(value: unknown, path: string): Record<string, unknown> {
  if (!isObject(value)) throw new ApiValidationError(path, 'object', value);
  return value;
}

function requireArray(value: unknown, path: string): unknown[] {
  if (!Array.isArray(value)) throw new ApiValidationError(path, 'array', value);
  return value;
}

function requireBoolean(value: unknown, path: string): boolean {
  if (typeof value !== 'boolean') throw new ApiValidationError(path, 'boolean', value);
  return value;
}

function stringArray(value: unknown, path: string): string[] {
  if (value === undefined || value === null) return [];
  return requireArray(value, path).filter((item): item is string => typeof item === 'string');
}

function stringRecord(value: unknown, path: string): Record<string, string> {
  const obj = requireObject(value, path);
  const result: Record<string, string> = {};
  for (const [key, raw] of Object.entries(obj)) {
    if (typeof raw === 'string') result[key] = raw;
  }
  return result;
}

// ---------------------------------------------------------------------------
// Run record validator. The frontend depends heavily on `run_id` + `status`;
// other fields are optional / defaulted.
// ---------------------------------------------------------------------------

export interface ValidatedRunRecord {
  run_id: string;
  status: string;
  workflow_name?: string;
  node_statuses: unknown[];
  artifacts: Record<string, unknown>;
  previews: Record<string, unknown>;
  start_time?: string;
  end_time?: string;
  error?: string;
}

export function validateRunRecord(value: unknown, path = 'run'): ValidatedRunRecord {
  const obj = requireObject(value, path);
  return {
    run_id: requireString(obj.run_id, `${path}.run_id`),
    status: requireString(obj.status, `${path}.status`),
    workflow_name: optionalString(obj.workflow_name, `${path}.workflow_name`),
    node_statuses: Array.isArray(obj.node_statuses) ? obj.node_statuses : [],
    artifacts: isObject(obj.artifacts) ? obj.artifacts : {},
    previews: isObject(obj.previews) ? obj.previews : {},
    start_time: optionalTimestamp(obj.start_time, `${path}.start_time`)
      ?? optionalTimestamp(obj.started_at, `${path}.started_at`),
    end_time: optionalTimestamp(obj.end_time, `${path}.end_time`)
      ?? optionalTimestamp(obj.finished_at, `${path}.finished_at`),
    error: optionalString(obj.error, `${path}.error`),
  };
}

// ---------------------------------------------------------------------------
// Workflow JSON validator. We only enforce that `nodes` is an array of
// objects with id+type; the inner params are intentionally `unknown` because
// the schema varies per node type.
// ---------------------------------------------------------------------------

export interface ValidatedWorkflowNode {
  id: string;
  type: string;
  params?: Record<string, unknown>;
  position?: [number, number];
  ui?: Record<string, unknown>;
}

export interface ValidatedWorkflowParameter {
  name: string;
  type: string;
  required?: boolean;
  default?: unknown;
  value?: unknown;
  description?: string;
}

export interface ValidatedWorkflow {
  id?: string;
  name?: string;
  nodes: ValidatedWorkflowNode[];
  edges: unknown[];
  groups?: unknown[];
  parameters?: ValidatedWorkflowParameter[];
}

export function validateWorkflow(value: unknown, path = 'workflow'): ValidatedWorkflow {
  const obj = requireObject(value, path);
  const nodes = requireArray(obj.nodes, `${path}.nodes`).map((raw, index) => {
    const nodePath = `${path}.nodes[${index}]`;
    const node = requireObject(raw, nodePath);
    const position = Array.isArray(node.position) && node.position.length === 2
      && typeof node.position[0] === 'number' && typeof node.position[1] === 'number'
      ? [node.position[0], node.position[1]] as [number, number]
      : undefined;
    return {
      id: requireString(node.id, `${nodePath}.id`),
      type: requireString(node.type, `${nodePath}.type`),
      params: isObject(node.params) ? node.params : undefined,
      position,
      ui: isObject(node.ui) ? node.ui : undefined,
    };
  });
  const parameters = validateWorkflowParameters(obj.parameters, `${path}.parameters`);
  return {
    id: optionalString(obj.id, `${path}.id`),
    name: optionalString(obj.name, `${path}.name`),
    nodes,
    edges: Array.isArray(obj.edges) ? obj.edges : [],
    groups: Array.isArray(obj.groups) ? obj.groups : undefined,
    parameters,
  };
}

function validateWorkflowParameters(value: unknown, path: string): ValidatedWorkflowParameter[] | undefined {
  if (value === undefined || value === null) return undefined;
  const rawParameters = requireArray(value, path);
  const seenNames = new Set<string>();
  return rawParameters.map((raw, index) => {
    const paramPath = `${path}[${index}]`;
    const param = requireObject(raw, paramPath);
    const name = requireString(param.name, `${paramPath}.name`).trim();
    if (!name) throw new ApiValidationError(`${paramPath}.name`, 'non-empty string', param.name);
    if (seenNames.has(name)) throw new ApiValidationError(`${paramPath}.name`, 'unique parameter name', name);
    seenNames.add(name);
    const type = requireString(param.type, `${paramPath}.type`).trim();
    if (!type) throw new ApiValidationError(`${paramPath}.type`, 'non-empty string', param.type);
    return {
      name,
      type,
      required: typeof param.required === 'boolean' ? param.required : undefined,
      default: param.default,
      value: param.value,
      description: typeof param.description === 'string' ? param.description : undefined,
    };
  });
}

// ---------------------------------------------------------------------------
// Object-info validator. The object_info endpoint is the largest payload we
// fetch and the most prone to backend shape drift, so we only enforce that
// each key maps to an object — the per-node normalisation already happens in
// `useObjectInfo`.
// ---------------------------------------------------------------------------

export function validateObjectInfo(value: unknown): Record<string, Record<string, unknown>> {
  const obj = requireObject(value, 'object_info');
  const result: Record<string, Record<string, unknown>> = {};
  for (const [key, raw] of Object.entries(obj)) {
    if (isObject(raw)) result[key] = raw;
    // else: silently drop. We don't want a single bad entry to break the panel.
  }
  return result;
}

// ---------------------------------------------------------------------------
// Safe-validator wrappers. Use these from API hooks that should degrade
// gracefully (eg fall back to cached data) instead of throwing.
// ---------------------------------------------------------------------------

export type ValidationResult<T> =
  | { ok: true; value: T }
  | { ok: false; error: ApiValidationError };

function safe<T>(fn: () => T): ValidationResult<T> {
  try {
    return { ok: true, value: fn() };
  } catch (err) {
    if (err instanceof ApiValidationError) return { ok: false, error: err };
    throw err;
  }
}

export const safeValidateRunRecord = (value: unknown): ValidationResult<ValidatedRunRecord> =>
  safe(() => validateRunRecord(value));

export const safeValidateWorkflow = (value: unknown): ValidationResult<ValidatedWorkflow> =>
  safe(() => validateWorkflow(value));

export const safeValidateObjectInfo = (value: unknown): ValidationResult<Record<string, Record<string, unknown>>> =>
  safe(() => validateObjectInfo(value));

// ---------------------------------------------------------------------------
// Host-status validator. The HostPrerequisitesBanner trusts the shape pretty
// directly; we only coerce missing booleans to false rather than crashing.
// ---------------------------------------------------------------------------

export interface ValidatedHostStatus {
  ready: boolean;
  checks: Record<string, unknown>;
  missing_required: string[];
  missing_optional: string[];
  message: string;
}

export function validateHostStatus(value: unknown): ValidatedHostStatus {
  const obj = requireObject(value, 'host_status');
  return {
    ready: typeof obj.ready === 'boolean' ? obj.ready : false,
    checks: isObject(obj.checks) ? obj.checks : {},
    missing_required: Array.isArray(obj.missing_required)
      ? obj.missing_required.filter((x): x is string => typeof x === 'string')
      : [],
    missing_optional: Array.isArray(obj.missing_optional)
      ? obj.missing_optional.filter((x): x is string => typeof x === 'string')
      : [],
    message: typeof obj.message === 'string' ? obj.message : '',
  };
}

export const safeValidateHostStatus = (value: unknown): ValidationResult<ValidatedHostStatus> =>
  safe(() => validateHostStatus(value));

// ---------------------------------------------------------------------------
// HPC-status validator. The endpoint can return either { status: 'on'|'off' }
// or { connected: bool } — the topbar treats both as equivalent.
// ---------------------------------------------------------------------------

export interface ValidatedHpcStatus {
  status?: 'on' | 'off' | 'error';
  connected?: boolean;
}

export function validateHpcStatus(value: unknown): ValidatedHpcStatus {
  const obj = requireObject(value, 'hpc_status');
  const rawStatus = obj.status;
  const status = typeof rawStatus === 'string'
    && (rawStatus === 'on' || rawStatus === 'off' || rawStatus === 'error')
    ? rawStatus
    : undefined;
  return {
    status,
    connected: typeof obj.connected === 'boolean' ? obj.connected : undefined,
  };
}

export const safeValidateHpcStatus = (value: unknown): ValidationResult<ValidatedHpcStatus> =>
  safe(() => validateHpcStatus(value));

// ---------------------------------------------------------------------------
// Runs list validator. The queue/history endpoints have had a few shapes over
// time: { runs }, { pending, running }, { history }, plus legacy top-level
// arrays. Normalize them here so callers do not duplicate shape handling.
// ---------------------------------------------------------------------------

export function validateRunsList(value: unknown): ValidatedRunRecord[] {
  const raw = (() => {
    if (Array.isArray(value)) return value;
    if (!isObject(value)) {
      throw new ApiValidationError('runs_list', '{ runs: [] }, { pending/running }, { history }, or array', value);
    }
    if ('runs' in value) return requireArray(value.runs, 'runs_list.runs');
    if ('history' in value) return requireArray(value.history, 'runs_list.history');
    if ('pending' in value || 'running' in value) {
      const pending = value.pending === undefined ? [] : requireArray(value.pending, 'runs_list.pending');
      const running = value.running === undefined ? [] : requireArray(value.running, 'runs_list.running');
      return [...pending, ...running];
    }
    throw new ApiValidationError('runs_list', '{ runs: [] }, { pending/running }, { history }, or array', value);
  })();
  const out: ValidatedRunRecord[] = [];
  for (let i = 0; i < raw.length; i++) {
    try {
      out.push(validateRunRecord(raw[i], `runs_list[${i}]`));
    } catch {
      // Skip individual bad rows rather than failing the whole list.
    }
  }
  return out;
}

export const safeValidateRunsList = (value: unknown): ValidationResult<ValidatedRunRecord[]> =>
  safe(() => validateRunsList(value));

// ---------------------------------------------------------------------------
// Runtime-artifact validators. These endpoints power the runtime artifacts
// panel; top-level contracts must be stable, but malformed individual records
// should not blank the whole panel.
// ---------------------------------------------------------------------------

export type RuntimeArtifactRecord = Record<string, unknown>;

export interface ValidatedCheckpointManifestResponse {
  exists: boolean;
  manifest_path: string;
  manifest: Record<string, unknown>;
  resume_manifest_supported?: boolean;
  resume_supported?: boolean;
  resume_note?: string;
}

export interface ValidatedResolveCheckpointResponse {
  found: boolean;
  manifest_path: string;
  checkpoint: RuntimeArtifactRecord | null;
  resume_manifest_supported?: boolean;
  resume_supported?: boolean;
  resume_note?: string;
}

export interface ValidatedPauseRequestsResponse {
  pause_requests_dir: string;
  pause_requests: RuntimeArtifactRecord[];
  count: number;
  errors: Record<string, string>[];
  review_decision_supported?: boolean;
  engine_pause_supported?: boolean;
  pause_note?: string;
}

export interface ValidatedResolvePauseRequestResponse {
  pause_request: RuntimeArtifactRecord;
}

export interface ValidatedWorkflowTriggersResponse {
  trigger_dir: string;
  triggers: RuntimeArtifactRecord[];
  count: number;
  errors: Record<string, string>[];
  scheduler_runner_contract_supported?: boolean;
  file_watch_runner_contract_supported?: boolean;
  durable_scheduler_supported?: boolean;
  polling_file_watcher_supported?: boolean;
  run_submission_supported?: boolean;
  workflow_trigger_note?: string;
}

export interface ValidatedWorkflowTriggerEvaluationResponse {
  trigger_dir?: string;
  due_schedule_triggers: RuntimeArtifactRecord[];
  due_schedule_count: number;
  due_file_watch_triggers: RuntimeArtifactRecord[];
  due_file_watch_count: number;
  submitted_runs: RuntimeArtifactRecord[];
  submitted_run_count: number;
  errors: Record<string, string>[];
  scheduler_runner_contract_supported?: boolean;
  file_watch_runner_contract_supported?: boolean;
  durable_scheduler_supported?: boolean;
  polling_file_watcher_supported?: boolean;
  run_submission_supported?: boolean;
  workflow_trigger_note?: string;
}

function optionalBoolean(value: unknown, path: string): boolean | undefined {
  if (value === undefined || value === null) return undefined;
  if (typeof value !== 'boolean') throw new ApiValidationError(path, 'boolean | undefined', value);
  return value;
}

function objectList(value: unknown, path: string): RuntimeArtifactRecord[] {
  return requireArray(value, path)
    .filter((item): item is RuntimeArtifactRecord => isObject(item))
    .map(item => ({ ...item }));
}

function stringRecordList(value: unknown, path: string): Record<string, string>[] {
  return requireArray(value, path).flatMap((item): Record<string, string>[] => {
    if (!isObject(item)) return [];
    const out: Record<string, string> = {};
    for (const [key, raw] of Object.entries(item)) {
      if (typeof raw === 'string') out[key] = raw;
    }
    return Object.keys(out).length > 0 ? [out] : [];
  });
}

export function validateCheckpointManifestResponse(value: unknown): ValidatedCheckpointManifestResponse {
  const obj = requireObject(value, 'checkpoint_manifest');
  return {
    exists: requireBoolean(obj.exists, 'checkpoint_manifest.exists'),
    manifest_path: requireString(obj.manifest_path, 'checkpoint_manifest.manifest_path'),
    manifest: requireObject(obj.manifest, 'checkpoint_manifest.manifest'),
    resume_manifest_supported: optionalBoolean(
      obj.resume_manifest_supported,
      'checkpoint_manifest.resume_manifest_supported',
    ),
    resume_supported: optionalBoolean(obj.resume_supported, 'checkpoint_manifest.resume_supported'),
    resume_note: optionalString(obj.resume_note, 'checkpoint_manifest.resume_note'),
  };
}

export function validateResolveCheckpointResponse(value: unknown): ValidatedResolveCheckpointResponse {
  const obj = requireObject(value, 'resolve_checkpoint');
  const rawCheckpoint = obj.checkpoint;
  const checkpoint = rawCheckpoint === null
    ? null
    : requireObject(rawCheckpoint, 'resolve_checkpoint.checkpoint');
  return {
    found: requireBoolean(obj.found, 'resolve_checkpoint.found'),
    manifest_path: requireString(obj.manifest_path, 'resolve_checkpoint.manifest_path'),
    checkpoint,
    resume_manifest_supported: optionalBoolean(
      obj.resume_manifest_supported,
      'resolve_checkpoint.resume_manifest_supported',
    ),
    resume_supported: optionalBoolean(obj.resume_supported, 'resolve_checkpoint.resume_supported'),
    resume_note: optionalString(obj.resume_note, 'resolve_checkpoint.resume_note'),
  };
}

export function validatePauseRequestsResponse(value: unknown): ValidatedPauseRequestsResponse {
  const obj = requireObject(value, 'pause_requests');
  const pauseRequests = objectList(obj.pause_requests, 'pause_requests.pause_requests');
  return {
    pause_requests_dir: requireString(obj.pause_requests_dir, 'pause_requests.pause_requests_dir'),
    pause_requests: pauseRequests,
    count: pauseRequests.length,
    errors: stringRecordList(obj.errors, 'pause_requests.errors'),
    review_decision_supported: optionalBoolean(
      obj.review_decision_supported,
      'pause_requests.review_decision_supported',
    ),
    engine_pause_supported: optionalBoolean(obj.engine_pause_supported, 'pause_requests.engine_pause_supported'),
    pause_note: optionalString(obj.pause_note, 'pause_requests.pause_note'),
  };
}

export function validateResolvePauseRequestResponse(value: unknown): ValidatedResolvePauseRequestResponse {
  const obj = requireObject(value, 'resolve_pause_request');
  return {
    pause_request: requireObject(obj.pause_request, 'resolve_pause_request.pause_request'),
  };
}

export function validateWorkflowTriggersResponse(value: unknown): ValidatedWorkflowTriggersResponse {
  const obj = requireObject(value, 'workflow_triggers');
  const triggers = objectList(obj.triggers, 'workflow_triggers.triggers');
  return {
    trigger_dir: requireString(obj.trigger_dir, 'workflow_triggers.trigger_dir'),
    triggers,
    count: triggers.length,
    errors: stringRecordList(obj.errors, 'workflow_triggers.errors'),
    scheduler_runner_contract_supported: optionalBoolean(
      obj.scheduler_runner_contract_supported,
      'workflow_triggers.scheduler_runner_contract_supported',
    ),
    file_watch_runner_contract_supported: optionalBoolean(
      obj.file_watch_runner_contract_supported,
      'workflow_triggers.file_watch_runner_contract_supported',
    ),
    durable_scheduler_supported: optionalBoolean(
      obj.durable_scheduler_supported,
      'workflow_triggers.durable_scheduler_supported',
    ),
    polling_file_watcher_supported: optionalBoolean(
      obj.polling_file_watcher_supported,
      'workflow_triggers.polling_file_watcher_supported',
    ),
    run_submission_supported: optionalBoolean(obj.run_submission_supported, 'workflow_triggers.run_submission_supported'),
    workflow_trigger_note: optionalString(obj.workflow_trigger_note, 'workflow_triggers.workflow_trigger_note'),
  };
}

export function validateWorkflowTriggerEvaluationResponse(
  value: unknown,
): ValidatedWorkflowTriggerEvaluationResponse {
  const obj = requireObject(value, 'workflow_trigger_evaluation');
  const dueScheduleTriggers = objectList(
    obj.due_schedule_triggers,
    'workflow_trigger_evaluation.due_schedule_triggers',
  );
  const dueFileWatchTriggers = objectList(
    obj.due_file_watch_triggers,
    'workflow_trigger_evaluation.due_file_watch_triggers',
  );
  const submittedRuns = objectList(obj.submitted_runs, 'workflow_trigger_evaluation.submitted_runs');
  return {
    trigger_dir: optionalString(obj.trigger_dir, 'workflow_trigger_evaluation.trigger_dir'),
    due_schedule_triggers: dueScheduleTriggers,
    due_schedule_count: dueScheduleTriggers.length,
    due_file_watch_triggers: dueFileWatchTriggers,
    due_file_watch_count: dueFileWatchTriggers.length,
    submitted_runs: submittedRuns,
    submitted_run_count: submittedRuns.filter(run => run.status === 'submitted').length,
    errors: stringRecordList(obj.errors, 'workflow_trigger_evaluation.errors'),
    scheduler_runner_contract_supported: optionalBoolean(
      obj.scheduler_runner_contract_supported,
      'workflow_trigger_evaluation.scheduler_runner_contract_supported',
    ),
    file_watch_runner_contract_supported: optionalBoolean(
      obj.file_watch_runner_contract_supported,
      'workflow_trigger_evaluation.file_watch_runner_contract_supported',
    ),
    durable_scheduler_supported: optionalBoolean(
      obj.durable_scheduler_supported,
      'workflow_trigger_evaluation.durable_scheduler_supported',
    ),
    polling_file_watcher_supported: optionalBoolean(
      obj.polling_file_watcher_supported,
      'workflow_trigger_evaluation.polling_file_watcher_supported',
    ),
    run_submission_supported: optionalBoolean(
      obj.run_submission_supported,
      'workflow_trigger_evaluation.run_submission_supported',
    ),
    workflow_trigger_note: optionalString(
      obj.workflow_trigger_note,
      'workflow_trigger_evaluation.workflow_trigger_note',
    ),
  };
}

export const safeValidateCheckpointManifestResponse = (
  value: unknown,
): ValidationResult<ValidatedCheckpointManifestResponse> =>
  safe(() => validateCheckpointManifestResponse(value));

export const safeValidateResolveCheckpointResponse = (
  value: unknown,
): ValidationResult<ValidatedResolveCheckpointResponse> =>
  safe(() => validateResolveCheckpointResponse(value));

export const safeValidatePauseRequestsResponse = (
  value: unknown,
): ValidationResult<ValidatedPauseRequestsResponse> =>
  safe(() => validatePauseRequestsResponse(value));

export const safeValidateResolvePauseRequestResponse = (
  value: unknown,
): ValidationResult<ValidatedResolvePauseRequestResponse> =>
  safe(() => validateResolvePauseRequestResponse(value));

export const safeValidateWorkflowTriggersResponse = (
  value: unknown,
): ValidationResult<ValidatedWorkflowTriggersResponse> =>
  safe(() => validateWorkflowTriggersResponse(value));

export const safeValidateWorkflowTriggerEvaluationResponse = (
  value: unknown,
): ValidationResult<ValidatedWorkflowTriggerEvaluationResponse> =>
  safe(() => validateWorkflowTriggerEvaluationResponse(value));

// ---------------------------------------------------------------------------
// Manager registry validator. The /api/manager/registry endpoint drives
// custom-node discovery/install surfaces, so callers need stable registry,
// compatibility, and installed-package arrays even when optional manifest
// fields are absent.
// ---------------------------------------------------------------------------

function validateCustomNodePackage(value: unknown, path: string): CustomNodePackage {
  const obj = requireObject(value, path);
  return {
    name: requireString(obj.name, `${path}.name`),
    version: requireString(obj.version, `${path}.version`),
    description: typeof obj.description === 'string' ? obj.description : '',
    repository: typeof obj.repository === 'string' ? obj.repository : '',
    entrypoints: stringArray(obj.entrypoints, `${path}.entrypoints`),
    requirements: stringArray(obj.requirements, `${path}.requirements`),
    directory: requireString(obj.directory, `${path}.directory`),
    manifest_path: typeof obj.manifest_path === 'string' ? obj.manifest_path : '',
    manifest_present: typeof obj.manifest_present === 'boolean' ? obj.manifest_present : false,
    valid: typeof obj.valid === 'boolean' ? obj.valid : true,
    errors: stringArray(obj.errors, `${path}.errors`),
  };
}

function validateRegistryCompatibility(value: unknown, path: string): CustomNodeRegistryCompatibility {
  const obj = requireObject(value, path);
  return {
    manifest_required: requireBoolean(obj.manifest_required, `${path}.manifest_required`),
    supported_manifest: requireString(obj.supported_manifest, `${path}.supported_manifest`),
  };
}

function validateCustomNodeRegistryEntry(value: unknown, path: string): CustomNodeRegistryEntry {
  const obj = requireObject(value, path);
  return {
    name: requireString(obj.name, `${path}.name`),
    url: requireString(obj.url, `${path}.url`),
    description: typeof obj.description === 'string' ? obj.description : '',
    installed: requireBoolean(obj.installed, `${path}.installed`),
    install_status: requireString(obj.install_status, `${path}.install_status`),
    installed_package: obj.installed_package === undefined || obj.installed_package === null
      ? null
      : validateCustomNodePackage(obj.installed_package, `${path}.installed_package`),
    verified: typeof obj.verified === 'boolean' ? obj.verified : false,
    compatibility: validateRegistryCompatibility(obj.compatibility, `${path}.compatibility`),
  };
}

export function validateManagerRegistry(value: unknown): ManagerRegistryResponse {
  const obj = requireObject(value, 'manager_registry');
  const rawRegistries = requireObject(obj.custom_node_registries, 'manager_registry.custom_node_registries');
  const customNodeRegistries: Record<string, CustomNodeRegistryEntry> = {};
  for (const [name, raw] of Object.entries(rawRegistries)) {
    customNodeRegistries[name] = validateCustomNodeRegistryEntry(
      raw,
      `manager_registry.custom_node_registries.${name}`,
    );
  }
  return {
    registries: stringRecord(obj.registries, 'manager_registry.registries'),
    tool_paths: stringRecord(obj.tool_paths, 'manager_registry.tool_paths'),
    custom_node_registries: customNodeRegistries,
    installed_packages: requireArray(obj.installed_packages, 'manager_registry.installed_packages')
      .map((raw, index) => validateCustomNodePackage(raw, `manager_registry.installed_packages[${index}]`)),
  };
}

export const safeValidateManagerRegistry = (value: unknown): ValidationResult<ManagerRegistryResponse> =>
  safe(() => validateManagerRegistry(value));
