import { fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

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

describe('InspectorPanel i18n', () => {
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

  it('renders panel chrome and empty state from the active locale', async () => {
    const { default: InspectorPanel } = await import('../components/panels/InspectorPanel');
    const { setLanguage } = await import('../i18n');
    const onClose = vi.fn();

    await setLanguage('es');

    render(
      <InspectorPanel
        selectedNode={null}
        objectInfo={{}}
        workflowParameters={[]}
        onParamChange={() => undefined}
        onClose={onClose}
      />,
    );

    expect(screen.getByText('Inspector')).toBeInTheDocument();
    expect(screen.getByTitle('Cerrar inspector')).toBeInTheDocument();
    expect(screen.getByText('Ningun nodo seleccionado')).toBeInTheDocument();
    expect(screen.getByText('Haz clic en cualquier nodo del lienzo para editar sus parametros aqui. Doble clic tambien abre un editor flotante.')).toBeInTheDocument();

    fireEvent.click(screen.getByTitle('Cerrar inspector'));

    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('shows declared workflow parameters when no node is selected', async () => {
    const { default: InspectorPanel } = await import('../components/panels/InspectorPanel');

    render(
      <InspectorPanel
        selectedNode={null}
        objectInfo={{}}
        workflowParameters={[
          {
            name: 'sample_id',
            type: 'STRING',
            required: true,
            default: 'S1',
            description: 'Sample identifier used in {{sample_id}} bindings.',
          },
          {
            name: 'threads',
            type: 'INTEGER',
            required: false,
            default: 8,
          },
        ]}
        onParamChange={() => undefined}
        onClose={() => undefined}
      />,
    );

    expect(screen.getByText('Workflow parameters')).toBeInTheDocument();
    expect(screen.getByText('sample_id')).toBeInTheDocument();
    expect(screen.getByText('STRING')).toBeInTheDocument();
    expect(screen.getByText('Required')).toBeInTheDocument();
    expect(screen.getByText('Default: S1')).toBeInTheDocument();
    expect(screen.getByText('Sample identifier used in {{sample_id}} bindings.')).toBeInTheDocument();
    expect(screen.getByText('threads')).toBeInTheDocument();
    expect(screen.getByText('INTEGER')).toBeInTheDocument();
    expect(screen.getByText('Optional')).toBeInTheDocument();
    expect(screen.getByText('Default: 8')).toBeInTheDocument();
  });
});
