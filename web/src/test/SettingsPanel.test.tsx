import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

const loggingMock = vi.hoisted(() => ({
  logError: vi.fn(),
}));

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

describe('SettingsPanel shell i18n', () => {
  let fetchSpy: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    storage.clear();
    loggingMock.logError.mockReset();
    vi.stubGlobal('localStorage', localStorageStub);
    fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response(JSON.stringify({}), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    }));
  });

  afterEach(async () => {
    const { setLanguage } = await import('../i18n');
    const { dismissAllNotifications } = await import('../state/notifications');
    await setLanguage('en');
    dismissAllNotifications();
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
    expect(search).toHaveAttribute('placeholder', 'Buscar ajustes... (p. ej. tema, almacenamiento, hpc)');

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
    expect(screen.getByText('Ayudas emergentes')).toBeInTheDocument();
    expect(screen.getByText('Mostrar ayudas emergentes al pasar el cursor')).toBeInTheDocument();
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
    expect(screen.getByText('Guardar flujos de trabajo automaticamente')).toBeInTheDocument();
    expect(screen.queryByText('Guardar workflows automaticamente')).not.toBeInTheDocument();
    expect(screen.getByRole('option', { name: 'Desactivado' })).toBeInTheDocument();
    expect(screen.getByRole('option', { name: 'Cada 30 s' })).toBeInTheDocument();
    expect(screen.getByRole('option', { name: 'Cada minuto' })).toBeInTheDocument();
    expect(screen.getByText('Calidad de renderizado')).toBeInTheDocument();
    expect(screen.getByRole('option', { name: 'Auto (recomendado)' })).toBeInTheDocument();
    expect(screen.getByRole('option', { name: 'Alta (siempre)' })).toBeInTheDocument();
    expect(screen.getByRole('option', { name: 'Baja (rapida)' })).toBeInTheDocument();
    expect(screen.getByText('Color por estado')).toBeInTheDocument();
    expect(screen.getByText('Tintar encabezados de nodos segun el ultimo estado de ejecucion (completado/error/almacenado)')).toBeInTheDocument();
    expect(screen.getByText('Color de enlaces')).toBeInTheDocument();
    expect(screen.getByRole('option', { name: 'Por tipo de dato' })).toBeInTheDocument();
    expect(screen.getByRole('option', { name: 'Gradiente (resalta incompatibilidad)' })).toBeInTheDocument();
    expect(screen.getByRole('option', { name: 'Uniforme' })).toBeInTheDocument();
  });

  it('renders Collaboration, Cache, Execution, and Files rows from the active locale', async () => {
    const { default: SettingsPanel } = await import('../components/panels/SettingsPanel');
    const { setLanguage } = await import('../i18n');

    await setLanguage('es');

    render(
      <SettingsPanel
        collabEnabled
        collabShareLink="http://localhost:5173/?room=demo"
        onClose={() => undefined}
      />,
    );

    fireEvent.click(screen.getByRole('button', { name: 'Colaboracion' }));

    expect(screen.getByText('Modo')).toBeInTheDocument();
    expect(screen.getByText('BioNodulo inicia sin conexion. Crea o unite a una sala temporal cuando quieras edicion compartida.')).toBeInTheDocument();
    expect(screen.getByText('Activado')).toBeInTheDocument();
    expect(screen.getByText('Crear enlace')).toBeInTheDocument();
    expect(screen.getByText('Iniciar una sala temporal y copiar un enlace para otros usuarios.')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Crear' })).toBeInTheDocument();
    expect(screen.getByText('Unirse con enlace')).toBeInTheDocument();
    expect(screen.getByText('Pega un enlace de colaboracion de BioNodulo o ID de sala.')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Unirse' })).toBeInTheDocument();
    expect(screen.getByText('Enlace actual')).toBeInTheDocument();
    expect(screen.getByText('Enlace temporal para este servidor BioNodulo en ejecucion.')).toBeInTheDocument();
    expect(screen.getByText('Detener colaboracion')).toBeInTheDocument();
    expect(screen.getByText('Devolver este navegador al modo sin conexion.')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Detener' })).toBeInTheDocument();
    expect(screen.getByText('Cursores de presencia')).toBeInTheDocument();
    expect(screen.getByText('Mostrar colaboradores en el lienzo')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Almacenamiento' }));

    expect(screen.getByText('Activar almacenamiento temporal')).toBeInTheDocument();
    expect(screen.getByText('Guardar resultados de nodos de flujo de trabajo entre ejecuciones')).toBeInTheDocument();
    expect(screen.getByText('Limpiar almacenamiento temporal')).toBeInTheDocument();
    expect(screen.getByText('Eliminar todos los resultados de ejecucion guardados temporalmente')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Limpiar' })).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Ejecucion' }));

    expect(screen.getByText('Tamano de historial de cola')).toBeInTheDocument();
    expect(screen.getByText('Entradas maximas del historial')).toBeInTheDocument();
    expect(screen.getByText('Hashing fuerte')).toBeInTheDocument();
    expect(screen.getByText('Usar claves de cache mas fuertes')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Archivos' }));

    expect(screen.getByText('Profundidad del explorador')).toBeInTheDocument();
    expect(screen.getByText('Limite de anidacion del arbol de archivos')).toBeInTheDocument();
    expect(screen.getByText('Mostrar archivos ocultos')).toBeInTheDocument();
    expect(screen.getByText('Mostrar dotfiles')).toBeInTheDocument();
    expect(screen.getByText('Confirmar eliminacion')).toBeInTheDocument();
    expect(screen.getByText('Pedir confirmacion antes de eliminar archivos')).toBeInTheDocument();
  });

  it('renders AI and Telemetry rows from the active locale', async () => {
    const { default: SettingsPanel } = await import('../components/panels/SettingsPanel');
    const { setLanguage } = await import('../i18n');

    await setLanguage('es');

    render(<SettingsPanel onClose={() => undefined} />);

    fireEvent.click(screen.getByRole('button', { name: 'Asistente de IA' }));

    expect(screen.getByText('Proveedor')).toBeInTheDocument();
    expect(screen.getByText('Proveedor de API LLM')).toBeInTheDocument();
    expect(screen.getByRole('option', { name: 'Proxy LiteLLM' })).toBeInTheDocument();
    expect(screen.getByRole('option', { name: 'Personalizado compatible con OpenAI' })).toBeInTheDocument();
    expect(screen.getByText('Modelo')).toBeInTheDocument();
    expect(screen.getByText('Nombre de modelo o cadena de modelo LiteLLM')).toBeInTheDocument();
    expect(screen.getByText('URL base')).toBeInTheDocument();
    expect(screen.getByText('URL base de API para proxy o endpoint personalizado')).toBeInTheDocument();
    expect(screen.getByText('Clave API')).toBeInTheDocument();
    expect(screen.getByText('Tu clave API')).toBeInTheDocument();
    expect(screen.getByText('Temperatura')).toBeInTheDocument();
    expect(screen.getByText('Temperatura de muestreo')).toBeInTheDocument();
    expect(screen.getByText('Tokens maximos')).toBeInTheDocument();
    expect(screen.getByText('Tokens maximos de respuesta')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('http://localhost:4000/v1')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('sk-...')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Telemetria' }));

    expect(screen.getByText('Registrar eventos de diagnostico')).toBeInTheDocument();
    expect(screen.getByText('Captura un registro circular local de eventos de interfaz para depuracion. Nunca sale de tu maquina.')).toBeInTheDocument();
    expect(screen.getByText('Registro')).toBeInTheDocument();
    expect(screen.getByText('0 eventos almacenados (limite 200)')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Exportar' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Limpiar' })).toBeInTheDocument();
  });

  it('keeps AI placeholder examples behind settings i18n keys', () => {
    const source = readFileSync(resolve(__dirname, '../components/panels/SettingsPanel.tsx'), 'utf8');

    expect(source).toContain('ai.baseUrlPlaceholder');
    expect(source).toContain('ai.apiKeyPlaceholder');
    expect(source).not.toContain('placeholder="http://localhost:4000/v1"');
    expect(source).not.toContain('placeholder="sk-..."');
  });

  it('shows palette toasts from the active locale', async () => {
    const { default: SettingsPanel } = await import('../components/panels/SettingsPanel');
    const { setLanguage } = await import('../i18n');
    const { getNotificationsSnapshot } = await import('../state/notifications');

    await setLanguage('es');

    const createObjectURL = vi.spyOn(URL, 'createObjectURL').mockReturnValue('blob:palette');
    const revokeObjectURL = vi.spyOn(URL, 'revokeObjectURL').mockImplementation(() => undefined);
    const linkClick = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => undefined);

    try {
      render(<SettingsPanel onClose={() => undefined} />);

      fireEvent.click(screen.getByRole('button', { name: 'Exportar paleta' }));

      expect(getNotificationsSnapshot().at(0)?.title).toBe('Paleta exportada');

      const fileInput = document.querySelector<HTMLInputElement>('input[type="file"]');
      expect(fileInput).not.toBeNull();
      const invalidPalette = new File(['{}'], 'invalid.palette.json', { type: 'application/json' });
      fireEvent.change(fileInput!, { target: { files: [invalidPalette] } });

      await waitFor(() => expect(getNotificationsSnapshot().at(0)?.title).toBe('No se pudo importar la paleta'));
      expect(loggingMock.logError).toHaveBeenCalledWith('settings.palette.import', expect.any(Error));
    } finally {
      createObjectURL.mockRestore();
      revokeObjectURL.mockRestore();
      linkClick.mockRestore();
    }
  });

  it('logs cache clear failures while preserving the error toast', async () => {
    const { default: SettingsPanel } = await import('../components/panels/SettingsPanel');
    const { getNotificationsSnapshot } = await import('../state/notifications');
    const clearError = new Error('cache endpoint unavailable');
    fetchSpy.mockRejectedValueOnce(clearError);

    render(<SettingsPanel onClose={() => undefined} />);

    fireEvent.click(screen.getByRole('button', { name: 'Cache' }));
    fireEvent.click(screen.getByRole('button', { name: 'Clear' }));

    await waitFor(() => expect(getNotificationsSnapshot().at(0)?.title).toBe('Failed to clear cache'));
    expect(getNotificationsSnapshot().at(0)?.message).toBe('Server unreachable');
    expect(loggingMock.logError).toHaveBeenCalledWith('settings.cache.clear', clearError);
  });

  it('uses the active locale for built-in palette preview names and descriptions', async () => {
    const { default: SettingsPanel } = await import('../components/panels/SettingsPanel');
    const { setLanguage } = await import('../i18n');

    await setLanguage('es');

    render(<SettingsPanel onClose={() => undefined} />);

    expect(screen.getByRole('option', { name: 'Estacion de campo' })).toBeInTheDocument();
    expect(screen.queryByRole('option', { name: 'Field Station' })).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Alto contraste' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'High Contrast' })).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Clinica' })).toHaveAttribute(
      'title',
      'Tema clinico de alto contraste para estacion de trabajo.',
    );
    expect(screen.getByRole('button', { name: 'Clinica' })).not.toHaveAttribute(
      'title',
      'High-contrast clinical workstation theme.',
    );
  });

  it('renders feature flags from optional locale keys', async () => {
    const { default: SettingsPanel } = await import('../components/panels/SettingsPanel');
    const { setLanguage } = await import('../i18n');
    const { registerFlag } = await import('../state/featureFlags');

    registerFlag({
      key: 'settingsPanelI18nTestFlag',
      defaultValue: false,
      label: 'Fallback feature label',
      description: 'Fallback feature description',
      labelKey: 'settings.ai.provider',
      descriptionKey: 'settings.ai.providerDescription',
    });

    await setLanguage('es');

    render(<SettingsPanel onClose={() => undefined} />);

    fireEvent.click(screen.getByRole('button', { name: 'Funciones experimentales' }));

    expect(screen.getByText('Proveedor')).toBeInTheDocument();
    expect(screen.getByText('Proveedor de API LLM')).toBeInTheDocument();

    fireEvent.change(screen.getByRole('searchbox', { name: 'Buscar ajustes' }), { target: { value: 'Fallback feature label' } });

    expect(screen.getByText('Proveedor')).toBeInTheDocument();
    expect(screen.getByText('Proveedor de API LLM')).toBeInTheDocument();
  });

  it('keeps residual settings labels in the Spanish locale dictionary', async () => {
    const { default: es } = await import('../i18n/locales/es');

    expect(es.settings.gridSize).toBe('Tamano de cuadricula');
    expect(es.settings.edgeStyle).toBe('Estilo de enlace');
    expect(es.settings.edgeStyles).toEqual({
      bezier: 'Bezier',
      step: 'Escalonado',
      orthogonal: 'Ortogonal',
      straight: 'Recto',
    });
    expect(es.settings.workspaceRoot).toBe('Raiz del espacio de trabajo');
    expect(es.settings.cacheLocation).toBe('Ubicacion de cache');
    expect(es.settings.clearCacheBody).toBe('{{count}} entrada de cache borrada');
    expect(es.settings.clearCacheBody_plural).toBe('{{count}} entradas de cache borradas');
    expect(es.settings.telemetry).toBe('Telemetria anonima');
    expect(es.settings.crashReports).toBe('Informes de fallos');
    expect(es.settings.debugLogging).toBe('Registro de depuracion');
    expect(es.settings.experimentalLabel).toBe('Funciones experimentales');
    expect(es.settings.experimentalHint).toBe('Desactivadas por defecto; pueden ser inestables');
  });
});
