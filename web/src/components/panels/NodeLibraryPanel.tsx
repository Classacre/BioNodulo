import { useEffect, useMemo, useState } from 'react';
import type { KeyboardEvent } from 'react';
import type { ObjectInfo, NodeMetadata } from '../../types';
import { groupNodesByCategory } from '../../utils';
import { useNodeSearch, useRecentNodes } from '../../utils/nodeSearch';
import Icon from '../ui/Icon';
import { SkeletonList } from '../ui/Skeleton';
import { deleteBlueprint, listBlueprints, subscribeBlueprints, type SubgraphBlueprint } from '../../state/subgraphLibrary';

interface NodeLibraryPanelProps {
  objectInfo: ObjectInfo;
  onAddNode: (meta: NodeMetadata) => void;
  onAddBlueprint?: (blueprint: SubgraphBlueprint) => void;
  onClose: () => void;
}

interface NodeGroup {
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

function buildGroups(searchResults: NodeMetadata[], recentNodes: NodeMetadata[], showRecent: boolean): NodeGroup[] {
  const groups: NodeGroup[] = [];
  if (showRecent && recentNodes.length > 0) {
    groups.push({ label: 'Recently Used', nodes: recentNodes, recent: true });
  }

  const grouped = groupNodesByCategory(searchResults);
  for (const [label, nodes] of Object.entries(grouped)) {
    groups.push({ label, nodes });
  }
  return groups;
}

function NodeLibraryResult({
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
  const tools = meta.requires_external_tools || [];
  const subtitle = meta.description || meta.id;
  return (
    <button
      id={safeNodeDomId('node-library-result', meta.id)}
      type="button"
      className={`node-search-result node-library-result ${active ? 'is-active' : ''} ${recent ? 'is-recent' : ''}`}
      onClick={() => onChoose(meta)}
      onMouseEnter={() => onFocus(meta.id)}
      title={`Add ${meta.display_name}`}
    >
      <span className="node-search-result-main">
        <span className="node-search-result-title">{meta.display_name}</span>
        <span className="node-search-result-desc">{subtitle}</span>
        <span className="node-search-result-meta">
          {meta.category || 'Other'}
          {tools.length > 0 && ` - ${tools.slice(0, 2).join(', ')}`}
        </span>
      </span>
      <span className="node-search-result-action" aria-hidden="true">
        <Icon name="plus" size={12} />
      </span>
    </button>
  );
}

export default function NodeLibraryPanel({ objectInfo, onAddNode, onAddBlueprint, onClose }: NodeLibraryPanelProps) {
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

  const searchResults = useNodeSearch(objectInfo, query);
  const { recentNodes, rememberNode, clearRecentNodes } = useRecentNodes(objectInfo);
  const searchedNodes = useMemo(() => searchResults.map(result => result.meta), [searchResults]);
  const hasQuery = query.trim().length > 0;
  const groups = useMemo(
    () => buildGroups(searchedNodes, recentNodes, !hasQuery),
    [hasQuery, recentNodes, searchedNodes],
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
        <span>Node Library</span>
        <button className="btn btn-icon btn-sm" onClick={onClose} title="Close node library">
          <Icon name="close" size={14} />
        </button>
      </div>
      <div className="rail-panel-body">
        <div className="node-search-wrap">
          <input
            className="palette-search node-search-input"
            placeholder="Search nodes..."
            value={query}
            onChange={e => setQuery(e.target.value)}
            onKeyDown={handleKeyDown}
            aria-activedescendant={activeNodeId ? safeNodeDomId('node-library-result', activeNodeId) : undefined}
            aria-label="Search nodes"
            role="combobox"
            aria-expanded="true"
          />
          <span className="node-search-icon"><Icon name="search" size={14} /></span>
        </div>
        <div className="node-search-summary">
          <span>{hasQuery ? `${searchResults.length} fuzzy matches` : `${totalNodes} nodes available`}</span>
          {!hasQuery && recentNodes.length > 0 && (
            <button className="node-search-clear" type="button" onClick={clearRecentNodes} title="Clear recent nodes">
              Clear recent
            </button>
          )}
        </div>
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
                title={expanded.has('Subgraphs') ? 'Collapse Subgraphs' : 'Expand Subgraphs'}
              >
                <Icon name={expanded.has('Subgraphs') ? 'chevronDown' : 'chevronRight'} size={12} />
                <span>Subgraphs</span>
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
                        title={`Add ${bp.name}`}
                      >
                        <span className="node-search-result-main">
                          <span className="node-search-result-title">{bp.name}</span>
                          <span className="node-search-result-desc">
                            {bp.workflow.nodes?.length ?? 0} nodes · {bp.inputPorts.length} in / {bp.outputPorts.length} out
                          </span>
                        </span>
                      </button>
                      <button
                        type="button"
                        onClick={() => deleteBlueprint(bp.id)}
                        title="Delete blueprint"
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
                    onClick={() => toggle(group.label)}
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
                      <NodeLibraryResult
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
