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

  it('renders Appearance and Canvas setting rows from the active locale', async () => {
    const { default: SettingsPanel } = await import('../components/panels/SettingsPanel');
    const { setLanguage } = await import('../i18n');

    await setLanguage('es');

    render(<SettingsPanel onClose={() => undefined} />);

    expect(screen.getByText('Tema')).toBeInTheDocument();
    expect(screen.getByText('Seleccionar tema de la app')).toBeInTheDocument();
    expect(screen.getByRole('option', { name: 'Sistema' })).toBeInTheDocument();
    expect(screen.getByRole('option', { name: 'Claro' })).toBeInTheDocument();
    expect(screen.getByRole('option', { name: 'Oscuro' })).toBeInTheDocument();
    expect(screen.getByText('Tooltips')).toBeInTheDocument();
    expect(screen.getByText('Mostrar tooltips al pasar el cursor')).toBeInTheDocument();
    expect(screen.getByText('Paleta')).toBeInTheDocument();
    expect(screen.getByText('Cambiar paleta de colores')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Restablecer' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Exportar paleta' })).toBeInTheDocument();
    expect(screen.getByText('Importar paleta')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Lienzo' }));

    expect(screen.getByText('Ajustar a la cuadricula')).toBeInTheDocument();
    expect(screen.getByText('Alinear nodos a la cuadricula')).toBeInTheDocument();
    expect(screen.getByText('Bloquear vista')).toBeInTheDocument();
    expect(screen.getByText('Impedir desplazamiento/zoom del lienzo')).toBeInTheDocument();
    expect(screen.getByText('Conservar vista')).toBeInTheDocument();
    expect(screen.getByText('Recordar posicion del lienzo')).toBeInTheDocument();
    expect(screen.getByText('Guardado automatico')).toBeInTheDocument();
    expect(screen.getByRole('option', { name: 'Desactivado' })).toBeInTheDocument();
    expect(screen.getByRole('option', { name: 'Cada 30 s' })).toBeInTheDocument();
    expect(screen.getByRole('option', { name: 'Cada minuto' })).toBeInTheDocument();
    expect(screen.getByText('Calidad de renderizado')).toBeInTheDocument();
    expect(screen.getByRole('option', { name: 'Auto (recomendado)' })).toBeInTheDocument();
    expect(screen.getByRole('option', { name: 'Alta (siempre)' })).toBeInTheDocument();
    expect(screen.getByRole('option', { name: 'Baja (rapida)' })).toBeInTheDocument();
    expect(screen.getByText('Color de enlaces')).toBeInTheDocument();
    expect(screen.getByRole('option', { name: 'Por tipo de dato' })).toBeInTheDocument();
    expect(screen.getByRole('option', { name: 'Gradiente (resalta incompatibilidad)' })).toBeInTheDocument();
    expect(screen.getByRole('option', { name: 'Uniforme' })).toBeInTheDocument();
  });
});
