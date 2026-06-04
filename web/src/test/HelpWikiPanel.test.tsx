import { fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
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
  diann: {
    id: 'diann',
    display_name: 'DIA-NN',
    category: 'proteomics',
    description: 'Analyze DIA proteomics data with DIA-NN.',
    search_aliases: ['dia-nn', 'data independent acquisition'],
    input_types: {
      required: {
        raw_files: { type: 'FILE', tooltip: 'DIA raw files' },
        library: { type: 'FILE', description: 'Spectral library TSV' },
        fasta: { type: 'FASTA', tooltip: 'Protein FASTA database' },
      },
      optional: {
        threads: { type: 'INT', default: 4 },
      },
    },
    return_types: ['TSV', 'JSON'],
    return_names: ['report', 'stats'],
    requires_external_tools: ['diann'],
    documentation_url: 'https://github.com/vdemichev/DiaNN',
    version: '1.8',
  },
};

describe('HelpWikiPanel node documentation search', () => {
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

  it('finds node docs by aliases, tools, ports, and output metadata', async () => {
    await import('../i18n');
    const { default: HelpWikiPanel } = await import('../components/panels/HelpWikiPanel');

    render(<HelpWikiPanel onClose={vi.fn()} objectInfo={objectInfo} />);

    fireEvent.change(screen.getByPlaceholderText('Search help...'), {
      target: { value: 'spectral library' },
    });

    expect(screen.getByText('Nodes')).toBeInTheDocument();
    expect(screen.getByText('DIA-NN')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /DIA-NN/i })).toHaveTextContent('Spectral library TSV');
  });

  it('opens full node documentation from a node search hit', async () => {
    await import('../i18n');
    const { default: HelpWikiPanel } = await import('../components/panels/HelpWikiPanel');

    render(<HelpWikiPanel onClose={vi.fn()} objectInfo={objectInfo} />);

    fireEvent.change(screen.getByPlaceholderText('Search help...'), {
      target: { value: 'diann' },
    });
    fireEvent.click(screen.getByRole('button', { name: /DIA-NN/i }));

    expect(screen.getByRole('heading', { name: 'DIA-NN' })).toBeInTheDocument();
    expect(screen.getByText('Inputs')).toBeInTheDocument();
    expect(screen.getByText('Outputs')).toBeInTheDocument();
    expect(screen.getByText('raw_files')).toBeInTheDocument();
    expect(screen.getByText('report')).toBeInTheDocument();
    expect(screen.getByText(/Requires:/)).toBeInTheDocument();
  });

  it('renders panel chrome, page navigation, search labels, and node docs from the active locale', async () => {
    const { default: HelpWikiPanel } = await import('../components/panels/HelpWikiPanel');
    const { setLanguage } = await import('../i18n');

    await setLanguage('es');

    render(
      <HelpWikiPanel
        onClose={vi.fn()}
        objectInfo={objectInfo}
        selectedNode={{
          id: 'selected-1',
          type: 'diann',
          title: 'DIA-NN selected',
          meta: {
            ...objectInfo.diann,
            experimental: true,
          },
        }}
      />,
    );

    expect(screen.getByText('Ayuda y wiki')).toBeInTheDocument();
    expect(screen.getByTitle('Cerrar')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('Buscar ayuda...')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Primeros pasos' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Lienzo y nodos' })).toBeInTheDocument();
    expect(screen.getByText('seleccionado en el lienzo')).toBeInTheDocument();
    expect(screen.getByTitle('Mostrar documentacion de DIA-NN selected')).toBeInTheDocument();

    expect(screen.getByText('experimental')).toBeInTheDocument();
    expect(screen.getByText(/Requiere:/)).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Entradas' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Salidas' })).toBeInTheDocument();
    expect(screen.getAllByText('Nombre').length).toBeGreaterThan(0);
    expect(screen.getAllByText('Tipo').length).toBeGreaterThan(0);
    expect(screen.getByText('Notas')).toBeInTheDocument();
    expect(screen.getByText(/predeterminado: 4/)).toBeInTheDocument();
    expect(screen.getByText('Consejo: selecciona otro nodo en el lienzo para ver su documentacion aqui.')).toBeInTheDocument();

    fireEvent.change(screen.getByPlaceholderText('Buscar ayuda...'), {
      target: { value: 'zzzz' },
    });

    expect(screen.getByText('Sin resultados para "zzzz"')).toBeInTheDocument();

    fireEvent.change(screen.getByPlaceholderText('Buscar ayuda...'), {
      target: { value: 'diann' },
    });

    expect(screen.getByText('Nodos')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /DIA-NN/i }));
    expect(screen.getByText('desde busqueda')).toBeInTheDocument();
  });

  it('renders getting-started article content from the active locale', async () => {
    const { default: HelpWikiPanel } = await import('../components/panels/HelpWikiPanel');
    const { setLanguage } = await import('../i18n');

    await setLanguage('es');

    render(<HelpWikiPanel onClose={vi.fn()} objectInfo={objectInfo} />);

    expect(screen.getByRole('heading', { name: 'Bienvenido a BioNodulo v2' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Inicio rapido' })).toBeInTheDocument();
    expect(screen.getByText(/BioNodulo es un entorno visual/)).toBeInTheDocument();
    expect(screen.queryByText('Welcome to BioNodulo v2')).not.toBeInTheDocument();
  });

  it('searches getting-started article content from the active locale', async () => {
    const { default: HelpWikiPanel } = await import('../components/panels/HelpWikiPanel');
    const { setLanguage } = await import('../i18n');

    await setLanguage('es');

    render(<HelpWikiPanel onClose={vi.fn()} objectInfo={objectInfo} />);

    fireEvent.change(screen.getByPlaceholderText('Buscar ayuda...'), {
      target: { value: 'lienzo infinito' },
    });

    expect(screen.getByText('Paginas wiki')).toBeInTheDocument();
    expect(screen.getByText('Primeros pasos')).toBeInTheDocument();
  });

  it('keeps getting-started wiki article content behind i18n keys', () => {
    const source = readFileSync(resolve(__dirname, '../components/panels/HelpWikiPanel.tsx'), 'utf8');

    expect(source).toContain('helpWiki.content.gettingStarted');
    expect(source).not.toContain('Welcome to BioNodulo v2');
    expect(source).not.toContain('BioNodulo is a visual bioinformatics workflow workbench.');
    expect(source).not.toContain('Quick Start');
  });

  it('renders canvas-features article content from the active locale', async () => {
    const { default: HelpWikiPanel } = await import('../components/panels/HelpWikiPanel');
    const { setLanguage } = await import('../i18n');

    await setLanguage('es');

    render(<HelpWikiPanel onClose={vi.fn()} objectInfo={objectInfo} />);

    fireEvent.click(screen.getByRole('button', { name: 'Lienzo y nodos' }));

    expect(screen.getByRole('heading', { name: 'Funciones del lienzo' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Navegacion' })).toBeInTheDocument();
    expect(screen.getByText(/El lienzo es un espacio de trabajo 2D infinito/)).toBeInTheDocument();
    expect(screen.queryByText('Canvas Features')).not.toBeInTheDocument();
  });

  it('searches canvas-features article content from the active locale', async () => {
    const { default: HelpWikiPanel } = await import('../components/panels/HelpWikiPanel');
    const { setLanguage } = await import('../i18n');

    await setLanguage('es');

    render(<HelpWikiPanel onClose={vi.fn()} objectInfo={objectInfo} />);

    fireEvent.change(screen.getByPlaceholderText('Buscar ayuda...'), {
      target: { value: 'caja de seleccion' },
    });

    expect(screen.getByText('Paginas wiki')).toBeInTheDocument();
    expect(screen.getByText('Lienzo y nodos')).toBeInTheDocument();
  });

  it('keeps canvas-features wiki article content behind i18n keys', () => {
    const source = readFileSync(resolve(__dirname, '../components/panels/HelpWikiPanel.tsx'), 'utf8');

    expect(source).toContain('helpWiki.content.canvasFeatures');
    expect(source).not.toContain('Canvas Features');
    expect(source).not.toContain('The canvas is an infinite 2D workspace');
    expect(source).not.toContain('Undo / Redo');
  });
});
