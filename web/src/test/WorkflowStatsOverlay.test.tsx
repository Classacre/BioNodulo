import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import type { Workflow } from '../types';

const apiMocks = vi.hoisted(() => ({
  apiGet: vi.fn(),
}));

vi.mock('../api/client', () => apiMocks);

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

const workflow: Workflow = {
  version: '1.0',
  app: 'BioNodulo',
  name: 'Stats workflow',
  description: '',
  nodes: [
    {
      id: 'n1',
      type: 'input_file',
      position: [0, 0],
      params: {},
      node_info: { id: 'input_file', display_name: 'Input', category: 'Input' },
    },
    {
      id: 'n2',
      type: 'fastqc',
      position: [200, 0],
      params: {},
      node_info: { id: 'fastqc', display_name: 'FastQC', category: 'Quality Control' },
    },
    {
      id: 'n3',
      type: 'custom_node',
      position: [400, 0],
      params: {},
      node_info: { id: 'custom_node', display_name: 'Custom', category: '' },
    },
    {
      id: 'note-1',
      type: 'note',
      position: [0, 120],
      params: {},
    },
  ],
  edges: [{ id: 'e1', from: { node: 'n1', output: 'file' }, to: { node: 'n2', input: 'reads' } }],
  groups: [{
    id: 'g1',
    name: 'QC',
    position: [0, 0],
    width: 300,
    height: 200,
    color: '#3b82f6',
    collapsed: false,
  }],
  outputs: {},
};

const systemStats = {
  system: {
    os: 'Linux',
    cpu_count: 8,
    cpu_percent: 23,
    cpu_temp_c: 61,
    ram_total: 16 * 1024 * 1024 * 1024,
    ram_used: 8 * 1024 * 1024 * 1024,
    ram_free: 8 * 1024 * 1024 * 1024,
    ram_percent: 47,
  },
  devices: [{
    index: 0,
    name: 'NVIDIA Test',
    type: 'gpu',
    vram_total: 8 * 1024 * 1024 * 1024,
    vram_used: 2 * 1024 * 1024 * 1024,
    vram_free: 6 * 1024 * 1024 * 1024,
    gpu_utilization: 35,
    temperature_c: 68,
  }],
};

describe('WorkflowStatsOverlay i18n', () => {
  beforeEach(() => {
    storage.clear();
    vi.stubGlobal('localStorage', localStorageStub);
    apiMocks.apiGet.mockReset();
  });

  afterEach(async () => {
    const { setLanguage } = await import('../i18n');
    await setLanguage('en');
    storage.clear();
    vi.unstubAllGlobals();
  });

  it('renders workflow and system stats overlay copy from the active locale', async () => {
    const { default: WorkflowStatsOverlay } = await import('../components/canvas/WorkflowStatsOverlay');
    const { setLanguage } = await import('../i18n');

    apiMocks.apiGet.mockResolvedValue(systemStats);
    await setLanguage('es');

    render(<WorkflowStatsOverlay workflow={workflow} />);

    await waitFor(() => expect(screen.getByText('NVIDIA Test')).toBeInTheDocument());

    expect(screen.getByRole('button', { name: 'Colapsar estadisticas de flujo de trabajo' })).toHaveAttribute('title', 'Colapsar');
    expect(screen.queryByRole('button', { name: 'Colapsar estadisticas de workflow' })).not.toBeInTheDocument();
    expect(screen.getByText('nodos')).toBeInTheDocument();
    expect(screen.getByText('enlaces')).toBeInTheDocument();
    expect(screen.getByText('grupos')).toBeInTheDocument();
    expect(screen.getByText('Entrada')).toBeInTheDocument();
    expect(screen.getByText('Control de calidad')).toBeInTheDocument();
    expect(screen.queryByText('Input')).not.toBeInTheDocument();
    expect(screen.queryByText('Quality Control')).not.toBeInTheDocument();
    expect(screen.getByText('Otros')).toBeInTheDocument();
    expect(screen.getByText('CPU')).toBeInTheDocument();
    expect(screen.getByText('RAM')).toBeInTheDocument();
    expect(screen.getByText('GPU')).toBeInTheDocument();
    expect(screen.getByText('VRAM')).toBeInTheDocument();
    expect(screen.getAllByText('Temp')).toHaveLength(2);
    expect(screen.getByText('8,0 GB / 16,0 GB')).toBeInTheDocument();
    expect(screen.getByText('2,0 GB / 8,0 GB')).toBeInTheDocument();
    expect(screen.queryByText('8.0 GB / 16.0 GB')).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Colapsar estadisticas de flujo de trabajo' }));

    expect(screen.getByTitle('Expandir estadisticas de flujo de trabajo y sistema')).toHaveTextContent('3n - 1e');
    expect(screen.queryByTitle('Expandir estadisticas de workflow y sistema')).not.toBeInTheDocument();
  });

  it('keeps WorkflowStatsOverlay labels behind i18n keys', () => {
    const source = readFileSync(resolve(__dirname, '../components/canvas/WorkflowStatsOverlay.tsx'), 'utf8');

    [
      'workflowStats.categoryFallback',
      'workflowStats.expandTitle',
      'workflowStats.collapseAria',
      'workflowStats.collapseTitle',
      'workflowStats.nodesLabel',
      'workflowStats.edgesLabel',
      'workflowStats.groupsLabel',
      'workflowStats.compactNodeSuffix',
      'workflowStats.compactEdgeSuffix',
      'workflowStats.cpuLabel',
      'workflowStats.ramLabel',
      'workflowStats.gpuLabel',
      'workflowStats.vramLabel',
      'workflowStats.tempLabel',
      'workflowStats.sizeMB',
      'workflowStats.sizeGB',
    ].forEach(key => expect(source).toContain(key));

    [
      "'Other'",
      'Expand workflow + system stats',
      'Collapse workflow stats',
      'title="Collapse"',
      '>nodes<',
      '>edges<',
      '>groups<',
      'label="CPU"',
      'label="RAM"',
      'label="GPU"',
      'label="VRAM"',
      '>Temp<',
    ].forEach(text => expect(source).not.toContain(text));
  });
});
