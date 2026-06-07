// Auto-naming heuristic for workflows.
//
// When a workflow is untitled (or empty), look at the dominant tools and
// categories in the node graph to produce a short, recognisable name such as
// BWA plus samtools alignment instead of forcing the user to think one up.
// Used by Save / Save-as / template-save flows that need a default; callers
// remain free to override.

import i18n from '../i18n';
import type { Workflow, WorkflowNode } from '../types';

const UNTITLED = new Set(['', 'untitled', 'untitled workflow', 'new workflow']);

function tally(nodes: WorkflowNode[]): { tools: Map<string, number>; categories: Map<string, number> } {
  const tools = new Map<string, number>();
  const categories = new Map<string, number>();
  for (const node of nodes) {
    if (node.type === 'reroute' || node.type === 'note') continue;
    const meta = node.node_info;
    for (const tool of meta?.requires_external_tools || []) {
      tools.set(tool, (tools.get(tool) ?? 0) + 1);
    }
    const category = meta?.category;
    if (category) categories.set(category, (categories.get(category) ?? 0) + 1);
  }
  return { tools, categories };
}

function topKeys<T>(map: Map<T, number>, n: number): T[] {
  return Array.from(map.entries()).sort(([, a], [, b]) => b - a).slice(0, n).map(([k]) => k);
}

function translatedCategoryName(category: string): string {
  const translated = i18n.t(`workflowNaming.categories.${category}`);
  return translated === `workflowNaming.categories.${category}`
    ? category.toLowerCase()
    : String(translated);
}

/**
 * Pick a name for a workflow based on the tools / categories used. Returns
 * an empty string when the workflow has no useful signal (e.g. only notes).
 */
export function suggestWorkflowName(workflow: Workflow): string {
  const nodes = workflow.nodes || [];
  if (nodes.length === 0) return '';
  const { tools, categories } = tally(nodes);
  const topTools = topKeys(tools, 2);
  const topCategory = topKeys(categories, 1)[0];
  const verb = topCategory ? translatedCategoryName(topCategory) : i18n.t('workflowNaming.fallbackCategory');

  if (topTools.length === 0) {
    return topCategory ? i18n.t('workflowNaming.categoryWorkflow', { category: translatedCategoryName(topCategory) }) : '';
  }
  if (topTools.length === 1) {
    return `${topTools[0]} ${verb}`.replace(/\s+/g, ' ').trim();
  }
  return `${topTools.join(' + ')} ${verb}`.replace(/\s+/g, ' ').trim();
}

/**
 * Return a suggestion when the workflow's current name reads as "untitled",
 * otherwise return the existing name unchanged so callers can use this as a
 * "default" without overriding a deliberate user choice.
 */
export function resolveWorkflowName(workflow: Workflow): string {
  const current = (workflow.name || '').trim();
  if (current && !UNTITLED.has(current.toLowerCase())) return current;
  const suggested = suggestWorkflowName(workflow);
  return suggested || current || i18n.t('workflowNaming.untitledWorkflow');
}
