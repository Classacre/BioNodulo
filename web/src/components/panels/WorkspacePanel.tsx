import { useState, useEffect, useCallback, useRef } from 'react';
import { useAtomValue } from 'jotai';
import type { TFunction } from 'i18next';
import { useTranslation } from 'react-i18next';
import Icon from '../ui/Icon';
import { alertDialog } from '../ui';
import Dialog from '../ui/Dialog';
import ContextMenu, { type MenuItem } from '../canvas/ContextMenu';
import { apiGet, apiGetText, apiPost, ApiError } from '../../api/client';
import { logError } from '../../state/logging';
import { useSettings } from '../../hooks/settings';
import { authUserAtom, cloudConfigAtom } from '../../state/appAtoms';
import { listCloudFiles, type CloudFile } from '../../api/website';
import { startCloudDownload, uploadWorkspaceFileToCloud } from '../../api/cloudFiles';

interface FileEntry {
  name: string;
  path: string;
  type: 'file' | 'directory';
  size?: number;
}

interface WorkspacePanelProps {
  onClose: () => void;
  onOpenSettings?: () => void;
  onImportWorkflow?: (wf: any) => void;
}

export default function WorkspacePanel({ onClose, onOpenSettings, onImportWorkflow }: WorkspacePanelProps) {
  const { t, i18n } = useTranslation();
  const { getBool } = useSettings();
  const showHidden = getBool('bionodulo.showHiddenFiles', false);
  const [path, setPath] = useState('/');
  const [files, setFiles] = useState<FileEntry[]>([]);
  // Hide dotfiles unless the user opts in (bionodulo.showHiddenFiles).
  const visibleFiles = showHidden ? files : files.filter(f => !f.name.startsWith('.'));
  const [loading, setLoading] = useState(false);
  const [, setRootPath] = useState('');
  const [rootInput, setRootInput] = useState('');
  const [rootLoading, setRootLoading] = useState(false);
  const [rootError, setRootError] = useState('');
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [previewFile, setPreviewFile] = useState<string | null>(null);
  const [previewContent, setPreviewContent] = useState('');
  const [previewLoading, setPreviewLoading] = useState(false);
  const fileListRef = useRef<HTMLDivElement>(null);
  const lastSelectedRef = useRef<string | null>(null);

  // Cloud tab: only offered when signed into a BioNodulo account.
  const authUser = useAtomValue(authUserAtom);
  const cloudConfig = useAtomValue(cloudConfigAtom);
  const cloudAvailable = Boolean(authUser) || Boolean(cloudConfig?.user);
  const [tab, setTab] = useState<'local' | 'cloud'>('local');
  const [cloudFiles, setCloudFiles] = useState<CloudFile[]>([]);
  const [cloudLoading, setCloudLoading] = useState(false);
  const [cloudError, setCloudError] = useState('');
  // Right-click menu over a local or cloud file row.
  const [menu, setMenu] = useState<{ x: number; y: number; items: MenuItem[] } | null>(null);

  const loadCloudFiles = useCallback(async () => {
    setCloudLoading(true); setCloudError('');
    try {
      setCloudFiles(await listCloudFiles());
    } catch (err) {
      logError('workspace.cloud.list', err);
      setCloudError(t('workspace.cloudListError', { defaultValue: 'Could not list cloud files.' }));
      setCloudFiles([]);
    }
    setCloudLoading(false);
  }, [t]);

  useEffect(() => {
    if (tab === 'cloud' && cloudAvailable) loadCloudFiles();
  }, [tab, cloudAvailable, loadCloudFiles]);
  // Fall back to local if the account signs out while on the cloud tab.
  useEffect(() => { if (!cloudAvailable && tab === 'cloud') setTab('local'); }, [cloudAvailable, tab]);

  // Read a local workspace file's raw bytes and upload it to cloud storage.
  const sendToCloud = useCallback(async (file: FileEntry) => {
    try {
      await uploadWorkspaceFileToCloud(file.path, file.name);
      if (tab === 'cloud') loadCloudFiles();
    } catch (err) {
      logError('workspace.sendToCloud', err);
      await alertDialog(t('workspace.sendToCloudError', { defaultValue: 'Could not send this file to the cloud.' }));
    }
  }, [t, tab, loadCloudFiles]);

  const openLocalMenu = useCallback((e: React.MouseEvent, file: FileEntry) => {
    if (file.type !== 'file' || !cloudAvailable) return;
    e.preventDefault();
    setMenu({ x: e.clientX, y: e.clientY, items: [
      { key: 'send', label: t('workspace.sendToCloud', { defaultValue: 'Send to cloud' }), icon: 'export', onClick: () => sendToCloud(file) },
    ] });
  }, [cloudAvailable, t, sendToCloud]);

  const openCloudMenu = useCallback((e: React.MouseEvent, file: CloudFile) => {
    e.preventDefault();
    setMenu({ x: e.clientX, y: e.clientY, items: [
      { key: 'download', label: t('workspace.download', { defaultValue: 'Download' }), icon: 'download', onClick: () => { void startCloudDownload(file); } },
    ] });
  }, [t]);

  const loadRoot = useCallback(async () => {
    try {
      const data = await apiGet<{ root?: string }>('/workspace/root');
      if (data.root) {
        setRootPath(data.root);
        setRootInput(data.root);
      }
    } catch (err) {
      logError('workspace.root.load', err);
    }
  }, []);

  const loadFiles = useCallback(async (p: string) => {
    setLoading(true);
    setSelected(new Set());
    lastSelectedRef.current = null;
    try {
      const data = await apiGet<{ entries?: FileEntry[]; path?: string }>(`/workspace/files?path=${encodeURIComponent(p)}`);
      setFiles(data.entries || []);
      setPath(data.path || p);
    } catch (err) {
      logError('workspace.files.load', err);
      setFiles([]);
    }
    setLoading(false);
  }, []);

  useEffect(() => {
    loadRoot();
    loadFiles('/');
  }, [loadRoot, loadFiles]);

  const handleSetRoot = async () => {
    setRootError('');
    if (!rootInput.trim()) return;
    setRootLoading(true);
    try {
      const data = await apiPost<{ root?: string; detail?: string }>('/workspace/root', { path: rootInput.trim() });
      if (data.root) {
        setRootPath(data.root);
        setRootInput(data.root);
        loadFiles('/');
      }
    } catch (err) {
      logError('workspace.root.change', err);
      if (err instanceof ApiError) {
        const detail = (err.body as { detail?: string } | null)?.detail?.trim();
        setRootError(detail ? `${t('workspace.changeFailed')}: ${detail}` : t('workspace.changeFailed'));
      } else {
        setRootError(t('workspace.networkError'));
      }
    }
    setRootLoading(false);
  };

  const handleDefaultRoot = async () => {
    setRootError('');
    // Default is workspace/ in project dir — we ask the backend to reset
    // by sending empty which the backend doesn't support, so instead
    // we compute the project default client-side or rely on the user
    // to know their path. Simpler: reload current root from API.
    await loadRoot();
    loadFiles('/');
  };

  const handleSelect = (e: React.MouseEvent, file: FileEntry) => {
    const isCtrl = e.ctrlKey || e.metaKey;
    const isShift = e.shiftKey;

    if (isShift && lastSelectedRef.current && fileListRef.current) {
      // Range select
      const names = visibleFiles.map(f => f.path);
      const lastIdx = names.indexOf(lastSelectedRef.current);
      const currIdx = names.indexOf(file.path);
      const [start, end] = lastIdx < currIdx ? [lastIdx, currIdx] : [currIdx, lastIdx];
      const range = visibleFiles.slice(start, end + 1).map(f => f.path);
      setSelected(prev => {
        const next = new Set(prev);
        range.forEach(p => next.add(p));
        return next;
      });
      lastSelectedRef.current = file.path;
      return;
    }

    if (isCtrl) {
      setSelected(prev => {
        const next = new Set(prev);
        if (next.has(file.path)) next.delete(file.path);
        else next.add(file.path);
        return next;
      });
      lastSelectedRef.current = file.path;
      return;
    }

    setSelected(new Set([file.path]));
    lastSelectedRef.current = file.path;
  };

  const handleDoubleClick = async (file: FileEntry) => {
    if (file.type === 'directory') {
      loadFiles(file.path);
      return;
    }
    // Preview file
    setPreviewFile(file.name);
    setPreviewContent('');
    setPreviewLoading(true);
    try {
      const text = await apiGetText(`/workspace/file?path=${encodeURIComponent(file.path)}`);
      setPreviewContent(text);
    } catch (err) {
      logError('workspace.file.preview', err);
      setPreviewContent(err instanceof ApiError ? t('workspace.fileLoadError', { status: err.status }) : t('workspace.networkError'));
    }
    setPreviewLoading(false);
  };

  const handleDragStart = (e: React.DragEvent, file: FileEntry) => {
    if (file.type === 'directory') return;
    if (file.name.endsWith('.json')) {
      // Workflow JSON: prefer workflow-import semantics when dropped on canvas.
      e.dataTransfer.setData('application/bionodulo-workflow-path', file.path);
    }
    // Always set the generic workspace-file mime so non-workflow files (FASTQ,
    // FASTA, ...) can be dropped onto the canvas to spawn an input_file node.
    e.dataTransfer.setData('application/bionodulo-workspace-file', file.path);
    e.dataTransfer.setData('text/plain', file.path);
    e.dataTransfer.effectAllowed = 'copy';
  };

  const isWorkflowFile = (name: string) => name.endsWith('.json');

  const parentPath = (p: string) => {
    if (p === '/' || p === '.' || p === '') return null;
    const parts = p.split('/').filter(Boolean);
    parts.pop();
    return parts.length === 0 ? '/' : '/' + parts.join('/');
  };

  const fileTitle = (file: FileEntry) => {
    if (file.type === 'directory') return t('workspace.directoryOpenTitle');
    if (isWorkflowFile(file.name)) return t('workspace.workflowFileTitle');
    return t('workspace.inputFileTitle');
  };

  const formatFileSize = (bytes: number) => formatBytes(bytes, t, i18n.language);

  return (
    <div className="rail-panel">
      <div className="rail-panel-header">
        <span>{t('workspace.title')}</span>
        <button className="btn btn-icon btn-sm" onClick={onClose} title={t('common.close')} aria-label={t('common.close')}>✕</button>
      </div>

      <div className="rail-panel-body">
        {cloudAvailable && (
          <div className="workspace-tabs" role="tablist">
            <button role="tab" aria-selected={tab === 'local'} className={`workspace-tab ${tab === 'local' ? 'active' : ''}`} onClick={() => setTab('local')}>
              <Icon name="folder" size={13} /> {t('workspace.tabLocal', { defaultValue: 'Local' })}
            </button>
            <button role="tab" aria-selected={tab === 'cloud'} className={`workspace-tab ${tab === 'cloud' ? 'active' : ''}`} onClick={() => setTab('cloud')}>
              <Icon name="server" size={13} /> {t('workspace.tabCloud', { defaultValue: 'Cloud' })}
            </button>
          </div>
        )}

        {tab === 'cloud' && cloudAvailable ? (
          <div className="workspace-cloud">
            <div className="workspace-cloud-toolbar">
              <span className="workspace-cloud-hint">{t('workspace.cloudHint', { defaultValue: 'Right-click a file to download.' })}</span>
              <button className="btn btn-icon btn-sm" onClick={loadCloudFiles} title={t('common.refresh', { defaultValue: 'Refresh' })}><Icon name="activity" size={13} /></button>
            </div>
            {cloudError && <div className="workspace-root-error">{cloudError}</div>}
            {cloudLoading ? (
              <div className="workspace-loading">{t('common.loading')}</div>
            ) : cloudFiles.length === 0 ? (
              <div className="workspace-empty">{t('workspace.cloudEmpty', { defaultValue: 'No cloud files yet.' })}</div>
            ) : (
              <div className="workspace-file-list">
                {cloudFiles.map(f => (
                  <div
                    key={f.key}
                    className="workspace-file-row"
                    onContextMenu={(e) => openCloudMenu(e, f)}
                    onDoubleClick={() => { void startCloudDownload(f); }}
                    title={t('workspace.download', { defaultValue: 'Download' })}
                  >
                    <span className="workspace-file-icon">☁️</span>
                    <span className="workspace-file-name">{f.name}</span>
                    <span className="workspace-file-size">{formatFileSize(f.size)}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        ) : (
        <>
        {/* Root controls */}
        <div className="workspace-root-controls">
          <div className="workspace-root-label">{t('workspace.rootLabel')}</div>
          <div className="workspace-root-row">
            <input
              type="text"
              className="text-input workspace-root-input"
              value={rootInput}
              onChange={e => setRootInput(e.target.value)}
              placeholder={t('workspace.rootPlaceholder')}
              onKeyDown={e => { if (e.key === 'Enter') handleSetRoot(); }}
            />
            <button className="btn btn-sm" onClick={handleSetRoot} disabled={rootLoading} title={t('workspace.setRootTitle')}>
              {rootLoading ? '...' : t('workspace.setRoot')}
            </button>
            <button className="btn btn-sm" onClick={handleDefaultRoot} title={t('workspace.defaultRootTitle')}>
              {t('workspace.defaultRoot')}
            </button>
            {onOpenSettings && (
              <button className="btn btn-icon btn-sm" onClick={onOpenSettings} title={t('workspace.openSettings')}>
                <Icon name="settings" size={14} />
              </button>
            )}
          </div>
          {rootError && <div className="workspace-root-error">{rootError}</div>}
        </div>

        <hr className="workspace-separator" />

        {/* Breadcrumb */}
        <div className="workspace-breadcrumb">
          {parentPath(path) !== null && (
            <span
              className="workspace-breadcrumb-parent"
              onClick={() => { const pp = parentPath(path); if (pp !== null) loadFiles(pp); }}
              title={t('workspace.goUp')}
            >
              <Icon name="arrow-up" size={12} /> ..
            </span>
          )}
          <span className="workspace-breadcrumb-path">{path === '.' ? '/' : path}</span>
          {selected.size > 0 && (
            <span className="workspace-selection-count">{t('workspace.selectedCount', { count: selected.size })}</span>
          )}
        </div>

        {/* File list */}
        {loading ? (
          <div className="workspace-loading">{t('common.loading')}</div>
        ) : (
          <div className="workspace-file-list" ref={fileListRef}>
            {visibleFiles.length === 0 && (
              <div className="workspace-empty">{t('workspace.emptyDirectory')}</div>
            )}
            {visibleFiles.map(file => {
              const isSelected = selected.has(file.path);
              return (
                <div
                  key={file.path}
                  className={`workspace-file-row ${isSelected ? 'selected' : ''}`}
                  onClick={(e) => handleSelect(e, file)}
                  onDoubleClick={() => handleDoubleClick(file)}
                  onContextMenu={(e) => openLocalMenu(e, file)}
                  draggable={file.type === 'file'}
                  onDragStart={(e) => handleDragStart(e, file)}
                  title={fileTitle(file)}
                >
                  <input
                    type="checkbox"
                    className="workspace-file-checkbox"
                    checked={isSelected}
                    onChange={() => {}}
                    onClick={e => e.stopPropagation()}
                  />
                  <span className="workspace-file-icon">
                    {file.type === 'directory' ? '📁' : isWorkflowFile(file.name) ? '🔷' : '📄'}
                  </span>
                  <span className="workspace-file-name">{file.name}</span>
                  {file.size !== undefined && file.type === 'file' && (
                    <span className="workspace-file-size">{formatFileSize(file.size)}</span>
                  )}
                </div>
              );
            })}
          </div>
        )}
        </>
        )}
      </div>

      {menu && <ContextMenu x={menu.x} y={menu.y} items={menu.items} onClose={() => setMenu(null)} />}

      {/* Preview modal */}
      {previewFile && (
        <Dialog
          title={previewFile}
          onClose={() => setPreviewFile(null)}
          width={700}
          maxHeight="80vh"
          hideCloseButton
          footer={(
            <>
              {previewFile.endsWith('.json') && onImportWorkflow && (
                <button
                  className="btn btn-primary"
                  onClick={async () => {
                    try {
                      const wf = JSON.parse(previewContent);
                      onImportWorkflow(wf);
                      setPreviewFile(null);
                    } catch {
                      await alertDialog(t('workspace.invalidWorkflowJson'));
                    }
                  }}
                >
                  {t('workspace.loadAsWorkflow')}
                </button>
              )}
              <button className="btn" onClick={() => navigator.clipboard.writeText(previewContent)}>{t('common.copy')}</button>
              <button className="btn" onClick={() => setPreviewFile(null)}>{t('common.close')}</button>
            </>
          )}
        >
          {previewLoading ? (
            <div>{t('common.loading')}</div>
          ) : (
            <textarea
              readOnly
              value={previewContent}
              style={{ width: '100%', minHeight: 300, fontFamily: 'JetBrains Mono, monospace', fontSize: 11, padding: 12, border: '1px solid var(--border)', borderRadius: 8, background: 'var(--surface-2)', color: 'var(--text)', resize: 'vertical' }}
            />
          )}
        </Dialog>
      )}
    </div>
  );
}

function formatBytes(bytes: number, t: TFunction, language: string): string {
  const whole = new Intl.NumberFormat(language, { maximumFractionDigits: 0 });
  const decimal = new Intl.NumberFormat(language, {
    maximumFractionDigits: 1,
    minimumFractionDigits: 1,
  });

  if (bytes < 1024) return t('workspace.sizeBytes', { size: whole.format(bytes) });
  if (bytes < 1024 * 1024) return t('workspace.sizeKB', { size: decimal.format(bytes / 1024) });
  if (bytes < 1024 * 1024 * 1024) {
    return t('workspace.sizeMB', { size: decimal.format(bytes / (1024 * 1024)) });
  }
  return t('workspace.sizeGB', { size: decimal.format(bytes / (1024 * 1024 * 1024)) });
}
