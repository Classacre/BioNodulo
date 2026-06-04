import { render, screen } from '@testing-library/react';
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

describe('WorkflowCanvas controls i18n', () => {
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

  it('renders canvas controls from the active locale', async () => {
    const { default: WorkflowCanvas } = await import('../components/canvas/WorkflowCanvas');
    const { setLanguage } = await import('../i18n');

    await setLanguage('es');

    render(
      <WorkflowCanvas
        nodes={[]}
        edges={[]}
        groups={[]}
        objectInfo={{} satisfies ObjectInfo}
        onNodesChange={() => undefined}
        onEdgesChange={() => undefined}
        onGroupsChange={() => undefined}
        onPushHistory={() => undefined}
        onUndo={() => undefined}
        onRedo={() => undefined}
        snapToGrid={false}
        showMinimap={false}
        viewportLocked={false}
        linksHidden={false}
        onToggleMinimap={() => undefined}
        onToggleLinksHidden={() => undefined}
      />,
    );

    expect(screen.getByRole('button', { name: 'Ajustar vista' })).toHaveAttribute('title', 'Ajustar vista');
    expect(screen.getByRole('button', { name: 'Ajustar seleccion' })).toHaveAttribute('title', 'Ajustar seleccion');
    expect(screen.getByRole('button', { name: 'Acercar' })).toHaveAttribute('title', 'Acercar');
    expect(screen.getByRole('button', { name: 'Alejar' })).toHaveAttribute('title', 'Alejar');
    expect(screen.getByTitle('Alternar minimapa')).toBeInTheDocument();
    expect(screen.getByTitle('Alternar enlaces')).toBeInTheDocument();
    expect(screen.getByTitle('Autoordenar nodos')).toBeInTheDocument();
  });
});
