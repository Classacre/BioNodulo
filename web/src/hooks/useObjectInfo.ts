import { useState, useEffect, useCallback } from 'react';
import type { InputSpec, ObjectInfo, NodeMetadata } from '../types';
import { safeValidateObjectInfo } from '../api/validators';

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

function normalizeObjectInfo(data: unknown): ObjectInfo {
  if (!data || typeof data !== 'object') return {};
  const entries = Object.entries(data as Record<string, Record<string, unknown>>);
  return Object.fromEntries(entries.map(([key, raw]) => {
    if (raw.input_types) {
      return [key, raw as unknown as NodeMetadata];
    }
    const id = String(raw.name || key);
    return [id, {
      id,
      display_name: String(raw.display_name || raw.name || key),
      category: String(raw.category || 'Other'),
      description: raw.description ? String(raw.description) : undefined,
      input_types: normalizeInputs(raw.input),
      return_types: Array.isArray(raw.output) ? raw.output.map(String) : [],
      return_names: Array.isArray(raw.output_name) ? raw.output_name.map(String) : [],
      output_node: Boolean(raw.output_node),
      visual_only: Boolean(raw.visual_only),
      experimental: Boolean(raw.experimental),
      version: raw.version ? String(raw.version) : undefined,
      function: raw.python_class ? String(raw.python_class) : undefined,
      requires_external_tools: Array.isArray(raw.required_executables)
        ? raw.required_executables.map(String)
        : [],
    } satisfies NodeMetadata];
  }));
}

export function useObjectInfo() {
  const [objectInfo, setObjectInfo] = useState<ObjectInfo>({});
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const r = await fetch('/api/object_info');
      if (r.ok) {
        const data = await r.json();
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
      }
    } catch {
      // Will be empty initially without backend
    }
    setLoading(false);
  }, []);

  useEffect(() => { refresh(); }, [refresh]);

  return { objectInfo, loading, refresh };
}
