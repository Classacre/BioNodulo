import { useDeferredValue, useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import type { NodeMetadata, ObjectInfo } from '../../types';
import './BiotoolsRegistryPanel.css';

interface RegistryTool {
  id: string;
  name: string;
  description: string;
  types: string[];
  topics: string[];
  nodes: string[];
}

interface RegistrySnapshot {
  records: number;
  updated_at: string;
  tools: RegistryTool[];
}

const PAGE_SIZE = 40;

export default function BiotoolsRegistryPanel({ objectInfo, onAddNode, onBack, onClose }: {
  objectInfo: ObjectInfo;
  onAddNode: (node: NodeMetadata) => void;
  onBack: () => void;
  onClose: () => void;
}) {
  const { t } = useTranslation();
  const [snapshot, setSnapshot] = useState<RegistrySnapshot | null>(null);
  const [error, setError] = useState(false);
  const [query, setQuery] = useState('');
  const [page, setPage] = useState(0);
  const deferredQuery = useDeferredValue(query);
  useEffect(() => {
    const controller = new AbortController();
    fetch(`${import.meta.env.BASE_URL}biotools-registry/index.json`, { signal: controller.signal })
      .then(async response => {
        if (!response.ok) throw new Error('Registry snapshot unavailable');
        const data = await response.json() as RegistrySnapshot;
        if (!Array.isArray(data.tools) || data.tools.length !== data.records) {
          throw new Error('Incomplete registry snapshot');
        }
        if (!controller.signal.aborted) setSnapshot(data);
      })
      .catch(() => { if (!controller.signal.aborted) setError(true); });
    return () => controller.abort();
  }, []);
  const searchable = useMemo(() => snapshot?.tools.map(tool => ({ tool, text:
    [tool.id, tool.name, tool.description, ...tool.types, ...tool.topics].join(' ').toLocaleLowerCase(),
  })) ?? [], [snapshot]);
  const generatedLinks = useMemo(() => {
    const links = new Map<string, string[]>();
    for (const [id, node] of Object.entries(objectInfo)) {
      const accession = node.declarative_runtime?.biotools_accession?.toLowerCase();
      if (accession) links.set(accession, [...(links.get(accession) ?? []), id]);
    }
    return links;
  }, [objectInfo]);
  const matches = useMemo(() => {
    const normalized = deferredQuery.trim().toLocaleLowerCase();
    const terms = normalized.split(/\s+/).filter(Boolean);
    const found = searchable.filter(row => terms.every(term => row.text.includes(term))).map(row => row.tool);
    if (!normalized) return found;
    const priority = (tool: RegistryTool) => {
      const id = tool.id.toLocaleLowerCase();
      const name = tool.name.toLocaleLowerCase();
      return id === normalized || name === normalized ? 0 : id.startsWith(normalized) || name.startsWith(normalized) ? 1 : 2;
    };
    return found.sort((a, b) => priority(a) - priority(b));
  }, [searchable, deferredQuery]);
  const pages = Math.max(1, Math.ceil(matches.length / PAGE_SIZE));
  const currentPage = Math.min(page, pages - 1);
  const visible = matches.slice(currentPage * PAGE_SIZE, (currentPage + 1) * PAGE_SIZE);
  return (
    <div className="rail-panel node-library-panel biotools-registry-panel">
      <div className="rail-panel-header">
        <button type="button" className="btn btn-sm" onClick={onBack}>{t('registry.back', 'Back to nodes')}</button>
        <span>bio.tools</span>
        <button type="button" className="btn btn-sm" onClick={onClose} aria-label={t('common.close', 'Close')}>×</button>
      </div>
      <div className="rail-panel-body">
        <p className="biotools-explanation">{t('registry.explanation', 'Discover registry tools. Metadata does not mean a tool is installed, executable here, or scientifically validated.')}</p>
        <input className="palette-search" type="search" value={query}
          aria-label={t('registry.search', 'Search bio.tools registry')}
          placeholder={t('registry.search', 'Search bio.tools registry')}
          onChange={event => { setQuery(event.target.value); setPage(0); }} />
        <p className="biotools-summary" role="status">
          {error ? t('registry.unavailable', 'The registry snapshot is unavailable in this build.') : !snapshot
            ? t('registry.loading', 'Loading registry metadata…')
            : t('registry.matches', { defaultValue: '{{matches}} matches · {{total}} registry records', matches: matches.length.toLocaleString(), total: snapshot.records.toLocaleString() })}
        </p>
        {snapshot && <p className="biotools-summary">{t('registry.updated', 'Snapshot')}: {snapshot.updated_at.slice(0, 10)} · <a href="https://bio.tools" target="_blank" rel="noreferrer">bio.tools contributors</a> · CC BY 4.0</p>}
        <div className="biotools-results">
          {visible.map(tool => {
            const linkedNodes = [...new Set([...tool.nodes, ...(generatedLinks.get(tool.id.toLowerCase()) ?? [])])]
              .map(id => objectInfo[id]).filter(Boolean);
            return <article className="biotools-result" key={tool.id}>
              <a href={`https://bio.tools/${encodeURIComponent(tool.id)}`} target="_blank" rel="noreferrer">{tool.name}</a>
              <small>{tool.id} · {tool.types.join(', ') || t('registry.unspecifiedType', 'Type unspecified')}</small>
              <p>{tool.description}</p>
              <small>{linkedNodes.length ? t('registry.linked', 'Linked app nodes; execution depends on your environment') : t('registry.metadataOnly', 'Metadata only · no linked app node')}</small>
              {linkedNodes.map(node => <button className="btn btn-sm" type="button" key={node.id} onClick={() => onAddNode(node)}
                title={node.declarative_runtime ? t('registry.generatedUnverified', 'Generated from an upstream executable description; scientific validation is pending') : undefined}>
                {t('registry.addLinked', { defaultValue: 'Add {{name}}', name: node.display_name || node.id })}
              </button>)}
            </article>;
          })}
        </div>
        {snapshot && <div className="biotools-pagination">
          <button className="btn btn-sm" type="button" disabled={currentPage === 0} onClick={() => setPage(currentPage - 1)}>{t('registry.previous', 'Previous')}</button>
          <span>{currentPage + 1} / {pages}</span>
          <button className="btn btn-sm" type="button" disabled={currentPage + 1 >= pages} onClick={() => setPage(currentPage + 1)}>{t('registry.next', 'Next')}</button>
        </div>}
      </div>
    </div>
  );
}
