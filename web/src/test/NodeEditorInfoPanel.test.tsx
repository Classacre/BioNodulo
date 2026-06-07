import { fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { GraphNode } from '../components/canvas/WorkflowCanvas';

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

function graphNode(): GraphNode {
  return {
    id: 'fastqc-1',
    type: 'fastqc',
    display_name: 'FastQC',
    category: 'Quality Control',
    x: 0,
    y: 0,
    width: 220,
    height: 120,
    inputs: [],
    outputs: [],
    params: {
      reads: '',
      mode: 'fast',
      threads: 4,
      adapter: '',
    },
    meta: {
      id: 'fastqc',
      display_name: 'FastQC',
      category: 'Quality Control',
      description: 'Read quality report',
      version: '1.0.0',
      environment: 'qc-env',
      search_aliases: ['quality', 'reads'],
      documentation_url: 'https://example.test/fastqc',
      requires_external_tools: ['fastqc'],
      input_types: {
        required: {
          reads: {
            type: 'FASTQ',
            label: 'Reads',
            default: 'sample.fastq.gz',
            tooltip: 'Input reads',
          },
        },
        optional: {
          mode: {
            type: 'STRING',
            label: 'Mode',
            options: ['fast', 'full'],
            default: 'fast',
          },
          threads: {
            type: 'INT',
            label: 'Threads',
            min: 1,
            max: 16,
            default: 4,
          },
          adapter: {
            type: 'FILE',
            label: 'Adapter',
            advanced: true,
          },
        },
      },
      return_types: ['HTML_REPORT'],
      return_names: ['report'],
    },
    color: '#2563eb',
    muted: false,
    bypassed: false,
    selected: true,
    collapsed: false,
    pinned: false,
    shape: 'round',
    title: 'FastQC node',
    visualOnly: false,
  };
}

describe('Node editor and info panel i18n', () => {
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

  it('renders editable parameter chrome from the active locale', async () => {
    const { default: NodeEditor } = await import('../components/nodes/NodeEditor');
    const { setLanguage } = await import('../i18n');
    const onParamChange = vi.fn();

    await setLanguage('es');

    render(<NodeEditor node={graphNode()} onParamChange={onParamChange} onClose={() => undefined} />);

    expect(screen.getByText('Obligatorio')).toBeInTheDocument();
    expect(screen.getByText('Opcional')).toBeInTheDocument();
    expect(screen.getByText('Mostrar avanzados')).toBeInTheDocument();
    expect(screen.getByText('Herramientas requeridas')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Documentacion ↗' })).toBeInTheDocument();
    expect(screen.getByPlaceholderText('Suelta un archivo o escribe una ruta...')).toBeInTheDocument();

    fireEvent.click(screen.getByText('Mostrar avanzados'));

    expect(screen.getByText('Ocultar avanzados')).toBeInTheDocument();
    expect(screen.getByText('avanzado')).toBeInTheDocument();

    fireEvent.change(screen.getByDisplayValue('4'), { target: { value: '8' } });

    expect(onParamChange).toHaveBeenCalledWith('fastqc-1', 'threads', 8);
  });

  it('renders read-only node information from the active locale', async () => {
    const { default: NodeInfoPanel } = await import('../components/nodes/NodeInfoPanel');
    const { setLanguage } = await import('../i18n');

    await setLanguage('es');

    render(<NodeInfoPanel node={graphNode()} onClose={() => undefined} />);

    expect(screen.getByText('Control de calidad · fastqc')).toBeInTheDocument();
    expect(screen.queryByText('Quality Control · fastqc')).not.toBeInTheDocument();
    expect(screen.getByText('Entradas obligatorias')).toBeInTheDocument();
    expect(screen.getByText('Entradas opcionales')).toBeInTheDocument();
    expect(screen.getByText('Salidas')).toBeInTheDocument();
    expect(screen.getByText('Metadatos')).toBeInTheDocument();
    expect(screen.getByText('Version')).toBeInTheDocument();
    expect(screen.getByText('Requiere')).toBeInTheDocument();
    expect(screen.getByText('Entorno')).toBeInTheDocument();
    expect(screen.getByText('Alias')).toBeInTheDocument();
    expect(screen.getAllByText(/Predeterminado:/)).toHaveLength(4);
    expect(screen.getByText('Sin valor predeterminado')).toBeInTheDocument();
    expect(screen.queryByText('—')).not.toBeInTheDocument();
    expect(screen.getByText(/Opciones:/)).toBeInTheDocument();
    expect(screen.getByText('Min: 1')).toBeInTheDocument();
    expect(screen.getByText('Max: 16')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Abrir documentacion ↗' })).toBeInTheDocument();
  });
});
