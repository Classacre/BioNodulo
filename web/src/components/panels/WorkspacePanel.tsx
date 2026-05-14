import { useState, useEffect } from 'react';

interface FileEntry {
  name: string;
  type: 'file' | 'directory';
  size?: number;
  mtime?: string;
}

interface WorkspacePanelProps {
  onClose: () => void;
}

export default function WorkspacePanel({ onClose }: WorkspacePanelProps) {
  const [path, setPath] = useState('/');
  const [files, setFiles] = useState<FileEntry[]>([]);
  const [loading, setLoading] = useState(false);
  const [rootPath, setRootPath] = useState('');

  const loadFiles = async (p: string) => {
    setLoading(true);
    try {
      const r = await fetch(`/api/workspace/files?path=${encodeURIComponent(p)}`);
      if (r.ok) {
        const data = await r.json();
        setFiles(data.files || []);
        setPath(data.path || p);
      } else {
        setFiles([]);
      }
    } catch {
      // Mock data when backend unavailable
      setFiles([
        { name: 'data', type: 'directory' },
        { name: 'results', type: 'directory' },
        { name: 'references', type: 'directory' },
        { name: 'README.md', type: 'file', size: 1024 },
      ]);
    }
    setLoading(false);
  };

  useEffect(() => {
    loadFiles('/');
    fetch('/api/workspace/root')
      .then(r => r.ok ? r.json() : null)
      .then(data => {
        if (data?.root) setRootPath(data.root);
      })
      .catch(() => {});
  }, []);

  return (
    <div className="rail-panel">
      <div className="rail-panel-header">
        <span>Workspace</span>
        <button className="btn btn-icon btn-sm" onClick={onClose}>✕</button>
      </div>
      <div className="rail-panel-body">
        {rootPath && (
          <div style={{ fontSize: 10, color: 'var(--muted)', marginBottom: 4, padding: '2px 8px' }} title="Workspace root">
            Root: {rootPath}
          </div>
        )}
        <div style={{ fontSize: 11, color: 'var(--muted)', marginBottom: 8, padding: '4px 8px', background: 'var(--surface-2)', borderRadius: 4 }}>
          {path}
        </div>
        {loading ? (
          <div style={{ color: 'var(--muted)', fontSize: 12, padding: 20, textAlign: 'center' }}>Loading...</div>
        ) : (
          <div>
            {path !== '/' && (
              <div
                style={{ padding: '6px 8px', cursor: 'pointer', fontSize: 12, borderRadius: 6, display: 'flex', alignItems: 'center', gap: 8 }}
                onClick={() => { const parent = path.split('/').slice(0, -1).join('/') || '/'; loadFiles(parent); }}
                onMouseEnter={e => (e.currentTarget.style.background = 'var(--surface-2)')}
                onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}
              >
                📁 ..
              </div>
            )}
            {files.map(f => (
              <div
                key={f.name}
                style={{ padding: '6px 8px', cursor: 'pointer', fontSize: 12, borderRadius: 6, display: 'flex', alignItems: 'center', gap: 8 }}
                onClick={() => f.type === 'directory' ? loadFiles(`${path === '/' ? '' : path}/${f.name}`) : undefined}
                onMouseEnter={e => (e.currentTarget.style.background = 'var(--surface-2)')}
                onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}
              >
                {f.type === 'directory' ? '📁' : '📄'} {f.name}
                {f.size !== undefined && <span style={{ marginLeft: 'auto', color: 'var(--muted)', fontSize: 10 }}>{(f.size / 1024).toFixed(1)} KB</span>}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
