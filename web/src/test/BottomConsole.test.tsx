import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { Provider, createStore } from 'jotai';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { RunRecord } from '../types';

const apiMocks = vi.hoisted(() => ({
  apiGetText: vi.fn(),
}));

const loggingMock = vi.hoisted(() => ({
  logError: vi.fn(),
}));

vi.mock('../api/client', () => apiMocks);
vi.mock('../state/logging', () => loggingMock);

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

describe('BottomConsole i18n', () => {
  beforeEach(() => {
    storage.clear();
    apiMocks.apiGetText.mockReset();
    loggingMock.logError.mockReset();
    vi.stubGlobal('localStorage', localStorageStub);
  });

  afterEach(async () => {
    const { setLanguage } = await import('../i18n');
    await setLanguage('en');
    vi.useRealTimers();
    storage.clear();
    vi.unstubAllGlobals();
  });

  it('keeps history bucket identifiers locale-neutral', () => {
    const source = readFileSync(resolve(__dirname, '../components/layout/BottomConsole.tsx'), 'utf8');

    expect(source).toContain('HistoryBucketId');
    [
      "return 'Today'",
      "return 'Yesterday'",
      "return 'Past Week'",
      "return 'Earlier'",
      "case 'Today'",
      "case 'Yesterday'",
      "case 'Past Week'",
      "case 'Earlier'",
    ].forEach(text => expect(source).not.toContain(text));
  });

  it('renders console tabs and empty states from the active locale', async () => {
    const { default: BottomConsole } = await import('../components/layout/BottomConsole');
    const { setLanguage } = await import('../i18n');

    await setLanguage('es');

    render(
      <Provider>
        <BottomConsole
          queue={[]}
          history={[]}
          onClose={() => undefined}
        />
      </Provider>,
    );

    expect(screen.getByRole('button', { name: 'Registros' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Cola (0)' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Historial (0)' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Previsualizaciones' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Informe' })).toBeInTheDocument();
    expect(screen.getByTitle('Cerrar consola')).toBeInTheDocument();
    expect(screen.getByText('Todavia no hay registros. Ejecuta un flujo de trabajo para verlos.')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Cola (0)' }));
    expect(screen.getByText('La cola esta vacia.')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Historial (0)' }));
    expect(screen.getByText('Todavia no hay ejecuciones completadas.')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Previsualizaciones' }));
    expect(screen.getByText('Todavia no hay previsualizaciones. Ejecuta un flujo de trabajo que genere graficos o informes HTML.')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Informe' }));
    expect(screen.getByText('Los informes de procedencia estaran disponibles cuando una ejecucion termine o falle.')).toBeInTheDocument();
  });

  it('localizes report fetch failures while logging the raw error', async () => {
    const { default: BottomConsole } = await import('../components/layout/BottomConsole');
    const { setLanguage } = await import('../i18n');
    const reportError = new Error('report unavailable');
    apiMocks.apiGetText.mockRejectedValueOnce(reportError);

    await setLanguage('es');

    const historyRun = runRecord({
      run_id: 'history-run-report',
      status: 'completed',
      workflow_name: 'Report workflow',
      end_time: new Date().toISOString(),
    });

    render(
      <Provider>
        <BottomConsole
          queue={[]}
          history={[historyRun]}
          onClose={() => undefined}
        />
      </Provider>,
    );

    fireEvent.click(screen.getByRole('button', { name: 'Informe' }));

    await waitFor(() => expect(screen.getByText('No se pudo cargar el informe de procedencia')).toBeInTheDocument());
    expect(screen.queryByText('report unavailable')).not.toBeInTheDocument();
    expect(apiMocks.apiGetText).toHaveBeenCalledWith('/api/runs/history-run-report/report');
    expect(loggingMock.logError).toHaveBeenCalledWith('console.report.fetch', reportError);
  });

  it('renders preview image and HTML labels from the active locale', async () => {
    const { default: BottomConsole } = await import('../components/layout/BottomConsole');
    const { setLanguage } = await import('../i18n');

    await setLanguage('es');

    const historyRun = runRecord({
      run_id: 'history-run-1',
      status: 'completed',
      workflow_name: 'Preview workflow',
      previews: { plot_node: '/runs/history-run-1/plot_node/plot.png' },
    });
    const htmlRun = runRecord({
      run_id: 'history-run-2',
      status: 'completed',
      workflow_name: 'HTML workflow',
      previews: { report_node: '/runs/history-run-2/report_node/report.html' },
    });

    render(
      <Provider>
        <BottomConsole
          queue={[]}
          history={[historyRun, htmlRun]}
          onClose={() => undefined}
        />
      </Provider>,
    );

    fireEvent.click(screen.getByRole('button', { name: /Previsualizaciones/ }));

    expect(screen.getByRole('img', { name: 'Previsualizacion plot_node' })).toBeInTheDocument();
    expect(screen.queryByRole('img', { name: 'Preview plot_node' })).not.toBeInTheDocument();
    expect(screen.getByText('Informe HTML')).toBeInTheDocument();
    expect(screen.queryByText('HTML')).not.toBeInTheDocument();
  });

  it('renders missing log run and node labels from the active locale', async () => {
    const { default: BottomConsole } = await import('../components/layout/BottomConsole');
    const { setLanguage } = await import('../i18n');
    const { logsAtom } = await import('../state/runAtoms');
    const store = createStore();

    await setLanguage('es');
    store.set(logsAtom, [{
      level: 'info',
      message: 'Runtime emitted a log without identifiers',
      timestamp: '2026-06-07T05:00:00.000Z',
    }]);

    render(
      <Provider store={store}>
        <BottomConsole
          queue={[]}
          history={[]}
          onClose={() => undefined}
        />
      </Provider>,
    );

    expect(screen.getByText('Desconocido')).toBeInTheDocument();
    expect(screen.queryByText('unknown')).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /Desconocido/ }));

    expect(screen.getByText('[Desconocido]')).toBeInTheDocument();
    expect(screen.queryByText('[unknown]')).not.toBeInTheDocument();
  });

  it('renders queue and history controls from the active locale', async () => {
    const { default: BottomConsole } = await import('../components/layout/BottomConsole');
    const { setLanguage } = await import('../i18n');

    await setLanguage('es');

    const queueRun = runRecord({
      run_id: 'queue-run-1',
      status: 'pending',
      execution_plan: ['node-a', 'node-b'],
      node_statuses: [{ node_id: 'node-a', status: 'running' }],
    });
    const historyRun = runRecord({
      run_id: 'history-run-1',
      status: 'completed',
      workflow_name: 'Completed workflow',
      execution_plan: ['node-a'],
      node_statuses: [{ node_id: 'node-a', status: 'completed' }],
      end_time: new Date().toISOString(),
    });

    render(
      <Provider>
        <BottomConsole
          queue={[queueRun]}
          history={[historyRun]}
          onClose={() => undefined}
          onMoveRun={() => undefined}
          onCancelRun={() => undefined}
          onRetryRun={() => undefined}
          onLoadRunWorkflow={() => undefined}
          onDeleteHistoryEntry={() => undefined}
          onClearQueue={() => undefined}
          onClearHistory={() => undefined}
        />
      </Provider>,
    );

    fireEvent.click(screen.getByRole('button', { name: 'Cola (1)' }));

    expect(screen.getAllByText('pendiente').length).toBeGreaterThan(0);
    expect(screen.getByText('Flujo de trabajo sin titulo')).toBeInTheDocument();
    expect(screen.queryByText('Workflow sin titulo')).not.toBeInTheDocument();
    expect(screen.getByText('0/2 nodos')).toBeInTheDocument();
    expect(screen.getByText('1 ejecutando')).toBeInTheDocument();
    expect(screen.getByText('1 pendiente')).toBeInTheDocument();
    expect(screen.getByTitle('Mover antes')).toBeInTheDocument();
    expect(screen.getByTitle('Mover despues')).toBeInTheDocument();
    expect(screen.getByTitle('Cancelar ejecucion')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Limpiar cola' })).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Historial (1)' }));

    expect(screen.getByRole('searchbox', { name: 'Filtrar historial' })).toHaveAttribute('placeholder', 'Filtrar por nombre o ID de ejecucion');
    expect(screen.getByRole('group', { name: 'Filtrar historial por estado' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Todas/ })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Completadas/ })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Errores/ })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Canceladas/ })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Comparar ejecuciones' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Limpiar historial' })).toBeInTheDocument();
    expect(screen.getByTitle('Cargar este flujo de trabajo en una pestana nueva')).toBeInTheDocument();
    expect(screen.queryByTitle('Cargar este workflow en una pestana nueva')).not.toBeInTheDocument();
    expect(screen.getByTitle('Reintentar ejecucion')).toBeInTheDocument();
    expect(screen.getByTitle('Eliminar esta ejecucion del historial')).toBeInTheDocument();
    expect(screen.getByText('Hoy')).toBeInTheDocument();

    fireEvent.change(screen.getByRole('searchbox', { name: 'Filtrar historial' }), {
      target: { value: 'missing' },
    });

    expect(screen.getByText('Ninguna ejecucion coincide con el filtro actual.')).toBeInTheDocument();

    const filters = screen.getByRole('group', { name: 'Filtrar historial por estado' });
    fireEvent.click(within(filters).getByRole('button', { name: /Canceladas/ }));
    expect(screen.getByText('Ninguna ejecucion coincide con el filtro actual.')).toBeInTheDocument();
  });

  it('uses the active locale for older same-year history month buckets', async () => {
    const { default: BottomConsole } = await import('../components/layout/BottomConsole');
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
        <BottomConsole
          queue={[]}
          history={[historyRun]}
          onClose={() => undefined}
        />
      </Provider>,
    );

    fireEvent.click(screen.getByRole('button', { name: 'Historial (1)' }));

    expect(screen.getByText('mayo')).toBeInTheDocument();
    expect(screen.getByText(new Date(historyRun.end_time!).toLocaleString('es'))).toBeInTheDocument();
    expect(screen.queryByText('May')).not.toBeInTheDocument();
  });
});
