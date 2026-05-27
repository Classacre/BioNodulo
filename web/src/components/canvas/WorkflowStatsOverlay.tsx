// Compact bottom-left overlay showing high-signal workflow shape stats
// (node, edge, group counts + breakdown by node category). The numbers are
// always present once you start building, so unlike the hardware monitor
// this overlay isn't gated behind a setting — but it collapses on click
// to a single pill so it doesn't fight the canvas for real estate.

import { useMemo, useState } from 'react';
import type { Workflow } from '../../types';

interface WorkflowStatsOverlayProps {
  workflow: Workflow;
  /** Hidden when focus mode is on; the workflow tabs row already shows the name. */
  hidden?: boolean;
}

interface CategoryBucket { label: string; count: number }

function summarise(workflow: Workflow): { nodes: number; edges: number; groups: number; categories: CategoryBucket[] } {
  const nodes = workflow.nodes || [];
  const edges = workflow.edges || [];
  const groups = workflow.groups || [];
  const byCategory = new Map<string, number>();
  for (const node of nodes) {
    if (node.type === 'reroute' || node.type === 'note') continue;
    const label = node.node_info?.category || 'Other';
    byCategory.set(label, (byCategory.get(label) ?? 0) + 1);
  }
  const categories = Array.from(byCategory.entries())
    .map(([label, count]) => ({ label, count }))
    .sort((a, b) => b.count - a.count)
    .slice(0, 4);
  return { nodes: nodes.length, edges: edges.length, groups: groups.length, categories };
}

export default function WorkflowStatsOverlay({ workflow, hidden }: WorkflowStatsOverlayProps) {
  const [collapsed, setCollapsed] = useState(false);
  const stats = useMemo(() => summarise(workflow), [workflow]);
  if (hidden) return null;
  if (stats.nodes === 0) return null;

  if (collapsed) {
    return (
      <button
        type="button"
        className="workflow-stats-overlay workflow-stats-pill"
        onClick={() => setCollapsed(false)}
        title="Expand workflow stats"
      >
        {stats.nodes}n · {stats.edges}e
      </button>
    );
  }

  return (
    <div className="workflow-stats-overlay" role="status" aria-live="polite">
      <button
        type="button"
        className="workflow-stats-collapse"
        onClick={() => setCollapsed(true)}
        aria-label="Collapse workflow stats"
        title="Collapse"
      >
        −
      </button>
      <div className="workflow-stats-row">
        <span className="workflow-stats-count">{stats.nodes}</span>
        <span className="workflow-stats-label">nodes</span>
        <span className="workflow-stats-count">{stats.edges}</span>
        <span className="workflow-stats-label">edges</span>
        {stats.groups > 0 && (
          <>
            <span className="workflow-stats-count">{stats.groups}</span>
            <span className="workflow-stats-label">groups</span>
          </>
        )}
      </div>
      {stats.categories.length > 0 && (
        <div className="workflow-stats-categories">
          {stats.categories.map(bucket => (
            <span key={bucket.label} className="workflow-stats-cat">
              <span className="workflow-stats-cat-label">{bucket.label}</span>
              <span className="workflow-stats-cat-count">{bucket.count}</span>
            </span>
          ))}
        </div>
      )}
    </div>
  );
}
