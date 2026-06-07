import { render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { ObjectInfo } from '../types';

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
});
