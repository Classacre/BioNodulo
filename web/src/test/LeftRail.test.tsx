import { fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { Provider } from 'jotai';

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

describe('LeftRail i18n', () => {
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

  it('renders built-in rail labels from the active locale', async () => {
    const { default: LeftRail } = await import('../components/layout/LeftRail');
    const { setLanguage } = await import('../i18n');
    const onChange = vi.fn();

    await setLanguage('es');

    render(
      <Provider>
        <LeftRail active={null} onChange={onChange} />
      </Provider>,
    );

    expect(screen.getByRole('button', { name: 'Espacio de trabajo (Ctrl+1)' })).toHaveAttribute(
      'title',
      'Espacio de trabajo (Ctrl+1)',
    );
    expect(screen.getByRole('button', { name: 'Nodos (Ctrl+2)' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Inspector' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Plantillas (Ctrl+3)' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Entorno (Ctrl+4)' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'HPC (Ctrl+5)' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Ayuda y wiki (Ctrl+6)' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Consola (Ctrl+7)' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Ajustes (Ctrl+,)' })).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Plantillas (Ctrl+3)' }));

    expect(onChange).toHaveBeenCalledWith('templates');

    fireEvent.click(screen.getByRole('button', { name: 'Inspector' }));

    expect(onChange).toHaveBeenCalledWith('inspector');
  });
});
