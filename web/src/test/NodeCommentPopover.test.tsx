import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const apiMocks = vi.hoisted(() => ({
  apiPost: vi.fn(),
}));

const loggingMock = vi.hoisted(() => ({
  logError: vi.fn(),
}));

vi.mock('../api/client', () => apiMocks);
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

describe('NodeCommentPopover i18n', () => {
  beforeEach(() => {
    storage.clear();
    vi.stubGlobal('localStorage', localStorageStub);
    apiMocks.apiPost.mockReset();
    loggingMock.logError.mockReset();
  });

  afterEach(async () => {
    const { setLanguage } = await import('../i18n');
    await setLanguage('en');
    storage.clear();
    vi.unstubAllGlobals();
  });

  it('renders node comment actions from the active locale', async () => {
    const { default: NodeCommentPopover } = await import('../collab/NodeCommentPopover');
    const { setLanguage } = await import('../i18n');
    await setLanguage('es');
    apiMocks.apiPost.mockResolvedValue({});

    render(
      <NodeCommentPopover
        workflowId="workflow-1"
        nodeId="node-1"
        currentUser={{ id: 'user-1', name: 'Mika', color: '#0d9488' }}
        comments={[
          {
            id: 'comment-1',
            workflow_id: 'workflow-1',
            node_id: 'node-1',
            user_id: 'user-2',
            user_name: 'Ada',
            user_color: '#7c3aed',
            content: 'Check this node',
            resolved: false,
            created_at: new Date().toISOString(),
            updated_at: new Date().toISOString(),
            replies: [],
          },
        ]}
        x={0}
        y={0}
        compose
        onChanged={() => undefined}
        onClose={() => undefined}
      />,
    );

    expect(screen.getByText('Comentarios del nodo')).toBeInTheDocument();
    expect(screen.getByText('ahora')).toBeInTheDocument();
    expect(screen.getByTitle('Cerrar comentarios')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Responder' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Resolver/ })).toBeInTheDocument();
    expect(screen.getByPlaceholderText('Mika, agrega un comentario al nodo...')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Publicar comentario' })).toBeDisabled();

    fireEvent.click(screen.getByRole('button', { name: 'Responder' }));
    expect(screen.getByPlaceholderText('Responder...')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Enviar respuesta' })).toBeDisabled();

    fireEvent.change(screen.getByPlaceholderText('Responder...'), { target: { value: 'Listo' } });
    fireEvent.click(screen.getByRole('button', { name: 'Enviar respuesta' }));

    await waitFor(() => expect(apiMocks.apiPost).toHaveBeenCalledWith(
      'api/collab/workflows/workflow-1/comments',
      {
        content: 'Listo',
        parent_id: 'comment-1',
        node_id: 'node-1',
      },
    ));
  });

  it('logs swallowed comment post and resolve failures with stable scopes', async () => {
    const { default: NodeCommentPopover } = await import('../collab/NodeCommentPopover');
    const { setLanguage } = await import('../i18n');
    await setLanguage('es');
    const postError = new Error('comment post failed');
    const resolveError = new Error('comment resolve failed');

    apiMocks.apiPost.mockRejectedValueOnce(postError);
    const postView = render(
      <NodeCommentPopover
        workflowId="workflow-1"
        nodeId="node-1"
        currentUser={{ id: 'user-1', name: 'Mika', color: '#0d9488' }}
        comments={[]}
        x={0}
        y={0}
        compose
        onChanged={() => undefined}
        onClose={() => undefined}
      />,
    );

    fireEvent.change(screen.getByPlaceholderText('Mika, agrega un comentario al nodo...'), { target: { value: 'Please check this' } });
    fireEvent.click(screen.getByRole('button', { name: 'Publicar comentario' }));

    await waitFor(() => expect(loggingMock.logError).toHaveBeenCalledWith('collab.nodeComment.post', postError));
    expect(screen.getByText('No se pudo publicar el comentario')).toBeInTheDocument();
    expect(screen.queryByText('comment post failed')).not.toBeInTheDocument();
    postView.unmount();

    apiMocks.apiPost.mockRejectedValueOnce(resolveError);
    render(
      <NodeCommentPopover
        workflowId="workflow-1"
        nodeId="node-1"
        currentUser={{ id: 'user-1', name: 'Mika', color: '#0d9488' }}
        comments={[
          {
            id: 'comment-1',
            workflow_id: 'workflow-1',
            node_id: 'node-1',
            user_id: 'user-2',
            user_name: 'Ada',
            user_color: '#7c3aed',
            content: 'Check this node',
            resolved: false,
            created_at: new Date().toISOString(),
            updated_at: new Date().toISOString(),
            replies: [],
          },
        ]}
        x={0}
        y={0}
        compose
        onChanged={() => undefined}
        onClose={() => undefined}
      />,
    );

    fireEvent.click(screen.getByRole('button', { name: /Resolver/ }));

    await waitFor(() => expect(loggingMock.logError).toHaveBeenCalledWith('collab.nodeComment.resolve', resolveError));
    expect(screen.getByText('No se pudo resolver el comentario')).toBeInTheDocument();
    expect(screen.queryByText('comment resolve failed')).not.toBeInTheDocument();
  });
});
