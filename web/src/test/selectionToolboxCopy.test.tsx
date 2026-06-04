import { fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import type { GraphNode } from '../components/canvas/WorkflowCanvas';

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

const makeNode = (id: string, x: number): GraphNode => ({
  id,
  type: 'fastqc',
  display_name: 'FastQC',
  category: 'Quality Control',
  x,
  y: 40,
  width: 120,
  height: 80,
  inputs: [],
  outputs: [],
  params: {},
  meta: null,
  color: '#3b82f6',
  muted: false,
  bypassed: false,
  selected: true,
  collapsed: false,
  pinned: false,
  shape: 'card',
  title: 'FastQC',
  visualOnly: false,
});

describe('SelectionToolbox copy i18n', () => {
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

  it('renders action tooltips from the active locale', async () => {
    const { default: SelectionToolbox } = await import('../components/canvas/SelectionToolbox');
    const { setLanguage } = await import('../i18n');
    const onAction = vi.fn();
    const host = document.createElement('div');
    host.getBoundingClientRect = () => ({
      x: 0,
      y: 0,
      width: 800,
      height: 600,
      top: 0,
      left: 0,
      right: 800,
      bottom: 600,
      toJSON: () => ({}),
    });
    const hostRef = { current: host };

    await setLanguage('es');

    render(
      <SelectionToolbox
        graphNodes={[makeNode('a', 20), makeNode('b', 180), makeNode('c', 340)]}
        groups={[]}
        offset={{ x: 0, y: 0 }}
        scale={1}
        isDragging={false}
        onAction={onAction}
        hostRef={hostRef}
      />,
    );

    [
      'Eliminar seleccion',
      'Duplicar seleccion',
      'Alinear izquierda',
      'Alinear centro horizontal',
      'Alinear derecha',
      'Alinear arriba',
      'Alinear centro vertical',
      'Alinear abajo',
      'Distribuir horizontalmente',
      'Distribuir verticalmente',
      'Color de seleccion',
      'Alternar colapso de seleccion',
    ].forEach(title => expect(screen.getByTitle(title)).toBeInTheDocument());

    fireEvent.click(screen.getByTitle('Color de seleccion'));
    fireEvent.click(screen.getByTitle('#ef4444'));

    expect(onAction).toHaveBeenCalledWith('color', '#ef4444');
  });

  it('renders single-node tooltips from the active locale', async () => {
    const { default: SelectionToolbox } = await import('../components/canvas/SelectionToolbox');
    const { setLanguage } = await import('../i18n');

    await setLanguage('es');

    render(
      <SelectionToolbox
        graphNodes={[makeNode('a', 20)]}
        groups={[]}
        offset={{ x: 0, y: 0 }}
        scale={1}
        isDragging={false}
        onAction={() => undefined}
        hostRef={{ current: document.createElement('div') }}
      />,
    );

    expect(screen.getByTitle('Silenciar seleccion')).toBeInTheDocument();
    expect(screen.getByTitle('Omitir seleccion')).toBeInTheDocument();
  });

  it('keeps SelectionToolbox tooltip copy behind i18n keys', () => {
    const source = readFileSync(resolve(__dirname, '../components/canvas/SelectionToolbox.tsx'), 'utf8');

    expect(source).toContain('canvas.deleteSelection');
    [
      'title="Delete"',
      'title="Duplicate"',
      'title="Mute"',
      'title="Bypass"',
      'title="Collapse/Expand"',
      'title="Align left"',
      'title="Align center horizontal"',
      'title="Align right"',
      'title="Align top"',
      'title="Align center vertical"',
      'title="Align bottom"',
      'title="Distribute horizontally"',
      'title="Distribute vertically"',
      'title="Color"',
    ].forEach(text => expect(source).not.toContain(text));
  });
});
