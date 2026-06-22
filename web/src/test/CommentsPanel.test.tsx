import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { Provider } from 'jotai';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { Comment } from '../collab/types';

const dialogMocks = vi.hoisted(() => ({
  confirmDialog: vi.fn(),
}));

vi.mock('../components/ui', () => dialogMocks);

function comment(overrides: Partial<Comment>): Comment {
  return {
    id: 'c1',
    workflow_id: 'wf-1',
    node_id: null,
    user_id: 'user-2',
    user_name: 'Ada',
    user_color: '#7c3aed',
    content: 'Top level comment',
    parent_id: null,
    resolved: false,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    replies: [],
    ...overrides,
  };
}

describe('CommentsPanel (Yjs-backed)', () => {
  beforeEach(() => {
    dialogMocks.confirmDialog.mockReset();
  });

  afterEach(async () => {
    const { setLanguage } = await import('../i18n');
    await setLanguage('en');
  });

  async function renderPanel(handlers: {
    onAddComment?: ReturnType<typeof vi.fn>;
    onResolveComment?: ReturnType<typeof vi.fn>;
    onDeleteComment?: ReturnType<typeof vi.fn>;
    comments?: Comment[];
  } = {}) {
    const { default: CommentsPanel } = await import('../collab/CommentsPanel');
    const onAddComment = handlers.onAddComment ?? vi.fn();
    const onResolveComment = handlers.onResolveComment ?? vi.fn();
    const onDeleteComment = handlers.onDeleteComment ?? vi.fn();
    render(
      <Provider>
        <CommentsPanel
          comments={handlers.comments ?? [comment({})]}
          currentUser={{ id: 'user-1', name: 'Mika', color: '#0d9488' }}
          isOpen
          onClose={() => undefined}
          onAddComment={onAddComment}
          onResolveComment={onResolveComment}
          onDeleteComment={onDeleteComment}
        />
      </Provider>,
    );
    return { onAddComment, onResolveComment, onDeleteComment };
  }

  it('renders comments and chrome from the active locale', async () => {
    const { setLanguage } = await import('../i18n');
    await setLanguage('es');
    await renderPanel({ comments: [comment({ content: 'Revisa esto' })] });
    expect(screen.getByText('Revisa esto')).toBeInTheDocument();
    expect(screen.getByText('Ada')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Publicar comentario' })).toBeDisabled();
  });

  it('posts a new comment via onAddComment', async () => {
    const { onAddComment } = await renderPanel({ comments: [] });
    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'A new note' } });
    fireEvent.click(screen.getByRole('button', { name: /post comment/i }));
    expect(onAddComment).toHaveBeenCalledWith('A new note', null, null);
  });

  it('resolves a comment via onResolveComment', async () => {
    const { onResolveComment } = await renderPanel({ comments: [comment({ id: 'res-1' })] });
    fireEvent.click(screen.getByTitle(/resolve/i));
    expect(onResolveComment).toHaveBeenCalledWith('res-1');
  });

  it('deletes an own comment after confirmation via onDeleteComment', async () => {
    dialogMocks.confirmDialog.mockResolvedValue(true);
    const { onDeleteComment } = await renderPanel({ comments: [comment({ id: 'del-1', user_id: 'user-1' })] });
    fireEvent.click(screen.getByTitle(/delete/i));
    await waitFor(() => expect(onDeleteComment).toHaveBeenCalledWith('del-1'));
  });

  it('nests replies under their parent via parent_id', async () => {
    await renderPanel({
      comments: [
        comment({ id: 'root', content: 'Parent' }),
        comment({ id: 'reply', parent_id: 'root', user_name: 'Bo', content: 'A reply' }),
      ],
    });
    expect(screen.getByText('Parent')).toBeInTheDocument();
    expect(screen.getByText('A reply')).toBeInTheDocument();
    expect(screen.getByText('Bo')).toBeInTheDocument();
  });
});
