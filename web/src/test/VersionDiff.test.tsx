import { render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import type { VersionDiffResult } from '../collab/types';

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

const populatedDiff: VersionDiffResult = {
  nodes: {
    added: ['node-added'],
    removed: ['node-removed'],
    modified: ['node-modified'],
  },
  edges: {
    added: ['edge-added'],
    removed: ['edge-removed'],
    modified: ['edge-modified'],
  },
  groups: {
    added: ['group-added'],
    removed: ['group-removed'],
    modified: ['group-modified'],
  },
  meta_changes: {
    name: { before: 'Old', after: 'New' },
  },
};

const emptyDiff: VersionDiffResult = {
  nodes: { added: [], removed: [], modified: [] },
  edges: { added: [], removed: [], modified: [] },
  groups: { added: [], removed: [], modified: [] },
  meta_changes: {},
};

describe('VersionDiff i18n', () => {
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

  it('renders diff labels and summaries from the active locale', async () => {
    const { default: VersionDiff } = await import('../collab/VersionDiff');
    const { setLanguage } = await import('../i18n');
    await setLanguage('es');

    const { rerender } = render(
      <VersionDiff
        versionA={{ id: 'a', name: 'Anterior' }}
        versionB={{ id: 'b', name: 'Actual' }}
        diff={populatedDiff}
        isOpen
        onClose={() => undefined}
      />,
    );

    expect(screen.getByText('Diff de versiones')).toBeInTheDocument();
    expect(screen.getByTitle('Cerrar')).toBeInTheDocument();
    expect(screen.getAllByText('(7 cambiados)')).toHaveLength(2);
    expect(screen.getByText('+ Nodo agregado')).toBeInTheDocument();
    expect(screen.getByText('- Nodo eliminado')).toBeInTheDocument();
    expect(screen.getAllByText('~ Nodo modificado')).toHaveLength(2);
    expect(screen.getByText('+ Enlace agregado')).toBeInTheDocument();
    expect(screen.getByText('- Enlace eliminado')).toBeInTheDocument();
    expect(screen.getAllByText('~ Enlace modificado')).toHaveLength(2);
    expect(screen.getByText('+ Grupo agregado')).toBeInTheDocument();
    expect(screen.getByText('- Grupo eliminado')).toBeInTheDocument();
    expect(screen.getAllByText('~ Grupo modificado')).toHaveLength(2);
    expect(screen.getByText('~ Meta: name (antes)')).toBeInTheDocument();
    expect(screen.getByText('~ Meta: name (despues)')).toBeInTheDocument();
    expect(screen.getByText('3 agregados')).toBeInTheDocument();
    expect(screen.getByText('3 eliminados')).toBeInTheDocument();
    expect(screen.getByText('4 modificados')).toBeInTheDocument();

    rerender(
      <VersionDiff
        versionA={{ id: 'a', name: 'Anterior' }}
        versionB={{ id: 'b', name: 'Actual' }}
        diff={emptyDiff}
        isOpen
        onClose={() => undefined}
      />,
    );

    expect(screen.getByText('Sin diferencias entre estas versiones.')).toBeInTheDocument();
  });
});
