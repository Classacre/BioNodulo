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

export interface ValidatedWorkflow {
  id?: string;
  name?: string;
  nodes: ValidatedWorkflowNode[];
  edges: unknown[];
  groups?: unknown[];
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
  return {
    id: optionalString(obj.id, `${path}.id`),
    name: optionalString(obj.name, `${path}.name`),
    nodes,
    edges: Array.isArray(obj.edges) ? obj.edges : [],
    groups: Array.isArray(obj.groups) ? obj.groups : undefined,
  };
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
