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
      citation_dois: ['10.1093/bioinformatics/btw000'],
      citation_urls: ['https://doi.org/10.1093/bioinformatics/btw000'],
      citation_text: 'FastQC methods paper.',
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

function httpRequestNode(params: Record<string, unknown> = { body_format: 'none', auth_mode: 'none' }): GraphNode {
  return {
    ...graphNode(),
    id: 'http-1',
    type: 'http_request',
    display_name: 'HTTP Request',
    category: 'api',
    params,
    meta: {
      id: 'http_request',
      display_name: 'HTTP Request',
      category: 'api',
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
    },
    title: 'HTTP Request node',
  };
}

function switchNode(params: Record<string, unknown> = { num_branches: 6 }): GraphNode {
  return {
    ...graphNode(),
    id: 'switch-1',
    type: 'switch',
    display_name: 'Switch',
    category: 'flow_control',
    inputs: [],
    outputs: [],
    params,
    meta: {
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
    title: 'Switch node',
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

  it('inserts workflow parameter references into text-like node fields', async () => {
    const { default: NodeEditor } = await import('../components/nodes/NodeEditor');
    const onParamChange = vi.fn();

    render(
      <NodeEditor
        node={graphNode()}
        workflowParameters={[{ name: 'sample_id', type: 'STRING' }]}
        onParamChange={onParamChange}
        onClose={() => undefined}
      />,
    );

    fireEvent.change(screen.getByLabelText('Insert workflow parameter into Reads'), {
      target: { value: 'sample_id' },
    });

    expect(onParamChange).toHaveBeenCalledWith('fastqc-1', 'reads', '{{sample_id}}');
  });

  it('hides conditional editor fields until their controlling parameter matches', async () => {
    const { default: NodeEditor } = await import('../components/nodes/NodeEditor');
    const onParamChange = vi.fn();
    const node = httpRequestNode();

    const { rerender } = render(<NodeEditor node={node} onParamChange={onParamChange} onClose={() => undefined} />);

    expect(screen.getByText('Body format')).toBeInTheDocument();
    expect(screen.getByText('Auth mode')).toBeInTheDocument();
    expect(screen.queryByText('Body')).not.toBeInTheDocument();
    expect(screen.queryByText('Bearer token')).not.toBeInTheDocument();
    expect(screen.queryByText('Username')).not.toBeInTheDocument();
    expect(screen.queryByText('Password')).not.toBeInTheDocument();

    rerender(
      <NodeEditor
        node={{
          ...node,
          params: {
            ...node.params,
            body_format: 'json',
            auth_mode: 'basic',
          },
        }}
        onParamChange={onParamChange}
        onClose={() => undefined}
      />,
    );

    expect(screen.getByText('Body')).toBeInTheDocument();
    expect(screen.getByText('Username')).toBeInTheDocument();
    expect(screen.getByText('Password')).toBeInTheDocument();
    expect(screen.queryByText('Bearer token')).not.toBeInTheDocument();
  });

  it('hides conditional read-only info inputs until their controlling parameter matches', async () => {
    const { default: NodeInfoPanel } = await import('../components/nodes/NodeInfoPanel');
    const node = httpRequestNode();

    const { rerender } = render(<NodeInfoPanel node={node} onClose={() => undefined} />);

    expect(screen.getByText('Body format')).toBeInTheDocument();
    expect(screen.getByText('Auth mode')).toBeInTheDocument();
    expect(screen.queryByText('Body')).not.toBeInTheDocument();
    expect(screen.queryByText('Bearer token')).not.toBeInTheDocument();
    expect(screen.queryByText('Username')).not.toBeInTheDocument();
    expect(screen.queryByText('Password')).not.toBeInTheDocument();

    rerender(
      <NodeInfoPanel
        node={httpRequestNode({ body_format: 'json', auth_mode: 'basic' })}
        onClose={() => undefined}
      />,
    );

    expect(screen.getByText('Body')).toBeInTheDocument();
    expect(screen.getByText('Username')).toBeInTheDocument();
    expect(screen.getByText('Password')).toBeInTheDocument();
    expect(screen.queryByText('Bearer token')).not.toBeInTheDocument();
  });

  it('renders dynamic outputs in read-only node information', async () => {
    const { default: NodeInfoPanel } = await import('../components/nodes/NodeInfoPanel');

    render(<NodeInfoPanel node={switchNode()} onClose={() => undefined} />);

    expect(screen.getByText('output_5')).toBeInTheDocument();
    expect(screen.getByText('output_6')).toBeInTheDocument();
    expect(screen.getByText('default')).toBeInTheDocument();
  });

  it('wraps long citation metadata values inside the info panel', async () => {
    const { default: NodeInfoPanel } = await import('../components/nodes/NodeInfoPanel');
    const longCitation = 'Sensitive protein alignments at tree-of-life scale using DIAMOND.';

    render(
      <NodeInfoPanel
        node={{
          ...graphNode(),
          meta: {
            ...graphNode().meta,
            citation_text: longCitation,
          },
        }}
        onClose={() => undefined}
      />,
    );

    expect(screen.getByText(longCitation)).toHaveStyle({ overflowWrap: 'anywhere' });
  });

  it('lets the canvas wrapper control the read-only info panel position', async () => {
    const { default: NodeInfoPanel } = await import('../components/nodes/NodeInfoPanel');

    render(<NodeInfoPanel node={graphNode()} onClose={() => undefined} />);

    expect(screen.getByTestId('node-info-panel')).toHaveStyle({
      position: 'relative',
      right: 'auto',
      top: 'auto',
    });
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
    expect(screen.getByText('DOI')).toBeInTheDocument();
    expect(screen.getByText('10.1093/bioinformatics/btw000')).toBeInTheDocument();
    expect(screen.getByText('Cita')).toBeInTheDocument();
    expect(screen.getByText('FastQC methods paper.')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'https://doi.org/10.1093/bioinformatics/btw000' })).toHaveAttribute(
      'href',
      'https://doi.org/10.1093/bioinformatics/btw000',
    );
    expect(screen.getAllByText(/Predeterminado:/)).toHaveLength(4);
    expect(screen.getByText('Sin valor predeterminado')).toBeInTheDocument();
    expect(screen.queryByText('—')).not.toBeInTheDocument();
    expect(screen.getByText(/Opciones:/)).toBeInTheDocument();
    expect(screen.getByText('Min: 1')).toBeInTheDocument();
    expect(screen.getByText('Max: 16')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Abrir documentacion ↗' })).toBeInTheDocument();
  });
});
