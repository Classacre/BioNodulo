import { act, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { RunRecord } from '../types';

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

function runRecord(partial: Partial<RunRecord> & Pick<RunRecord, 'run_id' | 'status'>): RunRecord {
  return {
    run_id: partial.run_id,
    status: partial.status,
    workflow_name: '',
    node_statuses: [],
    node_outputs: {},
    execution_plan: [],
    previews: {},
    artifacts: {},
    ...partial,
  };
}

const leftRun = runRecord({
  run_id: 'left-run-123',
  status: 'completed',
  workflow_name: '',
  node_statuses: [{ node_id: 'align', status: 'completed' }],
  artifacts: { 'reports/multiqc.html': '/runs/left/multiqc.html' },
  start_time: '2026-06-04T10:15:00.000Z',
});

const rightRun = runRecord({
  run_id: 'right-run-456',
  status: 'error',
  workflow_name: 'Variant workflow',
  node_statuses: [{ node_id: 'align', status: 'error' }],
  artifacts: {},
  error: 'Variant caller failed',
  start_time: '2026-06-04T11:15:00.000Z',
});

describe('OutputDiffModal i18n', () => {
  let fetchSpy: ReturnType<typeof vi.spyOn>;
  let releaseFetches: () => void;

  beforeEach(() => {
    storage.clear();
    vi.stubGlobal('localStorage', localStorageStub);
    const fetchGate = new Promise<void>(resolve => {
      releaseFetches = resolve;
    });
    fetchSpy = vi.spyOn(globalThis, 'fetch').mockImplementation(async (input: RequestInfo | URL) => {
      await fetchGate;
      const url = typeof input === 'string' ? input : input.toString();
      const payload = url.includes('right-run-456') ? rightRun : leftRun;
      return new Response(JSON.stringify(payload), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      });
    });
  });

  afterEach(async () => {
    const { setLanguage } = await import('../i18n');
    await setLanguage('en');
    storage.clear();
    vi.unstubAllGlobals();
    fetchSpy.mockRestore();
  });

  it('renders run comparison chrome and generated labels from the active locale', async () => {
    const { default: OutputDiffModal } = await import('../components/modals/OutputDiffModal');
    const { setLanguage } = await import('../i18n');

    await setLanguage('es');

    render(
      <OutputDiffModal
        runs={[leftRun, rightRun]}
        initialLeftRunId="left-run-123"
        initialRightRunId="right-run-456"
        onClose={() => undefined}
      />,
    );

    expect(screen.getByRole('dialog', { name: 'Comparar ejecuciones' })).toBeInTheDocument();
    expect(screen.getByText(/Ejecucion A \(cargando...\)/)).toBeInTheDocument();
    expect(screen.getByText(/Ejecucion B \(cargando...\)/)).toBeInTheDocument();
    expect(screen.getAllByRole('option', { name: /completada - left-run/ })).toHaveLength(2);
    expect(screen.getAllByRole('option', { name: /error - right-ru/ })).toHaveLength(2);
    expect(screen.getAllByRole('button', { name: 'Cerrar' }).length).toBeGreaterThan(0);

    await act(async () => {
      releaseFetches();
    });

    await waitFor(() => expect(screen.getByText('Sin titulo')).toBeInTheDocument());

    expect(screen.getByText('Variant workflow')).toBeInTheDocument();
    expect(screen.getAllByText('completada').length).toBeGreaterThan(0);
    expect(screen.getByText(/1 nodo - 1 artefacto/)).toBeInTheDocument();
    expect(screen.getByText(/1 nodo - 0 artefactos/)).toBeInTheDocument();
    expect(screen.getAllByText(/iniciada/).length).toBeGreaterThan(0);
    expect(screen.getByText(`1 nodo - 1 artefacto - iniciada ${new Date(leftRun.start_time!).toLocaleString('es')}`)).toBeInTheDocument();
    expect(screen.queryByText(`1 nodo - 1 artefacto - iniciada ${new Date(leftRun.start_time!).toLocaleString()}`)).not.toBeInTheDocument();
    expect(screen.getByText('Estado por nodo (1)')).toBeInTheDocument();
    expect(screen.getAllByText((_, node) => node?.textContent === 'aligncompletadaerror').length).toBeGreaterThan(0);
    expect(screen.getByText('Artefactos (1)')).toBeInTheDocument();
    expect(screen.getByText('Errores')).toBeInTheDocument();
    expect(screen.getByText('mensaje')).toBeInTheDocument();
    expect(screen.queryByText('completed')).not.toBeInTheDocument();
  });

  it('renders empty comparison states from the active locale', async () => {
    const { default: OutputDiffModal } = await import('../components/modals/OutputDiffModal');
    const { setLanguage } = await import('../i18n');

    await setLanguage('es');

    render(
      <OutputDiffModal
        runs={[]}
        onClose={() => undefined}
      />,
    );

    expect(screen.getAllByText('Ninguna ejecucion seleccionada')).toHaveLength(2);
    expect(screen.getByText('Estado por nodo (0)')).toBeInTheDocument();
    expect(screen.getByText('No hay nodos en ninguna ejecucion.')).toBeInTheDocument();
    expect(screen.getByText('Artefactos (0)')).toBeInTheDocument();
    expect(screen.getByText('Ninguna ejecucion produjo artefactos todavia.')).toBeInTheDocument();
    expect(screen.getAllByText('- elige una ejecucion -')).toHaveLength(2);
  });
});
