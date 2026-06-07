import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const apiMocks = vi.hoisted(() => ({
  apiGet: vi.fn(),
  apiGetBlob: vi.fn(),
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

describe('AuditLog i18n', () => {
  beforeEach(() => {
    storage.clear();
    vi.stubGlobal('localStorage', localStorageStub);
    apiMocks.apiGet.mockReset();
    apiMocks.apiGetBlob.mockReset();
    loggingMock.logError.mockReset();
  });

  afterEach(async () => {
    const { setLanguage } = await import('../i18n');
    await setLanguage('en');
    storage.clear();
    vi.unstubAllGlobals();
  });

  it('renders audit summaries, filters, and table chrome from the active locale', async () => {
    const { default: AuditLog } = await import('../collab/AuditLog');
    const { setLanguage } = await import('../i18n');
    await setLanguage('es');
    apiMocks.apiGet.mockResolvedValue({
      entries: [
        {
          id: 'entry-1',
          workflow_id: 'workflow-1',
          user_id: 'user-1',
          user_name: 'Mika',
          action: 'node_create',
          target_type: 'workflow',
          target_id: 'workflow-1234567890abcdef',
          metadata: {},
          performed_at: '2026-06-04T15:00:00Z',
        },
      ],
      count: 1,
    });

    render(
      <AuditLog
        workflowId="workflow-1"
        isOpen
        onClose={() => undefined}
      />,
    );

    await waitFor(() => expect(screen.getAllByText('Crear nodo')).toHaveLength(2));

    expect(screen.getByText('Registro de auditoria')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Exportar CSV' })).toBeInTheDocument();
    expect(screen.getByTitle('Cerrar')).toBeInTheDocument();
    expect(screen.getByText('1 accion')).toBeInTheDocument();
    expect(screen.getByText('1 usuario')).toBeInTheDocument();
    expect(screen.getByText('Principal: Crear nodo (1)')).toBeInTheDocument();
    expect(screen.getByRole('option', { name: 'Todos los usuarios' })).toBeInTheDocument();
    expect(screen.getByRole('option', { name: 'Todas las acciones' })).toBeInTheDocument();
    expect(screen.getByRole('option', { name: 'Crear nodo' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Aplicar filtros' })).toBeInTheDocument();
    expect(screen.getByText('Hora')).toBeInTheDocument();
    expect(screen.getByText('Usuario')).toBeInTheDocument();
    expect(screen.getByText('Accion')).toBeInTheDocument();
    expect(screen.getByText('Destino')).toBeInTheDocument();
    expect(screen.getByText('Flujo de trabajo:workflow-123')).toBeInTheDocument();
    expect(screen.queryByText('Workflow:workflow-123')).not.toBeInTheDocument();
  });

  it('logs swallowed audit API failures with stable scopes', async () => {
    const { default: AuditLog } = await import('../collab/AuditLog');
    const { setLanguage } = await import('../i18n');
    await setLanguage('es');
    const loadError = new Error('audit load failed');
    const exportError = new Error('audit export failed');

    apiMocks.apiGet.mockRejectedValueOnce(loadError);
    const loadView = render(
      <AuditLog
        workflowId="workflow-1"
        isOpen
        onClose={() => undefined}
      />,
    );

    await waitFor(() => expect(loggingMock.logError).toHaveBeenCalledWith('collab.audit.load', loadError));
    expect(screen.getByText('No se pudo cargar el registro de auditoria')).toBeInTheDocument();
    expect(screen.queryByText('audit load failed')).not.toBeInTheDocument();
    loadView.unmount();

    apiMocks.apiGet.mockResolvedValueOnce({ entries: [], count: 0 });
    apiMocks.apiGetBlob.mockRejectedValueOnce(exportError);

    render(
      <AuditLog
        workflowId="workflow-1"
        isOpen
        onClose={() => undefined}
      />,
    );

    await waitFor(() => expect(screen.getByText('No se encontraron entradas de auditoria.')).toBeInTheDocument());
    fireEvent.click(screen.getByRole('button', { name: 'Exportar CSV' }));

    await waitFor(() => expect(loggingMock.logError).toHaveBeenCalledWith('collab.audit.export', exportError));
    expect(screen.getByText('No se pudo exportar')).toBeInTheDocument();
    expect(screen.queryByText('audit export failed')).not.toBeInTheDocument();
  });
});
