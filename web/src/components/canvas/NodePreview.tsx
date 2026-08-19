// Inline run-output preview rendered at the bottom of a node body. Images
// render inline (click opens the lightbox), tsv/csv previews render a compact
// mini-table (fetched once per run/node, cached), everything else shows a chip
// that opens the existing HTML preview modal. Only the LATEST run with a
// preview for the node is shown (see deriveLatestPreviews); while a run is
// executing it carries no previews, so nothing flickers mid-run.
import { memo, useEffect, useState } from 'react';
import { useAtomValue, useSetAtom } from 'jotai';
import { useTranslation } from 'react-i18next';
import { nodePreviewsAtom } from '../../state/nodePreviews';
import { openLightboxAtom, htmlPreviewStateAtom } from '../../state/lightboxAtoms';
import { appPath } from '../../utils/appBase';
import { apiGetText } from '../../api/client';
import {
  parseDelimitedPreview,
  previewKindForPath,
  type NodePreviewRef,
  type TablePreviewData,
} from '../../utils/nodePreview';

// Fetch-once cache for table previews: one in-flight/finished request per URL.
const tableCache = new Map<string, Promise<string>>();

function fetchTableText(src: string): Promise<string> {
  let pending = tableCache.get(src);
  if (!pending) {
    pending = apiGetText(src);
    tableCache.set(src, pending);
    // A failed fetch should not poison the cache forever — allow one retry on
    // the next render by dropping rejected entries.
    pending.catch(() => tableCache.delete(src));
  }
  return pending;
}

function useTablePreview(src: string): { table: TablePreviewData | null; error: boolean } {
  const [table, setTable] = useState<TablePreviewData | null>(null);
  const [error, setError] = useState(false);
  useEffect(() => {
    let cancelled = false;
    setError(false);
    fetchTableText(src)
      .then(text => { if (!cancelled) setTable(parseDelimitedPreview(text, 5)); })
      .catch(() => { if (!cancelled) setError(true); });
    return () => { cancelled = true; };
  }, [src]);
  return { table, error };
}

function TablePreviewView({ src }: { src: string }) {
  const { t } = useTranslation();
  const { table, error } = useTablePreview(src);
  if (error) return <div className="bio-node-preview-footer">{t('canvas.previewLoadFailed')}</div>;
  if (!table || table.header.length === 0) return null;
  return (
    <div className="bio-node-preview-table-wrap nodrag nowheel">
      <table className="bio-node-preview-table">
        <thead>
          <tr>{table.header.map((cell, i) => <th key={i}>{cell}</th>)}</tr>
        </thead>
        <tbody>
          {table.rows.map((row, ri) => (
            <tr key={ri}>{row.map((cell, ci) => <td key={ci}>{cell}</td>)}</tr>
          ))}
        </tbody>
      </table>
      {table.truncated && (
        <div className="bio-node-preview-footer">
          {t('canvas.previewMoreRows', { count: table.totalRows - table.rows.length })}
        </div>
      )}
    </div>
  );
}

function NodePreviewBody({ preview }: { preview: NodePreviewRef }) {
  const { t } = useTranslation();
  const openLightbox = useSetAtom(openLightboxAtom);
  const setHtmlPreview = useSetAtom(htmlPreviewStateAtom);
  // Per-node collapse toggle (component state only — deliberately not
  // persisted). Expanded by default when a preview exists.
  const [collapsed, setCollapsed] = useState(false);
  const kind = previewKindForPath(preview.path);
  const src = appPath(`/api/previews/${preview.runId}/${preview.nodeId}?path=${encodeURIComponent(preview.path)}`);
  const filename = preview.path.split(/[\\/]/).pop() || preview.path;

  return (
    <div className="bio-node-preview nodrag" data-preview-kind={kind}>
      <button
        type="button"
        className="bio-node-preview-toggle nodrag"
        onClick={() => setCollapsed(c => !c)}
        title={collapsed ? t('canvas.previewExpand') : t('canvas.previewCollapse')}
        aria-expanded={!collapsed}
      >
        <span aria-hidden className={`bio-node-preview-chevron ${collapsed ? 'collapsed' : ''}`}>▾</span>
        <span className="bio-node-preview-name" title={preview.path}>{filename}</span>
      </button>
      {!collapsed && kind === 'image' && (
        <img
          className="bio-node-preview-img nodrag"
          src={src}
          alt={filename}
          onClick={() => openLightbox({ images: [{ src, alt: filename, filename }], index: 0 })}
        />
      )}
      {!collapsed && kind === 'table' && <TablePreviewView src={src} />}
      {!collapsed && kind === 'other' && (
        <button
          type="button"
          className="bio-node-preview-chip nodrag"
          onClick={() => setHtmlPreview({ src, filename })}
        >
          {t('canvas.previewAvailable')}
        </button>
      )}
    </div>
  );
}

function NodePreview({ nodeId }: { nodeId: string }) {
  const preview = useAtomValue(nodePreviewsAtom)[nodeId];
  if (!preview) return null;
  return <NodePreviewBody preview={preview} />;
}

export default memo(NodePreview);
