import type { InputSpec, NodeMetadata } from '../types';
import { getVisibleInputSpecs } from './nodeInputVisibility';

export const NODE_HEADER_H = 32;
export const NODE_PIN_H = 22;

export interface WidgetEntry {
  key: string;
  spec: InputSpec;
}

export function isInteractiveWidgetSpec(spec: unknown): spec is InputSpec {
  const s = spec as InputSpec | null | undefined;
  if (!s) return false;
  // forceInput/link params are always ports, never on-node widgets.
  if (s.forceInput || s.link) return false;
  if (s.type === 'BOOLEAN') return true;
  if (Array.isArray(s.options) && s.options.length > 0) return true;
  if (s.type === 'INT' || s.type === 'FLOAT') return true;
  if (s.type === 'JSON') return true;
  if (s.type === 'STRING') return true;
  return false;
}

export function formatJsonWidgetValue(value: unknown): string {
  if (typeof value === 'string') return value;
  if (value === undefined) return '';
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return '';
  }
}

export function parseJsonWidgetValue(value: string): unknown {
  return JSON.parse(value);
}

export function parseNumericWidgetValue(value: string, type: string): number | undefined {
  if (!value.trim()) return undefined;
  const number = Number(value);
  if (!Number.isFinite(number)) return undefined;
  return type === 'INT' ? Math.round(number) : number;
}

/**
 * Input File is a source node: users must be able to type/paste its path even
 * though `file` remains a FILE port so workspace drops and graph links work.
 * Keep this exception narrow; ordinary FILE inputs should be supplied by an
 * upstream node rather than a competing stale text parameter.
 */
export function isInlineFileValueSpec(
  meta: NodeMetadata | null | undefined,
  key: string,
  spec: unknown,
): spec is InputSpec {
  const input = spec as InputSpec | null | undefined;
  return meta?.id === 'input_file' && key === 'file' && input?.type === 'FILE';
}

/**
 * A STRING param is treated as a colour when the backend marks it
 * (`display: 'color'`) or its key reads like a colour (e.g. `color`,
 * `up_color`, `border_colour`). Such params get a swatch + native colour
 * picker instead of a plain text box.
 */
export function isColorParam(key: string, spec: unknown): boolean {
  const s = spec as InputSpec | null | undefined;
  if (!s || s.type !== 'STRING' || s.forceInput) return false;
  if (Array.isArray(s.options) && s.options.length > 0) return false;
  if (s.display === 'color') return true;
  return /colou?r$/i.test(key);
}

/** Coerce a stored colour value (named or hex) into a `#rrggbb` the picker accepts. */
export function toHexColor(value: unknown): string {
  const raw = String(value ?? '').trim();
  if (/^#[0-9a-fA-F]{6}$/.test(raw)) return raw.toLowerCase();
  if (/^#[0-9a-fA-F]{3}$/.test(raw)) {
    const r = raw[1], g = raw[2], b = raw[3];
    return `#${r}${r}${g}${g}${b}${b}`.toLowerCase();
  }
  return NAMED_COLORS[raw.toLowerCase()] ?? '#4682b4'; // steelblue default
}

// Minimal named-colour map covering the defaults used by the chart nodes.
const NAMED_COLORS: Record<string, string> = {
  steelblue: '#4682b4', red: '#ff0000', green: '#008000', blue: '#0000ff',
  black: '#000000', white: '#ffffff', gray: '#808080', grey: '#808080',
  orange: '#ffa500', purple: '#800080', teal: '#008080', navy: '#000080',
  firebrick: '#b22222', forestgreen: '#228b22', goldenrod: '#daa520',
  tomato: '#ff6347', slategray: '#708090', darkblue: '#00008b',
};

export function getInteractiveWidgetEntries(
  meta: NodeMetadata | null | undefined,
  params: Record<string, unknown> = {},
): WidgetEntry[] {
  const visibleInputs = getVisibleInputSpecs(meta, params);
  return Object.entries({ ...visibleInputs.required, ...visibleInputs.optional })
    .filter((entry): entry is [string, InputSpec] =>
      isInteractiveWidgetSpec(entry[1]) || isInlineFileValueSpec(meta, entry[0], entry[1]))
    .map(([key, spec]) => ({ key, spec }));
}

/**
 * Param keys that CAN be given an input dot ("Add input") — i.e. the scalar
 * params that render as on-node widgets. `forceInput`/`link` params are already
 * ports and never appear here.
 */
export function getPromotableParamKeys(
  meta: NodeMetadata | null | undefined,
  params: Record<string, unknown> = {},
): string[] {
  const visibleInputs = getVisibleInputSpecs(meta, params);
  return Object.entries({ ...visibleInputs.required, ...visibleInputs.optional })
    .filter((entry): entry is [string, InputSpec] => isInteractiveWidgetSpec(entry[1]))
    .map(([key]) => key);
}
