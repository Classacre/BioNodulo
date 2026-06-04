import { useState, useEffect, useCallback, useRef } from 'react';
import Icon from '../ui/Icon';
import { alertDialog } from '../ui';
import { apiGet, apiGetText, apiPost, ApiError } from '../../api/client';

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
  const [path, setPath] = useState('/');
  const [files, setFiles] = useState<FileEntry[]>([]);
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

  const loadRoot = useCallback(async () => {
    try {
      const data = await apiGet<{ root?: string }>('/workspace/root');
      if (data.root) {
        setRootPath(data.root);
        setRootInput(data.root);
      }
    } catch { /* backend unavailable */ }
  }, []);

  const loadFiles = useCallback(async (p: string) => {
    setLoading(true);
    setSelected(new Set());
    lastSelectedRef.current = null;
    try {
      const data = await apiGet<{ entries?: FileEntry[]; path?: string }>(`/workspace/files?path=${encodeURIComponent(p)}`);
      setFiles(data.entries || []);
      setPath(data.path || p);
    } catch {
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
      if (err instanceof ApiError) {
        const detail = (err.body as { detail?: string } | null)?.detail;
        setRootError(detail || 'Failed to change workspace');
      } else {
        setRootError('Network error');
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
      const names = files.map(f => f.path);
      const lastIdx = names.indexOf(lastSelectedRef.current);
      const currIdx = names.indexOf(file.path);
      const [start, end] = lastIdx < currIdx ? [lastIdx, currIdx] : [currIdx, lastIdx];
      const range = files.slice(start, end + 1).map(f => f.path);
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
      setPreviewContent(err instanceof ApiError ? `Error loading file: ${err.status}` : 'Network error');
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

  return (
    <div className="rail-panel">
      <div className="rail-panel-header">
        <span>Workspace</span>
        <button className="btn btn-icon btn-sm" onClick={onClose}>✕</button>
      </div>

      <div className="rail-panel-body">
        {/* Root controls */}
        <div className="workspace-root-controls">
          <div className="workspace-root-label">Workspace Root</div>
          <div className="workspace-root-row">
            <input
              type="text"
              className="text-input workspace-root-input"
              value={rootInput}
              onChange={e => setRootInput(e.target.value)}
              placeholder="/path/to/workspace"
              onKeyDown={e => { if (e.key === 'Enter') handleSetRoot(); }}
            />
            <button className="btn btn-sm" onClick={handleSetRoot} disabled={rootLoading} title="Set workspace root">
              {rootLoading ? '...' : 'Set'}
            </button>
            <button className="btn btn-sm" onClick={handleDefaultRoot} title="Reload current root">
              Default
            </button>
            {onOpenSettings && (
              <button className="btn btn-icon btn-sm" onClick={onOpenSettings} title="Open settings">
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
              title="Go up"
            >
              <Icon name="arrow-up" size={12} /> ..
            </span>
          )}
          <span className="workspace-breadcrumb-path">{path === '.' ? '/' : path}</span>
          {selected.size > 0 && (
            <span className="workspace-selection-count">{selected.size} selected</span>
          )}
        </div>

        {/* File list */}
        {loading ? (
          <div className="workspace-loading">Loading...</div>
        ) : (
          <div className="workspace-file-list" ref={fileListRef}>
            {files.length === 0 && (
              <div className="workspace-empty">No files in this directory</div>
            )}
            {files.map(file => {
              const isSelected = selected.has(file.path);
              return (
                <div
                  key={file.path}
                  className={`workspace-file-row ${isSelected ? 'selected' : ''}`}
                  onClick={(e) => handleSelect(e, file)}
                  onDoubleClick={() => handleDoubleClick(file)}
                  draggable={file.type === 'file'}
                  onDragStart={(e) => handleDragStart(e, file)}
                  title={file.type === 'directory' ? 'Double-click to open' : isWorkflowFile(file.name) ? 'Double-click to preview, drag to canvas to import' : 'Double-click to preview, drag to canvas to add as input'}
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
                    <span className="workspace-file-size">{formatBytes(file.size)}</span>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Preview modal */}
      {previewFile && (
        <div className="modal-overlay" onClick={() => setPreviewFile(null)}>
          <div className="modal-content" style={{ width: 700, maxHeight: '80vh' }} onClick={e => e.stopPropagation()}>
            <div className="modal-header">{previewFile}</div>
            <div className="modal-body">
              {previewLoading ? (
                <div>Loading...</div>
              ) : (
                <textarea
                  readOnly
                  value={previewContent}
                  style={{ width: '100%', minHeight: 300, fontFamily: 'JetBrains Mono, monospace', fontSize: 11, padding: 12, border: '1px solid var(--border)', borderRadius: 8, background: 'var(--surface-2)', color: 'var(--text)', resize: 'vertical' }}
                />
              )}
            </div>
            <div className="modal-footer">
              {previewFile.endsWith('.json') && onImportWorkflow && (
                <button
                  className="btn btn-primary"
                  onClick={async () => {
                    try {
                      const wf = JSON.parse(previewContent);
                      onImportWorkflow(wf);
                      setPreviewFile(null);
                    } catch {
                      await alertDialog('Invalid workflow JSON');
                    }
                  }}
                >
                  Load as Workflow
                </button>
              )}
              <button className="btn" onClick={() => navigator.clipboard.writeText(previewContent)}>Copy</button>
              <button className="btn" onClick={() => setPreviewFile(null)}>Close</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(1)} GB`;
}
