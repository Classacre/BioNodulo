// The dynamic island: a pill resting at the bottom-centre of the canvas.
//
// Three states:
//   min  — the pill. Workflow shape + system summary + status badges
//          (AI spinner, notification count). Default.
//   peek — a partial, event-driven expansion. Appears when something new
//          happens (an AI build stage advances, a toast arrives), shows the
//          newest content, and folds back to the pill after a few seconds
//          of quiet. Never opens on its own beyond this — the user stays in
//          control of the full panel.
//   full — the whole panel, only on click: AI build telemetry (stages,
//          model, token rate, reasoning stream when the backend provides
//          it), the live notification feed (toasts live here now, not in a
//          corner stack), and the workflow/system stats that used to sit at
//          the bottom-left.
//
// The morph between states is CSS-driven (`.island-*` classes in index.css):
// one absolutely-positioned container, bottom-centre, animating width,
// max-height and opacity with a snappy spring-ish curve.

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import type { TFunction } from 'i18next';
import type { Workflow } from '../../types';
import { apiGet } from '../../api/client';
import { nodeCategoryDisplayLabel } from '../../utils/nodeCategories';
import {
  dismissNotification,
  useNotifications,
  type NotificationRecord,
} from '../../state/notifications';
import {
  SYSTEM_STATS_POLL_HIDDEN_MS,
  SYSTEM_STATS_POLL_VISIBLE_MS,
  startVisibilityAwarePolling,
} from '../../utils/pollingPolicy';

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

/** Live telemetry for an in-flight (or just-finished) AI workflow build. */
export interface DoiTelemetry {
  active: boolean;
  /** Completed stage lines, oldest first. */
  lines: string[];
  /** Sanitized model label currently answering (e.g. "glm-5.2"), or null. */
  model: string | null;
  /** Accumulated reasoning text from the model, when the backend streams it. */
  thinking: string;
  inputTokens: number;
  outputTokens: number;
  /** Epoch ms when the analysis call started (for tok/s), or null. */
  startedAt: number | null;
}

export const EMPTY_DOI_TELEMETRY: DoiTelemetry = {
  active: false,
  lines: [],
  model: null,
  thinking: '',
  inputTokens: 0,
  outputTokens: 0,
  startedAt: null,
};

interface DynamicIslandProps {
  workflow: Workflow;
  /** Hidden when focus mode is on; the workflow tabs row already shows the name. */
  hidden?: boolean;
  /**
   * Whether to poll `/system_stats`. Off in the cloud editor, where the only
   * machine behind the endpoint is the stateless Lambda — its CPU/RAM numbers
   * are meaningless and the 2 s poll is pure noise.
   */
  systemStats?: boolean;
  /** AI build telemetry; activity drives the peek state automatically. */
  doi?: DoiTelemetry;
}

type IslandMode = 'min' | 'peek' | 'full';

/** How long a peek stays open after the last event before folding back. */
const PEEK_QUIET_MS = 5000;
/** How long a finished AI build's result stays peeked before folding. */
const DONE_LINGER_MS = 8000;

interface CategoryBucket { label: string; count: number }

function summarise(workflow: Workflow, t: TFunction, categoryFallback: string): { nodes: number; edges: number; groups: number; categories: CategoryBucket[] } {
  const nodes = workflow.nodes || [];
  const edges = workflow.edges || [];
  const groups = workflow.groups || [];
  const byCategory = new Map<string, number>();
  for (const node of nodes) {
    if (node.type === 'reroute' || node.type === 'note') continue;
    const label = nodeCategoryDisplayLabel(node.node_info?.category, t, categoryFallback);
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

function formatBytes(bytes: number, t: TFunction, language: string): string {
  const integer = new Intl.NumberFormat(language, { maximumFractionDigits: 0 });
  const decimal = new Intl.NumberFormat(language, {
    maximumFractionDigits: 1,
    minimumFractionDigits: 1,
  });
  const gb = bytes / (1024 * 1024 * 1024);
  if (gb >= 1) return t('workflowStats.sizeGB', { size: decimal.format(gb) });
  const mb = bytes / (1024 * 1024);
  return t('workflowStats.sizeMB', { size: integer.format(mb) });
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

const TONE_MARK: Record<NotificationRecord['tone'], string> = {
  info: 'ℹ',
  success: '✓',
  warning: '⚠',
  error: '✕',
  loading: '◌',
};

function toneColor(tone: NotificationRecord['tone']): string {
  switch (tone) {
    case 'success': return 'var(--success)';
    case 'warning': return 'var(--warning)';
    case 'error': return 'var(--danger)';
    case 'loading': return 'var(--accent, #2dd4bf)';
    default: return 'var(--muted)';
  }
}

export default function DynamicIsland({ workflow, hidden, systemStats = true, doi }: DynamicIslandProps) {
  const { t, i18n } = useTranslation();
  const stats = useMemo(() => summarise(workflow, t, t('workflowStats.categoryFallback')), [workflow, t]);

  const doiActive = Boolean(doi?.active);
  const showDoi = Boolean(doi && (doi.active || doi.lines.length > 0));

  // --- notifications: the island is the toast surface now -------------------
  const notifications = useNotifications();

  // --- island state machine -------------------------------------------------
  const [mode, setMode] = useState<IslandMode>('min');
  const userPinnedRef = useRef(false);
  const quietTimerRef = useRef<number | null>(null);

  const armQuietTimer = useCallback((ms: number) => {
    if (quietTimerRef.current !== null) window.clearTimeout(quietTimerRef.current);
    quietTimerRef.current = window.setTimeout(() => {
      quietTimerRef.current = null;
      setMode((m) => (m === 'peek' ? 'min' : m));
    }, ms);
  }, []);
  useEffect(() => () => {
    if (quietTimerRef.current !== null) window.clearTimeout(quietTimerRef.current);
  }, []);

  // New AI stage lines drive the peek state (never the full panel).
  const lastLineCountRef = useRef(doi?.lines.length ?? 0);
  useEffect(() => {
    const count = doi?.lines.length ?? 0;
    const grew = count > lastLineCountRef.current;
    lastLineCountRef.current = count;
    if (!grew) return;
    if (userPinnedRef.current) return; // the user chose a state; don't fight them
    setMode('peek');
    armQuietTimer(doiActive ? PEEK_QUIET_MS : DONE_LINGER_MS);
  }, [doi?.lines.length, doiActive, armQuietTimer]);

  // A finished build lingers a beat, then folds.
  useEffect(() => {
    if (doiActive || !doi || doi.lines.length === 0) return;
    if (userPinnedRef.current) return;
    armQuietTimer(DONE_LINGER_MS);
    return () => {
      if (quietTimerRef.current !== null) window.clearTimeout(quietTimerRef.current);
    };
  }, [doiActive, doi, armQuietTimer]);

  // New toasts peek too.
  const lastNotifIdsRef = useRef<Set<string>>(new Set());
  useEffect(() => {
    const current = new Set(notifications.map((n) => n.id));
    const fresh = notifications.find((n) => !lastNotifIdsRef.current.has(n.id));
    lastNotifIdsRef.current = current;
    if (!fresh || userPinnedRef.current || doiActive) return; // AI activity wins the peek slot
    setMode((m) => (m === 'min' ? 'peek' : m));
    armQuietTimer(PEEK_QUIET_MS);
  }, [notifications, doiActive, armQuietTimer]);

  const expand = useCallback(() => {
    userPinnedRef.current = true;
    if (quietTimerRef.current !== null) window.clearTimeout(quietTimerRef.current);
    setMode('full');
  }, []);
  const collapse = useCallback(() => {
    userPinnedRef.current = true;
    setMode('min');
  }, []);

  // Escape folds a full panel.
  useEffect(() => {
    if (mode !== 'full') return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') collapse();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [mode, collapse]);

  // --- live system stats ----------------------------------------------------
  const [system, setSystem] = useState<SystemStats | null>(null);
  const [systemErrored, setSystemErrored] = useState(false);

  useEffect(() => {
    if (!systemStats) {
      setSystem(null);
      setSystemErrored(false);
      return;
    }
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
    const stopPolling = startVisibilityAwarePolling(
      fetchStats,
      SYSTEM_STATS_POLL_VISIBLE_MS,
      SYSTEM_STATS_POLL_HIDDEN_MS,
    );
    return () => {
      active = false;
      stopPolling();
    };
  }, [systemStats]);

  // Token rate needs a ticking clock while the build is active.
  const [, setTick] = useState(0);
  useEffect(() => {
    if (!doiActive) return;
    const timer = setInterval(() => setTick((n) => n + 1), 500);
    return () => clearInterval(timer);
  }, [doiActive]);

  // Auto-scroll the thinking log as reasoning streams in.
  const thinkingRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const el = thinkingRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [doi?.thinking, mode]);

  if (hidden) return null;

  const sys = system?.system;
  const gpu = system?.devices?.[0];

  // Don't render an empty pill — wait until there is anything to show.
  if (stats.nodes === 0 && !sys && !showDoi && notifications.length === 0) return null;

  const tps =
    doi?.startedAt && doi.outputTokens > 0
      ? doi.outputTokens / Math.max(0.5, (Date.now() - doi.startedAt) / 1000)
      : null;

  const lastLine = doi && doi.lines.length > 0 ? doi.lines[doi.lines.length - 1] : '';
  const latestNotification = notifications.length > 0 ? notifications[notifications.length - 1] : null;

  // --- min / peek share the pill chrome; full is the panel ------------------
  if (mode !== 'full') {
    const sysSummary = sys
      ? ` · ${sys.cpu_percent.toFixed(0)}% ${t('workflowStats.cpuLabel')} · ${sys.ram_percent.toFixed(0)}% ${t('workflowStats.ramLabel')}`
      : '';
    return (
      <div className={`island island-${mode}`} role="status" aria-live="polite">
        <button
          type="button"
          className="island-pill"
          onClick={expand}
          title={t('island.expandTitle', { defaultValue: 'Expand' })}
          aria-expanded={false}
        >
          {doiActive && <span className="island-spinner" aria-hidden />}
          <span className="island-stats">
            {stats.nodes}{t('workflowStats.compactNodeSuffix')} · {stats.edges}{t('workflowStats.compactEdgeSuffix')}{sysSummary}
          </span>
          {notifications.length > 0 && (
            <span className="island-badge" title={t('island.notificationsTitle', { defaultValue: 'Notifications' })}>
              {notifications.length > 9 ? '9+' : notifications.length}
            </span>
          )}
        </button>
        {mode === 'peek' && (
          <button type="button" className="island-peek" onClick={expand}>
            {showDoi ? (
              <>
                <span className="island-peek-title">
                  {doiActive
                    ? t('doiFlow.islandTitleActive', { defaultValue: 'Building from paper' })
                    : t('doiFlow.islandTitleDone', { defaultValue: 'Built from paper' })}
                </span>
                {doi?.model && <span className="island-chip">{doi.model}</span>}
                <span className="island-peek-line">{lastLine || t('doiFlow.islandWorking', { defaultValue: 'Working…' })}</span>
              </>
            ) : latestNotification ? (
              <>
                <span className="island-peek-title" style={{ color: toneColor(latestNotification.tone) }}>
                  {TONE_MARK[latestNotification.tone]} {latestNotification.title}
                </span>
                {latestNotification.message && (
                  <span className="island-peek-line">{latestNotification.message}</span>
                )}
                {latestNotification.progress !== null && (
                  <span className="island-peek-progress">
                    <span style={{ width: `${Math.min(100, Math.max(0, latestNotification.progress))}%` }} />
                  </span>
                )}
              </>
            ) : null}
          </button>
        )}
      </div>
    );
  }

  return (
    <div className="island island-full" role="status" aria-live="polite" style={{ opacity: systemErrored && !sys ? 0.85 : 1 }}>
      <button
        type="button"
        className="workflow-stats-collapse"
        onClick={collapse}
        aria-label={t('workflowStats.collapseAria')}
        title={t('workflowStats.collapseTitle')}
      >
        −
      </button>

      {/* AI build telemetry */}
      {showDoi && doi && (
        <div className="workflow-stats-doi">
          <div className="workflow-stats-doi-header">
            <span className="workflow-stats-doi-title">
              {doiActive
                ? t('doiFlow.islandTitleActive', { defaultValue: 'Building from paper' })
                : t('doiFlow.islandTitleDone', { defaultValue: 'Built from paper' })}
            </span>
            {doi.model && <span className="workflow-stats-chip">{doi.model}</span>}
            {(doi.outputTokens > 0 || doi.inputTokens > 0) && (
              <span className="workflow-stats-chip">
                {doi.outputTokens.toLocaleString()} tok
                {tps ? ` · ${tps.toFixed(0)} tok/s` : ''}
              </span>
            )}
          </div>
          <div className="workflow-stats-doi-lines">
            {doi.lines.map((line, i) => {
              const isLast = i === doi.lines.length - 1;
              return (
                <div key={`${i}-${line}`} className="workflow-stats-doi-row" style={{ opacity: isLast && doiActive ? 1 : 0.55 }}>
                  <span className="workflow-stats-doi-mark">{isLast && doiActive ? '●' : '✓'}</span>
                  <span>{line}</span>
                </div>
              );
            })}
          </div>
          {doi.thinking && (
            <div className="workflow-stats-thinking" ref={thinkingRef}>
              {doi.thinking}
            </div>
          )}
        </div>
      )}

      {/* Notifications — the island is the toast surface */}
      {notifications.length > 0 && (
        <div className="island-notifications">
          <div className="island-section-title">{t('island.notificationsTitle', { defaultValue: 'Notifications' })}</div>
          {notifications.slice(-6).reverse().map((n) => (
            <div key={n.id} className="island-notification" data-tone={n.tone}>
              <span className="island-notification-mark" style={{ color: toneColor(n.tone) }}>
                {TONE_MARK[n.tone]}
              </span>
              <div className="island-notification-body">
                <div className="island-notification-title">{n.title}</div>
                {n.message && <div className="island-notification-message">{n.message}</div>}
                {n.progress !== null && (
                  <div className="island-peek-progress island-notification-progress">
                    <span style={{ width: `${Math.min(100, Math.max(0, n.progress))}%` }} />
                  </div>
                )}
                {n.actions.length > 0 && (
                  <div className="island-notification-actions">
                    {n.actions.map((a) => (
                      <button
                        key={a.label}
                        type="button"
                        onClick={() => a.onClick(n.id)}
                      >
                        {a.label}
                      </button>
                    ))}
                  </div>
                )}
              </div>
              {n.dismissible && (
                <button
                  type="button"
                  className="island-notification-dismiss"
                  onClick={() => dismissNotification(n.id)}
                  aria-label={t('island.dismissAria', { defaultValue: 'Dismiss' })}
                >
                  ×
                </button>
              )}
            </div>
          ))}
        </div>
      )}

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
            paddingTop: stats.nodes > 0 || showDoi || notifications.length > 0 ? 6 : 0,
            borderTop: stats.nodes > 0 || showDoi || notifications.length > 0 ? '1px solid var(--border)' : undefined,
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
            {formatBytes(sys.ram_used, t, i18n.language)} / {formatBytes(sys.ram_total, t, i18n.language)}
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
                {formatBytes(gpu.vram_used, t, i18n.language)} / {formatBytes(gpu.vram_total, t, i18n.language)}
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}
