import { useEffect, useMemo, useState } from 'react';
import type { CSSProperties, KeyboardEvent } from 'react';
import type { ObjectInfo, NodeMetadata } from '../../types';
import { groupNodesByCategory } from '../../utils';
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

function buildGroups(searchResults: NodeMetadata[], recentNodes: NodeMetadata[], showRecent: boolean): NodePaletteGroup[] {
  const groups: NodePaletteGroup[] = [];
  if (showRecent && recentNodes.length > 0) {
    groups.push({ label: 'Recently Used', nodes: recentNodes, recent: true });
  }
  for (const [label, nodes] of Object.entries(groupNodesByCategory(searchResults))) {
    groups.push({ label, nodes });
  }
  return groups;
}

function NodePaletteResult({
  meta,
  active,
  recent,
  onChoose,
  onFocus,
}: {
  meta: NodeMetadata;
  active: boolean;
  recent?: boolean;
  onChoose: (meta: NodeMetadata) => void;
  onFocus: (id: string) => void;
}) {
  return (
    <button
      id={safeNodeDomId('node-palette-result', meta.id)}
      type="button"
      className={`node-search-result palette-node-result ${active ? 'is-active' : ''} ${recent ? 'is-recent' : ''}`}
      onClick={() => onChoose(meta)}
      onMouseEnter={() => onFocus(meta.id)}
      title={`Add ${meta.display_name}`}
    >
      <span className="node-search-result-main">
        <span className="node-search-result-title">{meta.display_name}</span>
        {meta.description && <span className="node-search-result-desc">{meta.description}</span>}
        <span className="node-search-result-meta">{meta.category || 'Other'}</span>
      </span>
      <span className="node-search-result-action" aria-hidden="true">
        <Icon name="plus" size={12} />
      </span>
    </button>
  );
}

export default function NodePalette({ objectInfo, onSelect, onClose, style, requireInputType, requireOutputType }: NodePaletteProps) {
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
  const groups = useMemo(
    () => buildGroups(searchedNodes, recentNodes, !hasQuery),
    [hasQuery, recentNodes, searchedNodes],
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
        <span>{requireInputType ? `Add node with ${requireInputType} input` : requireOutputType ? `Add node with ${requireOutputType} output` : 'Add Node'}</span>
        <button className="btn btn-icon btn-sm" onClick={onClose} title="Close node palette"><Icon name="close" size={14} /></button>
      </div>
      <div className="node-palette-body">
        <div className="node-search-wrap">
          <input
            className="palette-search node-search-input"
            placeholder="Search nodes..."
            value={query}
            onChange={e => setQuery(e.target.value)}
            onKeyDown={handleKeyDown}
            autoFocus
            aria-activedescendant={activeNodeId ? safeNodeDomId('node-palette-result', activeNodeId) : undefined}
            aria-label="Search nodes"
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
              ? `${searchResults.length} fuzzy matches`
              : `${Object.values(filteredObjectInfo).length} nodes${(requireInputType || requireOutputType) ? ' (filtered)' : ''}`}
          </span>
          {!hasQuery && recentNodes.length > 0 && (
            <button className="node-search-clear" type="button" onClick={clearRecentNodes} title="Clear recent nodes">
              Clear recent
            </button>
          )}
        </div>
        <div className="node-search-results node-palette-results">
          {groups.map(group => {
            const expandedGroup = group.recent || hasQuery || expanded.has(group.label);
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
                    title={expandedGroup ? `Collapse ${group.label}` : `Expand ${group.label}`}
                  >
                    <Icon name={expandedGroup ? 'chevronDown' : 'chevronRight'} size={12} />
                    <span>{group.label}</span>
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
                      />
                    ))}
                  </div>
                )}
              </section>
            );
          })}
          {keyboardNodes.length === 0 && (
            <div className="node-search-empty">
              No nodes match "{query}"
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
