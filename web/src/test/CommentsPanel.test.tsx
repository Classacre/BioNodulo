import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { Provider } from 'jotai';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

const apiMocks = vi.hoisted(() => ({
  apiDelete: vi.fn(),
  apiGet: vi.fn(),
  apiPost: vi.fn(),
}));

const dialogMocks = vi.hoisted(() => ({
  confirmDialog: vi.fn(),
}));

const loggingMock = vi.hoisted(() => ({
  logError: vi.fn(),
}));

vi.mock('../api/client', () => apiMocks);
vi.mock('../components/ui', () => dialogMocks);
vi.mock('../state/logging', () => loggingMock);

const storage = new Map<string, string>();
const localStorageStub: Storage = {
  get length() {
    return storage.size;
  },
  clear: () => storage.clear(),
  getItem: (key: string) => storage.get(key) ?? null,
  key: (index: number) => Array.from(storage.keys())[index] ?? null,
  removeItem: (key: string) => {
    storage.delete(key);
  },
  setItem: (key: string, value: string) => {
    storage.set(key, String(value));
  },
};

describe('CommentsPanel i18n', () => {
  beforeEach(() => {
    storage.clear();
    vi.stubGlobal('localStorage', localStorageStub);
    apiMocks.apiDelete.mockReset();
    apiMocks.apiGet.mockReset();
    apiMocks.apiPost.mockReset();
    dialogMocks.confirmDialog.mockReset();
    loggingMock.logError.mockReset();
    localStorage.setItem('bionodulo_auth_token', 'test-token');
  });

  afterEach(async () => {
    const { setLanguage } = await import('../i18n');
    await setLanguage('en');
    storage.clear();
    vi.unstubAllGlobals();
  });

  it('renders workflow comment chrome and actions from the active locale', async () => {
    const { default: CommentsPanel } = await import('../collab/CommentsPanel');
    const { setLanguage } = await import('../i18n');

    await setLanguage('es');
    apiMocks.apiGet.mockResolvedValue({
      comments: [
        {
          id: 'comment-1',
          workflow_id: 'workflow-1',
          node_id: 'node-1',
          user_id: 'user-1',
          user_name: 'Mika',
          user_color: '#0d9488',
          content: 'Revisar este nodo',
          parent_id: null,
          resolved: false,
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
          replies: [],
        },
      ],
      count: 1,
      workflow_names: { 'workflow-1': 'Demo workflow' },
    });

    render(
      <Provider>
        <CommentsPanel
          workflowId="workflow-1"
          currentUser={{ id: 'user-1', name: 'Mika', color: '#0d9488' }}
          isOpen
          onClose={() => undefined}
          onFocusNode={() => undefined}
        />
      </Provider>,
    );

    await waitFor(() => expect(screen.getByText('Revisar este nodo')).toBeInTheDocument());

    expect(screen.getByText('Comentarios')).toBeInTheDocument();
    expect(screen.getByTitle('Cerrar')).toBeInTheDocument();
    expect(screen.getByText('ahora')).toBeInTheDocument();
    expect(screen.getByTitle('Resolver')).toBeInTheDocument();
    expect(screen.getByTitle('Eliminar')).toBeInTheDocument();
    expect(screen.getByTitle('Centrar este nodo en el lienzo')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Ir al nodo/ })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Responder' })).toBeInTheDocument();
    expect(screen.getByPlaceholderText('Nuevo comentario... Usa @nombre para mencionar')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Publicar comentario' })).toBeDisabled();
  });

  it('renders missing workflow-name fallbacks from the active locale', async () => {
    const { default: CommentsPanel } = await import('../collab/CommentsPanel');
    const { default: i18n, setLanguage } = await import('../i18n');

    await setLanguage('es');
    apiMocks.apiGet.mockResolvedValue({
      comments: [
        {
          id: 'comment-1',
          workflow_id: 'workflow-abcdef1234567890',
          node_id: null,
          user_id: 'user-1',
          user_name: 'Mika',
          user_color: '#0d9488',
          content: 'Comentario sin nombre de workflow',
          parent_id: null,
          resolved: false,
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
          replies: [],
        },
      ],
      count: 1,
      workflow_names: {},
    });

    render(
      <Provider>
        <CommentsPanel
          workflowId="workflow-abcdef1234567890"
          currentUser={{ id: 'user-1', name: 'Mika', color: '#0d9488' }}
          isOpen
          onClose={() => undefined}
        />
      </Provider>,
    );

    await waitFor(() => expect(screen.getByText('Comentario sin nombre de workflow')).toBeInTheDocument());

    expect(i18n.t('collab.commentsWorkflowFallback', { id: 'workflow-abc' })).toBe('Flujo de trabajo workflow-abc');
    expect(screen.getByText('Flujo de trabajo workflow-abc')).toBeInTheDocument();
    expect(screen.queryByText('Workflow workflow-abc')).not.toBeInTheDocument();
  });

  it('renders empty all-comments copy from the active locale', async () => {
    const { default: CommentsPanel } = await import('../collab/CommentsPanel');
    const { setLanguage } = await import('../i18n');

    await setLanguage('es');
    apiMocks.apiGet.mockResolvedValue({
      comments: [],
      count: 0,
      workflow_names: {},
    });

    render(
      <Provider>
        <CommentsPanel
          workflowId="workflow-1"
          currentUser={{ id: 'user-1', name: 'Mika', color: '#0d9488' }}
          isOpen
          onClose={() => undefined}
        />
      </Provider>,
    );

    await waitFor(() => expect(screen.getByText((_, node) => (
      node?.textContent === 'Aun no hay comentarios en tus flujos de trabajo.\nInicia la conversacion!'
      && node.children.length === 0
    ))).toBeInTheDocument());
    expect(screen.queryByText((_, node) => (
      node?.textContent === 'Aun no hay comentarios en tus workflows.\nInicia la conversacion!'
      && node.children.length === 0
    ))).not.toBeInTheDocument();
  });

  it('renders join-required comment errors from the active locale', async () => {
    const { default: CommentsPanel } = await import('../collab/CommentsPanel');
    const { setLanguage } = await import('../i18n');

    await setLanguage('es');
    localStorage.removeItem('bionodulo_auth_token');

    render(
      <Provider>
        <CommentsPanel
          workflowId="workflow-1"
          currentUser={{ id: 'user-1', name: 'Mika', color: '#0d9488' }}
          isOpen
          onClose={() => undefined}
        />
      </Provider>,
    );

    await waitFor(() => expect(screen.getByText('Unete a la colaboracion antes de usar comentarios de flujo de trabajo.')).toBeInTheDocument());
    expect(screen.queryByText('Unete a la colaboracion antes de usar comentarios de workflow.')).not.toBeInTheDocument();
  });

  it('keeps comment polling failures out of structured logging to avoid repeated noise', async () => {
    const { default: CommentsPanel } = await import('../collab/CommentsPanel');
    const loadError = new Error('comments unavailable');

    apiMocks.apiGet.mockRejectedValueOnce(loadError);

    render(
      <Provider>
        <CommentsPanel
          workflowId="workflow-1"
          currentUser={{ id: 'user-1', name: 'Mika', color: '#0d9488' }}
          isOpen
          onClose={() => undefined}
        />
      </Provider>,
    );

    await waitFor(() => expect(screen.getByText('comments unavailable')).toBeInTheDocument());
    expect(loggingMock.logError).not.toHaveBeenCalled();
  });

  it('logs swallowed comment-panel action API failures with stable scopes', async () => {
    const { default: CommentsPanel } = await import('../collab/CommentsPanel');
    const { setLanguage } = await import('../i18n');
    const postError = new Error('post failed');
    const replyError = new Error('reply failed');
    const resolveError = new Error('resolve failed');
    const deleteError = new Error('delete failed');
    const comment = {
      id: 'comment-1',
      workflow_id: 'workflow-1',
      node_id: 'node-1',
      user_id: 'user-1',
      user_name: 'Mika',
      user_color: '#0d9488',
      content: 'Review this node',
      parent_id: null,
      resolved: false,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
      replies: [],
    };

    await setLanguage('es');

    apiMocks.apiGet.mockResolvedValueOnce({ comments: [], count: 0, workflow_names: {} });
    apiMocks.apiPost.mockRejectedValueOnce(postError);
    const postView = render(
      <Provider>
        <CommentsPanel
          workflowId="workflow-1"
          currentUser={{ id: 'user-1', name: 'Mika', color: '#0d9488' }}
          isOpen
          onClose={() => undefined}
        />
      </Provider>,
    );

    await waitFor(() => expect(screen.getByPlaceholderText('Nuevo comentario... Usa @nombre para mencionar')).toBeInTheDocument());
    fireEvent.change(screen.getByPlaceholderText('Nuevo comentario... Usa @nombre para mencionar'), { target: { value: 'Please review' } });
    fireEvent.click(screen.getByRole('button', { name: 'Publicar comentario' }));
    await waitFor(() => expect(loggingMock.logError).toHaveBeenCalledWith('collab.commentsPanel.post', postError));
    expect(screen.getByText('No se pudo publicar el comentario')).toBeInTheDocument();
    expect(screen.queryByText('post failed')).not.toBeInTheDocument();
    postView.unmount();

    apiMocks.apiGet.mockResolvedValueOnce({ comments: [comment], count: 1, workflow_names: {} });
    apiMocks.apiPost.mockRejectedValueOnce(replyError);
    const replyView = render(
      <Provider>
        <CommentsPanel
          workflowId="workflow-1"
          currentUser={{ id: 'user-1', name: 'Mika', color: '#0d9488' }}
          isOpen
          onClose={() => undefined}
        />
      </Provider>,
    );

    await waitFor(() => expect(screen.getByText('Review this node')).toBeInTheDocument());
    fireEvent.click(screen.getByRole('button', { name: 'Responder' }));
    fireEvent.change(screen.getByPlaceholderText('Escribe una respuesta...'), { target: { value: 'Reply text' } });
    fireEvent.click(screen.getByRole('button', { name: 'Enviar' }));
    await waitFor(() => expect(loggingMock.logError).toHaveBeenCalledWith('collab.commentsPanel.reply', replyError));
    expect(screen.getByText('No se pudo publicar la respuesta')).toBeInTheDocument();
    expect(screen.queryByText('reply failed')).not.toBeInTheDocument();
    replyView.unmount();

    apiMocks.apiGet.mockResolvedValueOnce({ comments: [comment], count: 1, workflow_names: {} });
    apiMocks.apiPost.mockRejectedValueOnce(resolveError);
    const resolveView = render(
      <Provider>
        <CommentsPanel
          workflowId="workflow-1"
          currentUser={{ id: 'user-1', name: 'Mika', color: '#0d9488' }}
          isOpen
          onClose={() => undefined}
        />
      </Provider>,
    );

    await waitFor(() => expect(screen.getByTitle('Resolver')).toBeInTheDocument());
    fireEvent.click(screen.getByTitle('Resolver'));
    await waitFor(() => expect(loggingMock.logError).toHaveBeenCalledWith('collab.commentsPanel.resolve', resolveError));
    expect(screen.getByText('No se pudo resolver el comentario')).toBeInTheDocument();
    expect(screen.queryByText('resolve failed')).not.toBeInTheDocument();
    resolveView.unmount();

    apiMocks.apiGet.mockResolvedValueOnce({ comments: [comment], count: 1, workflow_names: {} });
    vi.mocked(dialogMocks.confirmDialog).mockResolvedValueOnce(true);
    apiMocks.apiDelete.mockRejectedValueOnce(deleteError);
    render(
      <Provider>
        <CommentsPanel
          workflowId="workflow-1"
          currentUser={{ id: 'user-1', name: 'Mika', color: '#0d9488' }}
          isOpen
          onClose={() => undefined}
        />
      </Provider>,
    );

    await waitFor(() => expect(screen.getByTitle('Eliminar')).toBeInTheDocument());
    fireEvent.click(screen.getByTitle('Eliminar'));
    await waitFor(() => expect(loggingMock.logError).toHaveBeenCalledWith('collab.commentsPanel.delete', deleteError));
    expect(screen.getByText('No se pudo eliminar el comentario')).toBeInTheDocument();
    expect(screen.queryByText('delete failed')).not.toBeInTheDocument();
  });

  it('keeps comment workflow fallback copy behind i18n keys', () => {
    const source = readFileSync(resolve(__dirname, '../collab/CommentsPanel.tsx'), 'utf8');

    expect(source).toContain('collab.commentsWorkflowFallback');
    expect(source).not.toContain('`Workflow ${comment.workflow_id.slice(0, 12)}`');
  });
});
