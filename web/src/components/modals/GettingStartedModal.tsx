import { useEffect, useRef, useState } from 'react';
import type { TFunction } from 'i18next';
import { useTranslation } from 'react-i18next';
import { getRecentWorkflows, subscribeRecentWorkflows, forgetRecentWorkflow, setRecentTags, type RecentWorkflow } from '../../state/recentWorkflows';
import { useFocusTrap } from '../../hooks/ui';

interface GettingStartedModalProps {
  onClose: () => void;
  onDontShowAgain: (hide: boolean) => void;
  showOnStartup: boolean;
  onOpenRecent?: (entry: RecentWorkflow) => void;
}

type TabId = 'welcome' | 'news' | 'resources';

// "Example Data" tab was removed once input nodes learned to download
// http(s)/ftp URLs into a workspace-scoped cache on first use — templates
// now reference URLs directly in their node params instead of expecting a
// pre-populated example data directory.
const TABS: { id: TabId; labelKey: string }[] = [
  { id: 'welcome', labelKey: 'gettingStarted.tabs.welcome' },
  { id: 'news', labelKey: 'gettingStarted.tabs.news' },
  { id: 'resources', labelKey: 'gettingStarted.tabs.resources' },
];

interface BundledReleaseNote {
  version: string;
  date: string;
  itemKeys: string[];
}

const CHANGELOG: BundledReleaseNote[] = [
  {
    version: '2.0',
    date: '2026-05',
    itemKeys: [
      'gettingStarted.changelog.v2.items.commandPalette',
      'gettingStarted.changelog.v2.items.panels',
      'gettingStarted.changelog.v2.items.templates',
      'gettingStarted.changelog.v2.items.canvas',
      'gettingStarted.changelog.v2.items.queue',
      'gettingStarted.changelog.v2.items.collaboration',
    ],
  },
  {
    version: 'Alpha 1.5',
    date: '2025-05',
    itemKeys: [
      'gettingStarted.changelog.alpha15.items.visualNotes',
      'gettingStarted.changelog.alpha15.items.consoleGrouping',
      'gettingStarted.changelog.alpha15.items.environmentPanel',
      'gettingStarted.changelog.alpha15.items.biopythonFixes',
      'gettingStarted.changelog.alpha15.items.isolatedEnvironments',
      'gettingStarted.changelog.alpha15.items.hpcSupport',
      'gettingStarted.changelog.alpha15.items.gettingStartedData',
    ],
  },
  {
    version: 'Alpha 1.1',
    date: '2025-04',
    itemKeys: [
      'gettingStarted.changelog.alpha11.items.aiAssistant',
      'gettingStarted.changelog.alpha11.items.workflowExport',
      'gettingStarted.changelog.alpha11.items.nodeRegistry',
      'gettingStarted.changelog.alpha11.items.websocketLogs',
      'gettingStarted.changelog.alpha11.items.hardwareMonitor',
    ],
  },
  {
    version: 'Alpha 1.0',
    date: '2025-03',
    itemKeys: [
      'gettingStarted.changelog.alpha10.items.initialRelease',
      'gettingStarted.changelog.alpha10.items.workflowCanvas',
      'gettingStarted.changelog.alpha10.items.templates',
      'gettingStarted.changelog.alpha10.items.pixiPackages',
      'gettingStarted.changelog.alpha10.items.resultCaching',
    ],
  },
];

interface ReleaseNote {
  version: string;
  date: string;
  url?: string;
  body?: string;
  items?: string[];
}

type NewsEntry = ReleaseNote | BundledReleaseNote;

const UNNAMED_RELEASE_VERSION = '__bionodulo_unnamed_release__';

function releaseNoteItems(entry: NewsEntry, t: TFunction): string[] {
  if ('itemKeys' in entry) return entry.itemKeys.map(key => t(key));
  return entry.items ?? [];
}

function releaseNoteVersion(entry: NewsEntry, t: TFunction): string {
  return entry.version === UNNAMED_RELEASE_VERSION ? t('gettingStarted.newsUnreleased') : entry.version;
}

const RELEASES_CACHE_KEY = 'bionodulo.releases.cache';
const RELEASES_CACHE_TTL_MS = 6 * 60 * 60 * 1000; // 6 hours

function parseChangelogBody(body: string): string[] {
  // Extract bullet items from a GitHub release body. Tolerates `-`, `*`, and
  // `+` list markers and strips leading "## What's Changed" headers.
  const lines = body
    .replace(/\r\n/g, '\n')
    .split('\n')
    .map(line => line.trim());
  const items: string[] = [];
  for (const line of lines) {
    const match = line.match(/^[-*+]\s+(.+)$/);
    if (match) {
      // Drop trailing "by @user in #PR" suffixes for readability.
      const cleaned = match[1].replace(/\s+by @\S+\s+in\s+\S+$/i, '').trim();
      if (cleaned) items.push(cleaned);
    }
  }
  return items;
}

function loadCachedReleases(): ReleaseNote[] | null {
  if (typeof window === 'undefined') return null;
  try {
    const raw = window.localStorage.getItem(RELEASES_CACHE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as { fetchedAt?: number; releases?: ReleaseNote[] } | null;
    if (!parsed?.releases || !parsed.fetchedAt) return null;
    if (Date.now() - parsed.fetchedAt > RELEASES_CACHE_TTL_MS) return null;
    return parsed.releases;
  } catch {
    return null;
  }
}

function persistCachedReleases(releases: ReleaseNote[]): void {
  if (typeof window === 'undefined') return;
  try {
    window.localStorage.setItem(RELEASES_CACHE_KEY, JSON.stringify({ fetchedAt: Date.now(), releases }));
  } catch {
    // Cache write failures are non-fatal — we'll just re-fetch next time.
  }
}

export default function GettingStartedModal({
  onClose,
  onDontShowAgain,
  showOnStartup,
  onOpenRecent,
}: GettingStartedModalProps) {
  const { t } = useTranslation();
  const [tab, setTab] = useState<TabId>('welcome');
  const [recents, setRecents] = useState<RecentWorkflow[]>(() => getRecentWorkflows());
  // Tag filter. Empty string == "All". Set by clicking a tag chip.
  const [recentTagFilter, setRecentTagFilter] = useState<string>('');
  const [taggingRecentId, setTaggingRecentId] = useState<string | null>(null);
  const [tagDraft, setTagDraft] = useState('');
  const [liveReleases, setLiveReleases] = useState<ReleaseNote[] | null>(() => loadCachedReleases());
  const [releasesLoading, setReleasesLoading] = useState(false);
  const [releasesError, setReleasesError] = useState<string | null>(null);

  // Fetch live release notes when the News tab opens. Cached for 6 hours so
  // repeated opens don't hammer the GitHub API and offline users still see
  // the last-known good list.
  useEffect(() => {
    if (tab !== 'news') return;
    if (liveReleases && liveReleases.length > 0) return;
    const controller = new AbortController();
    setReleasesLoading(true);
    setReleasesError(null);
    fetch('https://api.github.com/repos/Classacre/BioNodulo/releases?per_page=10', {
      signal: controller.signal,
      headers: { Accept: 'application/vnd.github+json' },
    })
      .then(response => {
        if (!response.ok) throw new Error(`GitHub ${response.status}`);
        return response.json() as Promise<Array<{ tag_name?: string; name?: string; published_at?: string; html_url?: string; body?: string }>>;
      })
      .then(items => {
        const releases: ReleaseNote[] = items.map(item => ({
          version: item.name || item.tag_name || UNNAMED_RELEASE_VERSION,
          date: item.published_at ? item.published_at.slice(0, 10) : '',
          url: item.html_url,
          body: item.body || '',
          items: parseChangelogBody(item.body || ''),
        }));
        setLiveReleases(releases);
        persistCachedReleases(releases);
      })
      .catch((err: Error) => {
        if (err.name === 'AbortError') return;
        setReleasesError(err.message);
      })
      .finally(() => setReleasesLoading(false));
    return () => controller.abort();
  }, [tab, liveReleases]);
  useEffect(() => {
    const unsubscribe = subscribeRecentWorkflows(() => setRecents(getRecentWorkflows()));
    return unsubscribe;
  }, []);
  // The standalone Example Data tab was removed — see the comment near the
  // TABS constant. Templates now reference URLs directly in their input
  // node params, so the up-front /api/getting-started/download step isn't
  // needed; the existing backend endpoint stays in place so older user
  // workflows / scripts that still call it keep working.

  const dialogRef = useRef<HTMLDivElement>(null);
  useFocusTrap(dialogRef, true, onClose);

  return (
    <div className="modal-overlay" onClick={onClose} style={{ zIndex: 500 }}>
      <div
        ref={dialogRef}
        className="modal-content getting-started-modal"
        role="dialog"
        aria-modal="true"
        aria-label={t('gettingStarted.title')}
        onClick={e => e.stopPropagation()}
      >
        <div className="modal-header" style={{ borderBottom: 'none', paddingBottom: 4 }}>
          <div>
            <div style={{ fontSize: 16, fontWeight: 700 }}>{t('gettingStarted.title')}</div>
            <div style={{ fontSize: 11, color: 'var(--muted)', marginTop: 2 }}>BioNodulo v2</div>
          </div>
        </div>

        <div style={{ display: 'flex', gap: 4, padding: '0 16px', borderBottom: '1px solid var(--border)' }}>
          {TABS.map(tabDef => (
            <button
              key={tabDef.id}
              className={`env-type-tab ${tab === tabDef.id ? 'active' : ''}`}
              onClick={() => setTab(tabDef.id)}
              style={{ borderRadius: '6px 6px 0 0', borderBottom: 'none' }}
            >
              {t(tabDef.labelKey)}
            </button>
          ))}
        </div>

        <div className="modal-body" style={{ padding: 16, minHeight: 320, maxHeight: '60vh', overflowY: 'auto' }}>
          {tab === 'welcome' && (
            <div>
              <p style={{ fontSize: 13, lineHeight: 1.6, marginBottom: 12 }}>
                {t('gettingStarted.welcomeIntro')} <strong>BioNodulo</strong> — {t('gettingStarted.welcomeDescription')}
                {' '}
                {t('gettingStarted.welcomeBuildShare')}
              </p>

              {recents.length > 0 && onOpenRecent && (() => {
                const allTags = Array.from(new Set(recents.flatMap(r => r.tags || []))).sort();
                const filtered = recentTagFilter
                  ? recents.filter(r => (r.tags || []).includes(recentTagFilter))
                  : recents;
                return (
                <div style={{ background: 'var(--surface-2)', borderRadius: 8, padding: 12, marginBottom: 12 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                    <div style={{ fontWeight: 600, fontSize: 12 }}>{t('gettingStarted.recentsTitle')}</div>
                    {allTags.length > 0 && (
                      <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
                        <button
                          type="button"
                          onClick={() => setRecentTagFilter('')}
                          className={`env-type-tab ${!recentTagFilter ? 'active' : ''}`}
                          style={{ fontSize: 10, padding: '2px 8px' }}
                        >{t('gettingStarted.recentsAll')}</button>
                        {allTags.map(tag => (
                          <button
                            key={tag}
                            type="button"
                            onClick={() => setRecentTagFilter(tag === recentTagFilter ? '' : tag)}
                            className={`env-type-tab ${recentTagFilter === tag ? 'active' : ''}`}
                            style={{ fontSize: 10, padding: '2px 8px' }}
                          >#{tag}</button>
                        ))}
                      </div>
                    )}
                  </div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                    {filtered.slice(0, 8).map(entry => (
                      <div
                        key={entry.id}
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          gap: 8,
                          padding: '6px 8px',
                          borderRadius: 6,
                          border: '1px solid var(--border)',
                          background: 'var(--surface)',
                        }}
                      >
                        <button
                          type="button"
                          onClick={() => { onOpenRecent(entry); onClose(); }}
                          style={{
                            flex: 1,
                            display: 'flex',
                            alignItems: 'center',
                            gap: 8,
                            background: 'transparent',
                            border: 'none',
                            color: 'inherit',
                            cursor: 'pointer',
                            textAlign: 'left',
                            padding: 0,
                          }}
                          title={t('gettingStarted.recentOpenTitle', { name: entry.name })}
                        >
                          {entry.thumbnailUrl ? (
                            <img
                              src={entry.thumbnailUrl}
                              alt=""
                              style={{ width: 42, height: 28, objectFit: 'cover', borderRadius: 4, border: '1px solid var(--border)' }}
                            />
                          ) : (
                            <div style={{ width: 42, height: 28, borderRadius: 4, background: 'var(--surface-2)', border: '1px solid var(--border)' }} />
                          )}
                          <div style={{ display: 'flex', flexDirection: 'column', minWidth: 0, flex: 1 }}>
                            <span style={{ fontSize: 12, fontWeight: 600, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{entry.name}</span>
                            <span style={{ fontSize: 10, color: 'var(--muted)' }}>
                              {t('gettingStarted.recentMeta', {
                                source: recentSourceLabel(entry.source, t),
                                nodes: t('gettingStarted.recentNodeCount', { count: entry.nodeCount ?? 0 }),
                                age: timeAgo(entry.openedAt, t),
                              })}
                            </span>
                            {(entry.tags && entry.tags.length > 0) && (
                              <span style={{ display: 'flex', gap: 3, marginTop: 2, flexWrap: 'wrap' }}>
                                {entry.tags.map(tag => (
                                  <span key={tag} style={{ fontSize: 9, padding: '1px 5px', borderRadius: 8, background: 'rgba(45,212,191,0.14)', color: 'var(--accent, #2dd4bf)' }}>#{tag}</span>
                                ))}
                              </span>
                            )}
                          </div>
                        </button>
                        {taggingRecentId === entry.id ? (
                          <input
                            autoFocus
                            value={tagDraft}
                            onChange={e => setTagDraft(e.target.value)}
                            placeholder={t('gettingStarted.recentTagsPlaceholder')}
                            onBlur={() => {
                              const tags = tagDraft.split(',').map(t => t.trim()).filter(Boolean);
                              setRecentTags(entry.id, tags);
                              setRecents(getRecentWorkflows());
                              setTaggingRecentId(null);
                            }}
                            onKeyDown={e => {
                              if (e.key === 'Enter') (e.currentTarget as HTMLInputElement).blur();
                              else if (e.key === 'Escape') setTaggingRecentId(null);
                            }}
                            style={{
                              width: 120, fontSize: 11, padding: '2px 6px',
                              background: 'var(--surface)', border: '1px solid var(--accent, #2dd4bf)',
                              color: 'var(--text)', borderRadius: 4,
                            }}
                            aria-label={t('gettingStarted.recentTagsLabel')}
                          />
                        ) : (
                          <button
                            type="button"
                            onClick={() => { setTaggingRecentId(entry.id); setTagDraft((entry.tags || []).join(', ')); }}
                            title={t('gettingStarted.recentEditTagsTitle')}
                            style={{ background: 'transparent', border: 'none', color: 'var(--muted)', cursor: 'pointer', fontSize: 12, padding: '0 4px' }}
                          >
                            #
                          </button>
                        )}
                        <button
                          type="button"
                          onClick={() => forgetRecentWorkflow(entry.id)}
                          title={t('gettingStarted.recentForgetTitle')}
                          style={{
                            background: 'transparent',
                            border: 'none',
                            color: 'var(--muted)',
                            cursor: 'pointer',
                            fontSize: 14,
                            padding: '0 4px',
                          }}
                        >
                          ×
                        </button>
                      </div>
                    ))}
                  </div>
                </div>
                );
              })()}

              <div style={{ background: 'var(--surface-2)', borderRadius: 8, padding: 12, marginBottom: 12 }}>
                <div style={{ fontWeight: 600, fontSize: 12, marginBottom: 8 }}>{t('gettingStarted.quickStartTitle')}</div>
                <ol style={{ fontSize: 12, lineHeight: 1.7, paddingLeft: 16, color: 'var(--text-2)' }}>
                  <li>
                    {t('gettingStarted.quickStartTemplatesPrefix')} <strong>{t('gettingStarted.quickStartTemplatesPanel')}</strong> {t('gettingStarted.quickStartTemplatesShortcutPrefix')}<kbd>Ctrl+3</kbd>) {t('gettingStarted.quickStartTemplatesSuffix')}
                  </li>
                  <li>{t('gettingStarted.quickStartConfigureNode')}</li>
                  <li>{t('gettingStarted.quickStartRunPrefix')} <kbd>Ctrl+R</kbd> {t('gettingStarted.quickStartRunSuffix')}</li>
                  <li>
                    {t('gettingStarted.quickStartConsolePrefix')} <strong>{t('gettingStarted.quickStartConsole')}</strong> (<kbd>Ctrl+`</kbd>){t('gettingStarted.quickStartConsoleSuffix')}
                  </li>
                </ol>
              </div>

              <div style={{ fontSize: 11, color: 'var(--muted)', lineHeight: 1.5 }}>
                {t('gettingStarted.aiTipPrefix')} <strong>{t('gettingStarted.aiAssistant')}</strong> (<kbd>Ctrl+Shift+A</kbd>) {t('gettingStarted.aiTipSuffix')}
              </div>
            </div>
          )}

          {tab === 'news' && (
            <div>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
                <div style={{ fontSize: 11, color: 'var(--muted)' }}>
                  {liveReleases && liveReleases.length > 0
                    ? t('gettingStarted.newsLiveStatus', { count: liveReleases.length })
                    : releasesLoading
                      ? t('gettingStarted.newsFetching')
                      : releasesError
                        ? t('gettingStarted.newsOffline')
                        : t('gettingStarted.newsBundled')}
                </div>
                {liveReleases && (
                  <button
                    type="button"
                    onClick={() => { setLiveReleases(null); }}
                    style={{ background: 'transparent', border: 0, color: 'var(--accent-dark, var(--accent))', fontSize: 11, cursor: 'pointer' }}
                    title={t('gettingStarted.newsRefetchTitle')}
                  >
                    {t('common.refresh')}
                  </button>
                )}
              </div>
              {(liveReleases && liveReleases.length > 0 ? liveReleases : CHANGELOG).map(entry => {
                const items = releaseNoteItems(entry, t);
                const version = releaseNoteVersion(entry, t);
                const liveUrl = 'url' in entry ? entry.url : undefined;
                return (
                  <div key={entry.version} style={{ marginBottom: 16 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
                      <span style={{ fontWeight: 700, fontSize: 13 }}>{version}</span>
                      <span style={{ fontSize: 11, color: 'var(--muted)' }}>{entry.date}</span>
                      {liveUrl && (
                        <a
                          href={liveUrl}
                          target="_blank"
                          rel="noreferrer"
                          style={{ fontSize: 10, color: 'var(--accent-dark, var(--accent))' }}
                        >
                          {t('gettingStarted.newsViewOnGitHub')}
                        </a>
                      )}
                    </div>
                    {items.length > 0 ? (
                      <ul style={{ fontSize: 12, lineHeight: 1.6, color: 'var(--text-2)', paddingLeft: 16 }}>
                        {items.map((item, i) => (<li key={i}>{item}</li>))}
                      </ul>
                    ) : 'body' in entry && entry.body ? (
                      <pre style={{ fontSize: 11, color: 'var(--text-2)', whiteSpace: 'pre-wrap', fontFamily: 'inherit', margin: 0 }}>{entry.body.slice(0, 600)}{entry.body.length > 600 ? '…' : ''}</pre>
                    ) : null}
                  </div>
                );
              })}
            </div>
          )}

          {tab === 'resources' && (
            <div>
              <div style={{ display: 'grid', gap: 8 }}>
                <a href="https://github.com/Classacre/BioNodulo/wiki" target="_blank" rel="noreferrer" className="resource-link">
                  <span>📖</span>
                  <div>
                    <div style={{ fontWeight: 600, fontSize: 12 }}>{t('gettingStarted.resources.wikiTitle')}</div>
                    <div style={{ fontSize: 11, color: 'var(--muted)' }}>{t('gettingStarted.resources.wikiDescription')}</div>
                  </div>
                </a>
                <a href="https://github.com/Classacre/BioNodulo" target="_blank" rel="noreferrer" className="resource-link">
                  <span>🐙</span>
                  <div>
                    <div style={{ fontWeight: 600, fontSize: 12 }}>{t('gettingStarted.resources.githubTitle')}</div>
                    <div style={{ fontSize: 11, color: 'var(--muted)' }}>{t('gettingStarted.resources.githubDescription')}</div>
                  </div>
                </a>
                <a href="https://github.com/Classacre/BioNodulo/issues/new" target="_blank" rel="noreferrer" className="resource-link">
                  <span>🐛</span>
                  <div>
                    <div style={{ fontWeight: 600, fontSize: 12 }}>{t('gettingStarted.resources.issueTitle')}</div>
                    <div style={{ fontSize: 11, color: 'var(--muted)' }}>{t('gettingStarted.resources.issueDescription')}</div>
                  </div>
                </a>
                <button
                  className="resource-link"
                  onClick={() => {
                    onClose();
                    setTimeout(() => {
                      window.dispatchEvent(new CustomEvent('bionodulo:open-help', { detail: 'getting-started' }));
                    }, 100);
                  }}
                  style={{ textAlign: 'left' }}
                >
                  <span>❓</span>
                  <div>
                    <div style={{ fontWeight: 600, fontSize: 12 }}>{t('gettingStarted.resources.inAppHelpTitle')}</div>
                    <div style={{ fontSize: 11, color: 'var(--muted)' }}>{t('gettingStarted.resources.inAppHelpDescription')}</div>
                  </div>
                </button>
              </div>
            </div>
          )}
        </div>

        <div className="modal-footer" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, cursor: 'pointer', userSelect: 'none' }}>
            <input
              type="checkbox"
              checked={!showOnStartup}
              onChange={e => onDontShowAgain(e.target.checked)}
              style={{ accentColor: 'var(--accent)' }}
            />
            {t('gettingStarted.hideOnStartup')}
          </label>
          <button className="btn btn-primary" onClick={onClose}>{t('common.close')}</button>
        </div>
      </div>
    </div>
  );
}

function recentSourceLabel(source: RecentWorkflow['source'], t: TFunction): string {
  switch (source) {
    case 'template':
      return t('gettingStarted.recentSource.template');
    case 'import':
      return t('gettingStarted.recentSource.import');
    case 'collab':
      return t('gettingStarted.recentSource.collab');
    case 'workspace':
      return t('gettingStarted.recentSource.workspace');
    case 'manual':
      return t('gettingStarted.recentSource.manual');
    default:
      return source;
  }
}

function timeAgo(ts: number, t: TFunction): string {
  const diff = Date.now() - ts;
  const sec = Math.floor(diff / 1000);
  if (sec < 60) return t('gettingStarted.recentJustNow');
  const min = Math.floor(sec / 60);
  if (min < 60) return t('gettingStarted.recentMinutesAgo', { count: min });
  const hr = Math.floor(min / 60);
  if (hr < 24) return t('gettingStarted.recentHoursAgo', { count: hr });
  const day = Math.floor(hr / 24);
  if (day < 7) return t('gettingStarted.recentDaysAgo', { count: day });
  return new Date(ts).toLocaleDateString();
}
