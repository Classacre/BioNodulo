import { useState, useEffect, useCallback, useMemo } from 'react';
import type { WorkflowTemplate } from './types';
import type { Workflow } from '../types';
import Icon from '../components/ui/Icon';
import { promptDialog } from '../components/ui';
import { apiGet, apiPost } from '../api/client';

const API_BASE = 'api/collab';

interface TemplateGalleryProps {
  isOpen: boolean;
  currentWorkflowId: string | null;
  onClose: () => void;
  onFork: (fork: { workflowId: string; workflow?: Workflow }) => void;
}

function timeAgo(ts: string): string {
  const s = Math.floor((Date.now() - new Date(ts).getTime()) / 1000);
  if (s < 60) return 'just now';
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
  return `${Math.floor(s / 86400)}d ago`;
}

export default function TemplateGallery({ isOpen, currentWorkflowId, onClose, onFork }: TemplateGalleryProps) {
  const [templates, setTemplates] = useState<WorkflowTemplate[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState('');
  const [activeTag, setActiveTag] = useState<string | null>(null);
  const [forkingId, setForkingId] = useState<string | null>(null);
  const [savingWorkflowId, setSavingWorkflowId] = useState<string | null>(null);

  const fetchTemplates = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (search) params.set('search', search);
      if (activeTag) params.set('tags', activeTag);
      const query = params.toString();
      const data = await apiGet<{ templates: WorkflowTemplate[]; count: number }>(
        `${API_BASE}/templates${query ? `?${query}` : ''}`,
      );
      setTemplates(data.templates ?? []);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load templates');
    } finally {
      setLoading(false);
    }
  }, [search, activeTag]);

  useEffect(() => {
    if (!isOpen) return;
    fetchTemplates();
  }, [isOpen, fetchTemplates]);

  const allTags = useMemo(() => {
    const set = new Set<string>();
    templates.forEach(t => {
      t.tags.split(',').forEach(tag => { const s = tag.trim(); if (s) set.add(s); });
    });
    return Array.from(set).slice(0, 20);
  }, [templates]);

  const handleFork = async (templateId: string) => {
    setForkingId(templateId);
    try {
      const data = await apiPost<{ workflow_id?: string; workflow?: Workflow }>(
        `${API_BASE}/templates/${templateId}/fork`,
      );
      const workflowId = data.workflow_id || data.workflow?.id;
      if (workflowId) {
        onFork({ workflowId, workflow: data.workflow });
      }
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Fork failed');
    } finally {
      setForkingId(null);
    }
  };

  const handleSaveAsTemplate = async () => {
    if (!currentWorkflowId) {
      setError('No active workflow to save as a template');
      return;
    }
    const title = await promptDialog({
      title: 'Save template',
      message: 'Name this shared workflow template.',
      inputLabel: 'Template title',
      confirmLabel: 'Next',
    });
    if (!title) return;
    const description = await promptDialog({
      title: 'Template description',
      message: 'Add a short description for this template.',
      inputLabel: 'Description',
      confirmLabel: 'Next',
    }) || '';
    const tags = await promptDialog({
      title: 'Template tags',
      message: 'Add comma-separated tags.',
      inputLabel: 'Tags',
      placeholder: 'rna, alignment, qc',
      confirmLabel: 'Save Template',
    }) || '';
    setSavingWorkflowId(currentWorkflowId);
    try {
      await apiPost(`${API_BASE}/templates`, {
        workflow_id: currentWorkflowId,
        title,
        description,
        tags,
        is_public: true,
      });
      fetchTemplates();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save template');
    } finally {
      setSavingWorkflowId(null);
    }
  };

  if (!isOpen) return null;

  return (
    <div style={{
      position: 'fixed', top: 0, right: 0, width: 320, height: '100vh',
      background: 'var(--surface)', borderLeft: '1px solid var(--border)',
      zIndex: 50, display: 'flex', flexDirection: 'column', transition: 'transform 0.2s ease',
      boxShadow: '-4px 0 12px rgba(0,0,0,0.15)',
    }}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '12px 14px', borderBottom: '1px solid var(--border)' }}>
        <strong style={{ fontSize: 14 }}>Template Gallery</strong>
        <div style={{ display: 'flex', gap: 6 }}>
          <button className="btn btn-xs" onClick={handleSaveAsTemplate} disabled={!!savingWorkflowId || !currentWorkflowId} style={{ fontSize: 10 }}>
            {savingWorkflowId ? 'Saving...' : '+ Save'}
          </button>
          <button className="btn btn-icon btn-xs" onClick={onClose} title="Close"><Icon name="close" size={12} /></button>
        </div>
      </div>

      {/* Search */}
      <div style={{ padding: '8px 14px', borderBottom: '1px solid var(--border)' }}>
        <input
          type="text"
          value={search}
          onChange={e => setSearch(e.target.value)}
          placeholder="Search templates..."
          onKeyDown={e => e.key === 'Enter' && fetchTemplates()}
          style={{
            width: '100%', fontSize: 12, padding: '6px 10px', borderRadius: 4,
            border: '1px solid var(--border)', background: 'var(--surface-2)',
            color: 'var(--text)', boxSizing: 'border-box',
          }}
        />
      </div>

      {/* Tag filter chips */}
      {allTags.length > 0 && (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, padding: '6px 14px', borderBottom: '1px solid var(--border)' }}>
          <button
            className="btn btn-xs"
            onClick={() => setActiveTag(null)}
            style={{ fontSize: 9, padding: '2px 8px', background: activeTag === null ? 'var(--accent, #3b82f6)' : undefined, color: activeTag === null ? '#fff' : undefined }}
          >All</button>
          {allTags.map(tag => (
            <button
              key={tag}
              className="btn btn-xs"
              onClick={() => setActiveTag(tag === activeTag ? null : tag)}
              style={{ fontSize: 9, padding: '2px 8px', background: tag === activeTag ? 'var(--accent, #3b82f6)' : undefined, color: tag === activeTag ? '#fff' : undefined }}
            >{tag}</button>
          ))}
        </div>
      )}

      {error && <div style={{ padding: '8px 14px', fontSize: 11, color: '#ef4444', background: '#ef444410' }}>{error}</div>}

      {/* Template grid */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '8px 0' }}>
        {loading && templates.length === 0 && <div style={{ padding: 20, textAlign: 'center', fontSize: 12, color: 'var(--muted)' }}>Loading templates...</div>}
        {templates.length === 0 && !loading && <div style={{ padding: 20, textAlign: 'center', fontSize: 12, color: 'var(--muted)' }}>No templates found.</div>}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6, padding: '0 10px' }}>
          {templates.map(t => (
            <div key={t.id} style={{
              padding: 10, borderRadius: 8, border: '1px solid var(--border)',
              background: 'var(--surface-2)', display: 'flex', flexDirection: 'column', gap: 4,
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                <strong style={{ fontSize: 12, fontWeight: 600 }}>{t.title}</strong>
                <span style={{ fontSize: 9, color: 'var(--muted)' }}>{timeAgo(t.created_at)}</span>
              </div>
              <p style={{ fontSize: 11, color: 'var(--muted)', margin: 0, lineHeight: 1.4, display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical', overflow: 'hidden' }}>
                {t.description}
              </p>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 2 }}>
                <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
                  {t.tags.split(',').map(tag => { const s = tag.trim(); return s ? (
                    <span key={s} style={{ fontSize: 9, padding: '1px 6px', borderRadius: 4, background: 'var(--surface)', color: 'var(--muted)' }}>{s}</span>
                  ) : null; })}
                </div>
                <span style={{ fontSize: 10, color: 'var(--muted)', display: 'inline-flex', alignItems: 'center', gap: 3 }}>
                  <Icon name="copy" size={10} /> {t.fork_count}
                </span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 2 }}>
                <span style={{ fontSize: 10, color: 'var(--muted)' }}>by {t.user_id.slice(0, 8)}</span>
                <button
                  className="btn btn-sm"
                  onClick={() => handleFork(t.id)}
                  disabled={forkingId === t.id}
                  style={{ fontSize: 10, padding: '3px 12px' }}
                >
                  {forkingId === t.id ? 'Forking...' : 'Fork'}
                </button>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
