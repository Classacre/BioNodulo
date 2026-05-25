import { useEffect, useState, useCallback, useRef } from 'react';

interface GettingStartedModalProps {
  onClose: () => void;
  onDontShowAgain: (hide: boolean) => void;
  collabEnabled: boolean;
  onSetCollabEnabled: (enabled: boolean) => void;
  showOnStartup: boolean;
}

type TabId = 'welcome' | 'data' | 'news' | 'resources';

const TABS: { id: TabId; label: string }[] = [
  { id: 'welcome', label: 'Welcome' },
  { id: 'data', label: 'Example Data' },
  { id: 'news', label: "What's New" },
  { id: 'resources', label: 'Resources' },
];

const CHANGELOG = [
  {
    version: '2.0',
    date: '2026-05',
    items: [
      'ComfyUI-inspired command palette, keybindings, toasts, dialogs, and panel workflow',
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
      'LiteGraph canvas with custom bioinformatics nodes',
      '14 built-in pipeline templates',
      'Pixi-based package management',
      'Result caching and queue-based execution',
    ],
  },
];

interface DataStatus {
  has_example_data: boolean;
  categories: string[];
  files_per_category: Record<string, number>;
  total_size_mb: number;
}

export default function GettingStartedModal({
  onClose,
  onDontShowAgain,
  collabEnabled,
  onSetCollabEnabled,
  showOnStartup,
}: GettingStartedModalProps) {
  const [tab, setTab] = useState<TabId>('welcome');
  const [dataStatus, setDataStatus] = useState<DataStatus | null>(null);
  const [downloading, setDownloading] = useState(false);
  const [downloadError, setDownloadError] = useState<string | null>(null);
  const [downloadResult, setDownloadResult] = useState<{
    downloaded: string[];
    skipped: string[];
    failed: string[];
  } | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const fetchStatus = useCallback(async () => {
    try {
      const r = await fetch('/api/getting-started/status');
      if (r.ok) {
        const d = await r.json() as DataStatus;
        setDataStatus(d);
      }
    } catch { /* offline */ }
  }, []);

  useEffect(() => {
    fetchStatus();
  }, [fetchStatus]);

  // Auto-poll while downloading
  useEffect(() => {
    if (downloading) {
      pollRef.current = setInterval(fetchStatus, 2000);
    } else if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [downloading, fetchStatus]);

  const handleDownload = async () => {
    setDownloading(true);
    setDownloadError(null);
    setDownloadResult(null);
    try {
      const r = await fetch('/api/getting-started/download', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({}),
      });
      if (!r.ok) {
        const err = await r.json().catch(() => ({ detail: 'Download failed' }));
        setDownloadError(err.detail || 'Download failed');
      } else {
        const d = await r.json() as DataStatus & { download_result?: { downloaded: string[]; skipped: string[]; failed: string[] } };
        setDataStatus(d);
        if (d.download_result) {
          setDownloadResult(d.download_result);
        }
      }
    } catch (e) {
      setDownloadError(e instanceof Error ? e.message : 'Network error');
    }
    setDownloading(false);
  };

  return (
    <div className="modal-overlay" onClick={onClose} style={{ zIndex: 500 }}>
      <div className="modal-content getting-started-modal" onClick={e => e.stopPropagation()}>
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

          {tab === 'data' && (
            <div>
              <p style={{ fontSize: 12, lineHeight: 1.6, marginBottom: 12, color: 'var(--text-2)' }}>
                Built-in templates reference public datasets (ENA, NCBI, Zenodo, 10x Genomics, etc.).
                Download them (~340 MB) to run templates out-of-the-box.
                Each file is fetched directly from its public source so you can inspect provenance.
              </p>

              {dataStatus ? (
                <div style={{ background: 'var(--surface-2)', borderRadius: 8, padding: 12, marginBottom: 12 }}>
                  {dataStatus.has_example_data ? (
                    <>
                      <div style={{ fontWeight: 600, fontSize: 12, color: 'var(--success)', marginBottom: 6 }}>
                        ✓ Example data is installed
                      </div>
                      <div style={{ fontSize: 11, color: 'var(--muted)', marginBottom: 8 }}>
                        {dataStatus.categories.length} categories · {dataStatus.total_size_mb} MB
                      </div>
                      <div style={{ display: 'grid', gap: 6 }}>
                        {dataStatus.categories.map(c => (
                          <div key={c} style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, padding: '4px 8px', background: 'var(--surface)', borderRadius: 4 }}>
                            <span>{c}</span>
                            <span style={{ color: 'var(--muted)' }}>{dataStatus.files_per_category[c] || 0} files</span>
                          </div>
                        ))}
                      </div>
                    </>
                  ) : (
                    <>
                      <div style={{ fontWeight: 600, fontSize: 12, color: 'var(--warning)', marginBottom: 6 }}>
                        ⚠ Example data not found
                      </div>
                      <div style={{ fontSize: 11, color: 'var(--muted)', marginBottom: 10 }}>
                        Templates that reference example files will fail until data is downloaded.
                      </div>
                      <button className="btn btn-primary" onClick={handleDownload} disabled={downloading}>
                        {downloading ? 'Downloading…' : 'Download Example Data'}
                      </button>
                      {downloading && (
                        <div style={{ marginTop: 10, fontSize: 11, color: 'var(--text-2)' }}>
                          <span className="pulse-dot" style={{ marginRight: 6 }} />
                          Downloading from public sources… check the <strong>Console</strong> for live per-file progress.
                        </div>
                      )}
                      {downloadError && (
                        <div style={{ marginTop: 8, fontSize: 11, color: 'var(--danger)' }}>
                          Error: {downloadError}
                        </div>
                      )}
                    </>
                  )}

                  {downloadResult && (
                    <div style={{ marginTop: 12, fontSize: 11 }}>
                      {downloadResult.downloaded.length > 0 && (
                        <div style={{ marginBottom: 6, color: 'var(--success)' }}>
                          ✓ {downloadResult.downloaded.length} file(s) downloaded
                        </div>
                      )}
                      {downloadResult.skipped.length > 0 && (
                        <div style={{ marginBottom: 6, color: 'var(--muted)' }}>
                          → {downloadResult.skipped.length} file(s) already existed
                        </div>
                      )}
                      {downloadResult.failed.length > 0 && (
                        <div style={{ color: 'var(--danger)' }}>
                          ✗ {downloadResult.failed.length} file(s) failed — see Console for details
                        </div>
                      )}
                    </div>
                  )}
                </div>
              ) : (
                <div style={{ fontSize: 12, color: 'var(--muted)' }}>Checking status…</div>
              )}
            </div>
          )}

          {tab === 'news' && (
            <div>
              {CHANGELOG.map(entry => (
                <div key={entry.version} style={{ marginBottom: 16 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
                    <span style={{ fontWeight: 700, fontSize: 13 }}>{entry.version}</span>
                    <span style={{ fontSize: 11, color: 'var(--muted)' }}>{entry.date}</span>
                  </div>
                  <ul style={{ fontSize: 12, lineHeight: 1.6, color: 'var(--text-2)', paddingLeft: 16 }}>
                    {entry.items.map((item, i) => (
                      <li key={i}>{item}</li>
                    ))}
                  </ul>
                </div>
              ))}
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
