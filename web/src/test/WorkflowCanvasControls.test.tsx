import { act, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { ObjectInfo } from '../types';

const apiMocks = vi.hoisted(() => ({
  apiGet: vi.fn(),
  apiPost: vi.fn(),
}));

const loggingMock = vi.hoisted(() => ({
  logError: vi.fn(),
}));

const notificationMocks = vi.hoisted(() => ({
  toast: {
    error: vi.fn(),
    success: vi.fn(),
  },
}));

vi.mock('../api/client', () => apiMocks);
vi.mock('../state/logging', () => loggingMock);
vi.mock('../components/ui', async importOriginal => ({
  ...(await importOriginal<typeof import('../components/ui')>()),
  toast: notificationMocks.toast,
}));

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

function stubCanvasContext(fillText: ReturnType<typeof vi.fn>) {
  const gradient = { addColorStop: vi.fn() };
  const context = {
    arc: vi.fn(),
    beginPath: vi.fn(),
    bezierCurveTo: vi.fn(),
    clearRect: vi.fn(),
    closePath: vi.fn(),
    createLinearGradient: vi.fn(() => gradient),
    fill: vi.fn(),
    fillRect: vi.fn(),
    fillText,
    lineTo: vi.fn(),
    measureText: vi.fn((text: string) => ({ width: text.length * 6 })),
    moveTo: vi.fn(),
    quadraticCurveTo: vi.fn(),
    restore: vi.fn(),
    rotate: vi.fn(),
    save: vi.fn(),
    scale: vi.fn(),
    setLineDash: vi.fn(),
    setTransform: vi.fn(),
    stroke: vi.fn(),
    strokeRect: vi.fn(),
    translate: vi.fn(),
  };

  vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockImplementation(() => context as unknown as CanvasRenderingContext2D);
}

describe('WorkflowCanvas controls i18n', () => {
  beforeEach(() => {
    storage.clear();
    vi.stubGlobal('localStorage', localStorageStub);
    apiMocks.apiGet.mockReset();
    apiMocks.apiGet.mockResolvedValue({});
    apiMocks.apiPost.mockReset();
    loggingMock.logError.mockReset();
    notificationMocks.toast.error.mockReset();
    notificationMocks.toast.success.mockReset();
  });

  afterEach(async () => {
    const { setLanguage } = await import('../i18n');
    await setLanguage('en');
    storage.clear();
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it('renders canvas controls from the active locale', async () => {
    const { default: WorkflowCanvas } = await import('../components/canvas/WorkflowCanvas');
    const { setLanguage } = await import('../i18n');

    await setLanguage('es');

    render(
      <WorkflowCanvas
        nodes={[]}
        edges={[]}
        groups={[]}
        objectInfo={{} satisfies ObjectInfo}
        onNodesChange={() => undefined}
        onEdgesChange={() => undefined}
        onGroupsChange={() => undefined}
        onPushHistory={() => undefined}
        onUndo={() => undefined}
        onRedo={() => undefined}
        snapToGrid={false}
        showMinimap={false}
        viewportLocked={false}
        linksHidden={false}
        onToggleMinimap={() => undefined}
        onToggleLinksHidden={() => undefined}
      />,
    );

    expect(screen.getByRole('button', { name: 'Ajustar vista' })).toHaveAttribute('title', 'Ajustar vista');
    expect(screen.getByRole('button', { name: 'Ajustar seleccion' })).toHaveAttribute('title', 'Ajustar seleccion');
    expect(screen.getByRole('button', { name: 'Acercar' })).toHaveAttribute('title', 'Acercar');
    expect(screen.getByRole('button', { name: 'Alejar' })).toHaveAttribute('title', 'Alejar');
    expect(screen.getByTitle('Alternar minimapa')).toBeInTheDocument();
    expect(screen.getByTitle('Alternar enlaces')).toBeInTheDocument();
    expect(screen.getByTitle('Autoordenar nodos')).toBeInTheDocument();
  });

  it('draws array parameter summaries from the active locale', async () => {
    const { default: WorkflowCanvas } = await import('../components/canvas/WorkflowCanvas');
    const { setLanguage } = await import('../i18n');
    const fillText = vi.fn();
    stubCanvasContext(fillText);

    await setLanguage('es');

    render(
      <WorkflowCanvas
        nodes={[{
          id: 'array-node',
          type: 'array_node',
          position: [100, 100],
          params: {
            samples: ['S1', 'S2', 'S3'],
          },
        }]}
        edges={[]}
        groups={[]}
        objectInfo={{
          array_node: {
            id: 'array_node',
            display_name: 'Array Node',
            category: 'Utility',
            return_types: [],
          },
        } satisfies ObjectInfo}
        onNodesChange={() => undefined}
        onEdgesChange={() => undefined}
        onGroupsChange={() => undefined}
        onPushHistory={() => undefined}
        onUndo={() => undefined}
        onRedo={() => undefined}
        snapToGrid={false}
        showMinimap={false}
        viewportLocked={false}
        linksHidden={false}
        onToggleMinimap={() => undefined}
        onToggleLinksHidden={() => undefined}
      />,
    );

    await waitFor(() => {
      expect(fillText).toHaveBeenCalledWith('samples: 3 elementos', expect.any(Number), expect.any(Number));
    });
    expect(fillText).not.toHaveBeenCalledWith('samples: 3 items', expect.any(Number), expect.any(Number));
  });

  it('draws missing node titles from the active locale', async () => {
    const { default: WorkflowCanvas } = await import('../components/canvas/WorkflowCanvas');
    const { setLanguage } = await import('../i18n');
    const fillText = vi.fn();
    stubCanvasContext(fillText);

    await setLanguage('es');

    render(
      <WorkflowCanvas
        nodes={[{
          id: 'fallback-node',
          type: '',
          position: [100, 100],
          params: {},
        }]}
        edges={[]}
        groups={[]}
        objectInfo={{} satisfies ObjectInfo}
        onNodesChange={() => undefined}
        onEdgesChange={() => undefined}
        onGroupsChange={() => undefined}
        onPushHistory={() => undefined}
        onUndo={() => undefined}
        onRedo={() => undefined}
        snapToGrid={false}
        showMinimap={false}
        viewportLocked={false}
        linksHidden={false}
        onToggleMinimap={() => undefined}
        onToggleLinksHidden={() => undefined}
      />,
    );

    await waitFor(() => {
      expect(fillText).toHaveBeenCalledWith('Nodo', expect.any(Number), expect.any(Number));
    });
    expect(fillText).not.toHaveBeenCalledWith('Node', expect.any(Number), expect.any(Number));
  });

  it('hides conditional canvas widgets until their controlling parameter matches', async () => {
    const { default: WorkflowCanvas } = await import('../components/canvas/WorkflowCanvas');
    stubCanvasContext(vi.fn());
    const objectInfo = {
      http_request: {
        id: 'http_request',
        display_name: 'HTTP Request',
        category: 'API',
        input_types: {
          required: {
            url: { type: 'STRING', label: 'URL', default: '' },
          },
          optional: {
            body_format: { type: 'STRING', label: 'Body format', default: 'none', options: ['none', 'json', 'text', 'form'] },
            body: {
              type: 'STRING',
              label: 'Body',
              displayOptions: { show: { body_format: ['json', 'text', 'form'] } },
            },
            auth_mode: { type: 'STRING', label: 'Auth mode', default: 'none', options: ['none', 'bearer', 'basic'] },
            bearer_token: {
              type: 'STRING',
              label: 'Bearer token',
              displayOptions: { show: { auth_mode: ['bearer'] } },
            },
            username: {
              type: 'STRING',
              label: 'Username',
              displayOptions: { show: { auth_mode: ['basic'] } },
            },
            password: {
              type: 'STRING',
              label: 'Password',
              displayOptions: { show: { auth_mode: ['basic'] } },
            },
          },
        },
        return_types: [],
      },
    } satisfies ObjectInfo;
    const baseProps = {
      edges: [],
      groups: [],
      objectInfo,
      onNodesChange: () => undefined,
      onEdgesChange: () => undefined,
      onGroupsChange: () => undefined,
      onPushHistory: () => undefined,
      onUndo: () => undefined,
      onRedo: () => undefined,
      snapToGrid: false,
      showMinimap: false,
      viewportLocked: false,
      linksHidden: false,
      onToggleMinimap: () => undefined,
      onToggleLinksHidden: () => undefined,
    };

    const { rerender } = render(
      <WorkflowCanvas
        {...baseProps}
        nodes={[{
          id: 'http-1',
          type: 'http_request',
          position: [100, 100],
          params: { body_format: 'none', auth_mode: 'none' },
        }]}
      />,
    );

    await waitFor(() => {
      expect(screen.getByText('Body format')).toBeInTheDocument();
      expect(screen.getByText('Auth mode')).toBeInTheDocument();
    });
    expect(screen.queryByText('Body')).not.toBeInTheDocument();
    expect(screen.queryByText('Bearer token')).not.toBeInTheDocument();
    expect(screen.queryByText('Username')).not.toBeInTheDocument();
    expect(screen.queryByText('Password')).not.toBeInTheDocument();

    rerender(
      <WorkflowCanvas
        {...baseProps}
        nodes={[{
          id: 'http-1',
          type: 'http_request',
          position: [100, 100],
          params: { body_format: 'json', auth_mode: 'basic' },
        }]}
      />,
    );

    await waitFor(() => {
      expect(screen.getByText('Body')).toBeInTheDocument();
      expect(screen.getByText('Username')).toBeInTheDocument();
      expect(screen.getByText('Password')).toBeInTheDocument();
    });
    expect(screen.queryByText('Bearer token')).not.toBeInTheDocument();
  });

  it('logs media paste upload failures while keeping the failure toast', async () => {
    const { default: WorkflowCanvas } = await import('../components/canvas/WorkflowCanvas');
    const uploadError = new Error('upload unavailable');
    apiMocks.apiPost.mockRejectedValueOnce(uploadError);
    const getType = vi.fn().mockResolvedValue(new Blob(['image-data'], { type: 'image/png' }));

    vi.stubGlobal('navigator', {
      clipboard: {
        read: vi.fn().mockResolvedValue([
          {
            types: ['image/png'],
            getType,
          },
        ]),
        readText: vi.fn(),
      },
    });

    render(
      <WorkflowCanvas
        nodes={[]}
        edges={[]}
        groups={[]}
        objectInfo={{
          input_file: {
            id: 'input_file',
            display_name: 'Input File',
            category: 'Inputs',
            return_types: [],
          },
        } satisfies ObjectInfo}
        onNodesChange={() => undefined}
        onEdgesChange={() => undefined}
        onGroupsChange={() => undefined}
        onPushHistory={() => undefined}
        onUndo={() => undefined}
        onRedo={() => undefined}
        snapToGrid={false}
        showMinimap={false}
        viewportLocked={false}
        linksHidden={false}
        onToggleMinimap={() => undefined}
        onToggleLinksHidden={() => undefined}
      />,
    );

    await act(async () => {
      window.dispatchEvent(new KeyboardEvent('keydown', {
        key: 'v',
        ctrlKey: true,
        bubbles: true,
      }));
    });

    await waitFor(() => {
      expect(loggingMock.logError).toHaveBeenCalledWith('workflow.canvas.uploadMedia', uploadError);
    });
    expect(notificationMocks.toast.error).toHaveBeenCalledWith('Upload failed', { message: 'upload unavailable' });
    expect(notificationMocks.toast.success).not.toHaveBeenCalled();
  });
});
