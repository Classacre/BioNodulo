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

describe('NodeContextMenu i18n', () => {
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

  it('renders node actions from the active locale and dispatches selected actions', async () => {
    const { default: NodeContextMenu } = await import('../components/nodes/NodeContextMenu');
    const { setLanguage } = await import('../i18n');
    const onAction = vi.fn();

    await setLanguage('es');

    render(<NodeContextMenu x={10} y={20} nodeId="node-1" onAction={onAction} onClose={() => undefined} />);

    expect(screen.getByText('Editar propiedades')).toBeInTheDocument();
    expect(screen.getByText('Informacion del nodo')).toBeInTheDocument();
    expect(screen.getByText('Agregar comentario')).toBeInTheDocument();
    expect(screen.getByText('Silenciar nodo')).toBeInTheDocument();
    expect(screen.getByText('Omitir nodo')).toBeInTheDocument();
    expect(screen.getByText('Fijar / bloquear nodo')).toBeInTheDocument();
    expect(screen.getByText('Contraer/expandir')).toBeInTheDocument();
    expect(screen.getByText('Definir como salida')).toBeInTheDocument();
    expect(screen.getByText('Forma redonda')).toBeInTheDocument();
    expect(screen.getByText('Guardar parametros como preset...')).toBeInTheDocument();
    expect(screen.getByText('Aplicar preset...')).toBeInTheDocument();
    expect(screen.getByText('Ejecutar seleccionados')).toBeInTheDocument();

    fireEvent.click(screen.getByText('Forma redonda'));

    expect(onAction).toHaveBeenCalledWith('shape', 'node-1', 'round');
  });

  it('renders canvas actions from the active locale', async () => {
    const { default: NodeContextMenu } = await import('../components/nodes/NodeContextMenu');
    const { setLanguage } = await import('../i18n');

    await setLanguage('es');

    render(<NodeContextMenu x={10} y={20} nodeId={null} onAction={() => undefined} onClose={() => undefined} />);

    expect(screen.getByText('Agregar nodo')).toBeInTheDocument();
    expect(screen.getByText('Agregar grupo')).toBeInTheDocument();
    expect(screen.getByText('Seleccionar todo')).toBeInTheDocument();
    expect(screen.getByText('Pegar')).toBeInTheDocument();
  });

  it('renders the color submenu back action from the active locale', async () => {
    const { default: NodeContextMenu } = await import('../components/nodes/NodeContextMenu');
    const { setLanguage } = await import('../i18n');

    await setLanguage('es');

    render(<NodeContextMenu x={10} y={20} nodeId="node-1" onAction={() => undefined} onClose={() => undefined} />);

    fireEvent.click(screen.getByText('Definir color'));

    expect(screen.getByText('← Volver')).toBeInTheDocument();
  });
});
