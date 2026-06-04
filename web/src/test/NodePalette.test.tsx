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
  },
  bwa: {
    id: 'bwa',
    display_name: 'BWA align',
    category: 'Alignment',
    description: 'Map reads',
    input_types: { required: { reads: { type: 'FASTQ' } } },
    return_types: ['BAM'],
    return_names: ['alignment'],
  },
  notes: {
    id: 'notes',
    display_name: 'Notes',
    category: '',
    description: 'Workflow note',
    input_types: { optional: { value: { type: 'STRING' } } },
    return_types: ['TEXT'],
    return_names: ['text'],
  },
};

describe('NodePalette i18n', () => {
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

  it('renders palette chrome, recent controls, fallback categories, and selection in the active locale', async () => {
    const { default: NodePalette } = await import('../components/nodes/NodePalette');
    const { setLanguage } = await import('../i18n');
    const onSelect = vi.fn();

    localStorage.setItem('bionodulo.recentNodes', JSON.stringify(['fastqc']));
    await setLanguage('es');

    render(<NodePalette objectInfo={objectInfo} onSelect={onSelect} onClose={() => undefined} />);

    expect(screen.getByText('Agregar nodo')).toBeInTheDocument();
    expect(screen.getByTitle('Cerrar paleta de nodos')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('Buscar nodos...')).toBeInTheDocument();
    expect(screen.getByRole('combobox', { name: 'Buscar nodos' })).toBeInTheDocument();
    expect(screen.getByText('3 nodos')).toBeInTheDocument();
    expect(screen.getByText('Usados recientemente')).toBeInTheDocument();
    expect(screen.getByTitle('Limpiar nodos recientes')).toBeInTheDocument();
    expect(screen.getByText('Limpiar recientes')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Otro/ })).toBeInTheDocument();
    expect(screen.getByTitle('Agregar FastQC')).toBeInTheDocument();

    fireEvent.keyDown(screen.getByRole('combobox', { name: 'Buscar nodos' }), { key: 'Enter' });

    expect(onSelect).toHaveBeenCalledWith(expect.objectContaining({ id: 'fastqc' }));
  });

  it('renders filtered summaries and empty search states in the active locale', async () => {
    const { default: NodePalette } = await import('../components/nodes/NodePalette');
    const { setLanguage } = await import('../i18n');

    await setLanguage('es');

    render(
      <NodePalette
        objectInfo={objectInfo}
        onSelect={() => undefined}
        onClose={() => undefined}
        requireInputType="FASTQ"
      />,
    );

    expect(screen.getByText('Agregar nodo con entrada FASTQ')).toBeInTheDocument();
    expect(screen.getByText('2 nodos (filtrados)')).toBeInTheDocument();

    fireEvent.change(screen.getByRole('combobox', { name: 'Buscar nodos' }), {
      target: { value: 'zzz' },
    });

    expect(screen.getByText('0 coincidencias aproximadas')).toBeInTheDocument();
    expect(screen.getByText('Ningun nodo coincide con "zzz"')).toBeInTheDocument();
  });
});
