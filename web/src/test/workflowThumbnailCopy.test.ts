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

// The thumbnail renderer now emits an inline SVG data URL (no Canvas2D). Decode
// it back to the SVG markup so we can assert on the rendered label text.
function decodeSvg(dataUrl: string): string {
  const comma = dataUrl.indexOf(',');
  return decodeURIComponent(dataUrl.slice(comma + 1));
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

  it('renders the empty-workflow thumbnail label from the active locale', async () => {
    const { setLanguage } = await import('../i18n');
    const { renderWorkflowThumbnail } = await import('../utils/workflowThumbnail');

    await setLanguage('es');
    const svg = decodeSvg(renderWorkflowThumbnail(emptyWorkflow));

    expect(svg).toContain('(flujo de trabajo vacio)');
    expect(svg).not.toContain('(workflow vacio)');
    expect(svg).not.toContain('(empty workflow)');
  });

  it('renders the node fallback label from the active locale', async () => {
    const { setLanguage } = await import('../i18n');
    const { renderWorkflowThumbnail } = await import('../utils/workflowThumbnail');

    await setLanguage('es');
    const svg = decodeSvg(renderWorkflowThumbnail({
      ...emptyWorkflow,
      nodes: [{
        id: 'node-1',
        type: '',
        position: [0, 0],
        params: {},
        ui: {},
      }],
    }));

    expect(svg).toContain('Nodo');
  });
});
