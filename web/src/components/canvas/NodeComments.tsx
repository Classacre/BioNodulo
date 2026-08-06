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
import { markThreadRead, threadHasUnread } from '../../collab/commentReads';
import { NODE_WIDTH } from './canvasModel';

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
  /** Hide all comment pins on the canvas (persisted to a setting upstream). */
  onHideComments: () => void;
}

interface NodeThread {
  nodeId: string;
  count: number;
  unresolved: boolean;
  /** Holds something this reader has not seen (not the same as unresolved). */
  unread: boolean;
  thread: Comment[];
}

// Not memoized: reads live node positions via rf.getNode(), so pins/popover must
// re-render with the canvas as nodes move.
export default function NodeComments({
  comments, currentUserId, currentUserName, currentUserColor,
  openNodeId, onOpenChange,
  onAddComment, onResolveComment, onDeleteComment, onHideComments,
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
      const entry = map.get(c.node_id) ?? { nodeId: c.node_id, count: 0, unresolved: false, unread: false, thread: [] };
      entry.thread.push(c);
      entry.count += 1 + (c.replies?.length ?? 0);
      entry.unresolved = entry.unresolved || !c.resolved;
      map.set(c.node_id, entry);
    }
    for (const entry of map.values()) {
      entry.unread = threadHasUnread(entry.nodeId, entry.thread, currentUserId);
    }
    return map;
  }, [comments, currentUserId]);

  // Opening a thread is what marks it read. Done here rather than in the click
  // handler so opening from the node toolbar counts too.
  const openThread = useCallback((nodeId: string | null) => {
    if (nodeId) markThreadRead(nodeId);
    onOpenChange(nodeId);
  }, [onOpenChange]);

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
        // Stable width so the pin sits at the true top-right corner immediately
        // (measured?.width is 0 for a frame, which would flash it to the left).
        const w = node.width ?? node.measured?.width ?? NODE_WIDTH;
        // Anchor at the node's top-right corner (the pin's own transform centres it).
        const x = node.position.x + w;
        const y = node.position.y;
        return (
          // Two elements: the anchor is positioned by transform, the badge
          // inside it animates. One element cannot do both, because the bounce
          // animates `transform` and would overwrite the placement.
          <div
            key={`pin-${entry.nodeId}`}
            className="collab-comment-anchor"
            style={{ transform: `translate(${x}px, ${y}px)` }}
          >
            <button
              type="button"
              className={`collab-comment-pin nodrag nopan ${entry.unresolved ? 'open' : 'resolved'}${entry.unread ? ' unread' : ''}`}
              title={entry.unread
                ? t('canvas.comments.pinTitleUnread', { count: entry.count, defaultValue: '{{count}} comments, unread' })
                : t('canvas.comments.pinTitle', { count: entry.count })}
              aria-label={entry.unread
                ? t('canvas.comments.pinTitleUnread', { count: entry.count, defaultValue: '{{count}} comments, unread' })
                : t('canvas.comments.pinTitle', { count: entry.count })}
              onClick={(e) => { e.stopPropagation(); openThread(openNodeId === entry.nodeId ? null : entry.nodeId); setDraft(''); }}
            >
              {entry.count}
            </button>
          </div>
        );
      })}

      {openNodeId && (() => {
        const node = rf.getNode(openNodeId);
        if (!node) return null;
        // Pinned to the node's TOP-RIGHT: anchor at the top-right corner and let
        // the popover open downward/rightward from there (no left/right flipping).
        const w = node.width ?? node.measured?.width ?? NODE_WIDTH;
        const x = node.position.x + w + 10;
        const y = node.position.y;
        const thread = byNode.get(openNodeId)?.thread ?? [];
        const hasUnresolved = thread.some(c => !c.resolved);
        return (
          <div
            className="collab-comment-popover nodrag nopan"
            style={{ transform: `translate(${x}px, ${y}px)` }}
            onClick={(e) => e.stopPropagation()}
          >
            <div className="collab-comment-popover-head">
              <span>{t('canvas.comments.title')}</span>
              <span className="collab-comment-head-actions">
                {hasUnresolved && (
                  <button type="button" title={t('canvas.comments.closeAll')} aria-label={t('canvas.comments.closeAll')} onClick={() => thread.forEach(c => { if (!c.resolved) onResolveComment(c.id); })}>{t('canvas.comments.closeAll')}</button>
                )}
                <button type="button" title={t('canvas.comments.hide')} aria-label={t('canvas.comments.hide')} onClick={() => { onHideComments(); onOpenChange(null); }}>{t('canvas.comments.hide')}</button>
                <button type="button" aria-label={t('common.close', 'Close')} onClick={() => onOpenChange(null)}><span aria-hidden>✕</span></button>
              </span>
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

