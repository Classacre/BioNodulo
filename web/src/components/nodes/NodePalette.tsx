import { useEffect, useMemo, useState } from 'react';
import type { CSSProperties, KeyboardEvent } from 'react';
import { useTranslation } from 'react-i18next';
import type { ObjectInfo, NodeMetadata } from '../../types';
import { nodeCategoryDisplayLabel } from '../../utils/nodeCategories';
import { useNodeSearch, useRecentNodes } from '../../utils/nodeSearch';
import Icon from '../ui/Icon';

interface NodePaletteProps {
  objectInfo: ObjectInfo;
  onSelect: (meta: NodeMetadata) => void;
  onClose: () => void;
  style?: CSSProperties;
  // When set, only show nodes that have at least one matching slot. Used by
  // the canvas when the user drops a link on empty space so the next pick is
  // automatically a valid drop target.
  requireInputType?: string;
  requireOutputType?: string;
}

function nodeHasInputType(meta: NodeMetadata, type: string): boolean {
  const inputs = meta.input_types || {};
  for (const section of ['required', 'optional'] as const) {
    const specs = inputs[section] || {};
    for (const spec of Object.values(specs)) {
      const specType = (spec as { type?: string }).type;
      if (specType === type || specType === '*' || specType === 'ANY') return true;
    }
  }
  return false;
}

function nodeHasOutputType(meta: NodeMetadata, type: string): boolean {
  const outputs = meta.return_types || [];
  return outputs.some(t => t === type || t === '*' || t === 'ANY');
}

interface NodePaletteGroup {
  label: string;
  nodes: NodeMetadata[];
  recent?: boolean;
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
  showRecent: boolean,
  labels: { recentlyUsed: string; otherCategory: string },
): NodePaletteGroup[] {
  const groups: NodePaletteGroup[] = [];
  const recentNodeIds = showRecent ? new Set(recentNodes.map(node => node.id)) : new Set<string>();
  if (showRecent && recentNodes.length > 0) {
    groups.push({ label: labels.recentlyUsed, nodes: recentNodes, recent: true });
  }
  const categoryGroups = new Map<string, { label: string; nodes: NodeMetadata[] }>();
  for (const meta of searchResults) {
    if (recentNodeIds.has(meta.id)) continue;
    const key = meta.category || '__other';
    const label = meta.category || labels.otherCategory;
    const group = categoryGroups.get(key) || { label, nodes: [] };
    group.nodes.push(meta);
    categoryGroups.set(key, group);
  }
  for (const group of categoryGroups.values()) {
    group.nodes.sort((a, b) => a.display_name.localeCompare(b.display_name));
    groups.push(group);
  }
  return groups;
}

function NodePaletteResult({
  meta,
  active,
  recent,
  onChoose,
  onFocus,
  categoryLabel,
  addTitle,
}: {
  meta: NodeMetadata;
  active: boolean;
  recent?: boolean;
  onChoose: (meta: NodeMetadata) => void;
  onFocus: (id: string) => void;
  categoryLabel: string;
  addTitle: string;
}) {
  return (
    <button
      id={safeNodeDomId('node-palette-result', meta.id)}
      type="button"
      className={`node-search-result palette-node-result ${active ? 'is-active' : ''} ${recent ? 'is-recent' : ''}`}
      onClick={() => onChoose(meta)}
      onMouseEnter={() => onFocus(meta.id)}
      title={addTitle}
    >
      <span className="node-search-result-main">
        <span className="node-search-result-title">{meta.display_name}</span>
        {meta.description && <span className="node-search-result-desc">{meta.description}</span>}
        <span className="node-search-result-meta">{categoryLabel}</span>
      </span>
      <span className="node-search-result-action" aria-hidden="true">
        <Icon name="plus" size={12} />
      </span>
    </button>
  );
}

export default function NodePalette({ objectInfo, onSelect, onClose, style, requireInputType, requireOutputType }: NodePaletteProps) {
  const { t } = useTranslation();
  const filteredObjectInfo = useMemo(() => {
    if (!requireInputType && !requireOutputType) return objectInfo;
    const out: ObjectInfo = {};
    for (const [id, meta] of Object.entries(objectInfo)) {
      if (requireInputType && !nodeHasInputType(meta, requireInputType)) continue;
      if (requireOutputType && !nodeHasOutputType(meta, requireOutputType)) continue;
      out[id] = meta;
    }
    return out;
  }, [objectInfo, requireInputType, requireOutputType]);
  const [query, setQuery] = useState('');
  const [expanded, setExpanded] = useState<Set<string>>(new Set(['Input', 'Quality Control']));
  const [activeNodeId, setActiveNodeId] = useState<string | null>(null);
  const searchResults = useNodeSearch(filteredObjectInfo, query, requireInputType);
  const { recentNodes, rememberNode, clearRecentNodes } = useRecentNodes(filteredObjectInfo);
  const searchedNodes = useMemo(() => searchResults.map(result => result.meta), [searchResults]);
  const hasQuery = query.trim().length > 0;
  const otherCategory = t('nodePalette.otherCategory');
  const groups = useMemo(
    () => buildGroups(searchedNodes, recentNodes, !hasQuery, {
      recentlyUsed: t('nodePalette.recentlyUsed'),
      otherCategory,
    }),
    [hasQuery, recentNodes, searchedNodes, otherCategory, t],
  );
  const keyboardNodes = useMemo(() => uniqueNodes(groups.flatMap(group => group.nodes)), [groups]);

  useEffect(() => {
    if (keyboardNodes.length === 0) {
      setActiveNodeId(null);
      return;
    }
    setActiveNodeId(prev => (prev && keyboardNodes.some(node => node.id === prev) ? prev : keyboardNodes[0].id));
  }, [keyboardNodes]);

  useEffect(() => {
    if (!activeNodeId) return;
    document.getElementById(safeNodeDomId('node-palette-result', activeNodeId))?.scrollIntoView({ block: 'nearest' });
  }, [activeNodeId]);

  const toggleCategory = (cat: string) => {
    setExpanded(prev => {
      const next = new Set(prev);
      if (next.has(cat)) next.delete(cat); else next.add(cat);
      return next;
    });
  };

  const chooseNode = (meta: NodeMetadata) => {
    rememberNode(meta);
    onSelect(meta);
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
    <div className="context-menu node-palette-menu" style={{ ...style, width: 320, maxHeight: 520 }}>
      <div className="context-menu-header">
        <span>
          {requireInputType
            ? t('nodePalette.addNodeWithInput', { type: requireInputType })
            : requireOutputType
              ? t('nodePalette.addNodeWithOutput', { type: requireOutputType })
              : t('nodePalette.addNode')}
        </span>
        <button className="btn btn-icon btn-sm" onClick={onClose} title={t('nodePalette.closeTitle')}><Icon name="close" size={14} /></button>
      </div>
      <div className="node-palette-body">
        <div className="node-search-wrap">
          <input
            className="palette-search node-search-input"
            placeholder={t('nodePalette.searchPlaceholder')}
            value={query}
            onChange={e => setQuery(e.target.value)}
            onKeyDown={handleKeyDown}
            autoFocus
            aria-activedescendant={activeNodeId ? safeNodeDomId('node-palette-result', activeNodeId) : undefined}
            aria-label={t('nodePalette.searchAria')}
            role="combobox"
            aria-expanded="true"
          />
          <span className="node-search-icon">
            <Icon name="search" size={14} />
          </span>
        </div>
        <div className="node-search-summary">
          <span>
            {hasQuery
              ? t('nodePalette.fuzzyMatchCount', { count: searchResults.length })
              : `${t('nodePalette.nodeCount', { count: Object.values(filteredObjectInfo).length })}${(requireInputType || requireOutputType) ? ` ${t('nodePalette.filteredSuffix')}` : ''}`}
          </span>
          {!hasQuery && recentNodes.length > 0 && (
            <button className="node-search-clear" type="button" onClick={clearRecentNodes} title={t('nodePalette.clearRecentNodes')}>
              {t('nodePalette.clearRecent')}
            </button>
          )}
        </div>
        <div className="node-search-results node-palette-results">
          {groups.map(group => {
            const expandedGroup = group.recent || hasQuery || expanded.has(group.label);
            const groupLabel = group.recent ? group.label : nodeCategoryDisplayLabel(group.label, t, otherCategory);
            return (
              <section key={group.recent ? '__recent' : group.label} className={`node-search-group ${group.recent ? 'is-recent' : ''}`}>
                {group.recent ? (
                  <div className="node-search-group-label">
                    <Icon name="clock" size={12} />
                    <span>{group.label}</span>
                  </div>
                ) : (
                  <button
                    type="button"
                    className="node-category-toggle"
                    onClick={() => toggleCategory(group.label)}
                    title={expandedGroup
                      ? t('nodePalette.collapseGroup', { label: groupLabel })
                      : t('nodePalette.expandGroup', { label: groupLabel })}
                  >
                    <Icon name={expandedGroup ? 'chevronDown' : 'chevronRight'} size={12} />
                    <span>{groupLabel}</span>
                    <span className="node-category-count">{group.nodes.length}</span>
                  </button>
                )}
                {expandedGroup && (
                  <div className="node-result-list">
                    {group.nodes.map(meta => (
                      <NodePaletteResult
                        key={`${group.recent ? 'recent' : group.label}-${meta.id}`}
                        meta={meta}
                        active={activeNodeId === meta.id}
                        recent={group.recent}
                        onChoose={chooseNode}
                        onFocus={setActiveNodeId}
                        categoryLabel={nodeCategoryDisplayLabel(meta.category, t, otherCategory)}
                        addTitle={t('nodePalette.addNodeTitle', { name: meta.display_name })}
                      />
                    ))}
                  </div>
                )}
              </section>
            );
          })}
          {keyboardNodes.length === 0 && (
            <div className="node-search-empty">
              {t('nodePalette.emptyQuery', { query })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
