import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { HPCConfig } from '../types';

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

const enabledConfig: HPCConfig = {
  enabled: true,
  backend: 'slurm',
  partition: 'normal',
  account: 'project-a',
  walltime: '02:00:00',
  cpus_per_task: 8,
  mem_per_cpu: '8G',
  modules: ['bioinfo/BWA/0.7.17'],
  container: '',
  extra_args: '',
};

describe('HPCPanel i18n', () => {
  let fetchSpy: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    storage.clear();
    vi.stubGlobal('localStorage', localStorageStub);
    fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response('{}', { status: 503, statusText: 'Unavailable' }));
  });

  afterEach(async () => {
    const { setLanguage } = await import('../i18n');
    await setLanguage('en');
    storage.clear();
    vi.unstubAllGlobals();
    fetchSpy.mockRestore();
  });

  it('renders configuration labels and connection feedback from the active locale', async () => {
    const { default: HPCPanel } = await import('../components/panels/HPCPanel');
    const { setLanguage } = await import('../i18n');

    await setLanguage('es');

    render(
      <HPCPanel
        config={enabledConfig}
        onChange={() => undefined}
        onClose={() => undefined}
      />,
    );

    expect(screen.getByText('Configuracion HPC')).toBeInTheDocument();
    expect(screen.getByText('Activar modo HPC')).toBeInTheDocument();
    expect(screen.getByText('Enviar trabajos al cluster en lugar de ejecucion local')).toBeInTheDocument();
    expect(screen.getByText('HPC esta activado')).toBeInTheDocument();
    expect(screen.getByText('Los trabajos se enviaran al planificador configurado.')).toBeInTheDocument();
    expect(screen.getByText('Planificador')).toBeInTheDocument();
    expect(screen.getByText('Sistema de colas')).toBeInTheDocument();
    expect(screen.getByText('Recursos del trabajo')).toBeInTheDocument();
    expect(screen.getByText('Particion / Cola')).toBeInTheDocument();
    expect(screen.getByText('Cuenta / Proyecto')).toBeInTheDocument();
    expect(screen.getByText('CPUs por tarea')).toBeInTheDocument();
    expect(screen.getByText('Memoria por CPU')).toBeInTheDocument();
    expect(screen.getByText('Modulos (uno por linea)')).toBeInTheDocument();
    expect(screen.getByText('Vista previa del script de trabajo')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('normal, gpu, etc.')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('ID de proyecto')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('HH:MM:SS')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('4G')).toBeInTheDocument();
    expect(screen.getByPlaceholderText(/bioinfo\/BWA\/0\.7\.17\s+bioinfo\/samtools\/1\.17/)).toBeInTheDocument();
    expect(screen.getByPlaceholderText('ruta/al/contenedor.sif')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('--gres=gpu:1')).toBeInTheDocument();
    expect(screen.getByText(/# Comandos del flujo de trabajo aqui/)).toBeInTheDocument();
    expect(screen.queryByText(/# Comandos del workflow aqui/)).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Probar conexion' }));

    await waitFor(() => expect(screen.getByText('No se pudo conectar (503). Revisa tu configuracion HPC.')).toBeInTheDocument());
  });
});
