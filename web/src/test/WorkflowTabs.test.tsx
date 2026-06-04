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

describe('WorkflowTabs i18n', () => {
  beforeEach(() => {
    storage.clear();
    vi.stubGlobal('localStorage', localStorageStub);
    vi.stubGlobal('ResizeObserver', class ResizeObserver {
      observe() {}
      unobserve() {}
      disconnect() {}
    });
  });

  afterEach(async () => {
    const { setLanguage } = await import('../i18n');
    await setLanguage('en');
    storage.clear();
    vi.unstubAllGlobals();
  });

  it('renders fallback names, actions, and context menu labels from the active locale', async () => {
    const { default: WorkflowTabs } = await import('../components/layout/WorkflowTabs');
    const { setLanguage } = await import('../i18n');

    await setLanguage('es');

    render(
      <WorkflowTabs
        tabs={['Untitled', 'RNA workflow']}
        active={0}
        onChange={() => undefined}
        onClose={() => undefined}
        onAdd={() => undefined}
        onRename={() => undefined}
        onDuplicate={() => undefined}
        dirtyIndices={new Set([0])}
      />,
    );

    expect(screen.getByText('Sin titulo')).toBeInTheDocument();
    expect(screen.getByTitle('Cambios sin guardar')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Nueva pestana de workflow' })).toHaveAttribute('title', 'Nuevo workflow');

    fireEvent.contextMenu(screen.getByText('RNA workflow'));

    expect(screen.getByText('Renombrar')).toBeInTheDocument();
    expect(screen.getByText('Duplicar')).toBeInTheDocument();
    expect(screen.getByText('Cerrar pestana')).toBeInTheDocument();
    expect(screen.getByText('Cerrar pestanas a la izquierda')).toBeInTheDocument();
    expect(screen.getByText('Cerrar pestanas a la derecha')).toBeInTheDocument();
    expect(screen.getByText('Cerrar otras pestanas')).toBeInTheDocument();
  });
});
