import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { ResolveReport, Workflow } from '../types';

const apiMocks = vi.hoisted(() => ({
  apiGet: vi.fn(),
  apiPost: vi.fn(),
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

function workflow(): Workflow {
  return {
    version: '2.0',
    app: 'BioNodulo',
    name: 'Missing deps workflow',
    description: '',
    nodes: [],
    edges: [],
    groups: [],
    outputs: {},
  };
}

function report(): ResolveReport {
  return {
    missing_nodes: [
      {
        node_type: 'custom_qc',
        git_url: 'https://example.test/plugin.git',
        git_commit: '',
        requirements: [],
        message: 'Plugin missing',
      },
    ],
    missing_executables: [{ name: 'fastqc', conda_package: 'fastqc', node_types: ['fastqc'], message: 'fastqc missing' }],
    missing_packages: [{ name: 'pandas', source: 'pip', node_types: ['table_preview'], message: 'pandas missing' }],
    missing_r_packages: [{ name: 'DESeq2', source: 'bioconductor', node_types: ['deseq2'], message: 'DESeq2 missing' }],
    required_packages: ['fastqc', 'multiqc'],
    env_id: 'abcdef1234567890',
    env_ready: false,
    installable: true,
    errors: ['Could not inspect custom_qc'],
    has_issues: true,
    summary: '',
  };
}

describe('MissingDependenciesBanner i18n', () => {
  beforeEach(() => {
    storage.clear();
    vi.stubGlobal('localStorage', localStorageStub);
    apiMocks.apiGet.mockReset();
    apiMocks.apiPost.mockReset();
    loggingMock.logError.mockReset();
    vi.useRealTimers();
  });

  afterEach(async () => {
    const { setLanguage } = await import('../i18n');
    await setLanguage('en');
    storage.clear();
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  it('centralizes known installer progress protocol messages', () => {
    // The installer-progress message keys are centralized in the
    // useDependencyInstall hook (installProgressMessage); the banner consumes
    // that helper and must not hardcode the raw protocol strings itself.
    const hookSource = readFileSync(resolve(__dirname, '../hooks/workflow/useDependencyInstall.ts'), 'utf8');
    expect(hookSource).toContain('INSTALL_PROGRESS_MESSAGE_KEYS');

    const bannerSource = readFileSync(resolve(__dirname, '../components/layout/MissingDependenciesBanner.tsx'), 'utf8');
    [
      "trimmed === 'Generating pixi.toml manifest...'",
      "trimmed === 'Locking dependencies with pixi (this may take a moment)...'",
      "trimmed === 'Installing packages into environment...'",
      "trimmed === 'Installation cancelled'",
    ].forEach(text => expect(bannerSource).not.toContain(text));
  });

  it('renders dependency summary and expanded report sections from the active locale', async () => {
    const { default: MissingDependenciesBanner } = await import('../components/layout/MissingDependenciesBanner');
    const { setLanguage } = await import('../i18n');
    const onDismiss = vi.fn();
    const onOpenConsole = vi.fn();
    const onResolve = vi.fn();

    await setLanguage('es');

    render(
      <MissingDependenciesBanner
        report={report()}
        workflow={workflow()}
        onDismiss={onDismiss}
        onOpenConsole={onOpenConsole}
        onResolve={onResolve}
      />,
    );

    expect(screen.getByText('Dependencias faltantes:')).toBeInTheDocument();
    expect(screen.getByText('4 faltantes')).toBeInTheDocument();
    expect(screen.getByText(/entorno: abcdef12 \(no listo\)/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Instalar entorno/ })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Detalles' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Descartar' })).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Detalles' }));

    expect(screen.getByRole('button', { name: 'Ocultar' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Paquetes requeridos (2)' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Nodos faltantes (1)' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Paquetes Python faltantes (1)' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Paquetes R faltantes (1)' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Errores' })).toBeInTheDocument();
  });

  it('logs swallowed install and status-poll failures with stable scopes', async () => {
    vi.useFakeTimers();
    const { default: MissingDependenciesBanner } = await import('../components/layout/MissingDependenciesBanner');
    const onOpenConsole = vi.fn();
    const onResolve = vi.fn();
    const installError = new Error('install start failed');
    const statusError = new Error('status poll failed');

    apiMocks.apiPost.mockRejectedValueOnce(installError);

    const installView = render(
      <MissingDependenciesBanner
        report={report()}
        workflow={workflow()}
        onDismiss={() => undefined}
        onOpenConsole={onOpenConsole}
        onResolve={onResolve}
      />,
    );

    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /Install Env/ }));
      await Promise.resolve();
    });

    expect(loggingMock.logError).toHaveBeenCalledWith('dependencies.install.start', installError);
    expect(onOpenConsole).toHaveBeenCalledTimes(1);
    installView.unmount();

    apiMocks.apiPost.mockResolvedValueOnce({ job_id: 'job-1' });
    apiMocks.apiGet.mockRejectedValue(statusError);

    render(
      <MissingDependenciesBanner
        report={report()}
        workflow={workflow()}
        onDismiss={() => undefined}
        onOpenConsole={onOpenConsole}
        onResolve={onResolve}
      />,
    );

    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /Install Env/ }));
      await Promise.resolve();
    });
    expect(apiMocks.apiPost).toHaveBeenCalledWith('/manager/ensure-workflow-env', { workflow: workflow() });

    await act(async () => {
      await vi.advanceTimersByTimeAsync(1500);
    });
    expect(loggingMock.logError).toHaveBeenCalledWith('dependencies.install.status', statusError);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(4500);
    });
    expect(loggingMock.logError.mock.calls.filter(([scope]) => scope === 'dependencies.install.status')).toHaveLength(1);
  });

  it('localizes known installer progress messages from the active locale', async () => {
    vi.useFakeTimers();
    const { default: MissingDependenciesBanner } = await import('../components/layout/MissingDependenciesBanner');
    const { setLanguage } = await import('../i18n');

    await setLanguage('es');

    apiMocks.apiPost.mockResolvedValueOnce({ job_id: 'job-1' });
    apiMocks.apiGet.mockResolvedValueOnce({
      job_id: 'job-1',
      status: 'running',
      total_steps: 0,
      completed_steps: 0,
      current_step: '',
      message: 'Generating pixi.toml manifest...',
      errors: [],
      percent: 0,
    });

    render(
      <MissingDependenciesBanner
        report={report()}
        workflow={workflow()}
        onDismiss={() => undefined}
        onOpenConsole={() => undefined}
        onResolve={() => undefined}
      />,
    );

    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /Instalar entorno/ }));
      await Promise.resolve();
    });

    await act(async () => {
      await vi.advanceTimersByTimeAsync(1500);
    });

    expect(screen.getByText(/Generando manifiesto pixi\.toml/)).toBeInTheDocument();
    expect(screen.queryByText(/Generating pixi\.toml manifest/)).not.toBeInTheDocument();
  });
});
