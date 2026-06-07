import { useState, useEffect, useCallback, useRef } from 'react';
import type { KeyboardEvent, ReactNode } from 'react';
import { useAtomValue } from 'jotai';
import { useTranslation } from 'react-i18next';
import { getToken } from './auth';
import type { Comment, CollabUser } from './types';
import Icon from '../components/ui/Icon';
import { confirmDialog } from '../components/ui';
import { selectedNodeIdAtom } from '../state/uiAtoms';
import { apiDelete, apiGet, apiPost } from '../api/client';
import { logError } from '../state/logging';

const API_BASE = 'api/collab';

interface CommentsPanelProps {
  workflowId: string;
  currentUser: CollabUser;
  isOpen: boolean;
  onClose: () => void;
  onFocusNode?: (nodeId: string) => void;
  onCommentsChange?: (comments: Comment[]) => void;
  onWorkflowNamesChange?: (workflowNames: Record<string, string>) => void;
}

function getInitials(name: string): string {
  return name.split(' ').map(w => w[0]).join('').toUpperCase().slice(0, 2);
}

function timeAgo(ts: string, translate: (key: string, options?: Record<string, unknown>) => string): string {
  const s = Math.floor((Date.now() - new Date(ts).getTime()) / 1000);
  if (s < 60) return translate('collab.timeJustNow');
  if (s < 3600) return translate('collab.timeMinutesAgo', { count: Math.floor(s / 60) });
  if (s < 86400) return translate('collab.timeHoursAgo', { count: Math.floor(s / 3600) });
  return translate('collab.timeDaysAgo', { count: Math.floor(s / 86400) });
}

function renderCommentContent(text: string, resolved: boolean): ReactNode {
  const parts: ReactNode[] = [];
  const mentionRe = /@(\w+)/g;
  let lastIndex = 0;
  let match: RegExpExecArray | null;

  while ((match = mentionRe.exec(text)) !== null) {
    if (match.index > lastIndex) {
      parts.push(text.slice(lastIndex, match.index));
    }
    parts.push(
      <span key={`${match.index}-${match[0]}`} style={{ color: 'var(--accent)', fontWeight: 600 }}>
        {match[0]}
      </span>,
    );
    lastIndex = match.index + match[0].length;
  }

  if (lastIndex < text.length) {
    parts.push(text.slice(lastIndex));
  }

  return resolved ? <s>{parts}</s> : parts;
}

export default function CommentsPanel({ workflowId, currentUser, isOpen, onClose, onFocusNode, onCommentsChange, onWorkflowNamesChange }: CommentsPanelProps) {
  const { t } = useTranslation();
  const selectedNodeId = useAtomValue(selectedNodeIdAtom);
  const [comments, setComments] = useState<Comment[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [newContent, setNewContent] = useState('');
  const [replyTo, setReplyTo] = useState<string | null>(null);
  const [replyContent, setReplyContent] = useState('');
  const [showAll, setShowAll] = useState(true);
  const [workflowNames, setWorkflowNames] = useState<Record<string, string>>({});
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const fetchComments = useCallback(async () => {
    if (!workflowId) return;
    try {
      const token = getToken();
      if (!token) {
        setComments([]);
        setError(t('collab.commentsJoinRequired'));
        return;
      }
      const url = selectedNodeId && !showAll
        ? `${API_BASE}/workflows/${workflowId}/comments?node_id=${encodeURIComponent(selectedNodeId)}`
        : `${API_BASE}/comments`;
      const data = await apiGet<{ comments: Comment[]; count: number; workflow_names?: Record<string, string> }>(url);
      setComments(data.comments ?? []);
      if (selectedNodeId && !showAll) {
        onCommentsChange?.(data.comments ?? []);
      }
      setWorkflowNames(data.workflow_names ?? {});
      onWorkflowNamesChange?.(data.workflow_names ?? {});
      setError(null);
    } catch {
      setError(t('collab.commentsLoadError'));
    }
  }, [workflowId, selectedNodeId, showAll, onCommentsChange, onWorkflowNamesChange, t]);

  useEffect(() => {
    if (!isOpen) return;
    if (selectedNodeId) setShowAll(false);
    setLoading(true);
    fetchComments().then(() => setLoading(false));
    intervalRef.current = setInterval(fetchComments, 2500);
    return () => { if (intervalRef.current) clearInterval(intervalRef.current); };
  }, [isOpen, fetchComments, selectedNodeId]);

  const postComment = async (content: string, parentId: string | null = null, nodeId: string | null = null) => {
    const token = getToken();
    if (!token) throw new Error(t('collab.commentsPostJoinRequired'));
    return apiPost(`${API_BASE}/workflows/${workflowId}/comments`, { content, parent_id: parentId, node_id: nodeId });
  };

  const handleSubmit = async () => {
    if (!newContent.trim()) return;
    try {
      await postComment(newContent.trim(), null, selectedNodeId);
      setNewContent('');
      fetchComments();
    } catch (err) {
      logError('collab.commentsPanel.post', err);
      setError(t('collab.commentsPostError'));
    }
  };

  const handleCommentKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key !== 'Enter' || event.shiftKey) return;
    event.preventDefault();
    void handleSubmit();
  };

  const handleReply = async (parentId: string) => {
    if (!replyContent.trim()) return;
    try {
      await postComment(replyContent.trim(), parentId, selectedNodeId);
      setReplyContent('');
      setReplyTo(null);
      fetchComments();
    } catch (err) {
      logError('collab.commentsPanel.reply', err);
      setError(t('collab.commentsReplyError'));
    }
  };

  const handleReplyKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>, parentId: string) => {
    if (event.key !== 'Enter' || event.shiftKey) return;
    event.preventDefault();
    void handleReply(parentId);
  };

  const handleResolve = async (commentId: string) => {
    try {
      await apiPost(`${API_BASE}/comments/${commentId}/resolve`);
      fetchComments();
    } catch (err) {
      logError('collab.commentsPanel.resolve', err);
      setError(t('collab.commentsResolveError'));
    }
  };

  const handleDelete = async (commentId: string) => {
    const ok = await confirmDialog({
      title: t('collab.commentsDeleteTitle'),
      message: t('collab.commentsDeleteMessage'),
      confirmLabel: t('common.delete'),
      tone: 'danger',
    });
    if (!ok) return;
    try {
      await apiDelete(`${API_BASE}/comments/${commentId}`);
      fetchComments();
    } catch (err) {
      logError('collab.commentsPanel.delete', err);
      setError(t('collab.commentsDeleteError'));
    }
  };

  const rootComments = comments.filter(c => !c.parent_id);
  const unresolvedCount = comments.filter(c => !c.resolved).length;

  if (!isOpen) return null;

  return (
    <div style={{
      position: 'fixed', top: 0, right: 0, width: 320, height: '100vh',
      background: 'var(--surface)', borderLeft: '1px solid var(--border)',
      zIndex: 260, display: 'flex', flexDirection: 'column', transition: 'transform 0.2s ease',
      boxShadow: '-4px 0 12px rgba(0,0,0,0.15)',
    }}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '12px 14px', borderBottom: '1px solid var(--border)' }}>
        <div>
          <strong style={{ fontSize: 14 }}>{t('collab.commentsTitle')}</strong>
          <span style={{ fontSize: 11, color: 'var(--muted)', marginLeft: 6 }}>({unresolvedCount})</span>
        </div>
        <div style={{ display: 'flex', gap: 6 }}>
          {selectedNodeId && (
            <button className="btn btn-xs" onClick={() => setShowAll(v => !v)} style={{ fontSize: 10 }}>
              {showAll ? t('collab.commentsNodeOnly') : t('collab.commentsShowAll')}
            </button>
          )}
          <button className="btn btn-icon btn-xs" onClick={onClose} title={t('common.close')}><Icon name="close" size={12} /></button>
        </div>
      </div>

      {/* Error */}
      {error && <div style={{ padding: '8px 14px', fontSize: 11, color: '#ef4444', background: '#ef444410' }}>{error}</div>}

      {/* Comment list */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '8px 0' }}>
        {loading && comments.length === 0 && <div style={{ padding: 20, textAlign: 'center', fontSize: 12, color: 'var(--muted)' }}>{t('collab.commentsLoading')}</div>}
        {rootComments.length === 0 && !loading && (
          <div style={{ padding: 20, textAlign: 'center', fontSize: 12, color: 'var(--muted)' }}>
            {selectedNodeId && !showAll ? t('collab.commentsEmptyNode', { showAll: t('collab.commentsShowAll') }) : t('collab.commentsEmptyAll')}
          </div>
        )}
        {rootComments.map(comment => (
          <div key={comment.id} style={{ padding: '8px 14px', borderBottom: '1px solid var(--border)', opacity: comment.resolved ? 0.5 : 1 }}>
            {/* Avatar + name + time */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
              <div style={{
                width: 24, height: 24, borderRadius: '50%', backgroundColor: comment.user_color,
                display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 10, fontWeight: 700, color: '#fff', flexShrink: 0,
              }}>{getInitials(comment.user_name)}</div>
              <div style={{ flex: 1, minWidth: 0 }}>
                <span style={{ fontSize: 12, fontWeight: 600 }}>{comment.user_name}</span>
                <span style={{ fontSize: 10, color: 'var(--muted)', marginLeft: 6 }}>{timeAgo(comment.created_at, t)}</span>
              </div>
              {!comment.resolved && (
                <button className="btn btn-icon btn-xs" onClick={() => handleResolve(comment.id)} title={t('collab.resolveComment')} style={{ padding: '2px 6px' }}><Icon name="check" size={12} /></button>
              )}
              {comment.user_id === currentUser.id && (
                <button className="btn btn-icon btn-xs" onClick={() => handleDelete(comment.id)} title={t('common.delete')} style={{ fontSize: 9 }}><Icon name="trash" size={12} /></button>
              )}
            </div>
            {comment.node_id && (
              <button
                className="btn btn-xs"
                onClick={() => onFocusNode?.(comment.node_id!)}
                title={t('collab.commentsFocusNodeTitle')}
                style={{ fontSize: 10, margin: '0 0 5px 32px' }}
              >
                <Icon name="target" size={10} /> {t('collab.commentsGoToNode')}
              </button>
            )}
            <div title={comment.workflow_id} style={{ fontSize: 10, color: 'var(--muted)', paddingLeft: 32, marginBottom: 4 }}>
              {workflowNames[comment.workflow_id] || t('collab.commentsWorkflowFallback', { id: comment.workflow_id.slice(0, 12) })}
            </div>
            {/* Content */}
            <div style={{ fontSize: 12, lineHeight: 1.5, paddingLeft: 32, whiteSpace: 'pre-wrap' }}>
              {renderCommentContent(comment.content, comment.resolved)}
            </div>
            {/* Reply button */}
            <div style={{ paddingLeft: 32, marginTop: 4 }}>
              <button className="btn btn-xs" onClick={() => setReplyTo(replyTo === comment.id ? null : comment.id)} style={{ fontSize: 10, color: 'var(--accent, #3b82f6)' }}>{t('collab.reply')}</button>
            </div>
            {/* Reply form */}
            {replyTo === comment.id && (
              <div style={{ paddingLeft: 32, marginTop: 6, display: 'flex', gap: 6 }}>
                <textarea
                  value={replyContent}
                  onChange={e => setReplyContent(e.target.value)}
                  onKeyDown={e => handleReplyKeyDown(e, comment.id)}
                  placeholder={t('collab.commentsWriteReplyPlaceholder')}
                  style={{ flex: 1, fontSize: 12, padding: 6, borderRadius: 4, border: '1px solid var(--border)', background: 'var(--surface-2)', color: 'var(--text)', resize: 'none', minHeight: 50 }}
                />
                <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                  <button className="btn btn-sm" onClick={() => handleReply(comment.id)} style={{ fontSize: 10 }}>{t('collab.commentsSend')}</button>
                  <button className="btn btn-xs" onClick={() => { setReplyTo(null); setReplyContent(''); }} style={{ fontSize: 10 }}>{t('common.cancel')}</button>
                </div>
              </div>
            )}
            {/* Nested replies */}
            {comment.replies?.length > 0 && comment.replies.map(reply => (
              <div key={reply.id} style={{ marginLeft: 32, marginTop: 8, padding: '6px 10px', background: 'var(--surface-2)', borderRadius: 6, opacity: reply.resolved ? 0.5 : 1 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 2 }}>
                  <div style={{
                    width: 18, height: 18, borderRadius: '50%', backgroundColor: reply.user_color,
                    display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 8, fontWeight: 700, color: '#fff', flexShrink: 0,
                  }}>{getInitials(reply.user_name)}</div>
                  <span style={{ fontSize: 11, fontWeight: 600 }}>{reply.user_name}</span>
                  <span style={{ fontSize: 9, color: 'var(--muted)' }}>{timeAgo(reply.created_at, t)}</span>
                </div>
                <div style={{ fontSize: 11, lineHeight: 1.4, paddingLeft: 24, whiteSpace: 'pre-wrap' }}>
                  {renderCommentContent(reply.content, reply.resolved)}
                </div>
              </div>
            ))}
          </div>
        ))}
      </div>

      {/* New comment textarea */}
      <div style={{ padding: '10px 14px', borderTop: '1px solid var(--border)' }}>
        <textarea
          value={newContent}
          onChange={e => setNewContent(e.target.value)}
          onKeyDown={handleCommentKeyDown}
          placeholder={selectedNodeId ? t('collab.commentsNodePlaceholder') : t('collab.commentsNewPlaceholder')}
          style={{ width: '100%', fontSize: 12, padding: 8, borderRadius: 4, border: '1px solid var(--border)', background: 'var(--surface-2)', color: 'var(--text)', resize: 'none', minHeight: 60, boxSizing: 'border-box' }}
        />
        <button className="btn btn-sm" onClick={handleSubmit} disabled={!newContent.trim()} style={{ marginTop: 6, width: '100%', fontSize: 12 }}>
          {t('collab.postComment')}
        </button>
      </div>
    </div>
  );
}
