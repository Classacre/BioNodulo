import { fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { ObjectInfo, Workflow, WorkflowNode } from '../types';

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
    name: partial.name ?? 'Test workflow',
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

describe('WorkflowDoctorModal i18n', () => {
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

  it('renders empty-workflow findings from the active locale', async () => {
    const { default: WorkflowDoctorModal } = await import('../components/modals/WorkflowDoctorModal');
    const { setLanguage } = await import('../i18n');

    await setLanguage('es');

    render(
      <WorkflowDoctorModal
        workflow={workflow({})}
        objectInfo={{}}
        onClose={() => undefined}
        onJumpToNode={() => undefined}
      />,
    );

    expect(screen.getByRole('dialog', { name: 'Doctor de flujo de trabajo' })).toBeInTheDocument();
    expect(screen.queryByRole('dialog', { name: 'Doctor de workflow' })).not.toBeInTheDocument();
    expect(screen.getByText('1 info')).toBeInTheDocument();
    expect(screen.getByText('El flujo de trabajo esta vacio')).toBeInTheDocument();
    expect(screen.queryByText('El workflow esta vacio')).not.toBeInTheDocument();
    expect(screen.getByText('Suelta una plantilla, arrastra un archivo desde el espacio de trabajo o abre la biblioteca de nodos para empezar.')).toBeInTheDocument();
    expect(screen.getAllByRole('button', { name: 'Cerrar' }).length).toBeGreaterThan(0);
  });

  it('renders the healthy state from the active locale', async () => {
    const { default: WorkflowDoctorModal } = await import('../components/modals/WorkflowDoctorModal');
    const { setLanguage } = await import('../i18n');

    await setLanguage('es');

    render(
      <WorkflowDoctorModal
        workflow={workflow({
          nodes: [node({ id: 'out', type: 'output_node' })],
        })}
        objectInfo={{
          output_node: {
            id: 'output_node',
            display_name: 'Output',
            category: 'IO',
            output_node: true,
          },
        }}
        onClose={() => undefined}
        onJumpToNode={() => undefined}
      />,
    );

    expect(screen.getByText('El flujo de trabajo se ve correcto')).toBeInTheDocument();
    expect(screen.queryByText('El workflow se ve correcto')).not.toBeInTheDocument();
    expect(screen.getByText('No se encontraron incidencias. Todo esta conectado.')).toBeInTheDocument();
  });

  it('renders node diagnostics and jump action from the active locale', async () => {
    const { default: WorkflowDoctorModal } = await import('../components/modals/WorkflowDoctorModal');
    const { setLanguage } = await import('../i18n');
    const onJumpToNode = vi.fn();

    await setLanguage('es');

    const objectInfo: ObjectInfo = {
      bwa_align: {
        id: 'bwa_align',
        display_name: 'BWA align',
        category: 'Alignment',
        input_types: { required: { reads: { type: 'FASTQ' } } },
        return_types: ['BAM'],
        requires_external_tools: ['bwa', 'samtools'],
      },
      multiqc: {
        id: 'multiqc',
        display_name: 'MultiQC',
        category: 'QC',
        output_node: true,
      },
    };

    render(
      <WorkflowDoctorModal
        workflow={workflow({
          nodes: [
            node({ id: 'align', type: 'bwa_align', ui: { title: 'Alinear reads' } }),
            node({ id: 'report', type: 'multiqc' }),
          ],
        })}
        objectInfo={objectInfo}
        onClose={() => undefined}
        onJumpToNode={onJumpToNode}
      />,
    );

    expect(screen.getByText('1 error')).toBeInTheDocument();
    expect(screen.getByText('2 advertencias')).toBeInTheDocument();
    expect(screen.getByText('1 info')).toBeInTheDocument();
    expect(screen.getByText('Alinear reads: la entrada obligatoria "reads" no esta definida')).toBeInTheDocument();
    expect(screen.getByText('Conecta una salida anterior o define un valor predeterminado en el editor del nodo.')).toBeInTheDocument();
    expect(screen.getByText('Alinear reads tiene salidas sin usar')).toBeInTheDocument();
    expect(screen.getByText('Conecta a un nodo posterior o elimina si es intencional.')).toBeInTheDocument();
    expect(screen.getByText('Alinear reads requiere: bwa, samtools')).toBeInTheDocument();
    expect(screen.getByText('No hay conexiones entre nodos')).toBeInTheDocument();
    expect(screen.getByText('Conecta salidas con entradas arrastrando entre puertos.')).toBeInTheDocument();

    fireEvent.click(screen.getAllByRole('button', { name: 'Ir' })[0]);

    expect(onJumpToNode).toHaveBeenCalledWith('align');
  });

  it('reports unknown workflow parameter references in node parameters', async () => {
    const { default: WorkflowDoctorModal } = await import('../components/modals/WorkflowDoctorModal');

    render(
      <WorkflowDoctorModal
        workflow={workflow({
          nodes: [
            node({
              id: 'input',
              type: 'input_fastq',
              ui: { title: 'FASTQ input' },
              params: {
                reads: 'sample-{{sample_typo}}.fastq.gz',
                template: 'local {{sample}} placeholder',
              },
            }),
          ],
          parameters: [{ name: 'sample_id', type: 'STRING' }],
        })}
        objectInfo={{
          input_fastq: {
            id: 'input_fastq',
            display_name: 'FASTQ input',
            category: 'Input',
            input_types: { required: { reads: { type: 'FASTQ' } } },
            output_node: true,
          },
        }}
        onClose={() => undefined}
        onJumpToNode={() => undefined}
      />,
    );

    expect(screen.getByText('1 error')).toBeInTheDocument();
    expect(screen.getByText('FASTQ input references unknown workflow parameter "sample_typo" in params.reads')).toBeInTheDocument();
    expect(screen.getByText('Declare this workflow parameter or update the placeholder name before running.')).toBeInTheDocument();
    expect(screen.queryByText(/sample" in params.template/)).not.toBeInTheDocument();
  });
});
