import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { Workflow, WorkflowNode } from '../types';
import type { SampleSheetRun } from '../components/modals/BatchSampleSheetModal';

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

function node(partial: Partial<WorkflowNode> & Pick<WorkflowNode, 'id' | 'type'>): WorkflowNode {
  return {
    id: partial.id,
    type: partial.type,
    position: partial.position ?? [0, 0],
    params: partial.params ?? {},
    node_info: partial.node_info,
    parentId: partial.parentId,
    ui: partial.ui,
  };
}

function workflow(partial: Partial<Workflow>): Workflow {
  return {
    version: '1.0',
    app: 'BioNodulo',
    name: partial.name ?? '',
    description: partial.description ?? '',
    nodes: partial.nodes ?? [],
    edges: partial.edges ?? [],
    groups: partial.groups ?? [],
    outputs: partial.outputs ?? {},
    environment: partial.environment,
    dependencies: partial.dependencies,
    parameters: partial.parameters,
  };
}

describe('BatchSampleSheetModal i18n', () => {
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

  it('renders CSV mapping and queue action from the active locale', async () => {
    const { default: BatchSampleSheetModal } = await import('../components/modals/BatchSampleSheetModal');
    const { setLanguage } = await import('../i18n');
    const onClose = vi.fn();
    const onSubmit = vi.fn<(runs: SampleSheetRun[]) => void>();

    await setLanguage('es');

    render(
      <BatchSampleSheetModal
        workflow={workflow({
          parameters: [
            { name: 'genome', type: 'STRING', required: false },
          ],
          nodes: [
            node({
              id: 'align',
              type: 'bwa_align',
              ui: { title: 'Alinear' },
              params: { fastq_in: '', threads: 4 },
            }),
          ],
        })}
        onClose={onClose}
        onSubmit={onSubmit}
      />,
    );

    expect(screen.getByRole('dialog', { name: 'Lote desde hoja de muestras' })).toBeInTheDocument();
    expect(screen.getByText('Una ejecucion por fila. Asigna columnas a parametros de nodos; el resto se omite. CSV y TSV funcionan.')).toBeInTheDocument();
    expect(screen.getByText('Subir hoja de muestras')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('Prefijo del nombre de ejecucion')).toHaveValue('Muestra');

    fireEvent.change(screen.getByPlaceholderText(/muestra,fastq_in,threads/), {
      target: {
        value: 'sample,fastq_in,threads\nctrl_01,/data/c1.fastq.gz,8\nctrl_02,/data/c2.fastq.gz,16',
      },
    });

    expect(screen.getByText('2 filas, 3 columnas (CSV)')).toBeInTheDocument();
    expect(screen.getByText('Mapeo de columnas')).toBeInTheDocument();
    expect(screen.getByText('Vista previa (2 de 2)')).toBeInTheDocument();
    expect(screen.getByText('ctrl_01')).toBeInTheDocument();
    expect(screen.getByText('ctrl_02')).toBeInTheDocument();
    expect(screen.getAllByText('Omitir').length).toBeGreaterThan(0);
    expect(screen.getAllByText('Usar como nombre de ejecucion').length).toBeGreaterThan(0);
    expect(screen.getAllByRole('option', { name: 'Parametro de flujo de trabajo -> genome' })).toHaveLength(3);
    expect(screen.queryAllByRole('option', { name: 'Parametro de workflow -> genome' })).toHaveLength(0);

    fireEvent.click(screen.getByRole('button', { name: /Encolar 2 ejecuciones/ }));

    expect(onSubmit).toHaveBeenCalledTimes(1);
    const submittedRuns = onSubmit.mock.calls[0][0];
    expect(submittedRuns).toHaveLength(2);
    expect(submittedRuns[0].name).toBe('ctrl_01');
    expect(submittedRuns[0].workflow.name).toBe('ctrl_01');
    expect(submittedRuns[0].workflow.nodes[0].params.fastq_in).toBe('/data/c1.fastq.gz');
    expect(submittedRuns[0].workflow.nodes[0].params.threads).toBe(8);
    await waitFor(() => expect(onClose).toHaveBeenCalledTimes(1));
  });

  it('maps declared workflow parameter columns to runtime overrides without replacing placeholders', async () => {
    const { default: BatchSampleSheetModal } = await import('../components/modals/BatchSampleSheetModal');
    const onClose = vi.fn();
    const onSubmit = vi.fn<(runs: SampleSheetRun[]) => void>();

    render(
      <BatchSampleSheetModal
        workflow={workflow({
          name: 'Parameter batch',
          parameters: [
            { name: 'sample_id', type: 'STRING', required: true },
          ],
          nodes: [
            node({
              id: 'report',
              type: 'report_node',
              params: { sample: '{{sample_id}}', threads: 4 },
            }),
          ],
        })}
        onClose={onClose}
        onSubmit={onSubmit}
      />,
    );

    fireEvent.change(screen.getByPlaceholderText(/sample,fastq_in,threads/), {
      target: {
        value: 'sample_id,threads\nS1,8',
      },
    });

    await waitFor(() => expect(screen.getByText('1 row, 2 columns (CSV)')).toBeInTheDocument());
    fireEvent.click(screen.getByRole('button', { name: /Queue 1 run/ }));

    expect(onSubmit).toHaveBeenCalledTimes(1);
    const submittedRun = onSubmit.mock.calls[0][0][0];
    expect(submittedRun.parameters).toEqual({ sample_id: 'S1' });
    expect(submittedRun.workflow.nodes[0].params.sample).toBe('{{sample_id}}');
    expect(submittedRun.workflow.nodes[0].params.threads).toBe(8);
    await waitFor(() => expect(onClose).toHaveBeenCalledTimes(1));
  });
});
