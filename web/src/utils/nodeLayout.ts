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
  if (s.type === 'BOOLEAN') return true;
  if (Array.isArray(s.options) && s.options.length > 0) return true;
  if (s.type === 'INT' || s.type === 'FLOAT') return true;
  if (s.type === 'STRING' && !s.forceInput) return true;
  return false;
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
    .filter((entry): entry is [string, InputSpec] => isInteractiveWidgetSpec(entry[1]))
    .map(([key, spec]) => ({ key, spec }));
}

