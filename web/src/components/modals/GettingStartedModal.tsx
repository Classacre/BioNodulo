import { useEffect, useRef, useState } from 'react';
import { getRecentWorkflows, subscribeRecentWorkflows, forgetRecentWorkflow, setRecentTags, type RecentWorkflow } from '../../state/recentWorkflows';
import { useFocusTrap } from '../../hooks/useFocusTrap';

interface GettingStartedModalProps {
  onClose: () => void;
  onDontShowAgain: (hide: boolean) => void;
  collabEnabled: boolean;
  onSetCollabEnabled: (enabled: boolean) => void;
  showOnStartup: boolean;
  onOpenRecent?: (entry: RecentWorkflow) => void;
}

type TabId = 'welcome' | 'news' | 'resources';

// "Example Data" tab was removed once input nodes learned to download
// http(s)/ftp URLs into a workspace-scoped cache on first use — templates
// now reference URLs directly in their node params instead of expecting a
// pre-populated example data directory.
const TABS: { id: TabId; label: string }[] = [
  { id: 'welcome', label: 'Welcome' },
  { id: 'news', label: "What's New" },
  { id: 'resources', label: 'Resources' },
];

const CHANGELOG = [
  {
    version: '2.0',
    date: '2026-05',
    items: [
      'BioNodulo command palette, keybindings, toasts, dialogs, and panel workflow',
      'Resizable/floating side panels with improved dock controls',
      'Template gallery redesign with previews, search ranking, tags, and workflow step summaries',
      'Canvas upgrades for node badges, hover details, reroute workflows, selected execution, and subgraph extraction',
      'Queue controls for cancel, retry, reorder, clear, progress tracking, and batch execution',
      'Collaboration, autosave, i18n, theme palette, and performance mode refinements',
    ],
  },
  {
    version: 'Alpha 1.5',
    date: '2025-05',
    items: [
      'Visual-only notes and node minimization support',
      'Console log grouping by run_id with expand/collapse',
      'Complete environment panel rework with pixi migration',
      'BioPython pipeline fixes (BLAST, translation, SeqIO)',
      'Per-workflow isolated environments with content-addressed envs',
      'HPC backend support (SLURM, PBS, SGE)',
      'Getting Started modal with public dataset downloads',
    ],
  },
  {
    version: 'Alpha 1.1',
    date: '2025-04',
    items: [
      'AI assistant with tool-calling for workflow building',
      'Workflow export to Snakemake, NextFlow, CWL, Galaxy',
      'Node registry with bioinformatics tool metadata',
      'Real-time WebSocket execution logs',
      'Hardware monitor overlay',
    ],
  },
  {
    version: 'Alpha 1.0',
    date: '2025-03',
    items: [
      'Initial BioNodulo v2 release',
      'Workflow canvas with custom bioinformatics nodes',
      '14 built-in pipeline templates',
      'Pixi-based package management',
      'Result caching and queue-based execution',
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
  collabEnabled,
  onSetCollabEnabled,
  showOnStartup,
  onOpenRecent,
}: GettingStartedModalProps) {
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
          version: item.name || item.tag_name || 'unreleased',
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
        aria-label="Getting started"
        onClick={e => e.stopPropagation()}
      >
        <div className="modal-header" style={{ borderBottom: 'none', paddingBottom: 4 }}>
          <div>
            <div style={{ fontSize: 16, fontWeight: 700 }}>Getting Started</div>
            <div style={{ fontSize: 11, color: 'var(--muted)', marginTop: 2 }}>BioNodulo v2</div>
          </div>
        </div>

        <div style={{ display: 'flex', gap: 4, padding: '0 16px', borderBottom: '1px solid var(--border)' }}>
          {TABS.map(t => (
            <button
              key={t.id}
              className={`env-type-tab ${tab === t.id ? 'active' : ''}`}
              onClick={() => setTab(t.id)}
              style={{ borderRadius: '6px 6px 0 0', borderBottom: 'none' }}
            >
              {t.label}
            </button>
          ))}
        </div>

        <div className="modal-body" style={{ padding: 16, minHeight: 320, maxHeight: '60vh', overflowY: 'auto' }}>
          {tab === 'welcome' && (
            <div>
              <p style={{ fontSize: 13, lineHeight: 1.6, marginBottom: 12 }}>
                Welcome to <strong>BioNodulo</strong> — a visual workflow builder for bioinformatics.
                Build, run, and share reproducible pipelines using a node-based canvas.
              </p>

              {recents.length > 0 && onOpenRecent && (() => {
                const allTags = Array.from(new Set(recents.flatMap(r => r.tags || []))).sort();
                const filtered = recentTagFilter
                  ? recents.filter(r => (r.tags || []).includes(recentTagFilter))
                  : recents;
                return (
                <div style={{ background: 'var(--surface-2)', borderRadius: 8, padding: 12, marginBottom: 12 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                    <div style={{ fontWeight: 600, fontSize: 12 }}>Recent workflows</div>
                    {allTags.length > 0 && (
                      <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
                        <button
                          type="button"
                          onClick={() => setRecentTagFilter('')}
                          className={`env-type-tab ${!recentTagFilter ? 'active' : ''}`}
                          style={{ fontSize: 10, padding: '2px 8px' }}
                        >All</button>
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
                          title={`Open ${entry.name}`}
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
                              {entry.source} · {entry.nodeCount ?? 0} nodes · {timeAgo(entry.openedAt)}
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
                            placeholder="tag1, tag2"
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
                            aria-label="Edit tags (comma-separated)"
                          />
                        ) : (
                          <button
                            type="button"
                            onClick={() => { setTaggingRecentId(entry.id); setTagDraft((entry.tags || []).join(', ')); }}
                            title="Edit tags"
                            style={{ background: 'transparent', border: 'none', color: 'var(--muted)', cursor: 'pointer', fontSize: 12, padding: '0 4px' }}
                          >
                            #
                          </button>
                        )}
                        <button
                          type="button"
                          onClick={() => forgetRecentWorkflow(entry.id)}
                          title="Forget this entry"
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
                <div style={{ fontWeight: 600, fontSize: 12, marginBottom: 8 }}>Quick Start</div>
                <ol style={{ fontSize: 12, lineHeight: 1.7, paddingLeft: 16, color: 'var(--text-2)' }}>
                  <li>Open the <strong>Templates</strong> panel (<kbd>Ctrl+3</kbd>) to load a built-in pipeline.</li>
                  <li>Double-click a node to configure its parameters.</li>
                  <li>Press <kbd>Ctrl+R</kbd> to validate and run your workflow.</li>
                  <li>Watch real-time logs in the <strong>Console</strong> (<kbd>Ctrl+`</kbd>).</li>
                </ol>
              </div>

              <div style={{ background: 'var(--surface-2)', borderRadius: 8, padding: 12, marginBottom: 12 }}>
                <div style={{ fontWeight: 600, fontSize: 12, marginBottom: 8 }}>Collaboration Mode</div>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
                  <button
                    className={`btn ${collabEnabled ? 'btn-primary' : 'btn-secondary'}`}
                    onClick={() => onSetCollabEnabled(true)}
                    style={{ justifyContent: 'center', minHeight: 34 }}
                  >
                    Use Collaboration
                  </button>
                  <button
                    className={`btn ${!collabEnabled ? 'btn-primary' : 'btn-secondary'}`}
                    onClick={() => onSetCollabEnabled(false)}
                    style={{ justifyContent: 'center', minHeight: 34 }}
                  >
                    Work Offline
                  </button>
                </div>
                <div style={{ fontSize: 11, color: 'var(--muted)', lineHeight: 1.5, marginTop: 8 }}>
                  Collaboration enables shared editing, comments, versions, and audit history. Offline mode keeps workflows local and avoids signing in.
                </div>
              </div>

              <div style={{ fontSize: 11, color: 'var(--muted)', lineHeight: 1.5 }}>
                Tip: Use the <strong>AI Assistant</strong> (<kbd>Ctrl+Shift+A</kbd>) to generate workflows from natural language descriptions.
              </div>
            </div>
          )}

          {tab === 'news' && (
            <div>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
                <div style={{ fontSize: 11, color: 'var(--muted)' }}>
                  {liveReleases && liveReleases.length > 0
                    ? `Live from GitHub releases · ${liveReleases.length} entries`
                    : releasesLoading
                      ? 'Fetching latest releases…'
                      : releasesError
                        ? `Offline mode — showing bundled changelog`
                        : 'Showing bundled changelog'}
                </div>
                {liveReleases && (
                  <button
                    type="button"
                    onClick={() => { setLiveReleases(null); }}
                    style={{ background: 'transparent', border: 0, color: 'var(--accent-dark, var(--accent))', fontSize: 11, cursor: 'pointer' }}
                    title="Refetch release notes"
                  >
                    Refresh
                  </button>
                )}
              </div>
              {(liveReleases && liveReleases.length > 0 ? liveReleases : CHANGELOG).map(entry => {
                const items = 'items' in entry && entry.items ? entry.items : [];
                const liveUrl = 'url' in entry ? entry.url : undefined;
                return (
                  <div key={entry.version} style={{ marginBottom: 16 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
                      <span style={{ fontWeight: 700, fontSize: 13 }}>{entry.version}</span>
                      <span style={{ fontSize: 11, color: 'var(--muted)' }}>{entry.date}</span>
                      {liveUrl && (
                        <a
                          href={liveUrl}
                          target="_blank"
                          rel="noreferrer"
                          style={{ fontSize: 10, color: 'var(--accent-dark, var(--accent))' }}
                        >
                          View on GitHub
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
                    <div style={{ fontWeight: 600, fontSize: 12 }}>Wiki & Documentation</div>
                    <div style={{ fontSize: 11, color: 'var(--muted)' }}>Learn how to build workflows and use nodes</div>
                  </div>
                </a>
                <a href="https://github.com/Classacre/BioNodulo" target="_blank" rel="noreferrer" className="resource-link">
                  <span>🐙</span>
                  <div>
                    <div style={{ fontWeight: 600, fontSize: 12 }}>GitHub Repository</div>
                    <div style={{ fontSize: 11, color: 'var(--muted)' }}>Source code, releases, and issues</div>
                  </div>
                </a>
                <a href="https://github.com/Classacre/BioNodulo/issues/new" target="_blank" rel="noreferrer" className="resource-link">
                  <span>🐛</span>
                  <div>
                    <div style={{ fontWeight: 600, fontSize: 12 }}>Report an Issue</div>
                    <div style={{ fontSize: 11, color: 'var(--muted)' }}>Bug reports and feature requests</div>
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
                    <div style={{ fontWeight: 600, fontSize: 12 }}>In-App Help</div>
                    <div style={{ fontSize: 11, color: 'var(--muted)' }}>Open the Help & Wiki panel</div>
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
            Hide on startup
          </label>
          <button className="btn btn-primary" onClick={onClose}>Close</button>
        </div>
      </div>
    </div>
  );
}

function timeAgo(ts: number): string {
  const diff = Date.now() - ts;
  const sec = Math.floor(diff / 1000);
  if (sec < 60) return 'just now';
  const min = Math.floor(sec / 60);
  if (min < 60) return `${min}m ago`;
  const hr = Math.floor(min / 60);
  if (hr < 24) return `${hr}h ago`;
  const day = Math.floor(hr / 24);
  if (day < 7) return `${day}d ago`;
  return new Date(ts).toLocaleDateString();
}
