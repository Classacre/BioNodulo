import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { Workflow } from '../types';

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

function workflowJson(name: string): string {
  return JSON.stringify({
    version: '2.0',
    app: 'BioNodulo',
    name,
    description: '',
    nodes: [],
    edges: [],
    groups: [],
    outputs: {},
  });
}

describe('ImportModal i18n', () => {
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

  it('renders import chrome from the active locale and imports JSON workflows', async () => {
    const { default: ImportModal } = await import('../components/modals/ImportModal');
    const { setLanguage } = await import('../i18n');
    const onImport = vi.fn<(workflow: Workflow) => void>();
    const onClose = vi.fn();

    await setLanguage('es');

    render(<ImportModal onImport={onImport} onClose={onClose} />);

    expect(screen.getByRole('dialog', { name: 'Importar workflow' })).toBeInTheDocument();
    expect(screen.getByText('Importar workflow')).toBeInTheDocument();
    expect(screen.getByText(/Pega codigo de workflow arriba/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Cancelar' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Importar' })).toBeDisabled();

    fireEvent.change(screen.getByPlaceholderText(/"version": "2.0"/), {
      target: { value: workflowJson('Imported workflow') },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Importar' }));

    await waitFor(() => expect(onClose).toHaveBeenCalledTimes(1));

    expect(onImport).toHaveBeenCalledTimes(1);
    expect(onImport.mock.calls[0][0].name).toBe('Imported workflow');
  });
});
