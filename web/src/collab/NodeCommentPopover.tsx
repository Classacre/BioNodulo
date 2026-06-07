import { useMemo, useState } from 'react';
import type { KeyboardEvent } from 'react';
import { useTranslation } from 'react-i18next';
import Icon from '../components/ui/Icon';
import { COMMENT_POPOVER_MAX_HEIGHT, COMMENT_POPOVER_WIDTH } from './commentLayout';
import type { CollabUser, Comment } from './types';
import { apiPost } from '../api/client';
import { logError } from '../state/logging';

interface NodeCommentPopoverProps {
  workflowId: string;
  nodeId: string;
  currentUser: CollabUser;
  comments: Comment[];
  x: number;
  y: number;
  compose: boolean;
  onChanged: () => void;
  onClose: () => void;
}

const API_BASE = 'api/collab';

export default function NodeCommentPopover({
  workflowId,
  nodeId,
  currentUser,
  comments,
  x,
  y,
  compose,
  onChanged,
  onClose,
}: NodeCommentPopoverProps) {
  const { t } = useTranslation();
  const roots = useMemo(
    () => comments.filter(comment => comment.node_id === nodeId && !comment.parent_id),
    [comments, nodeId],
  );
  const [content, setContent] = useState('');
  const [replyTo, setReplyTo] = useState<string | null>(null);
  const [reply, setReply] = useState('');
  const [error, setError] = useState<string | null>(null);

  const timeAgo = (timestamp: string): string => {
    const seconds = Math.floor((Date.now() - new Date(timestamp).getTime()) / 1000);
    if (seconds < 60) return t('collab.timeJustNow');
    if (seconds < 3600) return t('collab.timeMinutesAgo', { count: Math.floor(seconds / 60) });
    if (seconds < 86400) return t('collab.timeHoursAgo', { count: Math.floor(seconds / 3600) });
    return t('collab.timeDaysAgo', { count: Math.floor(seconds / 86400) });
  };

  const post = async (text: string, parentId: string | null) => {
    if (!text.trim()) return;
    try {
      await apiPost(`${API_BASE}/workflows/${workflowId}/comments`, {
        content: text.trim(),
        parent_id: parentId,
        node_id: nodeId,
      });
      setContent('');
      setReply('');
      setReplyTo(null);
      setError(null);
      onChanged();
    } catch (err) {
      logError('collab.nodeComment.post', err);
      setError(err instanceof Error ? err.message : t('collab.couldNotPostComment'));
    }
  };

  const resolve = async (commentId: string) => {
    try {
      await apiPost(`${API_BASE}/comments/${commentId}/resolve`);
      setError(null);
      onChanged();
    } catch (err) {
      logError('collab.nodeComment.resolve', err);
      setError(err instanceof Error ? err.message : t('collab.couldNotResolveComment'));
    }
  };

  const submitOnEnter = (event: KeyboardEvent<HTMLTextAreaElement>, action: () => void) => {
    if (event.key !== 'Enter' || event.shiftKey) return;
    event.preventDefault();
    action();
  };

  return (
    <div style={{
      position: 'absolute',
      left: x,
      top: y,
      zIndex: 225,
      width: COMMENT_POPOVER_WIDTH,
      maxHeight: COMMENT_POPOVER_MAX_HEIGHT,
      display: 'flex',
      flexDirection: 'column',
      background: 'var(--surface)',
      border: '1px solid var(--border)',
      borderRadius: 8,
      boxShadow: '0 14px 34px rgba(0,0,0,0.28)',
      color: 'var(--text)',
    }} onMouseDown={event => event.stopPropagation()}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8, padding: '9px 10px', borderBottom: '1px solid var(--border)' }}>
        <strong style={{ fontSize: 12 }}>{compose && roots.length === 0 ? t('collab.nodeCommentTitle') : t('collab.nodeCommentsTitle')}</strong>
        <button className="btn btn-icon btn-xs" onClick={onClose} title={t('collab.closeComments')}><Icon name="close" size={12} /></button>
      </div>
      {error ? <div style={{ color: 'var(--danger)', fontSize: 11, padding: '7px 10px', borderBottom: '1px solid var(--border)' }}>{error}</div> : null}
      {roots.length > 0 ? (
        <div style={{ overflowY: 'auto', display: 'grid', gap: 8, padding: 10 }}>
          {roots.map(comment => (
            <div key={comment.id} style={{ padding: 8, borderRadius: 7, border: '1px solid var(--border)', background: 'var(--surface-2)', opacity: comment.resolved ? 0.62 : 1 }}>
              <div style={{ display: 'flex', gap: 6, alignItems: 'center', fontSize: 11 }}>
                <span style={{ width: 8, height: 8, borderRadius: '50%', background: comment.user_color }} />
                <strong style={{ minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{comment.user_name}</strong>
                <span style={{ color: 'var(--muted)', marginLeft: 'auto' }}>{timeAgo(comment.created_at)}</span>
              </div>
              <div style={{ whiteSpace: 'pre-wrap', fontSize: 12, lineHeight: 1.45, marginTop: 6 }}>{comment.content}</div>
              {comment.replies?.map(replyComment => (
                <div key={replyComment.id} style={{ marginTop: 6, padding: 6, borderLeft: `2px solid ${replyComment.user_color}`, fontSize: 11, background: 'var(--surface)' }}>
                  <strong>{replyComment.user_name}</strong> <span style={{ color: 'var(--muted)' }}>{timeAgo(replyComment.created_at)}</span>
                  <div style={{ whiteSpace: 'pre-wrap', marginTop: 3 }}>{replyComment.content}</div>
                </div>
              ))}
              <div style={{ display: 'flex', gap: 5, marginTop: 7 }}>
                <button className="btn btn-xs" onClick={() => setReplyTo(replyTo === comment.id ? null : comment.id)}>{t('collab.reply')}</button>
                {!comment.resolved ? <button className="btn btn-xs" onClick={() => void resolve(comment.id)}><Icon name="check" size={11} /> {t('collab.resolveComment')}</button> : null}
              </div>
              {replyTo === comment.id ? (
                <div style={{ display: 'grid', gap: 5, marginTop: 7 }}>
                  <textarea
                    autoFocus
                    value={reply}
                    onChange={event => setReply(event.target.value)}
                    onKeyDown={event => submitOnEnter(event, () => void post(reply, comment.id))}
                    placeholder={t('collab.replyPlaceholder')}
                    style={{ minHeight: 50, resize: 'vertical', border: '1px solid var(--border)', borderRadius: 5, background: 'var(--surface)', color: 'var(--text)', padding: 6, fontSize: 12 }}
                  />
                  <button className="btn btn-xs" onClick={() => void post(reply, comment.id)} disabled={!reply.trim()}>{t('collab.sendReply')}</button>
                </div>
              ) : null}
            </div>
          ))}
        </div>
      ) : null}
      {compose || roots.length > 0 ? (
        <div style={{ display: 'grid', gap: 6, padding: 10, borderTop: roots.length > 0 ? '1px solid var(--border)' : 0 }}>
          <textarea
            autoFocus={compose}
            value={content}
            onChange={event => setContent(event.target.value)}
            onKeyDown={event => submitOnEnter(event, () => void post(content, null))}
            placeholder={t('collab.nodeCommentPlaceholder', { name: currentUser.name })}
            style={{ minHeight: 58, resize: 'vertical', border: '1px solid var(--border)', borderRadius: 5, background: 'var(--surface-2)', color: 'var(--text)', padding: 7, fontSize: 12 }}
          />
          <button className="btn btn-sm" onClick={() => void post(content, null)} disabled={!content.trim()}>{t('collab.postComment')}</button>
        </div>
      ) : null}
    </div>
  );
}
