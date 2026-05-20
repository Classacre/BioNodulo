import { useEffect, useState } from 'react';
import type { TemplateInfo } from '../../types';
import Icon from '../ui/Icon';
import { listLocalTemplates } from '../../localTemplates';

interface TemplatesPanelProps {
  onClose: () => void;
  onLoadTemplate: (template: TemplateInfo) => void;
}

export default function TemplatesPanel({ onClose, onLoadTemplate }: TemplatesPanelProps) {
  const [templates, setTemplates] = useState<TemplateInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState('');
  const [catFilter, setCatFilter] = useState<string>('All');

  useEffect(() => {
    let cancelled = false;
    fetch('/api/workflow_templates')
      .then(r => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then(data => {
        if (cancelled) return;
        const items: TemplateInfo[] = (data.templates || []).map((t: any) => ({
          id: t.id || t.filename.replace('.json', ''),
          name: t.name || t.filename.replace('.json', '').replace(/_/g, ' '),
          description: t.description || '',
          category: t.category || 'Other',
          tags: t.tags || [],
          tools: t.tools || [],
          node_count: t.node_count || 0,
          filename: t.filename,
        }));
        setTemplates(items);
        setLoading(false);
      })
      .catch(err => {
        if (cancelled) return;
        const localTemplates = listLocalTemplates();
        setTemplates(localTemplates);
        setError(localTemplates.length > 0 ? null : err.message);
        setLoading(false);
      });
    return () => { cancelled = true; };
  }, []);

  const categories = ['All', ...Array.from(new Set(templates.map(t => t.category)))];
  const filtered = templates.filter(t => {
    const matchCat = catFilter === 'All' || t.category === catFilter;
    const q = filter.toLowerCase();
    const matchFilter = !q || t.name.toLowerCase().includes(q) || t.description.toLowerCase().includes(q) || t.tags.some(tag => tag.includes(q)) || t.tools.some(tool => tool.toLowerCase().includes(q));
    return matchCat && matchFilter;
  });

  return (
    <div className="rail-panel">
      <div className="rail-panel-header">
        <span>Templates</span>
        <button className="btn btn-icon btn-sm" onClick={onClose}><Icon name="close" size={14} /></button>
      </div>
      <div className="rail-panel-body">
        <input className="palette-search" placeholder="Search templates..." value={filter} onChange={e => setFilter(e.target.value)} style={{ marginBottom: 8 }} />
        <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap', marginBottom: 12 }}>
          {categories.map(c => (
            <button key={c} className={`env-type-tab ${catFilter === c ? 'active' : ''}`} onClick={() => setCatFilter(c)} style={{ padding: '3px 10px', fontSize: 11 }}>
              {c}
            </button>
          ))}
        </div>
        {loading && <div style={{ color: 'var(--muted)', fontSize: 12, padding: 12 }}>Loading templates...</div>}
        {error && <div style={{ color: '#ef4444', fontSize: 12, padding: 12 }}>Error: {error}</div>}
        {!loading && !error && (
          <div className="template-grid">
            {filtered.map(t => (
              <div key={t.id} className="template-card" onClick={() => onLoadTemplate(t)}>
                <h4>{t.name}</h4>
                <p>{t.description}</p>
                <div className="tags">
                  {t.tools.slice(0, 4).map(tool => <span key={tool} className="template-tag">{tool}</span>)}
                  <span className="template-tag" style={{ background: 'var(--surface-2)', color: 'var(--muted)' }}>{t.node_count} nodes</span>
                </div>
              </div>
            ))}
            {filtered.length === 0 && <div style={{ color: 'var(--muted)', fontSize: 12 }}>No templates match your search.</div>}
          </div>
        )}
      </div>
    </div>
  );
}
