import { useState } from 'react';
import type { ObjectInfo, NodeMetadata } from '../../types';
import { groupNodesByCategory, filterNodes } from '../../utils';
import Icon from '../ui/Icon';

interface NodePaletteProps {
  objectInfo: ObjectInfo;
  onSelect: (meta: NodeMetadata) => void;
  onClose: () => void;
  style?: React.CSSProperties;
}

export default function NodePalette({ objectInfo, onSelect, onClose, style }: NodePaletteProps) {
  const [query, setQuery] = useState('');
  const [expanded, setExpanded] = useState<Set<string>>(new Set(['Input', 'Quality Control']));
  const filtered = filterNodes(objectInfo, query);
  const grouped = groupNodesByCategory(filtered);

  const toggleCategory = (cat: string) => {
    setExpanded(prev => {
      const next = new Set(prev);
      if (next.has(cat)) next.delete(cat); else next.add(cat);
      return next;
    });
  };

  return (
    <div className="context-menu" style={{ ...style, width: 300, maxHeight: 480 }}>
      <div className="context-menu-header">
        <span>Add Node</span>
        <button className="btn btn-icon btn-sm" onClick={onClose}><Icon name="close" size={14} /></button>
      </div>
      <div style={{ padding: 8 }}>
        <div style={{ position: 'relative', marginBottom: 8 }}>
          <Icon name="search" size={14} />
          <input
            className="palette-search"
            placeholder="Search nodes..."
            value={query}
            onChange={e => setQuery(e.target.value)}
            autoFocus
            style={{ paddingLeft: 28 }}
          />
          <span style={{ position: 'absolute', left: 8, top: 8, color: 'var(--muted)' }}>
            <Icon name="search" size={14} />
          </span>
        </div>
        <div style={{ maxHeight: 360, overflowY: 'auto' }}>
          {Object.entries(grouped).map(([cat, nodes]) => (
            <div key={cat}>
              <button
                onClick={() => toggleCategory(cat)}
                style={{ width: '100%', textAlign: 'left', padding: '4px 8px', border: 'none', background: 'none', cursor: 'pointer', fontSize: 11, fontWeight: 700, color: 'var(--muted)', textTransform: 'uppercase', letterSpacing: '0.03em', display: 'flex', alignItems: 'center', gap: 4 }}
              >
                <span>{expanded.has(cat) ? '▾' : '▸'}</span> {cat} ({nodes.length})
              </button>
              {expanded.has(cat) && nodes.map(meta => (
                <div key={meta.id} className="palette-node" onClick={() => onSelect(meta)}>
                  <strong>{meta.display_name}</strong>
                  {meta.description && <small>{meta.description}</small>}
                </div>
              ))}
            </div>
          ))}
          {filtered.length === 0 && (
            <div style={{ padding: 16, color: 'var(--muted)', textAlign: 'center', fontSize: 12 }}>
              No nodes match "{query}"
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
