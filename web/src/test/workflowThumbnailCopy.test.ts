import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { Workflow } from '../types';

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

const emptyWorkflow: Workflow = {
  version: '2.0',
  app: 'BioNodulo',
  name: 'Empty',
  description: '',
  nodes: [],
  edges: [],
  groups: [],
  outputs: {},
};

function stubCanvas(fillText: ReturnType<typeof vi.fn>) {
  const context = {
    clearRect: vi.fn(),
    fillRect: vi.fn(),
    fillText,
  };

  vi.spyOn(document, 'createElement').mockImplementation(((tagName: string) => {
    if (tagName !== 'canvas') return document.createElement(tagName);
    return {
      width: 0,
      height: 0,
      getContext: () => context,
      toDataURL: () => 'data:image/png;base64,thumbnail',
    } as unknown as HTMLCanvasElement;
  }) as typeof document.createElement);
}

describe('workflow thumbnail copy i18n', () => {
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

  it('draws the empty-workflow thumbnail label from the active locale', async () => {
    const { setLanguage } = await import('../i18n');
    const { renderWorkflowThumbnail } = await import('../utils/workflowThumbnail');
    const fillText = vi.fn();
    stubCanvas(fillText);

    await setLanguage('es');

    renderWorkflowThumbnail(emptyWorkflow);

    expect(fillText).toHaveBeenCalledWith('(workflow vacio)', 16, 24);
    expect(fillText).not.toHaveBeenCalledWith('(empty workflow)', 16, 24);
  });
});
