import { useMemo, useState } from 'react';
import { useAtomValue, useSetAtom } from 'jotai';
import { useTranslation } from 'react-i18next';
import type { TFunction } from 'i18next';
import type { RunRecord, NodeStatus } from '../../types';
import { batchCountAtom } from '../../state/runAtoms';
import { showOutputDiffAtom } from '../../state/uiAtoms';
import Icon from '../ui/Icon';

type RunStatusFilter = 'all' | 'active' | 'completed' | 'error' | 'cancelled';
type HistoryBucketId = 'today' | 'yesterday' | 'pastWeek' | 'earlier' | `month:${number}` | `year:${number}`;
export type QueueMoveDirection = 'up' | 'down';

interface HistoryBucket {
  id: HistoryBucketId;
  runs: RunRecord[];
}

interface RunsDrawerProps {
  open: boolean;
  queue: RunRecord[];
  history: RunRecord[];
  onClose: () => void;
  onCancelRun?: (run: RunRecord) => void;
  onRetryRun?: (run: RunRecord) => void;
  onLoadRunWorkflow?: (run: RunRecord) => void;
  onDeleteHistoryEntry?: (run: RunRecord) => void;
  onMoveRun?: (run: RunRecord, direction: QueueMoveDirection) => void;
  onClearQueue?: () => void;
  onClearHistory?: () => void;
}

function runStatusLabel(t: TFunction, status: RunRecord['status'] | 'failed'): string {
  return t(`console.status.${status}`, { defaultValue: status });
}

function filterLabel(t: TFunction, filter: RunStatusFilter): string {
  return t(`runsDrawer.filters.${filter}`);
}

function historyBucketLabel(t: TFunction, id: HistoryBucketId, locale?: string): string {
  switch (id) {
    case 'today':
      return t('common.today');
    case 'yesterday':
      return t('common.yesterday');
    case 'pastWeek':
      return t('console.bucketPastWeek');
    case 'earlier':
      return t('console.bucketEarlier');
  }
  if (id.startsWith('month:')) {
    const monthNumber = Number.parseInt(id.slice('month:'.length), 10);
    if (Number.isInteger(monthNumber) && monthNumber >= 1 && monthNumber <= 12) {
      return new Date(2000, monthNumber - 1, 1).toLocaleString(locale, { month: 'long' });
    }
  }
  if (id.startsWith('year:')) return id.slice('year:'.length);
  return id;
}

function runTimestamp(run: RunRecord): number {
  const value = run.end_time || run.start_time;
  if (!value) return 0;
  const parsed = Date.parse(value);
  return Number.isFinite(parsed) ? parsed : 0;
}

function bucketIdForRun(run: RunRecord, now: Date): HistoryBucketId {
  const ts = runTimestamp(run);
  if (!ts) return 'earlier';
  const runDate = new Date(ts);
  const todayStart = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
  const yesterdayStart = todayStart - 24 * 60 * 60 * 1000;
  const weekStart = todayStart - 6 * 24 * 60 * 60 * 1000;
  if (ts >= todayStart) return 'today';
  if (ts >= yesterdayStart) return 'yesterday';
  if (ts >= weekStart) return 'pastWeek';
  if (runDate.getFullYear() === now.getFullYear()) return `month:${runDate.getMonth() + 1}`;
  return `year:${runDate.getFullYear()}`;
}

function bucketHistory(history: RunRecord[]): HistoryBucket[] {
  const now = new Date();
  const order: HistoryBucketId[] = [];
  const groups = new Map<HistoryBucketId, RunRecord[]>();
  for (const run of history) {
    const id = bucketIdForRun(run, now);
    if (!groups.has(id)) {
      groups.set(id, []);
      order.push(id);
    }
    groups.get(id)!.push(run);
  }
  return order.map(id => ({ id, runs: groups.get(id)! }));
}

const COMPLETE_NODE_STATUSES = new Set<NodeStatus['status']>(['completed', 'cached', 'skipped']);

interface RunProgress {
  total: number;
  completed: number;
  running: number;
  pending: number;
  failed: number;
  percent: number;
}

function progressForRun(run: RunRecord): RunProgress {
  const statuses = Array.isArray(run.node_statuses) ? run.node_statuses : [];
  const total = Math.max(run.execution_plan?.length || 0, statuses.length);
  const completed = statuses.filter(node => COMPLETE_NODE_STATUSES.has(node.status)).length;
  const running = statuses.filter(node => node.status === 'running').length;
  const failed = statuses.filter(node => node.status === 'error').length;
  const pending = Math.max(0, total - completed - running - failed);

  let percent = total > 0 ? Math.round(((completed + running * 0.5) / total) * 100) : 0;
  if (run.status === 'completed') percent = 100;
  if (run.status === 'running' && total === 0) percent = 8;
  if (run.status === 'error' && total === 0) percent = 100;
  if (run.status === 'cancelled') percent = Math.max(percent, 5);

  return { total, completed, running, pending, failed, percent: Math.min(100, Math.max(0, percent)) };
}

function shortRunId(runId: string): string {
  return runId.length > 12 ? `${runId.slice(0, 8)}...${runId.slice(-4)}` : runId;
}

function RunProgressBar({ progress, status, t }: { progress: RunProgress; status: RunRecord['status']; t: TFunction }) {
  return (
    <div className={`queue-progress is-${status}`} title={t('console.progressComplete', { percent: progress.percent })}>
      <div className="queue-progress-fill" style={{ width: `${progress.percent}%` }} />
    </div>
  );
}

function RunActionButton({
  title,
  icon,
  onClick,
  disabled = false,
}: {
  title: string;
  icon: string;
  onClick: () => void;
  disabled?: boolean;
}) {
  return (
    <button
      className="btn btn-icon btn-sm queue-action-btn"
      type="button"
      title={title}
      aria-label={title}
      onClick={onClick}
      disabled={disabled}
    >
      <Icon name={icon} size={12} />
    </button>
  );
}

function QueueRunCard({
  run,
  index,
  totalRuns,
  onCancelRun,
  onRetryRun,
  onMoveRun,
  t,
}: {
  run: RunRecord;
  index: number;
  totalRuns: number;
  onCancelRun?: (run: RunRecord) => void;
  onRetryRun?: (run: RunRecord) => void;
  onMoveRun?: (run: RunRecord, direction: QueueMoveDirection) => void;
  t: TFunction;
}) {
  const progress = progressForRun(run);
  const canCancel = run.status === 'pending' || run.status === 'running';
  const canRetry = run.status === 'error' || run.status === 'cancelled';
  const canMove = run.status === 'pending';

  return (
    <div className={`queue-run-card is-${run.status}`}>
      <div className="queue-run-main">
        <div className="queue-run-title-row">
          <span className={`queue-status-pill is-${run.status}`}>{runStatusLabel(t, run.status)}</span>
          <strong className="queue-run-name">{run.workflow_name || t('console.untitledWorkflow')}</strong>
          <span className="queue-run-id" title={run.run_id}>{shortRunId(run.run_id)}</span>
        </div>
        <RunProgressBar progress={progress} status={run.status} t={t} />
        <div className="queue-run-meta">
          <span>{progress.total > 0 ? t('console.nodeProgress', { completed: progress.completed, total: progress.total }) : t('console.noNodePlan')}</span>
          {progress.running > 0 && <span>{t('console.runningCount', { count: progress.running })}</span>}
          {progress.pending > 0 && <span>{t('console.pendingCount', { count: progress.pending })}</span>}
          {progress.failed > 0 && <span className="queue-run-error">{t('console.failedCount', { count: progress.failed })}</span>}
        </div>
      </div>
      <div className="queue-run-actions">
        {onMoveRun && (
          <>
            <RunActionButton title={t('console.moveEarlier')} icon="chevronUp" onClick={() => onMoveRun(run, 'up')} disabled={!canMove || index === 0} />
            <RunActionButton title={t('console.moveLater')} icon="chevronDown" onClick={() => onMoveRun(run, 'down')} disabled={!canMove || index === totalRuns - 1} />
          </>
        )}
        {onRetryRun && canRetry && (
          <RunActionButton title={t('console.retryRun')} icon="play" onClick={() => onRetryRun(run)} />
        )}
        {onCancelRun && canCancel && (
          <RunActionButton title={t('console.cancelRun')} icon="stop" onClick={() => onCancelRun(run)} />
        )}
      </div>
    </div>
  );
}

function HistoryRunCard({ run, onRetryRun, onLoadRunWorkflow, onDeleteHistoryEntry, t, locale }: {
  run: RunRecord;
  onRetryRun?: (run: RunRecord) => void;
  onLoadRunWorkflow?: (run: RunRecord) => void;
  onDeleteHistoryEntry?: (run: RunRecord) => void;
  t: TFunction;
  locale?: string;
}) {
  const progress = progressForRun(run);
  const canRetry = run.status === 'error' || run.status === 'cancelled' || run.status === 'completed';
  return (
    <div className={`queue-run-card history-run-card is-${run.status}`}>
      <div className="queue-run-main">
        <div className="queue-run-title-row">
          <span className={`queue-status-pill is-${run.status}`}>{runStatusLabel(t, run.status)}</span>
          <strong className="queue-run-name">{run.workflow_name || t('console.untitledWorkflow')}</strong>
          <span className="queue-run-id" title={run.run_id}>{shortRunId(run.run_id)}</span>
        </div>
        <RunProgressBar progress={progress} status={run.status} t={t} />
        <div className="queue-run-meta">
          <span>{run.end_time ? new Date(run.end_time).toLocaleString(locale) : t('console.inProgress')}</span>
          <span>{progress.total > 0 ? t('console.nodeProgress', { completed: progress.completed, total: progress.total }) : t('console.noNodePlan')}</span>
        </div>
      </div>
      <div className="queue-run-actions">
        {onLoadRunWorkflow && (
          <RunActionButton
            title={t('console.loadWorkflow')}
            icon="import"
            onClick={() => onLoadRunWorkflow(run)}
          />
        )}
        {onRetryRun && canRetry && (
          <RunActionButton title={t('console.retryRun')} icon="play" onClick={() => onRetryRun(run)} />
        )}
        {onDeleteHistoryEntry && (
          <RunActionButton
            title={t('console.deleteHistoryRun')}
            icon="close"
            onClick={() => onDeleteHistoryEntry(run)}
          />
        )}
      </div>
    </div>
  );
}

function isActiveRun(run: RunRecord): boolean {
  return run.status === 'pending' || run.status === 'running';
}

export default function RunsDrawer({
  open,
  queue,
  history,
  onClose,
  onCancelRun,
  onRetryRun,
  onLoadRunWorkflow,
  onDeleteHistoryEntry,
  onMoveRun,
  onClearQueue,
  onClearHistory,
}: RunsDrawerProps) {
  const { t, i18n } = useTranslation();
  const batchCount = useAtomValue(batchCountAtom);
  const setShowOutputDiff = useSetAtom(showOutputDiffAtom);
  const [query, setQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState<RunStatusFilter>('all');
  const [collapsedHistoryBuckets, setCollapsedHistoryBuckets] = useState<Set<HistoryBucketId>>(new Set());

  const queueIds = useMemo(() => new Set(queue.map(run => run.run_id)), [queue]);
  const historicalRuns = useMemo(
    () => history.filter(run => !queueIds.has(run.run_id) && !isActiveRun(run)),
    [history, queueIds],
  );
  const allRuns = useMemo(() => [...queue, ...historicalRuns], [queue, historicalRuns]);
  const filteredRuns = useMemo(() => {
    const trimmed = query.trim().toLowerCase();
    return allRuns.filter(run => {
      if (statusFilter === 'active' && !isActiveRun(run)) return false;
      if (statusFilter !== 'all' && statusFilter !== 'active' && run.status !== statusFilter) return false;
      if (!trimmed) return true;
      const name = (run.workflow_name || '').toLowerCase();
      return name.includes(trimmed) || run.run_id.toLowerCase().includes(trimmed);
    });
  }, [allRuns, query, statusFilter]);
  const filteredQueue = filteredRuns.filter(isActiveRun);
  const filteredHistory = filteredRuns.filter(run => !isActiveRun(run));
  const historyBuckets = useMemo(() => bucketHistory(filteredHistory), [filteredHistory]);
  const counts = useMemo(() => {
    const next: Record<RunStatusFilter, number> = {
      all: allRuns.length,
      active: queue.length,
      completed: 0,
      error: 0,
      cancelled: 0,
    };
    for (const run of historicalRuns) {
      if (run.status === 'completed') next.completed += 1;
      else if (run.status === 'error') next.error += 1;
      else if (run.status === 'cancelled') next.cancelled += 1;
    }
    return next;
  }, [allRuns.length, historicalRuns, queue.length]);
  const queueStats = queue.reduce((stats, run) => {
    stats.totalNodes += Math.max(run.execution_plan?.length || 0, run.node_statuses?.length || 0);
    if (run.status === 'running') stats.running += 1;
    else if (run.status === 'pending') stats.pending += 1;
    else if (run.status === 'error') stats.failed += 1;
    return stats;
  }, { running: 0, pending: 0, failed: 0, totalNodes: 0 });

  if (!open) return null;

  const toggleHistoryBucket = (id: HistoryBucketId) => {
    setCollapsedHistoryBuckets(prev => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  };

  return (
    <aside className="runs-drawer" role="complementary" aria-label={t('runsDrawer.title')}>
      <div className="runs-drawer-header">
        <div>
          <div className="runs-drawer-title">{t('runsDrawer.title')}</div>
          <div className="runs-drawer-subtitle">{t('runsDrawer.subtitle', { active: queue.length, history: historicalRuns.length })}</div>
        </div>
        <button className="btn btn-icon btn-sm" onClick={onClose} title={t('runsDrawer.closeTitle')} aria-label={t('runsDrawer.closeTitle')}>
          <Icon name="close" size={14} />
        </button>
      </div>

      <div className="runs-drawer-toolbar">
        <input
          type="search"
          className="text-input runs-drawer-search"
          placeholder={t('runsDrawer.filterPlaceholder')}
          value={query}
          onChange={event => setQuery(event.target.value)}
          aria-label={t('runsDrawer.filterLabel')}
        />
        <div className="history-status-filters runs-drawer-filters" role="group" aria-label={t('runsDrawer.statusFilterLabel')}>
          {(['all', 'active', 'completed', 'error', 'cancelled'] as RunStatusFilter[]).map(filter => (
            <button
              key={filter}
              type="button"
              className={`history-status-chip ${statusFilter === filter ? 'is-active' : ''} is-${filter}`}
              onClick={() => setStatusFilter(filter)}
              title={t(filter === 'all' ? 'console.showAllRuns' : 'console.showStatusRuns', { status: filterLabel(t, filter).toLowerCase() })}
            >
              {filterLabel(t, filter)}
              <span className="history-status-chip-count">{counts[filter]}</span>
            </button>
          ))}
        </div>
      </div>

      <div className="runs-drawer-summary">
        <span className="queue-summary-item"><strong>{batchCount}</strong> {t('console.batchCount', { count: batchCount })}</span>
        <span className="queue-summary-item"><strong>{queueStats.running}</strong> {t('runsDrawer.summary.running')}</span>
        <span className="queue-summary-item"><strong>{queueStats.pending}</strong> {t('runsDrawer.summary.pending')}</span>
        <span className="queue-summary-item"><strong>{counts.completed}</strong> {t('runsDrawer.summary.completed')}</span>
        {queueStats.failed + counts.error > 0 && (
          <span className="queue-summary-item is-error"><strong>{queueStats.failed + counts.error}</strong> {t('runsDrawer.summary.error')}</span>
        )}
      </div>

      <div className="runs-drawer-actions">
        {onClearQueue && queue.length > 0 && (
          <button className="btn btn-sm btn-ghost" onClick={onClearQueue} type="button" title={t('console.clearQueuedRuns')}>
            <Icon name="trash" size={12} /> {t('console.clearQueue')}
          </button>
        )}
        <button
          type="button"
          className="btn btn-sm btn-ghost"
          onClick={() => setShowOutputDiff(true)}
          disabled={historicalRuns.length < 1}
          title={t('console.compareRunsTitle')}
        >
          <Icon name="layers" size={12} /> {t('console.compareRuns')}
        </button>
        {onClearHistory && historicalRuns.length > 0 && (
          <button className="btn btn-sm btn-ghost" onClick={onClearHistory} type="button" title={t('console.clearHistoryTitle')}>
            <Icon name="trash" size={12} /> {t('console.clearHistory')}
          </button>
        )}
      </div>

      <div className="runs-drawer-body">
        {filteredRuns.length === 0 ? (
          <div className="runs-drawer-empty">{query.trim() ? t('console.historyNoMatches') : t('runsDrawer.empty')}</div>
        ) : (
          <>
            {filteredQueue.length > 0 && (
              <section className="runs-drawer-section">
                <div className="runs-drawer-section-title">{t('runsDrawer.activeSection')}</div>
                <div className="queue-run-list">
                  {filteredQueue.map((run, index) => (
                    <QueueRunCard
                      key={run.run_id}
                      run={run}
                      index={index}
                      totalRuns={filteredQueue.length}
                      onCancelRun={onCancelRun}
                      onRetryRun={onRetryRun}
                      onMoveRun={onMoveRun}
                      t={t}
                    />
                  ))}
                </div>
              </section>
            )}
            {filteredHistory.length > 0 && (
              <section className="runs-drawer-section">
                <div className="runs-drawer-section-title">{t('runsDrawer.historySection')}</div>
                <div className="history-bucket-list">
                  {historyBuckets.map(bucket => {
                    const collapsed = collapsedHistoryBuckets.has(bucket.id);
                    return (
                      <section key={bucket.id} className="history-bucket">
                        <button
                          type="button"
                          className="history-bucket-header"
                          onClick={() => toggleHistoryBucket(bucket.id)}
                          aria-expanded={!collapsed}
                        >
                          <Icon name={collapsed ? 'chevronRight' : 'chevronDown'} size={12} />
                          <span className="history-bucket-label">{historyBucketLabel(t, bucket.id, i18n.language)}</span>
                          <span className="history-bucket-count">{bucket.runs.length}</span>
                        </button>
                        {!collapsed && (
                          <div className="queue-run-list history-run-list">
                            {bucket.runs.map(run => (
                              <HistoryRunCard
                                key={run.run_id}
                                run={run}
                                onRetryRun={onRetryRun}
                                onLoadRunWorkflow={onLoadRunWorkflow}
                                onDeleteHistoryEntry={onDeleteHistoryEntry}
                                t={t}
                                locale={i18n.language}
                              />
                            ))}
                          </div>
                        )}
                      </section>
                    );
                  })}
                </div>
              </section>
            )}
          </>
        )}
      </div>
    </aside>
  );
}
