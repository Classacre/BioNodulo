import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { createWorkflowDoc, docToWorkflow, workflowToDoc } from '../collab/yjsDoc';
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

describe('collaboration workflow document serialization', () => {
  beforeEach(() => {
    storage.clear();
    vi.stubGlobal('localStorage', localStorageStub);
  });

  afterEach(async () => {
    const { setLanguage } = await import('../i18n');
    await setLanguage('en');
    storage.clear();
    vi.unstubAllGlobals();
  });

  it('preserves workflow parameters across Yjs round trips', () => {
    const workflow: Workflow = {
      id: 'wf-params',
      version: '2.0',
      app: 'bionodulo',
      name: 'Parameterized collaboration',
      description: '',
      nodes: [],
      edges: [],
      groups: [],
      outputs: {},
      parameters: [
        {
          name: 'sample_id',
          type: 'STRING',
          required: true,
          default: 'S1',
          description: 'Sample identifier',
        },
      ],
    };

    const doc = workflowToDoc(workflow);
    const roundTripped = docToWorkflow(doc);

    expect(roundTripped.parameters).toEqual(workflow.parameters);
  });

  it('uses the active locale for collaborative workflow name fallbacks', async () => {
    const { setLanguage } = await import('../i18n');
    await setLanguage('es');

    const emptyDoc = createWorkflowDoc('wf-localized');
    expect(docToWorkflow(emptyDoc).name).toBe('Sin titulo');

    const unnamedWorkflow: Workflow = {
      id: 'wf-empty-name',
      version: '2.0',
      app: 'bionodulo',
      name: '',
      description: '',
      nodes: [],
      edges: [],
      groups: [],
      outputs: {},
      parameters: [],
    };

    expect(docToWorkflow(workflowToDoc(unnamedWorkflow)).name).toBe('Sin titulo');
  });
});
