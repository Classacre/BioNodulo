import { useEffect, useMemo, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { useTranslation } from 'react-i18next';
import { Background, Controls, Handle, MarkerType, Position, ReactFlow, type Edge, type Node, type NodeProps } from '@xyflow/react';
import type { NodeMetadata, ObjectInfo } from '../../types';
import { useNodeSearch } from '../../utils/nodeSearch';
import { nodeCategoryDisplayLabel } from '../../utils/nodeCategories';
import { safeKnowledgeUrl } from '../../utils/nodeKnowledge';
import { buildToolGraphIndex, graphCoverage, isDeprecated, neighborId, normalizeDoi, relatedTools, type RelationKind, type ToolRelation } from '../../utils/toolKnowledgeGraph';
import { saveToFile } from '../../utils';
import Dialog from '../ui/Dialog';
import './ToolAtlas.css';

type AtlasNode = Node<{ label: string; subtitle: string; focus?: boolean }, 'atlas'>;
function AtlasCard({ data }: NodeProps<AtlasNode>) {
  return <div className={`atlas-card ${data.focus ? 'is-focus' : ''}`}>
    <Handle type="target" position={Position.Left} isConnectable={false} />
    <strong>{data.label}</strong><span>{data.subtitle}</span>
    <Handle type="source" position={Position.Right} isConnectable={false} />
  </div>;
}
const nodeTypes = { atlas: AtlasCard };
const relatedKinds: RelationKind[] = ['tool', 'operation', 'topic', 'citation', 'category', 'alternative_to', 'complements', 'documented_successor', 'superseded_by'];
const relationColors = { format: '#0d9488', metadata: '#8b5cf6', documented: '#d97706' };
const NEIGHBORS_PER_PAGE = 6;

export default function ToolAtlas({ objectInfo, onAddNode, onClose }: {
  objectInfo: ObjectInfo; onAddNode: (meta: NodeMetadata) => void; onClose: () => void;
}) {
  const { t } = useTranslation();
  const index = useMemo(() => buildToolGraphIndex(objectInfo), [objectInfo]);
  const coverage = useMemo(() => graphCoverage(index), [index]);
  const [query, setQuery] = useState('');
  const [category, setCategory] = useState('');
  const [focusId, setFocusId] = useState<string | null>(null);
  const headingRef = useRef<HTMLHeadingElement>(null);
  useEffect(() => { headingRef.current?.focus({ preventScroll: true }); }, [focusId]);
  const [history, setHistory] = useState<string[]>([]);
  const [lens, setLens] = useState<'flow' | 'related'>('flow');
  const [relationFilter, setRelationFilter] = useState('');
  const [formatFilter, setFormatFilter] = useState('');
  const [direction, setDirection] = useState('');
  const [page, setPage] = useState(0);
  const [neighborsPage, setNeighborsPage] = useState(0);
  const [selectedRelation, setSelectedRelation] = useState<ToolRelation | null>(null);
  const searchableNodes = useMemo(() => Object.fromEntries(Object.entries(index.nodes).map(([id, meta]) => [id, {
    ...meta, search_aliases: [...(meta.search_aliases || []), ...(meta.return_types || []),
      ...Object.values({ ...meta.input_types?.required, ...meta.input_types?.optional }).map(spec => spec.type),
      ...(meta.knowledge?.topics || []).map(term => term.label), ...(meta.knowledge?.operations || []).map(term => term.label)],
  }])), [index]);
  const searchResults = useNodeSearch(searchableNodes, query);
  const results = useMemo(() => searchResults.map(r => r.meta).filter(m => !category || (m.category || 'Other') === category), [searchResults, category]);
  const categories = useMemo(() => [...index.categories.entries()].sort(([a], [b]) => a.localeCompare(b)), [index]);
  const focus = focusId ? index.nodes[focusId] : undefined;
  const relations = useMemo(() => focusId ? relatedTools(index, focusId) : [], [index, focusId]);
  const formats = useMemo(() => [...new Set(relations.filter(r => r.kind === 'format').map(r => r.value))].sort(), [relations]);
  const filteredRelations = useMemo(() => relations.filter(r => lens === 'flow'
    ? r.kind === 'format' && (!formatFilter || r.value === formatFilter)
      && (!direction || (direction === 'before' ? r.target === focusId : r.source === focusId))
    : r.kind !== 'format' && (!relationFilter || r.kind === relationFilter)), [relations, lens, formatFilter, direction, focusId, relationFilter]);
  const neighborIds = useMemo(() => {
    const ranks = new Map<string, number>();
    for (const r of filteredRelations) {
      const id = neighborId(r, focusId!);
      const rank = r.evidence ? -1 : r.kind === 'category' ? 5 : r.kind === 'citation' ? 4 : 0;
      ranks.set(id, Math.min(rank, ranks.get(id) ?? Infinity));
    }
    return [...ranks.keys()].sort((a, b) => ranks.get(a)! - ranks.get(b)! || index.nodes[a].display_name.localeCompare(index.nodes[b].display_name) || a.localeCompare(b));
  }, [filteredRelations, focusId, index]);
  const neighborPageCount = Math.max(1, Math.ceil(neighborIds.length / NEIGHBORS_PER_PAGE));
  const actualNeighborsPage = Math.min(neighborsPage, neighborPageCount - 1);
  const visibleIds = neighborIds.slice(actualNeighborsPage * NEIGHBORS_PER_PAGE, (actualNeighborsPage + 1) * NEIGHBORS_PER_PAGE);
  const visibleSet = new Set(visibleIds);
  const visibleRelations = filteredRelations.filter(r => visibleSet.has(neighborId(r, focusId!)));
  const labelCategory = (value: string) => nodeCategoryDisplayLabel(value, t, t('nodeLibrary.otherCategory'));
  const relationName = (kind: RelationKind) => t(`toolAtlas.relations.${kind}`);

  const focusNode = (id: string) => {
    if (focusId && focusId !== id) setHistory(prev => [...prev, focusId].slice(-40));
    setFocusId(id); setSelectedRelation(null); setNeighborsPage(0); setFormatFilter('');
  };
  const resetView = () => { setNeighborsPage(0); setSelectedRelation(null); };
  const graph = useMemo(() => {
    if (!focus || !focusId) return { nodes: [], edges: [] };
    const directedKinds = ['format', 'documented_successor', 'superseded_by'];
    const before = visibleIds.filter((id, i) => {
      const directed = visibleRelations.filter(r => neighborId(r, focusId) === id && directedKinds.includes(r.kind));
      return directed.length ? directed.some(r => r.source === id && r.target === focusId) : i % 2 === 0;
    });
    const after = visibleIds.filter(id => !before.includes(id));
    const height = Math.max(before.length, after.length, 1) * 106;
    const nodes: AtlasNode[] = [{ id: focusId, type: 'atlas', position: { x: 380, y: height / 2 - 40 }, data: { label: focus.display_name, subtitle: focus.id, focus: true } }];
    for (const [ids, x] of [[before, 0], [after, 760]] as const) {
      ids.forEach((id, i) => nodes.push({ id, type: 'atlas', position: { x, y: i * 106 + (height - ids.length * 106) / 2 }, data: { label: index.nodes[id].display_name, subtitle: labelCategory(index.nodes[id].category) } }));
    }
    // One visual edge per neighbor; every port-level reason remains in the list.
    const edges: Edge[] = visibleIds.map(id => {
      const matches = visibleRelations.filter(r => neighborId(r, focusId) === id);
      const r = matches.find(item => item.evidence) || matches.find(item => item.source === (before.includes(id) ? id : focusId)) || matches[0];
      const color = r.evidence ? relationColors.documented : r.kind === 'format' ? relationColors.format : relationColors.metadata;
      return { id: `relation:${id}`,
        source: directedKinds.includes(r.kind) ? r.source : before.includes(id) ? id : focusId,
        target: directedKinds.includes(r.kind) ? r.target : before.includes(id) ? focusId : id,
        label: `${r.kind === 'format' ? r.value : relationName(r.kind)}${matches.length > 1 ? ` +${matches.length - 1}` : ''}`,
        data: { relation: r },
        style: { stroke: color, strokeDasharray: r.evidence ? undefined : '5 4', strokeWidth: 1.5 },
        markerEnd: r.kind === 'format' || r.kind === 'documented_successor' || r.kind === 'superseded_by' ? { type: MarkerType.ArrowClosed, color } : undefined,
        labelStyle: { fill: 'var(--text)', fontSize: 11 }, labelBgStyle: { fill: 'var(--surface)' },
      };
    });
    return { nodes, edges };
    // Labels are localized when the locale changes; index and filters determine the view.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [focusId, focus, index, lens, actualNeighborsPage, filteredRelations, t]);

  const exportView = () => saveToFile(JSON.stringify({
    schema_version: 1, exported_at: new Date().toISOString(), scope: 'builtin-tool-atlas-view',
    catalog_counts: coverage, focus: focusId, filters: { query, category, lens, relationFilter, formatFilter, direction },
    nodes: focus ? [focus, ...visibleIds.map(id => index.nodes[id])] : Object.values(index.nodes),
    relations: focus ? visibleRelations : [],
    limitations: 'Descriptive metadata and exact port-type candidates; no execution or scientific compatibility is asserted. View is paginated; not a complete edge export.',
  }, null, 2), 'bionodulo-tool-atlas.json', 'application/json');

  const renderRelation = (r: ToolRelation, i: number) => <li key={`${r.source}/${r.target}/${r.kind}/${i}`}>
    <button type="button" className="atlas-reason" onClick={() => setSelectedRelation(r)}>
      <strong>{index.nodes[neighborId(r, focusId!)]?.display_name}</strong>
      <span>{r.kind === 'format' ? `${r.sourcePort} → ${r.targetPort} · ${r.value}` : `${relationName(r.kind)} · ${r.value}`}</span>
    </button>
    <button type="button" className="btn btn-sm" onClick={() => focusNode(neighborId(r, focusId!))}>{t('toolAtlas.explore')}</button>
  </li>;

  return createPortal(<Dialog title={t('toolAtlas.title')} onClose={onClose} width={1440} maxHeight="94vh" className="tool-atlas" dismissOnBackdrop={false}>
    <div className="atlas-intro">
      <div><p>{t('toolAtlas.subtitle')}</p><div className="atlas-counts" aria-label={t('toolAtlas.coverage')}>
        <span><b>{coverage.nodes.toLocaleString()}</b> {t('toolAtlas.builtins')}</span>
        <span><b>{coverage.categories}</b> {t('toolAtlas.categories')}</span>
        <span><b>{coverage.withReferences}</b> {t('toolAtlas.withReferences')}</span>
        <span><b>{coverage.withSourceChecks}</b> {t('toolAtlas.withChecks')}</span>
      </div></div>
      <button type="button" className="btn btn-sm" onClick={exportView}>{t('toolAtlas.exportView')}</button>
    </div>
    <div className="atlas-layout">
      <aside className="atlas-library" aria-label={t('toolAtlas.browse')}>
        <label>{t('toolAtlas.search')}<input type="search" value={query} onChange={e => { setQuery(e.target.value); setPage(0); }} placeholder={t('toolAtlas.searchPlaceholder')} /></label>
        <label>{t('toolAtlas.category')}<select value={category} onChange={e => { setCategory(e.target.value); setPage(0); }}>
          <option value="">{t('toolAtlas.allCategories')}</option>
          {categories.map(([name, ids]) => <option key={name} value={name}>{labelCategory(name)} ({ids.length})</option>)}
        </select></label>
        <div className="atlas-list-count" role="status">{t('toolAtlas.results', { count: results.length })}</div>
        <div className="atlas-results">
          {results.slice(page * 40, (page + 1) * 40).map(meta => <button type="button" key={meta.id} className={`atlas-result ${focusId === meta.id ? 'is-active' : ''}`} onClick={() => focusNode(meta.id)} aria-pressed={focusId === meta.id}>
            <strong>{meta.display_name}</strong><span>{labelCategory(meta.category)} · {meta.id}</span>
            {isDeprecated(meta) && <span>{t('toolAtlas.deprecated')}</span>}
          </button>)}
          {results.length === 0 && <p>{t('toolAtlas.noResults')}</p>}
        </div>
        <div className="atlas-pagination">
          <button className="btn btn-sm" disabled={!page} onClick={() => setPage(p => p - 1)}>{t('common.previous', 'Previous')}</button>
          <span>{page + 1} / {Math.max(1, Math.ceil(results.length / 40))}</span>
          <button className="btn btn-sm" disabled={(page + 1) * 40 >= results.length} onClick={() => setPage(p => p + 1)}>{t('common.next', 'Next')}</button>
        </div>
      </aside>
      <main className="atlas-main">
        {!focus ? <section className="atlas-overview">
          <h2>{t('toolAtlas.overviewTitle')}</h2><p>{t('toolAtlas.overviewHelp')}</p>
          {coverage.nodes === 0 && <p role="status">{t('toolAtlas.empty')}</p>}
          <div className="atlas-category-grid">{categories.map(([name, ids], i) => <button type="button" key={name} onClick={() => { setCategory(name); setQuery(''); setPage(0); focusNode(ids[0]); }} style={{ borderTopColor: `hsl(${(i * 47) % 360} 44% 47%)` }}>
            <strong>{labelCategory(name)}</strong><span>{t('toolAtlas.nodeCount', { count: ids.length })}</span>
          </button>)}</div>
          <p className="atlas-note">{t('toolAtlas.overviewScope')}</p>
        </section> : <>
          <div className="atlas-navigation">
            <button type="button" className="btn btn-sm" disabled={history.length === 0} onClick={() => { setFocusId(history[history.length - 1]); setHistory(h => h.slice(0, -1)); setFormatFilter(''); resetView(); }}>{t('toolAtlas.back')}</button>
            <button type="button" className="btn btn-sm" onClick={() => { setFocusId(null); setHistory([]); setSelectedRelation(null); }}>{t('toolAtlas.overview')}</button>
            <span>{labelCategory(focus.category)}</span>
          </div>
          <div className="atlas-focus-heading"><div><h2 ref={headingRef} tabIndex={-1}>{focus.display_name}</h2><code>{focus.id}</code>{focus.version && <span> · v{focus.version}</span>}</div>
            <button type="button" className="btn btn-primary" onClick={() => { onAddNode(focus); onClose(); }}>{t('toolAtlas.add')}</button>
          </div>
          <p className="atlas-description">{focus.description || t('toolAtlas.noDescription')}</p>
          {isDeprecated(focus) && <p className="atlas-note">{t('toolAtlas.deprecated')} · {focus.deprecation_message || focus.lifecycle?.deprecation_message} {focus.replaced_by || focus.lifecycle?.replaced_by}</p>}
          <div className="atlas-lenses" role="group" aria-label={t('toolAtlas.connectionView')}>
            <button type="button" aria-pressed={lens === 'flow'} onClick={() => { setLens('flow'); resetView(); }}>{t('toolAtlas.flow')}</button>
            <button type="button" aria-pressed={lens === 'related'} onClick={() => { setLens('related'); resetView(); }}>{t('toolAtlas.related')}</button>
            {lens === 'flow' ? <>
              <select aria-label={t('toolAtlas.format')} value={formatFilter} onChange={e => { setFormatFilter(e.target.value); resetView(); }}><option value="">{t('toolAtlas.allFormats')}</option>{formats.map(format => <option key={format}>{format}</option>)}</select>
              <select aria-label={t('toolAtlas.direction')} value={direction} onChange={e => { setDirection(e.target.value); resetView(); }}><option value="">{t('toolAtlas.bothDirections')}</option><option value="before">{t('toolAtlas.before')}</option><option value="after">{t('toolAtlas.after')}</option></select>
            </> : <select aria-label={t('toolAtlas.relationType')} value={relationFilter} onChange={e => { setRelationFilter(e.target.value); resetView(); }}><option value="">{t('toolAtlas.allRelations')}</option>{relatedKinds.map(kind => <option key={kind} value={kind}>{relationName(kind)}</option>)}</select>}
          </div>
          <p className="atlas-note">{t(lens === 'flow' ? 'toolAtlas.flowCaveat' : 'toolAtlas.relatedCaveat')}</p>
          <div className="atlas-graph" aria-label={t('toolAtlas.graph')}>
            <ReactFlow key={`${focusId}/${lens}/${actualNeighborsPage}/${formatFilter}/${direction}/${relationFilter}`} nodes={graph.nodes} edges={graph.edges} nodeTypes={nodeTypes}
              onNodeClick={(_, node) => { if (node.id !== focusId) focusNode(node.id); }}
              onEdgeClick={(_, edge) => setSelectedRelation(edge.data?.relation as ToolRelation)}
              nodesDraggable={false} nodesConnectable={false} edgesReconnectable={false} deleteKeyCode={null}
              fitView fitViewOptions={{ padding: 0.08, maxZoom: 1 }} minZoom={0.25} maxZoom={1.5} colorMode="system">
              <Background gap={20} size={1} /><Controls showInteractive={false} />
            </ReactFlow>
          </div>
          <div className="atlas-pagination">
            <span>{t('toolAtlas.neighbors', { shown: visibleIds.length, total: neighborIds.length })}</span>
            <button className="btn btn-sm" disabled={actualNeighborsPage === 0} onClick={() => { setNeighborsPage(actualNeighborsPage - 1); setSelectedRelation(null); }}>{t('common.previous', 'Previous')}</button>
            <span>{actualNeighborsPage + 1} / {neighborPageCount}</span>
            <button className="btn btn-sm" disabled={actualNeighborsPage + 1 >= neighborPageCount} onClick={() => { setNeighborsPage(actualNeighborsPage + 1); setSelectedRelation(null); }}>{t('common.next', 'Next')}</button>
          </div>
          {selectedRelation && <section className="atlas-evidence" aria-label={t('toolAtlas.connectionEvidence')}>
            <h3>{relationName(selectedRelation.kind)}</h3>
            <p>{index.nodes[selectedRelation.source].display_name}{selectedRelation.sourcePort && ` (${selectedRelation.sourcePort})`} {['format', 'documented_successor', 'superseded_by'].includes(selectedRelation.kind) ? '→' : '—'} {index.nodes[selectedRelation.target].display_name}{selectedRelation.targetPort && ` (${selectedRelation.targetPort})`}</p>
            <p>{selectedRelation.value}</p>
            {selectedRelation.evidence ? <p><a href={selectedRelation.evidence.url} target="_blank" rel="noreferrer">{t('toolAtlas.source')}</a> · {t('toolAtlas.checked', { date: selectedRelation.evidence.checked_at })}</p> : <p>{t('toolAtlas.inferred')}</p>}
          </section>}
          <details className="atlas-reasons" open><summary>{t('toolAtlas.reasons')}</summary>
            {visibleRelations.length ? <ul>{visibleRelations.map(renderRelation)}</ul> : <p>{t('toolAtlas.noConnections')}</p>}
          </details>
          <section className="atlas-references" aria-label={t('toolAtlas.references')}><h3>{t('toolAtlas.references')}</h3>
            {focus.citation_text && <p>{focus.citation_text}</p>}
            <ul>{[...new Set([...(focus.citation_dois || []).map(doi => `https://doi.org/${normalizeDoi(doi)}`), ...(focus.citation_urls || [])])].filter(url => safeKnowledgeUrl(url)).map(url => <li key={url}><a href={url} target="_blank" rel="noreferrer">{url}</a></li>)}</ul>
            {!focus.citation_text && !focus.citation_dois?.length && !focus.citation_urls?.length && <p>{t('toolAtlas.noReferences')}</p>}
            {focus.knowledge?.citation_evidence?.map((e, i) => <p key={i}><a href={e.source_url} target="_blank" rel="noreferrer">{e.identifier}</a> · {t('toolAtlas.checked', { date: e.checked_at })}<br />{e.note}</p>)}
            <p className="atlas-note">{t('toolAtlas.citationCaveat')}</p><p>{t('toolAtlas.exportHelp')}</p>
            {safeKnowledgeUrl(focus.documentation_url) && <a href={focus.documentation_url} target="_blank" rel="noreferrer">{t('toolAtlas.documentation')}</a>}
          </section>
        </>}
      </main>
    </div>
  </Dialog>, document.body);
}
