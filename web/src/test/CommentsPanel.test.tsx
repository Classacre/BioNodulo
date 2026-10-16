import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { Provider, createStore } from 'jotai';
import { cloudConfigAtom, type CloudConfig } from '../state/appAtoms';
import { selectedNodeIdAtom } from '../state/uiAtoms';
import { cloudInviteSessionAtom, type CloudInviteSession } from '../collab/cloudInvite';
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

  it('clears comment/reply drafts and node association on owner and workflow changes before paint', async () => {
    const { default: CommentsPanel } = await import('../collab/CommentsPanel');
    await import('../i18n');
    const store = createStore();
    const a = { editorMode: true, user: { id: 'a' }, team: { id: 'a' } } as CloudConfig;
    store.set(cloudConfigAtom, a);
    store.set(selectedNodeIdAtom, 'old-node');
    const onAddComment = vi.fn();
    const view = (workflowId: string) => <Provider store={store}><CommentsPanel workflowId={workflowId}
      comments={[comment({ id: 'root' })]} currentUser={{ id: 'me', name: 'Me', color: '#000' }} isOpen
      onClose={() => undefined} onAddComment={onAddComment} onResolveComment={() => undefined} onDeleteComment={() => undefined} /></Provider>;
    const rendered = render(view('same-workflow'));
    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'Private new comment' } });
    fireEvent.click(screen.getByRole('button', { name: /^reply$/i }));
    fireEvent.change(screen.getByPlaceholderText(/write.*reply/i), { target: { value: 'Private reply' } });
    act(() => store.set(cloudConfigAtom, { ...a, team: { id: 'b' } } as CloudConfig));
    expect(screen.queryByDisplayValue('Private new comment')).not.toBeInTheDocument();
    expect(screen.queryByDisplayValue('Private reply')).not.toBeInTheDocument();
    expect(store.get(selectedNodeIdAtom)).toBeNull();
    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'Team B draft' } });
    rendered.rerender(view('other-workflow'));
    expect(screen.queryByDisplayValue('Team B draft')).not.toBeInTheDocument();
    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'Other document draft' } });
    act(() => store.set(cloudConfigAtom, { ...a, user: { id: 'other' } } as CloudConfig));
    expect(screen.queryByDisplayValue('Other document draft')).not.toBeInTheDocument();
    expect(onAddComment).not.toHaveBeenCalled();
  });

  it('rejects a pending delete confirmation after A to B to A and after unmount', async () => {
    const { default: CommentsPanel } = await import('../collab/CommentsPanel');
    const store = createStore();
    const a = { editorMode: true, user: { id: 'a' }, team: { id: 'a' } } as CloudConfig;
    store.set(cloudConfigAtom, a);
    let finish!: (ok: boolean) => void;
    dialogMocks.confirmDialog.mockImplementation(() => new Promise<boolean>(resolve => { finish = resolve; }));
    const onDeleteComment = vi.fn();
    const rendered = render(<Provider store={store}><CommentsPanel workflowId="same"
      comments={[comment({ user_id: 'me' })]} currentUser={{ id: 'me', name: 'Me', color: '#000' }} isOpen
      onClose={() => undefined} onAddComment={() => undefined} onResolveComment={() => undefined} onDeleteComment={onDeleteComment} /></Provider>);
    fireEvent.click(screen.getByTitle(/delete/i));
    act(() => store.set(cloudConfigAtom, { ...a, team: { id: 'b' } } as CloudConfig));
    act(() => store.set(cloudConfigAtom, a));
    await act(async () => { finish(true); });
    expect(onDeleteComment).not.toHaveBeenCalled();
    fireEvent.click(screen.getByTitle(/delete/i));
    rendered.unmount();
    await act(async () => { finish(true); });
    expect(onDeleteComment).not.toHaveBeenCalled();
  });

  it('treats a newly redeemed invite for the same named guest and workflow as a new volatile session', async () => {
    const { default: CommentsPanel } = await import('../collab/CommentsPanel');
    const store = createStore();
    const invite: CloudInviteSession = { workflowId: 'same', member: false, role: 'editor', identity: { name: 'Guest', kind: 'guest' },
      room: null, roomToken: null, roomHost: null, roomExpiresAt: null, runToken: null, name: 'Guest' };
    store.set(cloudInviteSessionAtom, invite);
    let finish!: (ok: boolean) => void;
    dialogMocks.confirmDialog.mockImplementation(() => new Promise<boolean>(resolve => { finish = resolve; }));
    const onDeleteComment = vi.fn();
    render(<Provider store={store}><CommentsPanel workflowId="same" comments={[comment({ user_id: 'guest' })]}
      currentUser={{ id: 'guest', name: 'Guest', color: '#000' }} isOpen onClose={() => undefined}
      onAddComment={() => undefined} onResolveComment={() => undefined} onDeleteComment={onDeleteComment} /></Provider>);
    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'Previous invite draft' } });
    fireEvent.click(screen.getByTitle(/delete/i));
    act(() => store.set(cloudInviteSessionAtom, { ...invite }));
    expect(screen.queryByDisplayValue('Previous invite draft')).not.toBeInTheDocument();
    await act(async () => { finish(true); });
    expect(onDeleteComment).not.toHaveBeenCalled();
  });

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
