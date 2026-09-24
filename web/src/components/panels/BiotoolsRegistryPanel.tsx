import { useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { apiGet } from '../../api/client';
import type { NodeMetadata, ObjectInfo } from '../../types';
import './BiotoolsRegistryPanel.css';

interface RegistryEntry {
  node_id: string;
  accession: string;
  name: string;
  description: string;
  tool_types: string[];
  topics: string[];
  operations: string[];
  execution_status: 'definition_only';
  blockers: string[];
  reference_url: string;
  linked_node_ids: string[];
  runnable_node_ids: string[];
}

interface RegistryPage {
  schema_version: number;
  total: number;
  matched_count: number;
  offset: number;
  limit: number;
  snapshot: { records: number; sha256: string; updated_at: string };
  entries: RegistryEntry[];
}

const PAGE_SIZE = 40;

export default function BiotoolsRegistryPanel({ objectInfo, onAddNode, onAddGeneratedNode, onBack, onClose }: {
  objectInfo: ObjectInfo;
  onAddNode: (node: NodeMetadata) => void;
  onAddGeneratedNode: (nodeId: string) => Promise<void>;
  onBack: () => void;
  onClose: () => void;
}) {
  const { t } = useTranslation();
  const [query, setQuery] = useState('');
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(0);
  const [result, setResult] = useState<RegistryPage | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [retry, setRetry] = useState(0);
  const [adding, setAdding] = useState<string | null>(null);
  const [addError, setAddError] = useState<string | null>(null);
  const requestRevision = useRef(0);
  const edited = useRef(false);

  useEffect(() => {
    if (!edited.current) return;
    const timer = window.setTimeout(() => {
      setPage(0);
      setSearch(query.trim());
      if (edited.current) {
        edited.current = false;
        setRetry(value => value + 1);
      }
    }, 250);
    return () => window.clearTimeout(timer);
  }, [query]);

  useEffect(() => {
    const controller = new AbortController();
    const revision = ++requestRevision.current;
    setLoading(true);
    setError(null);
    setResult(null);
    const params = new URLSearchParams({ q: search, offset: String(page * PAGE_SIZE), limit: String(PAGE_SIZE) });
    apiGet<RegistryPage>(`/registry/nodes?${params}`, { signal: controller.signal })
      .then(data => {
        if (data.schema_version !== 1 || !Array.isArray(data.entries) || !Number.isFinite(data.matched_count)) {
          throw new Error('Invalid registry response');
        }
        if (!controller.signal.aborted && revision === requestRevision.current) setResult(data);
      })
      .catch(reason => { if (!controller.signal.aborted && revision === requestRevision.current) setError(reason instanceof Error ? reason.message : String(reason)); })
      .finally(() => { if (!controller.signal.aborted && revision === requestRevision.current) setLoading(false); });
    return () => controller.abort();
  }, [search, page, retry]);

  const addDefinition = async (entry: RegistryEntry) => {
    setAdding(entry.node_id);
    setAddError(null);
    try {
      await onAddGeneratedNode(entry.node_id);
    } catch (reason) {
      setAddError(reason instanceof Error ? reason.message : String(reason));
    } finally {
      setAdding(null);
    }
  };

  const pages = result ? Math.max(1, Math.ceil(result.matched_count / PAGE_SIZE)) : 1;
  return (
    <div className="rail-panel node-library-panel biotools-registry-panel">
      <div className="rail-panel-header">
        <button type="button" className="btn btn-sm" onClick={onBack}>{t('registry.back', 'Back to nodes')}</button>
        <span>bio.tools</span>
        <button type="button" className="btn btn-sm" onClick={onClose} aria-label={t('common.close', 'Close')}>×</button>
      </div>
      <div className="rail-panel-body">
        <p className="biotools-explanation">{t('registry.generatedExplanation', 'Every bio.tools record can be added as a reference node. These generated definitions have no execution binding or inferred ports. Exact linked app nodes are shown separately where available.')}</p>
        <input className="palette-search" type="search" value={query}
          aria-label={t('registry.search', 'Search bio.tools registry')}
          placeholder={t('registry.search', 'Search bio.tools registry')}
          onChange={event => { requestRevision.current++; edited.current = true; setResult(null); setLoading(true); setQuery(event.target.value); }} />
        <p className="biotools-summary" role="status">
          {error ? t('registry.unavailable', 'Registry nodes are unavailable.') : loading
            ? t('registry.loading', 'Loading registry nodes…')
            : result && t('registry.matches', { defaultValue: '{{matches}} matches · {{total}} registry records', matches: result.matched_count.toLocaleString(), total: result.total.toLocaleString() })}
        </p>
        {error && <button type="button" className="btn btn-sm" onClick={() => setRetry(value => value + 1)}>{t('registry.retry', 'Retry')}</button>}
        {result && <p className="biotools-summary">{t('registry.updated', 'Snapshot')}: {result.snapshot.updated_at.slice(0, 10)} · <a href="https://bio.tools" target="_blank" rel="noreferrer">bio.tools contributors</a> · CC BY 4.0</p>}
        {addError && <p className="biotools-error" role="alert">{t('registry.addFailed', 'Could not add registry node')}: {addError}</p>}
        <div className="biotools-results">
          {result?.entries.map(entry => {
            const linkedNodes = [...new Set(entry.linked_node_ids ?? [])].map(id => objectInfo[id]).filter((node): node is NodeMetadata => Boolean(node));
            return <article className="biotools-result" key={entry.node_id}>
              <a href={entry.reference_url} target="_blank" rel="noreferrer">{entry.name}</a>
              <small>{entry.accession} · {entry.tool_types.join(', ') || t('registry.unspecifiedType', 'Type unspecified')}</small>
              {(entry.topics.length > 0 || entry.operations.length > 0) && <small>{[...entry.topics, ...entry.operations].join(' · ')}</small>}
              {entry.description && <p>{entry.description}</p>}
              <small>{t('registry.definitionOnly', 'Execution unavailable for this generated definition')}</small>
              {entry.blockers.length > 0 && <small>{entry.blockers.join('; ')}</small>}
              <button className="btn btn-sm" type="button" disabled={adding !== null} onClick={() => void addDefinition(entry)}>
                {adding === entry.node_id ? t('registry.adding', 'Adding…') : t('registry.addDefinition', 'Add reference node')}
              </button>
              {linkedNodes.length > 0 && <small>{t('registry.exactLinked', 'Exact linked app nodes (execution depends on your environment):')}</small>}
              {linkedNodes.map(node => <button className="btn btn-sm" type="button" key={node.id} onClick={() => onAddNode(node)}>
                {t('registry.addLinked', { defaultValue: 'Add {{name}}', name: node.display_name || node.id })}
              </button>)}
            </article>;
          })}
        </div>
        {result && <div className="biotools-pagination">
          <button className="btn btn-sm" type="button" disabled={page === 0} onClick={() => setPage(value => value - 1)}>{t('registry.previous', 'Previous')}</button>
          <span>{page + 1} / {pages}</span>
          <button className="btn btn-sm" type="button" disabled={page + 1 >= pages} onClick={() => setPage(value => value + 1)}>{t('registry.next', 'Next')}</button>
        </div>}
      </div>
    </div>
  );
}
