import { fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { ObjectInfo } from '../types';

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

const objectInfo: ObjectInfo = {
  fastqc: {
    id: 'fastqc',
    display_name: 'FastQC',
    category: 'Quality Control',
    description: 'Read quality report',
    input_types: { required: { reads: { type: 'FASTQ' } } },
    return_types: ['HTML'],
    return_names: ['report'],
    requires_external_tools: ['fastqc'],
  },
  multiqc: {
    id: 'multiqc',
    display_name: 'MultiQC',
    category: 'Quality Control',
    description: 'Aggregate reports',
    input_types: { required: { reports: { type: 'FILE' } } },
    return_types: ['HTML'],
    return_names: ['report'],
    requires_external_tools: ['multiqc'],
  },
};

const objectInfoWithFallbackCategory: ObjectInfo = {
  mystery: {
    id: 'mystery',
    display_name: 'Mystery Tool',
    category: '',
    description: 'No category metadata',
    input_types: { required: { input: { type: 'FILE' } } },
    return_types: ['FILE'],
  },
};

describe('NodeLibraryPanel i18n', () => {
  let originalLocalStorage: Storage;

  beforeEach(() => {
    storage.clear();
    originalLocalStorage = window.localStorage;
    vi.stubGlobal('localStorage', localStorageStub);
    Element.prototype.scrollIntoView = vi.fn();
    Object.defineProperty(window, 'localStorage', {
      configurable: true,
      value: localStorageStub,
    });
  });

  afterEach(async () => {
    const { setLanguage } = await import('../i18n');
    await setLanguage('en');
    storage.clear();
    vi.unstubAllGlobals();
    Object.defineProperty(window, 'localStorage', {
      configurable: true,
      value: originalLocalStorage,
    });
  });

  it('renders panel controls and result affordances from the active locale', async () => {
    const { default: NodeLibraryPanel } = await import('../components/panels/NodeLibraryPanel');
    const { setLanguage } = await import('../i18n');

    await setLanguage('es');

    render(
      <NodeLibraryPanel
        objectInfo={objectInfo}
        onAddNode={() => undefined}
        onClose={() => undefined}
      />,
    );

    expect(screen.getByText('Biblioteca de nodos')).toBeInTheDocument();
    expect(screen.getByTitle('Cerrar biblioteca de nodos')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('Buscar nodos...')).toBeInTheDocument();
    expect(screen.getByRole('combobox', { name: 'Buscar nodos' })).toBeInTheDocument();
    expect(screen.getByText('2 nodos disponibles')).toBeInTheDocument();
    expect(screen.getByTitle('Agregar FastQC')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Marcar FastQC' })).toBeInTheDocument();

    fireEvent.change(screen.getByRole('combobox', { name: 'Buscar nodos' }), {
      target: { value: 'zz' },
    });

    expect(screen.getByText('0 coincidencias')).toBeInTheDocument();
    expect(screen.getByText('Ningun nodo coincide con "zz"')).toBeInTheDocument();
  });

  it('localizes the fallback category label for uncategorized nodes', async () => {
    const { default: NodeLibraryPanel } = await import('../components/panels/NodeLibraryPanel');
    const { setLanguage } = await import('../i18n');

    await setLanguage('es');

    render(
      <NodeLibraryPanel
        objectInfo={objectInfoWithFallbackCategory}
        onAddNode={() => undefined}
        onClose={() => undefined}
      />,
    );

    expect(screen.getAllByText('Otro').length).toBeGreaterThan(0);
    expect(screen.queryByText('Other')).not.toBeInTheDocument();
  });
});
