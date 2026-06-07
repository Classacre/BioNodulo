import type { DynamicOutputSpec, InputSpec, NodeMetadata } from '../types';

export interface ResolvedNodeOutput {
  name: string;
  type: string;
}

function getInputSpec(meta: NodeMetadata | null | undefined, name: string): InputSpec | undefined {
  return (
    meta?.input_types?.required?.[name]
    ?? meta?.input_types?.optional?.[name]
    ?? meta?.input_types?.hidden?.[name]
  );
}

function findDynamicOutputSpec(meta: NodeMetadata | null | undefined): { spec: InputSpec; dynamic: DynamicOutputSpec } | null {
  const sections = [
    meta?.input_types?.required,
    meta?.input_types?.optional,
    meta?.input_types?.hidden,
  ];
  for (const section of sections) {
    for (const spec of Object.values(section || {})) {
      if (spec.dynamic_outputs) {
        return { spec, dynamic: spec.dynamic_outputs };
      }
    }
  }
  return null;
}

function integerParam(value: unknown): number | null {
  if (typeof value === 'number' && Number.isFinite(value)) return Math.trunc(value);
  if (typeof value === 'string' && value.trim() !== '') {
    const parsed = Number(value);
    if (Number.isFinite(parsed)) return Math.trunc(parsed);
  }
  return null;
}

function staticNodeOutputs(meta: NodeMetadata | null): ResolvedNodeOutput[] {
  return (meta?.return_types || []).map((type, index) => ({
    name: meta?.return_names?.[index] || type,
    type,
  }));
}

export function resolveNodeOutputs(
  meta: NodeMetadata | null | undefined,
  params: Record<string, unknown> = {},
): ResolvedNodeOutput[] {
  if (!meta) return [];
  const dynamicConfig = findDynamicOutputSpec(meta);
  if (!dynamicConfig) return staticNodeOutputs(meta);

  const { dynamic, spec } = dynamicConfig;
  const countSpec = getInputSpec(meta, dynamic.count_input) || spec;
  const rawCount = Object.prototype.hasOwnProperty.call(params, dynamic.count_input)
    ? params[dynamic.count_input]
    : countSpec.default;
  let count = integerParam(rawCount);
  if (count === null) return staticNodeOutputs(meta);
  if (typeof countSpec.min === 'number') count = Math.max(countSpec.min, count);
  if (typeof countSpec.max === 'number') count = Math.min(countSpec.max, count);
  count = Math.max(0, count);

  const prefix = dynamic.prefix ?? 'output_';
  const outputType = dynamic.type ?? meta.return_types?.[0] ?? 'ANY';
  const outputs = Array.from({ length: count }, (_, index) => ({
    name: `${prefix}${index + 1}`,
    type: outputType,
  }));
  if (dynamic.default_output) {
    outputs.push({ name: dynamic.default_output, type: outputType });
  }
  return outputs;
}
