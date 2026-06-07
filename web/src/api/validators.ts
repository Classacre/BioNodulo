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
    start_time: optionalString(obj.start_time, `${path}.start_time`),
    end_time: optionalString(obj.end_time, `${path}.end_time`),
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
// Runs list validator. The /api/queue and /api/history endpoints both return
// { runs: RunRecord[] }; we tolerate a top-level array as a fallback.
// ---------------------------------------------------------------------------

export function validateRunsList(value: unknown): ValidatedRunRecord[] {
  const raw = isObject(value) && Array.isArray(value.runs)
    ? value.runs
    : Array.isArray(value)
      ? value
      : (() => { throw new ApiValidationError('runs_list', '{ runs: [] } or array', value); })();
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
