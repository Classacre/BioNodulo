import { useState, useEffect, useCallback } from 'react';
import type { InputSpec, ObjectInfo, NodeMetadata } from '../../types';
import { safeValidateObjectInfo } from '../../api/validators';
import { apiGet, ApiError } from '../../api/client';
import { logError } from '../../state/logging';

function normalizeInputSpec(spec: unknown): InputSpec {
  if (Array.isArray(spec)) {
    const [type, config] = spec;
    return {
      ...(config && typeof config === 'object' ? config as Record<string, unknown> : {}),
      type: String(Array.isArray(type) ? type[0] : type || 'STRING'),
    } as InputSpec;
  }
  if (spec && typeof spec === 'object') {
    const raw = spec as Record<string, unknown>;
    return {
      ...raw,
      type: String(raw.type || 'STRING'),
    } as InputSpec;
  }
  return { type: String(spec || 'STRING') };
}

function normalizeInputs(input: unknown): NodeMetadata['input_types'] {
  if (!input || typeof input !== 'object') return {};
  const sections = input as Record<string, unknown>;
  const normalized: NodeMetadata['input_types'] = {};
  for (const section of ['required', 'optional', 'hidden'] as const) {
    const rawSection = sections[section];
    if (!rawSection || typeof rawSection !== 'object') continue;
    normalized[section] = Object.fromEntries(
      Object.entries(rawSection as Record<string, unknown>).map(([name, spec]) => [
        name,
        normalizeInputSpec(spec),
      ]),
    );
  }
  return normalized;
}

function optionalString(value: unknown): string | undefined {
  return value ? String(value) : undefined;
}

function stringList(value: unknown): string[] {
  return Array.isArray(value) ? value.map(String) : [];
}

function normalizeCustomNodePackage(raw: unknown): NodeMetadata['custom_node_package'] | undefined {
  if (!raw || typeof raw !== 'object') return undefined;
  const obj = raw as Record<string, unknown>;
  return {
    name: String(obj.name || ''),
    version: String(obj.version || ''),
    repository: String(obj.repository || ''),
    directory: String(obj.directory || ''),
    entrypoint: String(obj.entrypoint || ''),
    manifest_present: Boolean(obj.manifest_present),
  };
}

function normalizeLifecycle(raw: unknown): NodeMetadata['lifecycle'] | undefined {
  if (!raw || typeof raw !== 'object') return undefined;
  const obj = raw as Record<string, unknown>;
  return {
    status: optionalString(obj.status),
    deprecated: typeof obj.deprecated === 'boolean' ? obj.deprecated : undefined,
    deprecation_message: optionalString(obj.deprecation_message),
    replaced_by: optionalString(obj.replaced_by),
  };
}

function normalizeVersioning(raw: unknown): NodeMetadata['versioning'] | undefined {
  if (!raw || typeof raw !== 'object') return undefined;
  const obj = raw as Record<string, unknown>;
  return {
    current: optionalString(obj.current),
    previous: Array.isArray(obj.previous) ? obj.previous.map(String) : [],
    migrations: Array.isArray(obj.migrations)
      ? obj.migrations
          .filter((migration): migration is Record<string, unknown> => Boolean(migration) && typeof migration === 'object')
          .map((migration) => ({
            ...migration,
            from_version: optionalString(migration.from_version),
            to_version: optionalString(migration.to_version),
            description: optionalString(migration.description),
          }))
      : [],
  };
}

function normalizeObjectInfo(data: unknown): ObjectInfo {
  if (!data || typeof data !== 'object') return {};
  const entries = Object.entries(data as Record<string, Record<string, unknown>>);
  return Object.fromEntries(entries.map(([key, raw]) => {
    if (raw.input_types) {
      return [key, raw as unknown as NodeMetadata];
    }
    // Key the registry by the ORIGINAL `key` — that's what WorkflowNode.type
    // references (objectInfo[wn.type]). Re-keying by raw.name diverged the map
    // key from the lookup key (→ meta=null for those nodes) and collided/dropped
    // entries whose `name` matched another entry. `id` keeps raw.name for
    // display/identity.
    const id = String(raw.name || key);
    return [key, {
      id,
      display_name: String(raw.display_name || raw.name || key),
      category: String(raw.category || 'Other'),
      description: raw.description ? String(raw.description) : undefined,
      search_aliases: Array.isArray(raw.search_aliases) ? raw.search_aliases.map(String) : [],
      input_types: normalizeInputs(raw.input),
      return_types: Array.isArray(raw.output) ? raw.output.map(String) : [],
      return_names: Array.isArray(raw.output_name) ? raw.output_name.map(String) : [],
      output_node: Boolean(raw.output_node),
      visual_only: Boolean(raw.visual_only),
      experimental: Boolean(raw.experimental),
      version: raw.version ? String(raw.version) : undefined,
      deprecated: Boolean(raw.deprecated),
      deprecation_message: optionalString(raw.deprecation_message),
      replaced_by: optionalString(raw.replaced_by),
      lifecycle: normalizeLifecycle(raw.lifecycle),
      versioning: normalizeVersioning(raw.versioning),
      function: raw.python_class ? String(raw.python_class) : undefined,
      requires_external_tools: stringList(raw.required_executables),
      required_conda_packages: stringList(raw.required_conda_packages),
      required_r_packages: stringList(raw.required_r_packages),
      documentation_url: optionalString(raw.documentation_url),
      citation_dois: stringList(raw.citation_dois),
      citation_urls: stringList(raw.citation_urls),
      citation_text: optionalString(raw.citation_text),
      builtin: typeof raw.builtin === 'boolean' ? raw.builtin : undefined,
      git_url: optionalString(raw.git_url),
      git_commit: optionalString(raw.git_commit),
      custom_node_package: normalizeCustomNodePackage(raw.custom_node_package),
    } satisfies NodeMetadata];
  }));
}

export function useObjectInfo() {
  const [objectInfo, setObjectInfo] = useState<ObjectInfo>({});
  const [loading, setLoading] = useState(true);
  // Surface fetch failures instead of silently leaving the registry empty. An
  // empty registry makes every node resolve `meta=null`, which strips its
  // input/output ports and drops all edges (they have no handles to anchor to)
  // — the graph then looks broken with no error shown. Callers render a retry
  // banner from `error`; we KEEP the last-good map so a transient 401/blip
  // doesn't wipe an already-loaded canvas.
  const [error, setError] = useState<ApiError | Error | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const data = await apiGet<unknown>('/object_info');
      // Reject the whole payload only if the top-level shape is wrong; the
      // per-key normaliser already tolerates missing inner fields.
      const validation = safeValidateObjectInfo(data);
      if (validation.ok) {
        setObjectInfo(normalizeObjectInfo(validation.value));
      } else {
        // Fall back to the raw normaliser so a backend rolling out a
        // schema change doesn't leave the panel empty.
        setObjectInfo(normalizeObjectInfo(data));
      }
      setError(null);
    } catch (err) {
      // Do NOT reset objectInfo to {} — keep the last-good registry so an
      // authed reload blip or an anonymous 401 doesn't erase node ports and
      // orphan every edge. Record the error so the UI can prompt sign-in/retry.
      const e = err instanceof Error ? err : new Error(String(err));
      logError('objectInfo.fetch', e);
      setError(e);
    }
    setLoading(false);
  }, []);

  useEffect(() => { refresh(); }, [refresh]);

  return { objectInfo, loading, error, refresh };
}
