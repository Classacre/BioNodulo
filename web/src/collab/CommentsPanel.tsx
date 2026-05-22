import { useState, useEffect, useCallback, useRef } from 'react';
import type { KeyboardEvent, ReactNode } from 'react';
import { getToken } from './auth';
import type { Comment, CollabUser } from './types';
import Icon from '../components/ui/Icon';

const API_BASE = '/api/collab';

interface CommentsPanelProps {
  workflowId: string;
  selectedNodeId: string | null;
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

function timeAgo(ts: string): string {
  const s = Math.floor((Date.now() - new Date(ts).getTime()) / 1000);
  if (s < 60) return 'just now';
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
  return `${Math.floor(s / 86400)}d ago`;
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

export default function CommentsPanel({ workflowId, selectedNodeId, currentUser, isOpen, onClose, onFocusNode, onCommentsChange, onWorkflowNamesChange }: CommentsPanelProps) {
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
        setError('Join collaboration before using workflow comments.');
        return;
      }
      const url = selectedNodeId && !showAll
        ? `${API_BASE}/workflows/${workflowId}/comments?node_id=${encodeURIComponent(selectedNodeId)}`
        : `${API_BASE}/comments`;
      const headers: Record<string, string> = {};
      if (token) headers['Authorization'] = `Bearer ${token}`;
      const res = await fetch(url, { headers });
      if (!res.ok) throw new Error(`Failed to fetch comments: ${res.status}`);
      const data = await res.json() as { comments: Comment[]; count: number; workflow_names?: Record<string, string> };
      setComments(data.comments ?? []);
      if (selectedNodeId && !showAll) {
        onCommentsChange?.(data.comments ?? []);
      }
      setWorkflowNames(data.workflow_names ?? {});
      onWorkflowNamesChange?.(data.workflow_names ?? {});
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load comments');
    }
  }, [workflowId, selectedNodeId, showAll, onCommentsChange, onWorkflowNamesChange]);

  useEffect(() => {
    if (!isOpen) return;
    if (selectedNodeId) setShowAll(false);
    setLoading(true);
    fetchComments().then(() => setLoading(false));
    intervalRef.current = setInterval(fetchComments, 2500);
    return () => { if (intervalRef.current) clearInterval(intervalRef.current); };
  }, [isOpen, fetchComments]);

  const postComment = async (content: string, parentId: string | null = null, nodeId: string | null = null) => {
    const token = getToken();
    if (!token) throw new Error('Join collaboration before posting comments.');
    const headers: Record<string, string> = { 'Content-Type': 'application/json' };
    if (token) headers['Authorization'] = `Bearer ${token}`;
    const res = await fetch(`${API_BASE}/workflows/${workflowId}/comments`, {
      method: 'POST',
      headers,
      body: JSON.stringify({ content, parent_id: parentId, node_id: nodeId }),
    });
    if (!res.ok) throw new Error(`Failed to post comment: ${res.status}`);
    return res.json();
  };

  const handleSubmit = async () => {
    if (!newContent.trim()) return;
    try {
      await postComment(newContent.trim(), null, selectedNodeId);
      setNewContent('');
      fetchComments();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to post comment');
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
      setError(err instanceof Error ? err.message : 'Failed to post reply');
    }
  };

  const handleReplyKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>, parentId: string) => {
    if (event.key !== 'Enter' || event.shiftKey) return;
    event.preventDefault();
    void handleReply(parentId);
  };

  const handleResolve = async (commentId: string) => {
    try {
      const token = getToken();
      const headers: Record<string, string> = {};
      if (token) headers['Authorization'] = `Bearer ${token}`;
      const res = await fetch(`${API_BASE}/comments/${commentId}/resolve`, {
        method: 'POST',
        headers,
      });
      if (!res.ok) throw new Error('Failed to resolve');
      fetchComments();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to resolve comment');
    }
  };

  const handleDelete = async (commentId: string) => {
    if (!confirm('Delete this comment?')) return;
    try {
      const token = getToken();
      const headers: Record<string, string> = {};
      if (token) headers['Authorization'] = `Bearer ${token}`;
      const res = await fetch(`${API_BASE}/comments/${commentId}`, {
        method: 'DELETE',
        headers,
      });
      if (!res.ok) throw new Error('Failed to delete');
      fetchComments();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete comment');
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
          <strong style={{ fontSize: 14 }}>Comments</strong>
          <span style={{ fontSize: 11, color: 'var(--muted)', marginLeft: 6 }}>({unresolvedCount})</span>
        </div>
        <div style={{ display: 'flex', gap: 6 }}>
          {selectedNodeId && (
            <button className="btn btn-xs" onClick={() => setShowAll(v => !v)} style={{ fontSize: 10 }}>
              {showAll ? 'Node Only' : 'Show All'}
            </button>
          )}
          <button className="btn btn-icon btn-xs" onClick={onClose} title="Close"><Icon name="close" size={12} /></button>
        </div>
      </div>

      {/* Error */}
      {error && <div style={{ padding: '8px 14px', fontSize: 11, color: '#ef4444', background: '#ef444410' }}>{error}</div>}

      {/* Comment list */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '8px 0' }}>
        {loading && comments.length === 0 && <div style={{ padding: 20, textAlign: 'center', fontSize: 12, color: 'var(--muted)' }}>Loading comments...</div>}
        {rootComments.length === 0 && !loading && (
          <div style={{ padding: 20, textAlign: 'center', fontSize: 12, color: 'var(--muted)' }}>
            {selectedNodeId && !showAll ? 'No comments for this node.\nClick "Show All" to see all comments.' : 'No comments yet across your workflows.\nStart the conversation!'}
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
                <span style={{ fontSize: 10, color: 'var(--muted)', marginLeft: 6 }}>{timeAgo(comment.created_at)}</span>
              </div>
              {!comment.resolved && (
                <button className="btn btn-icon btn-xs" onClick={() => handleResolve(comment.id)} title="Resolve" style={{ padding: '2px 6px' }}><Icon name="check" size={12} /></button>
              )}
              {comment.user_id === currentUser.id && (
                <button className="btn btn-icon btn-xs" onClick={() => handleDelete(comment.id)} title="Delete" style={{ fontSize: 9 }}><Icon name="trash" size={12} /></button>
              )}
            </div>
            {comment.node_id && (
              <button
                className="btn btn-xs"
                onClick={() => onFocusNode?.(comment.node_id!)}
                title="Focus this node on the canvas"
                style={{ fontSize: 10, margin: '0 0 5px 32px' }}
              >
                <Icon name="target" size={10} /> Go to node
              </button>
            )}
            <div title={comment.workflow_id} style={{ fontSize: 10, color: 'var(--muted)', paddingLeft: 32, marginBottom: 4 }}>
              {workflowNames[comment.workflow_id] || `Workflow ${comment.workflow_id.slice(0, 12)}`}
            </div>
            {/* Content */}
            <div style={{ fontSize: 12, lineHeight: 1.5, paddingLeft: 32, whiteSpace: 'pre-wrap' }}>
              {renderCommentContent(comment.content, comment.resolved)}
            </div>
            {/* Reply button */}
            <div style={{ paddingLeft: 32, marginTop: 4 }}>
              <button className="btn btn-xs" onClick={() => setReplyTo(replyTo === comment.id ? null : comment.id)} style={{ fontSize: 10, color: 'var(--accent, #3b82f6)' }}>Reply</button>
            </div>
            {/* Reply form */}
            {replyTo === comment.id && (
              <div style={{ paddingLeft: 32, marginTop: 6, display: 'flex', gap: 6 }}>
                <textarea
                  value={replyContent}
                  onChange={e => setReplyContent(e.target.value)}
                  onKeyDown={e => handleReplyKeyDown(e, comment.id)}
                  placeholder="Write a reply..."
                  style={{ flex: 1, fontSize: 12, padding: 6, borderRadius: 4, border: '1px solid var(--border)', background: 'var(--surface-2)', color: 'var(--text)', resize: 'none', minHeight: 50 }}
                />
                <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                  <button className="btn btn-sm" onClick={() => handleReply(comment.id)} style={{ fontSize: 10 }}>Send</button>
                  <button className="btn btn-xs" onClick={() => { setReplyTo(null); setReplyContent(''); }} style={{ fontSize: 10 }}>Cancel</button>
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
                  <span style={{ fontSize: 9, color: 'var(--muted)' }}>{timeAgo(reply.created_at)}</span>
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
          placeholder={selectedNodeId ? 'Comment on this node... Use @name to mention' : 'New comment... Use @name to mention'}
          style={{ width: '100%', fontSize: 12, padding: 8, borderRadius: 4, border: '1px solid var(--border)', background: 'var(--surface-2)', color: 'var(--text)', resize: 'none', minHeight: 60, boxSizing: 'border-box' }}
        />
        <button className="btn btn-sm" onClick={handleSubmit} disabled={!newContent.trim()} style={{ marginTop: 6, width: '100%', fontSize: 12 }}>
          Post Comment
        </button>
      </div>
    </div>
  );
}
