import { useState } from 'react';
import type { ObjectInfo, NodeMetadata } from '../../types';
import { groupNodesByCategory, filterNodes } from '../../utils';
import Icon from '../ui/Icon';

interface NodeLibraryPanelProps {
  objectInfo: ObjectInfo;
  onAddNode: (meta: NodeMetadata) => void;
  onClose: () => void;
}

export default function NodeLibraryPanel({ objectInfo, onAddNode, onClose: _onClose }: NodeLibraryPanelProps) {
  const [query, setQuery] = useState('');
  const [expanded, setExpanded] = useState<Set<string>>(new Set());

  const filtered = filterNodes(objectInfo, query);
  const grouped = groupNodesByCategory(filtered);

  const toggle = (cat: string) => {
    setExpanded(prev => {
      const n = new Set(prev);
      n.has(cat) ? n.delete(cat) : n.add(cat);
      return n;
    });
  };

  return (
    <div className="rail-panel">
      <div className="rail-panel-header">Node Library</div>
      <div className="rail-panel-body">
        <div style={{ position: 'relative', marginBottom: 8 }}>
          <input className="palette-search" placeholder="Search nodes..." value={query} onChange={e => setQuery(e.target.value)} />
          <span style={{ position: 'absolute', left: 8, top: 8, color: 'var(--muted)' }}><Icon name="search" size={14} /></span>
        </div>
        <div style={{ fontSize: 11, color: 'var(--muted)', marginBottom: 8 }}>
          {Object.values(objectInfo).length} nodes available
        </div>
        <div style={{ maxHeight: 'calc(100vh - 200px)', overflowY: 'auto' }}>
          {Object.entries(grouped).map(([cat, nodes]) => (
            <div key={cat} style={{ marginBottom: 4 }}>
              <button onClick={() => toggle(cat)} style={{ width: '100%', textAlign: 'left', padding: '6px 8px', border: 'none', background: 'none', cursor: 'pointer', fontSize: 11, fontWeight: 700, color: 'var(--muted)', display: 'flex', alignItems: 'center', gap: 4 }}>
                {expanded.has(cat) ? '▾' : '▸'} {cat} <span style={{ fontWeight: 400 }}>({nodes.length})</span>
              </button>
              {expanded.has(cat) && nodes.map(meta => (
                <div key={meta.id} style={{ padding: '6px 12px 6px 24px', cursor: 'pointer', borderRadius: 6, fontSize: 12, transition: 'background 0.1s', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }} onClick={() => onAddNode(meta)} onMouseEnter={e => (e.currentTarget.style.background = 'var(--accent-light)')} onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}>
                  <div>
                    <div style={{ fontWeight: 500 }}>{meta.display_name}</div>
                    <div style={{ fontSize: 10, color: 'var(--muted)' }}>{meta.description?.slice(0, 60)}...</div>
                  </div>
                  <button className="btn btn-icon btn-sm" title="Add to workflow"><Icon name="plus" size={12} /></button>
                </div>
              ))}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
