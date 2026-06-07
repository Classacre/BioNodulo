import { render, screen, waitFor } from '@testing-library/react';
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

vi.mock('../api/client', () => apiMocks);
vi.mock('../components/ui', () => dialogMocks);

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

  it('keeps comment workflow fallback copy behind i18n keys', () => {
    const source = readFileSync(resolve(__dirname, '../collab/CommentsPanel.tsx'), 'utf8');

    expect(source).toContain('collab.commentsWorkflowFallback');
    expect(source).not.toContain('`Workflow ${comment.workflow_id.slice(0, 12)}`');
  });
});
