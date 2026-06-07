import type { InputSpec, NodeMetadata } from '../types';

export interface VisibleInputSpecs {
  required: Record<string, InputSpec>;
  optional: Record<string, InputSpec>;
}

function inputDefault(meta: NodeMetadata | null | undefined, key: string): unknown {
  return (
    meta?.input_types?.required?.[key]?.default
    ?? meta?.input_types?.optional?.[key]?.default
    ?? meta?.input_types?.hidden?.[key]?.default
  );
}

function effectiveParamValue(
  key: string,
  meta: NodeMetadata | null | undefined,
  params: Record<string, unknown>,
): unknown {
  return Object.prototype.hasOwnProperty.call(params, key) ? params[key] : inputDefault(meta, key);
}

function valueMatches(actual: unknown, expected: unknown): boolean {
  if (Object.is(actual, expected)) return true;
  if (actual === null || actual === undefined || expected === null || expected === undefined) return false;
  return String(actual) === String(expected);
}

export function isNodeInputVisible(
  _name: string,
  spec: InputSpec | undefined,
  meta: NodeMetadata | null | undefined,
  params: Record<string, unknown> = {},
): boolean {
  const show = spec?.displayOptions?.show;
  if (!show || Object.keys(show).length === 0) return true;

  return Object.entries(show).every(([controller, expected]) => {
    const actual = effectiveParamValue(controller, meta, params);
    const expectedValues = Array.isArray(expected) ? expected : [expected];
    return expectedValues.some(value => valueMatches(actual, value));
  });
}

function visibleSection(
  section: Record<string, InputSpec> | undefined,
  meta: NodeMetadata | null | undefined,
  params: Record<string, unknown>,
): Record<string, InputSpec> {
  if (!section) return {};
  return Object.fromEntries(
    Object.entries(section).filter(([name, spec]) => isNodeInputVisible(name, spec, meta, params)),
  );
}

export function getVisibleInputSpecs(
  meta: NodeMetadata | null | undefined,
  params: Record<string, unknown> = {},
): VisibleInputSpecs {
  return {
    required: visibleSection(meta?.input_types?.required, meta, params),
    optional: visibleSection(meta?.input_types?.optional, meta, params),
  };
}
