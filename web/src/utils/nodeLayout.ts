import type { InputSpec, NodeMetadata } from '../types';
import { getVisibleInputSpecs } from './nodeInputVisibility';
import { resolveNodeOutputs } from './nodeOutputs';

export const NODE_HEADER_H = 32;
export const NODE_PIN_H = 22;
export const NODE_WIDGET_ROW_H = 24;
export const NODE_WIDGET_TOP_PAD = 6;
export const NODE_WIDGET_BOTTOM_PAD = 12;

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

export function getInteractiveWidgetEntries(
  meta: NodeMetadata | null | undefined,
  params: Record<string, unknown> = {},
): WidgetEntry[] {
  const visibleInputs = getVisibleInputSpecs(meta, params);
  return Object.entries({ ...visibleInputs.required, ...visibleInputs.optional })
    .filter((entry): entry is [string, InputSpec] => isInteractiveWidgetSpec(entry[1]))
    .map(([key, spec]) => ({ key, spec }));
}

export function getWidgetBlockTop(inputCount: number, outputCount: number): number {
  return NODE_HEADER_H + Math.max(inputCount, outputCount, 1) * NODE_PIN_H + NODE_WIDGET_TOP_PAD;
}

export function calcRegularNodeHeight(
  meta: NodeMetadata | null,
  params: Record<string, unknown> = {},
): number {
  const visibleInputs = getVisibleInputSpecs(meta, params);
  const ins = Object.keys(visibleInputs.required).length + Object.keys(visibleInputs.optional).length;
  const outs = resolveNodeOutputs(meta, params).length;
  const widgetCount = getInteractiveWidgetEntries(meta, params).length;
  const ioHeight = Math.max(ins, outs, 1) * NODE_PIN_H;
  const widgetHeight = widgetCount > 0
    ? NODE_WIDGET_TOP_PAD + widgetCount * NODE_WIDGET_ROW_H + NODE_WIDGET_BOTTOM_PAD
    : 0;
  const visibleParamCount = Object.keys(params || {}).filter(key => key !== 'text').length;
  const summaryHeight = widgetCount === 0 && visibleParamCount > 0 ? Math.min(3, visibleParamCount) * 15 + 10 : 0;
  const descriptionHeight = widgetCount === 0 && visibleParamCount === 0 && meta?.description ? 28 : 0;
  return NODE_HEADER_H + ioHeight + widgetHeight + summaryHeight + descriptionHeight + 12;
}
