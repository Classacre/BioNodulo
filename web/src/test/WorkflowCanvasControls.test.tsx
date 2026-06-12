import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { ObjectInfo, WorkflowNode } from '../types';

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

  it('renders hover-card node categories from the active locale', async () => {
    const { default: WorkflowCanvas } = await import('../components/canvas/WorkflowCanvas');
    const { setLanguage } = await import('../i18n');
    const fillText = vi.fn();
    stubCanvasContext(fillText);

    await setLanguage('es');

    const { container } = render(
      <WorkflowCanvas
        nodes={[{
          id: 'hover-node',
          type: 'hover_node',
          position: [100, 100],
          params: {},
        }]}
        edges={[]}
        groups={[]}
        objectInfo={{
          hover_node: {
            id: 'hover_node',
            display_name: 'Hover Node',
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
      expect(fillText).toHaveBeenCalledWith('Hover Node', expect.any(Number), expect.any(Number));
    });

    const canvas = container.querySelector('canvas');
    expect(canvas).toBeTruthy();
    act(() => {
      fireEvent.mouseMove(canvas!, { clientX: 120, clientY: 120 });
    });

    expect(await screen.findByText('Utilidad')).toBeInTheDocument();
    expect(screen.queryByText('Utility')).not.toBeInTheDocument();
  });

  it('draws dynamic switch outputs from the branch count parameter', async () => {
    const { default: WorkflowCanvas } = await import('../components/canvas/WorkflowCanvas');
    const fillText = vi.fn();
    stubCanvasContext(fillText);
    const objectInfo = {
      switch: {
        id: 'switch',
        display_name: 'Switch',
        category: 'flow_control',
        input_types: {
          required: {
            value: { type: 'ANY' },
            cases: { type: 'STRING', default: '' },
          },
          optional: {
            num_branches: {
              type: 'INT',
              default: 4,
              min: 1,
              max: 32,
              dynamic_outputs: {
                prefix: 'output_',
                count_input: 'num_branches',
                default_output: 'default',
                type: 'ANY',
              },
            },
          },
        },
        return_types: ['ANY', 'ANY', 'ANY', 'ANY', 'ANY'],
        return_names: ['output_1', 'output_2', 'output_3', 'output_4', 'default'],
      },
    } satisfies ObjectInfo;

    render(
      <WorkflowCanvas
        nodes={[{
          id: 'switch-1',
          type: 'switch',
          position: [100, 100],
          params: { num_branches: 6 },
        }]}
        edges={[]}
        groups={[]}
        objectInfo={objectInfo}
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
      expect(fillText).toHaveBeenCalledWith('output_5', expect.any(Number), expect.any(Number));
      expect(fillText).toHaveBeenCalledWith('output_6', expect.any(Number), expect.any(Number));
      expect(fillText).toHaveBeenCalledWith('default', expect.any(Number), expect.any(Number));
    });
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

  it('clips DOM widgets to each node and keeps them on their node layer', async () => {
    const { default: WorkflowCanvas } = await import('../components/canvas/WorkflowCanvas');
    stubCanvasContext(vi.fn());
    const objectInfo = {
      data_validator: {
        id: 'data_validator',
        display_name: 'Data Validator',
        category: 'workflow',
        input_types: {
          required: {
            input: { type: 'ANY' },
          },
          optional: {
            expected_format: { type: 'STRING', label: 'Expected format', options: ['auto', 'fasta', 'fastq'], default: 'auto' },
            min_size_bytes: { type: 'INT', label: 'Minimum bytes', default: 0 },
            max_size_bytes: { type: 'INT', label: 'Maximum bytes', default: 0 },
            required_fields: { type: 'STRING', label: 'Required fields', default: '' },
            min_records: { type: 'INT', label: 'Minimum records', default: 0 },
            checksum_expected: { type: 'STRING', label: 'Checksum', default: '' },
            fail_on_error: { type: 'BOOLEAN', label: 'Fail on Error', default: true },
          },
        },
        return_types: ['ANY', 'BOOLEAN', 'JSON', 'FILE'],
        return_names: ['passthrough', 'passed', 'validation_report', 'report_file'],
      },
    } satisfies ObjectInfo;

    const { container } = render(
      <WorkflowCanvas
        nodes={[{
          id: 'validator-1',
          type: 'data_validator',
          position: [100, 100],
          params: {
            expected_format: 'fasta',
            min_size_bytes: 1,
            max_size_bytes: 0,
            required_fields: '',
            min_records: 1,
            checksum_expected: '',
            fail_on_error: true,
          },
        }]}
        edges={[]}
        groups={[]}
        objectInfo={objectInfo}
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

    const failOnError = await screen.findByText('Fail on Error');
    const layer = failOnError.closest('.node-dom-widget-layer') as HTMLElement;
    expect(layer).toBeTruthy();
    expect(layer).toHaveStyle({
      overflow: 'hidden',
      pointerEvents: 'none',
    });
    expect(parseFloat(layer.style.height)).toBeGreaterThan(220);
    expect(Number(layer.style.zIndex)).toBeLessThan(100);
    expect(container.querySelectorAll('.node-dom-widget-layer')).toHaveLength(1);
  });

  it('auto-arranges tall nodes without vertical overlap', async () => {
    const { default: WorkflowCanvas } = await import('../components/canvas/WorkflowCanvas');
    stubCanvasContext(vi.fn());
    const onNodesChange = vi.fn();
    const objectInfo = {
      tall_node: {
        id: 'tall_node',
        display_name: 'Tall Node',
        category: 'workflow',
        input_types: {
          optional: Object.fromEntries(Array.from({ length: 8 }, (_, index) => [
            `option_${index}`,
            { type: 'STRING', label: `Option ${index}`, default: `value-${index}` },
          ])),
        },
        return_types: [],
      },
    } satisfies ObjectInfo;
    const nodes: WorkflowNode[] = [
      {
        id: 'n1',
        type: 'tall_node',
        position: [400, 100],
        params: Object.fromEntries(Array.from({ length: 8 }, (_, index) => [`option_${index}`, `value-${index}`])),
      },
      {
        id: 'n2',
        type: 'tall_node',
        position: [400, 110],
        params: Object.fromEntries(Array.from({ length: 8 }, (_, index) => [`option_${index}`, `value-${index}`])),
      },
    ];

    render(
      <WorkflowCanvas
        nodes={nodes}
        edges={[]}
        groups={[]}
        objectInfo={objectInfo}
        onNodesChange={onNodesChange}
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

    fireEvent.click(await screen.findByTitle('Auto-arrange nodes'));

    await waitFor(() => {
      expect(onNodesChange).toHaveBeenCalled();
    });
    const arranged = onNodesChange.mock.calls.at(-1)?.[0] as WorkflowNode[];
    const first = arranged.find(node => node.id === 'n1');
    const second = arranged.find(node => node.id === 'n2');
    expect(first?.position[1]).toBe(60);
    expect(second?.position[1]).toBeGreaterThan(300);
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
