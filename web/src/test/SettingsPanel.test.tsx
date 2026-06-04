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

describe('SettingsPanel shell i18n', () => {
  let fetchSpy: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    storage.clear();
    vi.stubGlobal('localStorage', localStorageStub);
    fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response(JSON.stringify({}), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    }));
  });

  afterEach(async () => {
    const { setLanguage } = await import('../i18n');
    await setLanguage('en');
    storage.clear();
    vi.unstubAllGlobals();
    fetchSpy.mockRestore();
  });

  it('renders settings shell, search, and section navigation from the active locale', async () => {
    const { default: SettingsPanel } = await import('../components/panels/SettingsPanel');
    const { setLanguage } = await import('../i18n');

    await setLanguage('es');

    render(<SettingsPanel onClose={() => undefined} />);

    expect(screen.getByRole('dialog', { name: 'Ajustes' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Cerrar' })).toBeInTheDocument();
    expect(screen.getByRole('navigation', { name: 'Secciones de ajustes' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Apariencia' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Lienzo' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Colaboracion' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Ejecucion' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Archivos' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Asistente de IA' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Funciones experimentales' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Telemetria' })).toBeInTheDocument();

    const search = screen.getByRole('searchbox', { name: 'Buscar ajustes' });
    expect(search).toHaveAttribute('placeholder', 'Buscar ajustes... (p. ej. tema, cache, hpc)');

    fireEvent.change(search, { target: { value: 'zzzz-no-match' } });

    expect(screen.getByText('Ningun ajuste coincide con "zzzz-no-match"')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Limpiar' })).toBeInTheDocument();
  });
});
