import { fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { ResolveReport, Workflow } from '../types';

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
  });

  afterEach(async () => {
    const { setLanguage } = await import('../i18n');
    await setLanguage('en');
    storage.clear();
    vi.unstubAllGlobals();
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
});
