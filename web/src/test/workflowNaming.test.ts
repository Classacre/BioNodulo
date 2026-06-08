import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import type { Workflow, WorkflowNode } from '../types';
import { isUntitledWorkflowName, resolveWorkflowName, suggestWorkflowName } from '../utils/workflowNaming';

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

function node(id: string, category: string, tools: string[] = []): WorkflowNode {
  return {
    id,
    type: id,
    position: [0, 0],
    params: {},
    node_info: {
      id,
      display_name: id,
      category,
      requires_external_tools: tools,
    },
  };
}

function workflow(partial: Partial<Workflow>): Workflow {
  return {
    version: '2.0',
    app: 'BioNodulo',
    name: '',
    description: '',
    nodes: [],
    edges: [],
    groups: [],
    outputs: {},
    ...partial,
  };
}

describe('workflow naming i18n', () => {
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

  it('returns generated workflow names from the active locale', async () => {
    const { default: i18n, setLanguage } = await import('../i18n');
    await setLanguage('es');

    expect(i18n.t('workflowNaming.categories.Alignment')).toBe('alineacion');
    expect(suggestWorkflowName(workflow({
      nodes: [
        node('bwa', 'Alignment', ['BWA']),
        node('samtools', 'Alignment', ['samtools']),
      ],
    }))).toBe('BWA + samtools alineacion');
    expect(suggestWorkflowName(workflow({
      nodes: [
        node('custom', 'Custom', []),
      ],
    }))).toBe('flujo de trabajo de custom');
    expect(resolveWorkflowName(workflow({ name: '', nodes: [] }))).toBe('Flujo de trabajo sin titulo');
    expect(resolveWorkflowName(workflow({ name: '', nodes: [] }))).not.toBe('Workflow sin titulo');
    expect(i18n.t('workflowNaming.fallbackCategory')).toBe('flujo de trabajo');
    expect(i18n.t('workflowNaming.categoryWorkflow', { category: 'custom' })).toBe('flujo de trabajo de custom');
  });

  it('recognizes canonical untitled workflow names for display fallbacks', () => {
    expect(isUntitledWorkflowName('')).toBe(true);
    expect(isUntitledWorkflowName('Untitled')).toBe(true);
    expect(isUntitledWorkflowName('Untitled Workflow')).toBe(true);
    expect(isUntitledWorkflowName('new workflow')).toBe(true);
    expect(isUntitledWorkflowName('RNA-seq QC')).toBe(false);
  });

  it('keeps workflow naming fragments behind i18n keys', () => {
    const source = readFileSync(resolve(__dirname, '../utils/workflowNaming.ts'), 'utf8');

    [
      "Alignment: 'alignment'",
      "'Variant Calling': 'variant call'",
      "'Read Preprocessing': 'preprocessing'",
      "'Quality Control': 'QC'",
      "Utility: 'pipeline'",
      "'workflow'",
      "'Untitled workflow'",
    ].forEach(text => expect(source).not.toContain(text));
  });
});
