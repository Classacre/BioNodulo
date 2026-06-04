import { fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { WorkflowNode } from '../types';

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

function node(partial: Partial<WorkflowNode> & Pick<WorkflowNode, 'id' | 'params'>): WorkflowNode {
  return {
    id: partial.id,
    type: partial.type ?? 'tool',
    position: partial.position ?? [0, 0],
    params: partial.params,
    node_info: partial.node_info,
    parentId: partial.parentId,
    ui: partial.ui,
  };
}

describe('BulkParamModal i18n', () => {
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

  it('renders shared-parameter chrome from the active locale', async () => {
    const { default: BulkParamModal } = await import('../components/modals/BulkParamModal');
    const { setLanguage } = await import('../i18n');

    await setLanguage('es');

    render(
      <BulkParamModal
        nodes={[
          node({ id: 'align-1', params: { threads: 4, preset: 'fast' } }),
          node({ id: 'align-2', params: { threads: 8, preset: 'fast' } }),
        ]}
        onApply={() => undefined}
        onClose={() => undefined}
      />,
    );

    expect(screen.getByRole('dialog', { name: 'Edicion masiva de parametros' })).toBeInTheDocument();
    expect(screen.getByText(/Editando parametros compartidos por/)).toBeInTheDocument();
    expect(screen.getByText('2')).toBeInTheDocument();
    expect(screen.getByText(/nodos seleccionados\./)).toBeInTheDocument();
    expect(screen.getByPlaceholderText('[varios]')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Aplicar a 2 nodos' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Cancelar' })).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText('threads'), { target: { value: '16' } });

    expect(screen.getByRole('button', { name: 'Aplicar a 2 nodos' })).toBeEnabled();
    expect(screen.getByTitle('No cambiar este parametro')).toBeInTheDocument();
  });

  it('renders no-shared-parameter empty state from the active locale', async () => {
    const { default: BulkParamModal } = await import('../components/modals/BulkParamModal');
    const { setLanguage } = await import('../i18n');

    await setLanguage('es');

    render(
      <BulkParamModal
        nodes={[
          node({ id: 'fastqc', params: { reads: 'sample.fastq.gz' } }),
          node({ id: 'multiqc', params: { report: 'multiqc.html' } }),
        ]}
        onApply={() => undefined}
        onClose={() => undefined}
      />,
    );

    expect(screen.getByText('Ningun parametro es comun a todos los nodos seleccionados.')).toBeInTheDocument();
    expect(screen.getByText('Los nodos seleccionados no comparten claves de parametros. Elige nodos del mismo tipo o un subconjunto compatible para editarlos en bloque.')).toBeInTheDocument();
  });
});
