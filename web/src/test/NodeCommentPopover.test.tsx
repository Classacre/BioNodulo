import { fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

describe('NodeCommentPopover i18n', () => {
  afterEach(async () => {
    const { setLanguage } = await import('../i18n');
    await setLanguage('en');
  });

  it('renders node comment actions from the active locale and calls handlers', async () => {
    const { default: NodeCommentPopover } = await import('../collab/NodeCommentPopover');
    const { setLanguage } = await import('../i18n');
    await setLanguage('es');
    const onAddComment = vi.fn();
    const onResolveComment = vi.fn();

    render(
      <NodeCommentPopover
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
        onAddComment={onAddComment}
        onResolveComment={onResolveComment}
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

    // Resolve calls the handler with the comment id.
    fireEvent.click(screen.getByRole('button', { name: /Resolver/ }));
    expect(onResolveComment).toHaveBeenCalledWith('comment-1');

    // A reply calls onAddComment(content, nodeId, parentId).
    fireEvent.click(screen.getByRole('button', { name: 'Responder' }));
    expect(screen.getByPlaceholderText('Responder...')).toBeInTheDocument();
    fireEvent.change(screen.getByPlaceholderText('Responder...'), { target: { value: 'Listo' } });
    fireEvent.click(screen.getByRole('button', { name: 'Enviar respuesta' }));
    expect(onAddComment).toHaveBeenCalledWith('Listo', 'node-1', 'comment-1');
  });
});
