import { useEffect, useMemo, useRef, useState } from 'react';
import type { KeyboardEvent } from 'react';
import { useTranslation } from 'react-i18next';
import type { ObjectInfo, NodeMetadata } from '../../types';
import { groupNodesByCategory } from '../../utils';
import { nodeCategoryDisplayLabel } from '../../utils/nodeCategories';
import { useNodeSearch, useRecentNodes, useNodeUsageStats } from '../../utils/nodeSearch';
import {
  isNodeBookmarked,
  listNodeBookmarks,
  subscribeNodeBookmarks,
  toggleNodeBookmark,
} from '../../state/nodeBookmarks';
import Icon from '../ui/Icon';
import { SkeletonList } from '../ui/Skeleton';
import { Spinner } from '../ui';
import { deleteBlueprint, listBlueprints, subscribeBlueprints, type SubgraphBlueprint } from '../../state/subgraphLibrary';

interface NodeLibraryPanelProps {
  objectInfo: ObjectInfo;
  loading?: boolean;
  onAddNode: (meta: NodeMetadata) => void;
  onAddBlueprint?: (blueprint: SubgraphBlueprint) => void;
  onClose: () => void;
}

interface NodeGroup {
  label: string;
  nodes: NodeMetadata[];
  recent?: boolean;
  frequent?: boolean;
  bookmarked?: boolean;
}

function safeNodeDomId(scope: string, id: string): string {
  return `${scope}-${id.replace(/[^a-zA-Z0-9_-]/g, '-')}`;
}

function uniqueNodes(nodes: NodeMetadata[]): NodeMetadata[] {
  const seen = new Set<string>();
  return nodes.filter(node => {
    if (seen.has(node.id)) return false;
    seen.add(node.id);
    return true;
  });
}

function buildGroups(
  searchResults: NodeMetadata[],
  recentNodes: NodeMetadata[],
  frequentNodes: NodeMetadata[],
  bookmarkedNodes: NodeMetadata[],
  showHeuristicGroups: boolean,
  labels: { bookmarks: string; mostUsed: string; recentlyUsed: string },
): NodeGroup[] {
  const groups: NodeGroup[] = [];
  // Bookmarks sit at the top regardless of search/category state — they're an
  // explicit user signal and should win over both frequency and recency.
  if (showHeuristicGroups && bookmarkedNodes.length > 0) {
    groups.push({ label: labels.bookmarks, nodes: bookmarkedNodes, bookmarked: true });
  }
  const bookmarkedIds = new Set(bookmarkedNodes.map(meta => meta.id));
  if (showHeuristicGroups && frequentNodes.length > 0) {
    const filteredFrequent = frequentNodes.filter(meta => !bookmarkedIds.has(meta.id));
    if (filteredFrequent.length > 0) {
      groups.push({ label: labels.mostUsed, nodes: filteredFrequent, frequent: true });
    }
  }
  if (showHeuristicGroups && recentNodes.length > 0) {
    // De-duplicate against bookmarks + frequent so the same node isn't shown
    // multiple times in the top section.
    const seen = new Set<string>(bookmarkedIds);
    frequentNodes.forEach(meta => seen.add(meta.id));
    const filteredRecent = recentNodes.filter(meta => !seen.has(meta.id));
    if (filteredRecent.length > 0) {
      groups.push({ label: labels.recentlyUsed, nodes: filteredRecent, recent: true });
    }
  }

  const grouped = groupNodesByCategory(searchResults);
  for (const [label, nodes] of Object.entries(grouped)) {
    groups.push({ label, nodes });
  }
  return groups;
}

interface PortPreview { name: string; type: string }

function collectPorts(meta: NodeMetadata): { inputs: PortPreview[]; outputs: PortPreview[] } {
  const inputsMap = {
    ...(meta.input_types?.required || {}),
    ...(meta.input_types?.optional || {}),
  } as Record<string, { type?: string } | unknown>;
  const inputs: PortPreview[] = Object.entries(inputsMap).map(([name, spec]) => ({
    name,
    type: (spec as { type?: string })?.type || 'ANY',
  }));
  const outputs: PortPreview[] = (meta.return_types || []).map((type, index) => ({
    name: (meta.return_names && meta.return_names[index]) || type || `out${index + 1}`,
    type: type || 'ANY',
  }));
  return { inputs, outputs };
}

function NodeLibraryResult({
  meta,
  active,
  recent,
  usageCount,
  bookmarked,
  onChoose,
  onFocus,
  onToggleBookmark,
}: {
  meta: NodeMetadata;
  active: boolean;
  recent?: boolean;
  usageCount?: number;
  bookmarked?: boolean;
  onChoose: (meta: NodeMetadata) => void;
  onFocus: (id: string) => void;
  onToggleBookmark: (meta: NodeMetadata) => void;
}) {
  const { t } = useTranslation();
  const tools = meta.requires_external_tools || [];
  const subtitle = meta.description || meta.id;
  const categoryLabel = nodeCategoryDisplayLabel(meta.category, t, t('nodeLibrary.otherCategory'));
  const [showPreview, setShowPreview] = useState(false);
  const hoverTimer = useRef<number | null>(null);
  const buttonRef = useRef<HTMLButtonElement | null>(null);

  // 350ms hover delay so the preview doesn't flash up while a user is
  // scanning the list. Cleared on leave / unmount.
  const scheduleShow = () => {
    if (hoverTimer.current) window.clearTimeout(hoverTimer.current);
    hoverTimer.current = window.setTimeout(() => setShowPreview(true), 350);
  };
  const cancelShow = () => {
    if (hoverTimer.current) {
      window.clearTimeout(hoverTimer.current);
      hoverTimer.current = null;
    }
    setShowPreview(false);
  };
  useEffect(() => () => {
    if (hoverTimer.current) window.clearTimeout(hoverTimer.current);
  }, []);

  const ports = useMemo(() => collectPorts(meta), [meta]);

  return (
    <button
      ref={buttonRef}
      id={safeNodeDomId('node-library-result', meta.id)}
      type="button"
      className={`node-search-result node-library-result ${active ? 'is-active' : ''} ${recent ? 'is-recent' : ''}`}
      onClick={() => onChoose(meta)}
      onMouseEnter={() => { onFocus(meta.id); scheduleShow(); }}
      onMouseLeave={cancelShow}
      onFocus={() => onFocus(meta.id)}
      onBlur={cancelShow}
      title={usageCount
        ? t('nodeLibrary.addNodeUsedTitle', { name: meta.display_name, count: usageCount })
        : t('nodeLibrary.addNodeTitle', { name: meta.display_name })}
    >
      <span className="node-search-result-main">
        <span className="node-search-result-title">
          {meta.display_name}
          {usageCount !== undefined && usageCount > 0 && (
            <span className="node-usage-badge" aria-label={t('nodeLibrary.usedTimes', { count: usageCount })}>
              {usageCount}×
            </span>
          )}
        </span>
        <span className="node-search-result-desc">{subtitle}</span>
        <span className="node-search-result-meta">
          {categoryLabel}
          {tools.length > 0 && ` - ${tools.slice(0, 2).join(', ')}`}
        </span>
      </span>
      <span
        className={`node-bookmark-toggle ${bookmarked ? 'is-on' : ''}`}
        role="button"
        tabIndex={-1}
        aria-label={bookmarked
          ? t('nodeLibrary.removeBookmark', { name: meta.display_name })
          : t('nodeLibrary.bookmarkNode', { name: meta.display_name })}
        onClick={event => { event.stopPropagation(); onToggleBookmark(meta); }}
        title={bookmarked ? t('nodeLibrary.bookmarkedTitle') : t('nodeLibrary.bookmarkTitle')}
      >
        <Icon name="star" size={12} />
      </span>
      <span className="node-search-result-action" aria-hidden="true">
        <Icon name="plus" size={12} />
      </span>
      {showPreview && (
        <div className="node-preview-tooltip" role="tooltip" onMouseEnter={cancelShow}>
          <div className="node-preview-tooltip-title">{meta.display_name}</div>
          <div className="node-preview-tooltip-id">{meta.id}</div>
          {meta.description && (
            <div className="node-preview-tooltip-desc">{meta.description}</div>
          )}
          {ports.inputs.length > 0 && (
            <div className="node-preview-tooltip-section">
              <div className="node-preview-tooltip-heading">{t('nodeLibrary.inputs')}</div>
              {ports.inputs.map(port => (
                <div key={port.name} className="node-preview-tooltip-port">
                  <span className="node-preview-tooltip-port-name">{port.name}</span>
                  <span className="node-preview-tooltip-port-type">{port.type}</span>
                </div>
              ))}
            </div>
          )}
          {ports.outputs.length > 0 && (
            <div className="node-preview-tooltip-section">
              <div className="node-preview-tooltip-heading">{t('nodeLibrary.outputs')}</div>
              {ports.outputs.map(port => (
                <div key={port.name} className="node-preview-tooltip-port">
                  <span className="node-preview-tooltip-port-name">{port.name}</span>
                  <span className="node-preview-tooltip-port-type">{port.type}</span>
                </div>
              ))}
            </div>
          )}
          {tools.length > 0 && (
            <div className="node-preview-tooltip-section">
              <div className="node-preview-tooltip-heading">{t('nodeLibrary.tools')}</div>
              <div className="node-preview-tooltip-tools">{tools.join(', ')}</div>
            </div>
          )}
        </div>
      )}
    </button>
  );
}

export default function NodeLibraryPanel({ objectInfo, loading, onAddNode, onAddBlueprint, onClose }: NodeLibraryPanelProps) {
  const { t } = useTranslation();
  const [query, setQuery] = useState('');
  const [expanded, setExpanded] = useState<Set<string>>(new Set(['Input', 'Quality Control', 'Subgraphs']));
  const [blueprints, setBlueprints] = useState<SubgraphBlueprint[]>(() => listBlueprints());
  useEffect(() => {
    const unsubscribe = subscribeBlueprints(() => setBlueprints(listBlueprints()));
    return unsubscribe;
  }, []);
  const filteredBlueprints = useMemo(() => {
    if (!query.trim()) return blueprints;
    const q = query.toLowerCase();
    return blueprints.filter(bp => bp.name.toLowerCase().includes(q) || (bp.description ?? '').toLowerCase().includes(q));
  }, [blueprints, query]);
  const [activeNodeId, setActiveNodeId] = useState<string | null>(null);

  // Active category filters: chips above the search input that narrow the
  // result list to those categories. Clicking a category header toggles it.
  const [categoryFilters, setCategoryFilters] = useState<Set<string>>(new Set());
  const toggleCategoryFilter = (label: string) => {
    setCategoryFilters(prev => {
      const next = new Set(prev);
      next.has(label) ? next.delete(label) : next.add(label);
      return next;
    });
  };
  const clearCategoryFilters = () => setCategoryFilters(new Set());

  const searchResults = useNodeSearch(objectInfo, query);
  const { recentNodes, rememberNode, clearRecentNodes } = useRecentNodes(objectInfo);
  const { frequentNodes, recordNodeUsage, getNodeUsageCount, clearUsageStats } = useNodeUsageStats(objectInfo);
  const frequentMetas = useMemo(() => frequentNodes.map(entry => entry.meta), [frequentNodes]);

  // Bookmarked node types, refreshed via the subscribe callback so toggling
  // from another panel (or another tab) is reflected without a remount.
  const [bookmarkVersion, setBookmarkVersion] = useState(0);
  useEffect(() => subscribeNodeBookmarks(() => setBookmarkVersion(v => v + 1)), []);
  const bookmarkedMetas = useMemo(() => {
    const ids = listNodeBookmarks();
    return ids.map(id => objectInfo[id]).filter((meta): meta is NodeMetadata => Boolean(meta));
  }, [objectInfo, bookmarkVersion]);

  const searchedNodes = useMemo(() => {
    const all = searchResults.map(result => result.meta);
    if (categoryFilters.size === 0) return all;
    return all.filter(meta => categoryFilters.has(meta.category || 'Other'));
  }, [searchResults, categoryFilters]);
  const categoryDisplayLabel = (label: string) => nodeCategoryDisplayLabel(label, t, t('nodeLibrary.otherCategory'));
  const hasQuery = query.trim().length > 0;
  const groups = useMemo(
    () => buildGroups(
      searchedNodes,
      recentNodes,
      frequentMetas,
      bookmarkedMetas,
      !hasQuery && categoryFilters.size === 0,
      {
        bookmarks: t('nodeLibrary.bookmarks'),
        mostUsed: t('nodeLibrary.mostUsed'),
        recentlyUsed: t('nodeLibrary.recentlyUsed'),
      },
    ),
    [hasQuery, recentNodes, frequentMetas, bookmarkedMetas, searchedNodes, categoryFilters, t],
  );
  const keyboardNodes = useMemo(() => uniqueNodes(groups.flatMap(group => group.nodes)), [groups]);
  const totalNodes = Object.values(objectInfo).length;

  useEffect(() => {
    if (keyboardNodes.length === 0) {
      setActiveNodeId(null);
      return;
    }
    setActiveNodeId(prev => (prev && keyboardNodes.some(node => node.id === prev) ? prev : keyboardNodes[0].id));
  }, [keyboardNodes]);

  useEffect(() => {
    if (!activeNodeId) return;
    document.getElementById(safeNodeDomId('node-library-result', activeNodeId))?.scrollIntoView({ block: 'nearest' });
  }, [activeNodeId]);

  const toggle = (cat: string) => {
    setExpanded(prev => {
      const n = new Set(prev);
      n.has(cat) ? n.delete(cat) : n.add(cat);
      return n;
    });
  };

  const chooseNode = (meta: NodeMetadata) => {
    rememberNode(meta);
    recordNodeUsage(meta);
    onAddNode(meta);
  };

  const moveActive = (delta: number) => {
    if (keyboardNodes.length === 0) return;
    const currentIndex = activeNodeId ? keyboardNodes.findIndex(node => node.id === activeNodeId) : -1;
    const nextIndex = currentIndex < 0
      ? 0
      : (currentIndex + delta + keyboardNodes.length) % keyboardNodes.length;
    setActiveNodeId(keyboardNodes[nextIndex].id);
  };

  const handleKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === 'Escape') {
      event.preventDefault();
      onClose();
      return;
    }
    if (keyboardNodes.length === 0) return;

    if (event.key === 'ArrowDown') {
      event.preventDefault();
      moveActive(1);
    } else if (event.key === 'ArrowUp') {
      event.preventDefault();
      moveActive(-1);
    } else if (event.key === 'Home') {
      event.preventDefault();
      setActiveNodeId(keyboardNodes[0].id);
    } else if (event.key === 'End') {
      event.preventDefault();
      setActiveNodeId(keyboardNodes[keyboardNodes.length - 1].id);
    } else if (event.key === 'Enter') {
      event.preventDefault();
      const active = keyboardNodes.find(node => node.id === activeNodeId) || keyboardNodes[0];
      chooseNode(active);
    }
  };

  return (
    <div className="rail-panel node-library-panel">
      <div className="rail-panel-header">
        <span>{t('nodeLibrary.title')}</span>
        <button className="btn btn-icon btn-sm" onClick={onClose} title={t('nodeLibrary.closeTitle')}>
          <Icon name="close" size={14} />
        </button>
      </div>
      <div className="rail-panel-body">
        <div className="node-search-wrap">
          <input
            className="palette-search node-search-input"
            placeholder={t('nodeLibrary.searchPlaceholder')}
            value={query}
            onChange={e => setQuery(e.target.value)}
            onKeyDown={handleKeyDown}
            aria-activedescendant={activeNodeId ? safeNodeDomId('node-library-result', activeNodeId) : undefined}
            aria-label={t('nodeLibrary.searchAria')}
            role="combobox"
            aria-expanded="true"
          />
          <span className="node-search-icon"><Icon name="search" size={14} /></span>
        </div>
        <div className="node-search-summary">
          <span>
            {loading && totalNodes === 0 ? (
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
                <Spinner size="sm" label={t('nodeLibrary.loadingNodes')} /> {t('nodeLibrary.loadingRegistry')}
              </span>
            ) : hasQuery
              ? `${t('nodeLibrary.matchCount', { count: searchedNodes.length })}${categoryFilters.size ? ` ${t('nodeLibrary.filteredSuffix')}` : ''}`
              : t('nodeLibrary.nodesAvailable', { count: totalNodes })}
          </span>
          {!hasQuery && recentNodes.length > 0 && (
            <button className="node-search-clear" type="button" onClick={clearRecentNodes} title={t('nodeLibrary.clearRecentNodes')}>
              {t('nodeLibrary.clearRecent')}
            </button>
          )}
        </div>
        {categoryFilters.size > 0 && (
          <div className="node-filter-chips" role="group" aria-label={t('nodeLibrary.activeCategoryFilters')}>
            {Array.from(categoryFilters).map(label => (
              <button
                key={label}
                type="button"
                className="node-filter-chip"
                onClick={() => toggleCategoryFilter(label)}
                title={t('nodeLibrary.removeFilterTitle', { label: categoryDisplayLabel(label) })}
              >
                <span>{categoryDisplayLabel(label)}</span>
                <Icon name="close" size={10} />
              </button>
            ))}
            {categoryFilters.size > 1 && (
              <button
                type="button"
                className="node-filter-chip-clear"
                onClick={clearCategoryFilters}
                title={t('nodeLibrary.clearAllFilters')}
              >
                {t('nodeLibrary.clearAll')}
              </button>
            )}
          </div>
        )}
        <div className="node-search-results node-library-results">
          {totalNodes === 0 && (
            <div className="node-search-group" style={{ padding: '8px 12px' }}>
              <SkeletonList count={6} rowHeight={18} widths={['65%', '90%', '40%', '75%', '85%', '55%']} />
            </div>
          )}
          {filteredBlueprints.length > 0 && onAddBlueprint && (
            <section className="node-search-group">
              <button
                type="button"
                className="node-category-toggle"
                onClick={() => toggle('Subgraphs')}
                title={expanded.has('Subgraphs')
                  ? t('nodeLibrary.collapseGroup', { label: t('nodeLibrary.subgraphs') })
                  : t('nodeLibrary.expandGroup', { label: t('nodeLibrary.subgraphs') })}
              >
                <Icon name={expanded.has('Subgraphs') ? 'chevronDown' : 'chevronRight'} size={12} />
                <span>{t('nodeLibrary.subgraphs')}</span>
                <span className="node-category-count">{filteredBlueprints.length}</span>
              </button>
              {expanded.has('Subgraphs') && (
                <div className="node-result-list">
                  {filteredBlueprints.map(bp => (
                    <div
                      key={bp.id}
                      className="node-search-result node-library-result"
                      style={{ display: 'flex', alignItems: 'center', gap: 6, paddingRight: 8 }}
                    >
                      <button
                        type="button"
                        onClick={() => onAddBlueprint(bp)}
                        style={{
                          flex: 1, background: 'transparent', border: 'none', color: 'inherit',
                          cursor: 'pointer', textAlign: 'left', padding: 0,
                        }}
                        title={t('nodeLibrary.addNodeTitle', { name: bp.name })}
                      >
                        <span className="node-search-result-main">
                          <span className="node-search-result-title">{bp.name}</span>
                          <span className="node-search-result-desc">
                            {t('nodeLibrary.blueprintPorts', {
                              nodes: bp.workflow.nodes?.length ?? 0,
                              inputs: bp.inputPorts.length,
                              outputs: bp.outputPorts.length,
                            })}
                          </span>
                        </span>
                      </button>
                      <button
                        type="button"
                        onClick={() => deleteBlueprint(bp.id)}
                        title={t('nodeLibrary.deleteBlueprint')}
                        style={{
                          background: 'transparent', border: 'none', color: 'var(--muted)',
                          cursor: 'pointer', padding: '0 4px', fontSize: 14,
                        }}
                      >×</button>
                    </div>
                  ))}
                </div>
              )}
            </section>
          )}
          {groups.map(group => {
            const isHeuristic = group.recent || group.frequent;
            const expandedGroup = isHeuristic || hasQuery || expanded.has(group.label);
            const sectionKey = group.frequent ? '__frequent' : group.recent ? '__recent' : group.label;
            const groupLabel = categoryDisplayLabel(group.label);
            return (
              <section key={sectionKey} className={`node-search-group ${group.recent ? 'is-recent' : ''} ${group.frequent ? 'is-frequent' : ''}`}>
                {isHeuristic ? (
                  <div className="node-search-group-label">
                    <Icon name={group.frequent ? 'star' : 'clock'} size={12} />
                    <span>{groupLabel}</span>
                    {group.frequent && (
                      <button
                        type="button"
                        className="node-search-clear"
                        onClick={clearUsageStats}
                        title={t('nodeLibrary.resetUsageFrequency')}
                        style={{ marginLeft: 'auto' }}
                      >
                        {t('nodeLibrary.reset')}
                      </button>
                    )}
                  </div>
                ) : (
                  <div className="node-category-row">
                    <button
                      type="button"
                      className="node-category-toggle"
                      onClick={() => toggle(group.label)}
                      title={expandedGroup
                        ? t('nodeLibrary.collapseGroup', { label: groupLabel })
                        : t('nodeLibrary.expandGroup', { label: groupLabel })}
                    >
                      <Icon name={expandedGroup ? 'chevronDown' : 'chevronRight'} size={12} />
                      <span>{groupLabel}</span>
                      <span className="node-category-count">{group.nodes.length}</span>
                    </button>
                    <button
                      type="button"
                      className={`node-category-filter ${categoryFilters.has(group.label) ? 'is-active' : ''}`}
                      onClick={(event) => { event.stopPropagation(); toggleCategoryFilter(group.label); }}
                      title={categoryFilters.has(group.label)
                        ? t('nodeLibrary.removeCategoryFilter', { label: groupLabel })
                        : t('nodeLibrary.filterTo', { label: groupLabel })}
                      aria-pressed={categoryFilters.has(group.label)}
                    >
                      <Icon name={categoryFilters.has(group.label) ? 'check' : 'plus'} size={10} />
                    </button>
                  </div>
                )}
                {expandedGroup && (
                  <div className="node-result-list">
                    {group.nodes.map(meta => (
                      <NodeLibraryResult
                        key={`${sectionKey}-${meta.id}`}
                        meta={meta}
                        active={activeNodeId === meta.id}
                        recent={group.recent}
                        usageCount={group.frequent ? getNodeUsageCount(meta.id) : undefined}
                        bookmarked={isNodeBookmarked(meta.id)}
                        onChoose={chooseNode}
                        onFocus={setActiveNodeId}
                        onToggleBookmark={(m) => toggleNodeBookmark(m.id)}
                      />
                    ))}
                  </div>
                )}
              </section>
            );
          })}
          {keyboardNodes.length === 0 && (
            <div className="node-search-empty">
              {t('nodeLibrary.emptyQuery', { query })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
