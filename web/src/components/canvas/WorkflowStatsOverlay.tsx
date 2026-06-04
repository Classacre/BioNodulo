// Combined bottom-left overlay: workflow shape stats (nodes / edges /
// categories) AND live system stats (CPU / RAM / GPU / VRAM / temps). These
// used to live in two separate cards that stacked on top of each other in
// the bottom-left corner; merging them avoids the overlap and lets the
// collapsed pill carry both signals at a glance.
//
// Workflow numbers are always present once the user starts building; the
// system block fills in once the backend `/system_stats` poll succeeds. If
// the backend is offline the system half just disappears (no error noise).

import { useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import type { Workflow } from '../../types';
import { apiGet } from '../../api/client';

interface SystemStats {
  system: {
    os: string;
    cpu_count: number;
    cpu_percent: number;
    cpu_temp_c: number | null;
    ram_total: number;
    ram_used: number;
    ram_free: number;
    ram_percent: number;
  };
  devices: Array<{
    index: number;
    name: string;
    type: string;
    vram_total: number;
    vram_used: number;
    vram_free: number;
    gpu_utilization: number;
    temperature_c: number | null;
  }>;
}

interface WorkflowStatsOverlayProps {
  workflow: Workflow;
  /** Hidden when focus mode is on; the workflow tabs row already shows the name. */
  hidden?: boolean;
}

interface CategoryBucket { label: string; count: number }

function summarise(workflow: Workflow, categoryFallback: string): { nodes: number; edges: number; groups: number; categories: CategoryBucket[] } {
  const nodes = workflow.nodes || [];
  const edges = workflow.edges || [];
  const groups = workflow.groups || [];
  const byCategory = new Map<string, number>();
  for (const node of nodes) {
    if (node.type === 'reroute' || node.type === 'note') continue;
    const label = node.node_info?.category || categoryFallback;
    byCategory.set(label, (byCategory.get(label) ?? 0) + 1);
  }
  const categories = Array.from(byCategory.entries())
    .map(([label, count]) => ({ label, count }))
    .sort((a, b) => b.count - a.count)
    .slice(0, 4);
  // Notes/reroutes are visual-only — exclude them from the headline count so
  // adding a sticky note doesn't bump the "node" number the user reads.
  const realNodeCount = nodes.filter(n => n.type !== 'note' && n.type !== 'reroute').length;
  return { nodes: realNodeCount, edges: edges.length, groups: groups.length, categories };
}

function formatBytes(bytes: number): string {
  const gb = bytes / (1024 * 1024 * 1024);
  if (gb >= 1) return `${gb.toFixed(1)} GB`;
  const mb = bytes / (1024 * 1024);
  return `${mb.toFixed(0)} MB`;
}

function Bar({ value, color, label }: { value: number; color: string; label: string }) {
  const pct = Math.min(100, Math.max(0, value));
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 10 }}>
      <span style={{ width: 30, textAlign: 'right', color: 'var(--muted)' }}>{label}</span>
      <div style={{ flex: 1, height: 4, background: 'var(--surface-3, rgba(127,127,127,0.18))', borderRadius: 2, overflow: 'hidden' }}>
        <div style={{ width: `${pct}%`, height: '100%', background: color, borderRadius: 2, transition: 'width 0.5s ease' }} />
      </div>
      <span style={{ width: 30, textAlign: 'right', fontVariantNumeric: 'tabular-nums' }}>{pct.toFixed(0)}%</span>
    </div>
  );
}

function tempColor(c: number, warn: number, danger: number): string {
  if (c >= danger) return 'var(--danger)';
  if (c >= warn) return 'var(--warning)';
  return 'var(--success)';
}

export default function WorkflowStatsOverlay({ workflow, hidden }: WorkflowStatsOverlayProps) {
  const { t } = useTranslation();
  const [collapsed, setCollapsed] = useState(false);
  const stats = useMemo(() => summarise(workflow, t('workflowStats.categoryFallback')), [workflow, t]);

  // Live system stats. Polled at 2 s on a single shared interval, regardless
  // of whether the card is collapsed (the pill needs CPU / RAM numbers too).
  const [system, setSystem] = useState<SystemStats | null>(null);
  const [systemErrored, setSystemErrored] = useState(false);

  useEffect(() => {
    let active = true;
    const fetchStats = async () => {
      try {
        const data = await apiGet<SystemStats>('/system_stats');
        if (!active) return;
        setSystem(data);
        setSystemErrored(false);
      } catch {
        if (!active) return;
        setSystemErrored(true);
      }
    };
    fetchStats();
    const id = window.setInterval(fetchStats, 2000);
    return () => {
      active = false;
      window.clearInterval(id);
    };
  }, []);

  if (hidden) return null;

  const sys = system?.system;
  const gpu = system?.devices?.[0];

  // Don't render an empty pill — wait until the user has at least one node OR
  // we have backend system stats to show.
  if (stats.nodes === 0 && !sys) return null;

  if (collapsed) {
    const sysSummary = sys
      ? ` - ${sys.cpu_percent.toFixed(0)}% ${t('workflowStats.cpuLabel')} - ${sys.ram_percent.toFixed(0)}% ${t('workflowStats.ramLabel')}`
      : '';
    return (
      <button
        type="button"
        className="workflow-stats-overlay workflow-stats-pill"
        onClick={() => setCollapsed(false)}
        title={t('workflowStats.expandTitle')}
      >
        {stats.nodes}{t('workflowStats.compactNodeSuffix')} - {stats.edges}{t('workflowStats.compactEdgeSuffix')}{sysSummary}
      </button>
    );
  }

  return (
    <div className="workflow-stats-overlay" role="status" aria-live="polite" style={{ opacity: systemErrored && !sys ? 0.85 : 1 }}>
      <button
        type="button"
        className="workflow-stats-collapse"
        onClick={() => setCollapsed(true)}
        aria-label={t('workflowStats.collapseAria')}
        title={t('workflowStats.collapseTitle')}
      >
        −
      </button>

      {/* Workflow shape */}
      {stats.nodes > 0 && (
        <>
          <div className="workflow-stats-row">
            <span className="workflow-stats-count">{stats.nodes}</span>
            <span className="workflow-stats-label">{t('workflowStats.nodesLabel')}</span>
            <span className="workflow-stats-count">{stats.edges}</span>
            <span className="workflow-stats-label">{t('workflowStats.edgesLabel')}</span>
            {stats.groups > 0 && (
              <>
                <span className="workflow-stats-count">{stats.groups}</span>
                <span className="workflow-stats-label">{t('workflowStats.groupsLabel')}</span>
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
        </>
      )}

      {/* System block — only renders when the backend is reachable. */}
      {sys && (
        <div
          style={{
            display: 'flex',
            flexDirection: 'column',
            gap: 4,
            paddingTop: stats.nodes > 0 ? 6 : 0,
            borderTop: stats.nodes > 0 ? '1px solid var(--border)' : undefined,
          }}
        >
          <Bar value={sys.cpu_percent} color="#3b82f6" label={t('workflowStats.cpuLabel')} />
          {sys.cpu_temp_c !== null && sys.cpu_temp_c !== undefined && (
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 10 }}>
              <span style={{ width: 30, textAlign: 'right', color: 'var(--muted)' }}>{t('workflowStats.tempLabel')}</span>
              <span style={{ color: tempColor(sys.cpu_temp_c, 65, 80) }}>
                {sys.cpu_temp_c.toFixed(0)}°C
              </span>
            </div>
          )}
          <Bar value={sys.ram_percent} color="#8b5cf6" label={t('workflowStats.ramLabel')} />
          <div style={{ fontSize: 9, color: 'var(--muted)', textAlign: 'right' }}>
            {formatBytes(sys.ram_used)} / {formatBytes(sys.ram_total)}
          </div>

          {gpu && (
            <>
              <div style={{ fontWeight: 500, fontSize: 10, color: 'var(--muted)', marginTop: 4 }}>{gpu.name}</div>
              <Bar value={gpu.gpu_utilization} color="#10b981" label={t('workflowStats.gpuLabel')} />
              <Bar value={(gpu.vram_used / Math.max(1, gpu.vram_total)) * 100} color="#f59e0b" label={t('workflowStats.vramLabel')} />
              {gpu.temperature_c !== null && gpu.temperature_c !== undefined && (
                <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 10 }}>
                  <span style={{ width: 30, textAlign: 'right', color: 'var(--muted)' }}>{t('workflowStats.tempLabel')}</span>
                  <span style={{ color: tempColor(gpu.temperature_c, 70, 80) }}>
                    {gpu.temperature_c.toFixed(0)}°C
                  </span>
                </div>
              )}
              <div style={{ fontSize: 9, color: 'var(--muted)', textAlign: 'right' }}>
                {formatBytes(gpu.vram_used)} / {formatBytes(gpu.vram_total)}
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}
