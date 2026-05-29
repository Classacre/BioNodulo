import { useEffect, useMemo, useState } from 'react';
import type { FormEvent } from 'react';
import Fuse from 'fuse.js';
import type { TemplateInfo } from '../../types';
import Icon from '../ui/Icon';
import Dialog from '../ui/Dialog';
import { listLocalTemplates } from '../../localTemplates';
import { getTemplateUsageMap, recordTemplateUse, subscribeTemplateUsage } from '../../state/templateUsage';
import { getOrRenderTemplateThumbnail } from '../../state/templateThumbnails';
import { apiGet, ApiError } from '../../api/client';

export type TemplateSortMode = 'ranked' | 'name' | 'category' | 'node_count' | 'recent';

export interface TemplateSaveDraft {
  name: string;
  description: string;
  category: string;
  tags: string[];
}

type TemplateCardInfo = TemplateInfo & {
  thumbnail_url?: string;
  thumbnail?: string;
  preview_url?: string;
  preview_steps?: string[];
  updated_at?: string;
  usage_count?: number;
};

interface TemplatesPanelProps {
  onClose: () => void;
  onLoadTemplate: (template: TemplateInfo) => void;
  onSaveTemplate?: (draft: TemplateSaveDraft) => void | Promise<void>;
  isSavingTemplate?: boolean;
  showSaveTemplateAction?: boolean;
  saveTemplateInitialName?: string;
  saveTemplateInitialDescription?: string;
  sortMode?: TemplateSortMode;
  onSortModeChange?: (sortMode: TemplateSortMode) => void;
}

interface RankedTemplate {
  template: TemplateCardInfo;
  score: number;
}

const SORT_LABELS: Record<TemplateSortMode, string> = {
  ranked: 'Best match',
  name: 'Name',
  category: 'Category',
  node_count: 'Node count',
  recent: 'Updated',
};

function normalizeTags(input: string): string[] {
  return input.split(',')
    .map(tag => tag.trim())
    .filter(Boolean);
}

function templateThumbnailUrl(template: TemplateCardInfo): string | undefined {
  return template.thumbnail_url || template.thumbnail || template.preview_url;
}

function scoreTemplate(template: TemplateCardInfo, searchScore: number, index: number, localUsage: number): number {
  const hasDescription = template.description.trim().length > 0 ? 0.08 : 0;
  const tagDepth = Math.min(template.tags.length, 6) * 0.015;
  const toolDepth = Math.min(template.tools.length, 6) * 0.01;
  const nodeBalance = template.node_count > 0 ? Math.min(template.node_count, 12) * 0.006 : 0;
  const usageBoost = Math.min(template.usage_count || 0, 10) * 0.006;
  // Local usage carries more weight than server usage_count: it reflects what
  // *this* user reaches for, not a global popularity score. Cap at 20 so a
  // single power-user template doesn't sit on top forever.
  const localUsageBoost = Math.min(localUsage, 20) * 0.012;
  const positionalPenalty = index * 0.002;
  const base = 1 - Math.min(searchScore, 1);
  return Math.max(0, Math.min(1, base + hasDescription + tagDepth + toolDepth + nodeBalance + usageBoost + localUsageBoost - positionalPenalty));
}

function templateSummary(template: TemplateCardInfo): string {
  if (template.description.trim()) return template.description;
  const steps = template.preview_steps?.slice(0, 3).join(' -> ');
  return steps ? `${template.category} workflow: ${steps}` : `${template.category} workflow template`;
}

function compactStep(step: string): string {
  return step.replace(/_/g, ' ').replace(/\s+/g, ' ').trim();
}

function sortRankedTemplates(items: RankedTemplate[], mode: TemplateSortMode): RankedTemplate[] {
  const next = [...items];
  next.sort((a, b) => {
    if (mode === 'name') return a.template.name.localeCompare(b.template.name);
    if (mode === 'category') {
      const category = a.template.category.localeCompare(b.template.category);
      return category || a.template.name.localeCompare(b.template.name);
    }
    if (mode === 'node_count') return b.template.node_count - a.template.node_count || a.template.name.localeCompare(b.template.name);
    if (mode === 'recent') {
      const aTime = a.template.updated_at ? Date.parse(a.template.updated_at) : 0;
      const bTime = b.template.updated_at ? Date.parse(b.template.updated_at) : 0;
      return bTime - aTime || a.template.name.localeCompare(b.template.name);
    }
    return b.score - a.score || a.template.name.localeCompare(b.template.name);
  });
  return next;
}

function TemplateThumbnail({ template }: { template: TemplateCardInfo }) {
  const url = templateThumbnailUrl(template);
  const initials = template.name.split(/\s+/).filter(Boolean).slice(0, 2).map(part => part[0]?.toUpperCase()).join('') || 'T';

  // When no server-supplied thumbnail URL exists, fetch the workflow JSON and
  // render an in-browser PNG (with the workflow embedded via tEXt) so a drag
  // off the card lands a workflow-bearing PNG identical to an export.
  const [renderedUrl, setRenderedUrl] = useState<string | null>(null);
  useEffect(() => {
    if (url || !template.filename) return;
    let cancelled = false;
    apiGet<{ workflow?: unknown; nodes?: unknown[] }>(
      `/workflow_templates/${encodeURIComponent(template.filename)}`,
    )
      .then(data => {
        if (cancelled) return;
        const workflow = (data.workflow ?? data) as unknown;
        if (!workflow || typeof workflow !== 'object') return;
        const result = getOrRenderTemplateThumbnail(template.id, workflow as never);
        if (result) setRenderedUrl(result.objectUrl);
      })
      .catch(() => { /* network/parse error — fall back to initials block */ });
    return () => { cancelled = true; };
  }, [url, template.id, template.filename]);

  const finalUrl = url || renderedUrl;

  return (
    <div className="template-thumbnail" aria-hidden="true">
      {finalUrl ? (
        <img src={finalUrl} alt="" onError={event => { (event.currentTarget as HTMLImageElement).style.display = 'none'; }} />
      ) : (
        <div className="template-thumbnail-generated">
          <span className="template-thumbnail-initials">{initials}</span>
          <span className="template-thumbnail-line line-a" />
          <span className="template-thumbnail-line line-b" />
          <span className="template-thumbnail-node node-a" />
          <span className="template-thumbnail-node node-b" />
          <span className="template-thumbnail-node node-c" />
        </div>
      )}
    </div>
  );
}

function TemplateSkeletons() {
  return (
    <div className="template-grid">
      {[0, 1, 2, 3].map(index => (
        <div key={index} className="template-card template-card-skeleton">
          <div className="template-skeleton-thumb" />
          <div className="template-skeleton-line wide" />
          <div className="template-skeleton-line" />
          <div className="template-skeleton-tags">
            <span />
            <span />
            <span />
          </div>
        </div>
      ))}
    </div>
  );
}

export default function TemplatesPanel({
  onClose,
  onLoadTemplate,
  onSaveTemplate,
  isSavingTemplate = false,
  showSaveTemplateAction = false,
  saveTemplateInitialName = '',
  saveTemplateInitialDescription = '',
  sortMode,
  onSortModeChange,
}: TemplatesPanelProps) {
  const [templates, setTemplates] = useState<TemplateCardInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState('');
  const [catFilter, setCatFilter] = useState<string>('All');
  const [internalSortMode, setInternalSortMode] = useState<TemplateSortMode>('ranked');
  const [saveOpen, setSaveOpen] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [saveDraft, setSaveDraft] = useState({
    name: saveTemplateInitialName,
    description: saveTemplateInitialDescription,
    category: 'Custom',
    tags: '',
  });
  const activeSortMode = sortMode || internalSortMode;

  // Re-render on local usage changes so the "ranked" sort picks up freshly-
  // loaded templates without a page refresh.
  const [usageVersion, setUsageVersion] = useState(0);
  useEffect(() => subscribeTemplateUsage(() => setUsageVersion(v => v + 1)), []);
  const localUsageMap = useMemo(() => getTemplateUsageMap(), [usageVersion]);

  useEffect(() => {
    let cancelled = false;
    apiGet<{ templates?: unknown[] }>('/workflow_templates')
      .then(data => {
        if (cancelled) return;
        const items: TemplateCardInfo[] = ((data.templates || []) as Record<string, unknown>[]).map((t: any) => ({
          id: t.id || t.filename.replace('.json', ''),
          name: t.name || t.filename.replace('.json', '').replace(/_/g, ' '),
          description: t.description || '',
          category: t.category || 'Other',
          tags: t.tags || [],
          tools: t.tools || [],
          node_count: t.node_count || 0,
          filename: t.filename,
          thumbnail_url: t.thumbnail_url || t.thumbnail || t.preview_url,
          updated_at: t.updated_at || t.modified_at || t.updatedAt,
          usage_count: Number(t.usage_count || t.uses || 0),
          preview_steps: Array.isArray(t.preview_steps) ? t.preview_steps : [],
        }));
        setTemplates(items);
        setLoading(false);
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        const localTemplates = listLocalTemplates() as TemplateCardInfo[];
        setTemplates(localTemplates);
        const message = err instanceof ApiError ? `${err.status} ${err.statusText}` : err instanceof Error ? err.message : String(err);
        setError(localTemplates.length > 0 ? null : message);
        setLoading(false);
      });
    return () => { cancelled = true; };
  }, []);

  const categories = useMemo(
    () => ['All', ...Array.from(new Set(templates.map(t => t.category))).sort((a, b) => a.localeCompare(b))],
    [templates],
  );

  const fuse = useMemo(() => new Fuse(templates, {
    includeScore: true,
    ignoreLocation: true,
    threshold: 0.38,
    keys: [
      { name: 'name', weight: 0.35 },
      { name: 'description', weight: 0.24 },
      { name: 'category', weight: 0.16 },
      { name: 'tags', weight: 0.14 },
      { name: 'tools', weight: 0.11 },
    ],
  }), [templates]);

  const rankedTemplates = useMemo(() => {
    const q = filter.trim();
    const localUsageFor = (id: string) => localUsageMap[id]?.count ?? 0;
    const base: RankedTemplate[] = q
      ? fuse.search(q).map((result, index) => ({
        template: result.item,
        score: scoreTemplate(result.item, result.score ?? 0, index, localUsageFor(result.item.id)),
      }))
      : templates.map((template, index) => ({
        template,
        score: scoreTemplate(template, 0.18, index, localUsageFor(template.id)),
      }));

    const categoryFiltered = base.filter(item => catFilter === 'All' || item.template.category === catFilter);
    return sortRankedTemplates(categoryFiltered, activeSortMode);
  }, [activeSortMode, catFilter, filter, fuse, templates, localUsageMap]);

  const setSort = (nextSort: TemplateSortMode) => {
    setInternalSortMode(nextSort);
    onSortModeChange?.(nextSort);
  };

  const handleSaveTemplate = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const name = saveDraft.name.trim();
    if (!name) {
      setSaveError('Name is required.');
      return;
    }
    if (!onSaveTemplate) return;

    setSaveError(null);
    await onSaveTemplate({
      name,
      description: saveDraft.description.trim(),
      category: saveDraft.category.trim() || 'Custom',
      tags: normalizeTags(saveDraft.tags),
    });
    setSaveOpen(false);
  };

  const showSaveAction = showSaveTemplateAction || Boolean(onSaveTemplate);

  return (
    <Dialog
      title="Templates"
      onClose={onClose}
      width={980}
      maxHeight="86vh"
      className="templates-menu-dialog templates-panel"
      header={(
        <div className="template-header-actions">
          {showSaveAction && (
            <button
              className="btn btn-sm template-save-trigger"
              type="button"
              onClick={() => setSaveOpen(open => !open)}
              disabled={!onSaveTemplate || isSavingTemplate}
              title={onSaveTemplate ? 'Save workflow as template' : 'Save-template hook is not wired'}
            >
              <Icon name="template" size={13} />
              Save
            </button>
          )}
        </div>
      )}
    >
      <div className="templates-menu-body">
        {saveOpen && (
          <form className="template-save-form" onSubmit={handleSaveTemplate}>
            <input
              className="text-input"
              value={saveDraft.name}
              onChange={event => setSaveDraft(prev => ({ ...prev, name: event.target.value }))}
              placeholder="Template name"
              disabled={isSavingTemplate}
            />
            <textarea
              className="text-input"
              value={saveDraft.description}
              onChange={event => setSaveDraft(prev => ({ ...prev, description: event.target.value }))}
              placeholder="Description"
              rows={2}
              disabled={isSavingTemplate}
            />
            <div className="template-save-row">
              <input
                className="text-input"
                value={saveDraft.category}
                onChange={event => setSaveDraft(prev => ({ ...prev, category: event.target.value }))}
                placeholder="Category"
                disabled={isSavingTemplate}
              />
              <input
                className="text-input"
                value={saveDraft.tags}
                onChange={event => setSaveDraft(prev => ({ ...prev, tags: event.target.value }))}
                placeholder="tags, comma separated"
                disabled={isSavingTemplate}
              />
            </div>
            {saveError && <div className="template-save-error">{saveError}</div>}
            <div className="template-save-actions">
              <button className="btn btn-sm btn-ghost" type="button" onClick={() => setSaveOpen(false)} disabled={isSavingTemplate}>
                Cancel
              </button>
              <button className="btn btn-sm btn-primary" type="submit" disabled={isSavingTemplate || !onSaveTemplate}>
                {isSavingTemplate ? 'Saving...' : 'Save Template'}
              </button>
            </div>
          </form>
        )}

        <div className="template-toolbar">
          <div className="node-search-wrap template-search-wrap">
            <input
              className="palette-search node-search-input"
              placeholder="Search templates..."
              value={filter}
              onChange={e => setFilter(e.target.value)}
              aria-label="Search templates"
            />
            <span className="node-search-icon"><Icon name="search" size={14} /></span>
          </div>
          <select
            className="select-input template-sort-select"
            value={activeSortMode}
            onChange={event => setSort(event.target.value as TemplateSortMode)}
            title="Sort templates"
            aria-label="Sort templates"
          >
            {(Object.keys(SORT_LABELS) as TemplateSortMode[]).map(mode => (
              <option key={mode} value={mode}>{SORT_LABELS[mode]}</option>
            ))}
          </select>
        </div>

        <div className="template-category-tabs">
          {categories.map(c => (
            <button
              key={c}
              className={`env-type-tab ${catFilter === c ? 'active' : ''}`}
              onClick={() => setCatFilter(c)}
              title={`Show ${c} templates`}
            >
              {c}
            </button>
          ))}
        </div>
        <div className="template-result-summary">
          <span>{loading ? 'Loading templates' : `${rankedTemplates.length} of ${templates.length} templates`}</span>
          {!loading && filter.trim() && <span>Ranked by fuzzy match</span>}
        </div>
        {loading && <TemplateSkeletons />}
        {error && <div className="template-error">Error: {error}</div>}
        {!loading && !error && (
          <div className="template-grid">
            {rankedTemplates.map(({ template, score }, index) => {
              const localUses = localUsageMap[template.id]?.count ?? 0;
              return (
              <button
                key={template.id}
                className="template-card"
                type="button"
                onClick={() => {
                  recordTemplateUse(template.id);
                  void Promise.resolve(onLoadTemplate(template)).then(onClose).catch(() => undefined);
                }}
                title={`Load ${template.name}`}
              >
                <TemplateThumbnail template={template} />
                <div className="template-card-content">
                  <div className="template-card-header">
                    <h4>{template.name}</h4>
                    <span className="template-rank-badge" title="Template match rank">
                      {Math.round(score * 100)}
                    </span>
                  </div>
                  <p>{templateSummary(template)}</p>
                  <div className="template-steps" aria-label="Workflow preview steps">
                    {(template.preview_steps?.length ? template.preview_steps : template.tools).slice(0, 4).map(step => (
                      <span key={step}>{compactStep(step)}</span>
                    ))}
                  </div>
                  <div className="template-card-meta">
                    <span>{template.category}</span>
                    <span>#{index + 1}</span>
                  </div>
                  <div className="tags">
                    {template.tags.slice(0, 2).map(tag => <span key={tag} className="template-tag">{tag}</span>)}
                    <span className="template-tag template-tag-muted">{template.node_count} nodes</span>
                    {localUses > 0 && (
                      <span className="template-tag template-tag-used" title="You've loaded this template before">
                        {localUses}× used
                      </span>
                    )}
                  </div>
                </div>
              </button>
              );
            })}
            {rankedTemplates.length === 0 && <div className="template-empty">No templates match your search.</div>}
          </div>
        )}
      </div>
    </Dialog>
  );
}
