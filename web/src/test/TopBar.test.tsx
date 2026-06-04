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

describe('TopBar i18n', () => {
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

  it('renders run controls and validation labels from the active locale', async () => {
    const { default: TopBar } = await import('../components/layout/TopBar');
    const { setLanguage } = await import('../i18n');

    await setLanguage('es');

    render(
      <TopBar
        validationValid={false}
        validationErrors={['missing input', 'missing output']}
        onRun={() => undefined}
        hpcStatus="on"
        hpcEnabled
        queueCount={3}
        queueMode="change"
        onQueueModeChange={() => undefined}
        onToggleQueue={() => undefined}
      />,
    );

    expect(screen.getByText('2 incidencias')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Cola: 3' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Ejecutar workflow/ })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Opciones de ejecucion' })).toHaveAttribute(
      'title',
      'Opciones de ejecucion - lote 1, Al cambiar',
    );

    fireEvent.click(screen.getByRole('button', { name: 'Opciones de ejecucion' }));

    expect(screen.getByText('Cantidad de lotes')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Disminuir cantidad de lotes' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Aumentar cantidad de lotes' })).toBeInTheDocument();
    expect(screen.getByText(/Modo de cola/)).toBeInTheDocument();
    expect(screen.getByRole('menuitemradio', { name: /Manual/ })).toBeInTheDocument();
    expect(screen.getByRole('menuitemradio', { name: /Al cambiar/ })).toBeInTheDocument();
    expect(screen.getByRole('menuitemradio', { name: /Instantaneo/ })).toBeInTheDocument();
    expect(screen.getByRole('menuitem', { name: /Lote desde hoja/ })).toBeInTheDocument();
  });
});
