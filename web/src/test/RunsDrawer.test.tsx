import { fireEvent, render, screen, within } from '@testing-library/react';
import { Provider } from 'jotai';
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
    workflow_name: '',
    node_statuses: [],
    node_outputs: {},
    execution_plan: [],
    previews: {},
    artifacts: {},
    ...partial,
  };
}

describe('RunsDrawer', () => {
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

  it('renders queued and historical runs in one right-side drawer', async () => {
    const { default: RunsDrawer } = await import('../components/layout/RunsDrawer');
    const { setLanguage } = await import('../i18n');
    const onClose = vi.fn();
    const onCancelRun = vi.fn();
    const onLoadRunWorkflow = vi.fn();

    await setLanguage('es');

    render(
      <Provider>
        <RunsDrawer
          open
          queue={[
            runRecord({
              run_id: 'pending-run-1',
              status: 'pending',
              workflow_name: 'Queued workflow',
              execution_plan: ['input', 'qc'],
            }),
          ]}
          history={[
            runRecord({
              run_id: 'completed-run-1',
              status: 'completed',
              workflow_name: 'Completed workflow',
              execution_plan: ['input', 'qc'],
              node_statuses: [
                { node_id: 'input', status: 'completed' },
                { node_id: 'qc', status: 'completed' },
              ],
              end_time: '2026-06-12T12:00:00.000Z',
            }),
          ]}
          onCancelRun={onCancelRun}
          onClose={onClose}
          onLoadRunWorkflow={onLoadRunWorkflow}
        />
      </Provider>,
    );

    const drawer = screen.getByRole('complementary', { name: 'Ejecuciones' });
    expect(drawer).toHaveClass('runs-drawer');
    expect(within(drawer).getByText('Queued workflow')).toBeInTheDocument();
    expect(within(drawer).getByText('Completed workflow')).toBeInTheDocument();
    expect(within(drawer).getByText((_, element) => element?.textContent === '1 Pendiente')).toBeInTheDocument();
    expect(within(drawer).getByText((_, element) => element?.textContent === '1 Completada')).toBeInTheDocument();

    fireEvent.click(within(drawer).getByTitle('Cancelar ejecucion'));
    expect(onCancelRun).toHaveBeenCalledWith(expect.objectContaining({ run_id: 'pending-run-1' }));

    fireEvent.change(within(drawer).getByRole('searchbox', { name: 'Filtrar ejecuciones' }), {
      target: { value: 'Completed' },
    });
    expect(within(drawer).queryByText('Queued workflow')).not.toBeInTheDocument();
    expect(within(drawer).getByText('Completed workflow')).toBeInTheDocument();

    fireEvent.click(within(drawer).getByTitle('Cerrar ejecuciones'));
    expect(onClose).toHaveBeenCalled();
  });

  it('renders moved queue and history controls from the active locale', async () => {
    const { default: RunsDrawer } = await import('../components/layout/RunsDrawer');
    const { setLanguage } = await import('../i18n');

    await setLanguage('es');

    render(
      <Provider>
        <RunsDrawer
          open
          queue={[
            runRecord({
              run_id: 'queue-run-1',
              status: 'pending',
              execution_plan: ['node-a', 'node-b'],
              node_statuses: [{ node_id: 'node-a', status: 'running' }],
            }),
          ]}
          history={[
            runRecord({
              run_id: 'history-run-1',
              status: 'completed',
              workflow_name: 'Completed workflow',
              execution_plan: ['node-a'],
              node_statuses: [{ node_id: 'node-a', status: 'completed' }],
              end_time: new Date().toISOString(),
            }),
          ]}
          onCancelRun={() => undefined}
          onClearHistory={() => undefined}
          onClearQueue={() => undefined}
          onClose={() => undefined}
          onDeleteHistoryEntry={() => undefined}
          onLoadRunWorkflow={() => undefined}
          onMoveRun={() => undefined}
          onRetryRun={() => undefined}
        />
      </Provider>,
    );

    const drawer = screen.getByRole('complementary', { name: 'Ejecuciones' });
    expect(within(drawer).getByText('Flujo de trabajo sin titulo')).toBeInTheDocument();
    expect(within(drawer).queryByText('Workflow sin titulo')).not.toBeInTheDocument();
    expect(within(drawer).getByText('0/2 nodos')).toBeInTheDocument();
    expect(within(drawer).getByText('1 ejecutando')).toBeInTheDocument();
    expect(within(drawer).getByText('1 pendiente')).toBeInTheDocument();
    expect(within(drawer).getByTitle('Mover antes')).toBeInTheDocument();
    expect(within(drawer).getByTitle('Mover despues')).toBeInTheDocument();
    expect(within(drawer).getByTitle('Cancelar ejecucion')).toBeInTheDocument();
    expect(within(drawer).getByRole('button', { name: 'Limpiar cola' })).toBeInTheDocument();
    expect(within(drawer).getByRole('searchbox', { name: 'Filtrar ejecuciones' })).toHaveAttribute('placeholder', 'Filtrar por nombre o ID de ejecucion');
    expect(within(drawer).getByRole('group', { name: 'Filtrar ejecuciones por estado' })).toBeInTheDocument();
    expect(within(drawer).getByRole('button', { name: /Todas/ })).toBeInTheDocument();
    expect(within(drawer).getByRole('button', { name: /Activas/ })).toBeInTheDocument();
    expect(within(drawer).getByRole('button', { name: /Completadas/ })).toBeInTheDocument();
    expect(within(drawer).getByRole('button', { name: /Errores/ })).toBeInTheDocument();
    expect(within(drawer).getByRole('button', { name: /Canceladas/ })).toBeInTheDocument();
    expect(within(drawer).getByRole('button', { name: 'Comparar ejecuciones' })).toBeInTheDocument();
    expect(within(drawer).getByRole('button', { name: 'Limpiar historial' })).toBeInTheDocument();
    expect(within(drawer).getByTitle('Cargar este flujo de trabajo en una pestana nueva')).toBeInTheDocument();
    expect(within(drawer).queryByTitle('Cargar este workflow en una pestana nueva')).not.toBeInTheDocument();
    expect(within(drawer).getByTitle('Reintentar ejecucion')).toBeInTheDocument();
    expect(within(drawer).getByTitle('Eliminar esta ejecucion del historial')).toBeInTheDocument();
    expect(within(drawer).getByText('Hoy')).toBeInTheDocument();

    fireEvent.change(within(drawer).getByRole('searchbox', { name: 'Filtrar ejecuciones' }), {
      target: { value: 'missing' },
    });

    expect(within(drawer).getByText('Ninguna ejecucion coincide con el filtro actual.')).toBeInTheDocument();

    const filters = within(drawer).getByRole('group', { name: 'Filtrar ejecuciones por estado' });
    fireEvent.click(within(filters).getByRole('button', { name: /Canceladas/ }));
    expect(within(drawer).getByText('Ninguna ejecucion coincide con el filtro actual.')).toBeInTheDocument();
  });

  it('uses the active locale for older same-year history month buckets', async () => {
    const { default: RunsDrawer } = await import('../components/layout/RunsDrawer');
    const { setLanguage } = await import('../i18n');

    vi.useFakeTimers();
    vi.setSystemTime(new Date('2026-06-07T12:00:00.000Z'));
    await setLanguage('es');

    const historyRun = runRecord({
      run_id: 'history-run-may',
      status: 'completed',
      workflow_name: 'May workflow',
      end_time: '2026-05-03T09:30:00.000Z',
    });

    render(
      <Provider>
        <RunsDrawer
          open
          queue={[]}
          history={[historyRun]}
          onClose={() => undefined}
        />
      </Provider>,
    );

    expect(screen.getByText('mayo')).toBeInTheDocument();
    expect(screen.getByText(new Date(historyRun.end_time!).toLocaleString('es'))).toBeInTheDocument();
    expect(screen.queryByText('May')).not.toBeInTheDocument();
  });
});
