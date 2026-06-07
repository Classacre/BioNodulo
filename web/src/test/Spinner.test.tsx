import { render, screen } from '@testing-library/react';
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

describe('Spinner i18n', () => {
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

  it('uses the active locale for its default accessible label', async () => {
    const { Spinner } = await import('../components/ui/Spinner');
    const { setLanguage } = await import('../i18n');

    await setLanguage('es');

    render(<Spinner />);

    expect(screen.getByRole('status', { name: 'Cargando...' })).toBeInTheDocument();
  });

  it('keeps explicit accessible labels unchanged', async () => {
    const { Spinner } = await import('../components/ui/Spinner');
    const { setLanguage } = await import('../i18n');

    await setLanguage('es');

    render(<Spinner label="Loading alignment index" />);

    expect(screen.getByRole('status', { name: 'Loading alignment index' })).toBeInTheDocument();
  });
});
