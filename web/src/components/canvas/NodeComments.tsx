// On-node comment pins + popover, rendered the React Flow way. A pin badge for
// each commented node is drawn in a <ViewportPortal> (flow coords, so it pans/
// zooms with the graph and sits at the node's top-right). Clicking a pin (or the
// node toolbar's comment button) opens a popover — also a viewport-portalled
// element in flow coords — to read the thread, resolve, and reply. Threading and
// persistence are handled upstream (the workflow's comments sync through the yjs
// collab doc); this component is pure presentation + dispatch.
import { useMemo, useState, useCallback } from 'react';
import { ViewportPortal, useReactFlow } from '@xyflow/react';
import { useTranslation } from 'react-i18next';
import type { Comment } from '../../collab/types';

interface NodeCommentsProps {
  comments: Comment[];
  currentUserId: string;
  currentUserName: string;
  currentUserColor: string;
  /** Controlled open thread (set by clicking a pin or the node toolbar). */
  openNodeId: string | null;
  onOpenChange: (nodeId: string | null) => void;
  onAddComment: (content: string, nodeId: string | null, parentId: string | null) => void;
  onResolveComment: (id: string) => void;
  onDeleteComment: (id: string) => void;
}

interface NodeThread {
  nodeId: string;
  count: number;
  unresolved: boolean;
  thread: Comment[];
}

// Not memoized: reads live node positions via rf.getNode(), so pins/popover must
// re-render with the canvas as nodes move.
export default function NodeComments({
  comments, currentUserId, currentUserName, currentUserColor,
  openNodeId, onOpenChange,
  onAddComment, onResolveComment, onDeleteComment,
}: NodeCommentsProps) {
  const { t } = useTranslation();
  const rf = useReactFlow();
  const [draft, setDraft] = useState('');

  // Group node-attached comments by node id (top-level threads only; replies
  // hang off their parent's `replies`).
  const byNode = useMemo(() => {
    const map = new Map<string, NodeThread>();
    for (const c of comments) {
      if (!c.node_id || c.parent_id) continue;
      const entry = map.get(c.node_id) ?? { nodeId: c.node_id, count: 0, unresolved: false, thread: [] };
      entry.thread.push(c);
      entry.count += 1 + (c.replies?.length ?? 0);
      entry.unresolved = entry.unresolved || !c.resolved;
      map.set(c.node_id, entry);
    }
    return map;
  }, [comments]);

  const submit = useCallback((nodeId: string) => {
    const text = draft.trim();
    if (!text) return;
    onAddComment(text, nodeId, null);
    setDraft('');
  }, [draft, onAddComment]);

  if (byNode.size === 0 && !openNodeId) return null;

  return (
    <ViewportPortal>
      {[...byNode.values()].map(entry => {
        const node = rf.getNode(entry.nodeId);
        if (!node) return null;
        const w = node.measured?.width ?? node.width ?? 0;
        const x = node.position.x + w - 6;
        const y = node.position.y - 10;
        return (
          <button
            key={`pin-${entry.nodeId}`}
            type="button"
            className={`collab-comment-pin nodrag nopan ${entry.unresolved ? 'unresolved' : ''}`}
            style={{ transform: `translate(${x}px, ${y}px)` }}
            title={t('canvas.comments.pinTitle', { count: entry.count })}
            aria-label={t('canvas.comments.pinTitle', { count: entry.count })}
            onClick={(e) => { e.stopPropagation(); onOpenChange(openNodeId === entry.nodeId ? null : entry.nodeId); setDraft(''); }}
          >
            <span aria-hidden>💬</span>
            <span className="collab-comment-count">{entry.count}</span>
          </button>
        );
      })}

      {openNodeId && (() => {
        const node = rf.getNode(openNodeId);
        if (!node) return null;
        const w = node.measured?.width ?? node.width ?? 0;
        const x = node.position.x + w + 8;
        const y = node.position.y - 10;
        const thread = byNode.get(openNodeId)?.thread ?? [];
        return (
          <div
            className="collab-comment-popover nodrag nopan"
            style={{ transform: `translate(${x}px, ${y}px)` }}
            onClick={(e) => e.stopPropagation()}
          >
            <div className="collab-comment-popover-head">
              <span>{t('canvas.comments.title')}</span>
              <button type="button" aria-label={t('common.close', 'Close')} onClick={() => onOpenChange(null)}><span aria-hidden>✕</span></button>
            </div>
            <div className="collab-comment-thread">
              {thread.length === 0 && <p className="collab-comment-empty">{t('canvas.comments.empty', 'No comments yet')}</p>}
              {thread.map(c => (
                <div key={c.id} className={`collab-comment ${c.resolved ? 'resolved' : ''}`}>
                  <div className="collab-comment-meta">
                    <span className="collab-comment-author" style={{ color: c.user_color }}>{c.user_name}</span>
                    <span className="collab-comment-actions">
                      {!c.resolved && (
                        <button type="button" title={t('canvas.comments.resolve', 'Resolve')} aria-label={t('canvas.comments.resolve', 'Resolve')} onClick={() => onResolveComment(c.id)}><span aria-hidden>✓</span></button>
                      )}
                      {c.user_id === currentUserId && (
                        <button type="button" className="danger" title={t('canvas.comments.delete', 'Delete')} aria-label={t('canvas.comments.delete', 'Delete')} onClick={() => onDeleteComment(c.id)}><span aria-hidden>🗑</span></button>
                      )}
                    </span>
                  </div>
                  <div className="collab-comment-body">{c.content}</div>
                  {c.replies?.map(r => (
                    <div key={r.id} className="collab-comment-reply">
                      <span className="collab-comment-author" style={{ color: r.user_color }}>{r.user_name}</span>
                      <div className="collab-comment-body">{r.content}</div>
                    </div>
                  ))}
                </div>
              ))}
            </div>
            <div className="collab-comment-compose">
              <input
                className="nodrag nopan"
                value={draft}
                placeholder={t('canvas.comments.placeholder', 'Add a comment…')}
                aria-label={t('canvas.comments.placeholder', 'Add a comment…')}
                style={{ ['--collab-user-color' as string]: currentUserColor }}
                onChange={(e) => setDraft(e.target.value)}
                onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); submit(openNodeId); } }}
              />
              <button type="button" onClick={() => submit(openNodeId)} title={`${currentUserName}`}>{t('canvas.comments.send', 'Send')}</button>
            </div>
          </div>
        );
      })()}
    </ViewportPortal>
  );
}

