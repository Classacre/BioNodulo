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

function ThrowingChild() {
  throw new Error('boom');
}

describe('ErrorBoundary i18n', () => {
  beforeEach(() => {
    storage.clear();
    vi.stubGlobal('localStorage', localStorageStub);
    vi.spyOn(console, 'error').mockImplementation(() => undefined);
  });

  afterEach(async () => {
    const { setLanguage } = await import('../i18n');
    await setLanguage('en');
    vi.restoreAllMocks();
    storage.clear();
    vi.unstubAllGlobals();
  });

  it('renders panel fallback copy from the active locale', async () => {
    const { default: ErrorBoundary } = await import('../components/layout/ErrorBoundary');
    const { setLanguage } = await import('../i18n');

    await setLanguage('es');

    render(
      <ErrorBoundary name="Inspector">
        <ThrowingChild />
      </ErrorBoundary>,
    );

    expect(screen.getByRole('alert')).toHaveTextContent('El panel Inspector fallo');
    expect(screen.getByText('boom')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Intentar de nuevo' })).toBeInTheDocument();
  });

  it('renders inline fallback copy from the active locale and can retry', async () => {
    const { default: ErrorBoundary } = await import('../components/layout/ErrorBoundary');
    const { setLanguage } = await import('../i18n');
    let shouldThrow = true;

    function RecoverableChild() {
      if (shouldThrow) throw new Error('boom');
      return <div>recuperado</div>;
    }

    await setLanguage('es');

    render(
      <ErrorBoundary name="Consola" variant="inline">
        <RecoverableChild />
      </ErrorBoundary>,
    );

    expect(screen.getByRole('alert')).toHaveTextContent('Consola fallo');
    expect(screen.getByRole('button', { name: 'reintentar' })).toBeInTheDocument();

    shouldThrow = false;
    fireEvent.click(screen.getByRole('button', { name: 'reintentar' }));

    expect(screen.getByText('recuperado')).toBeInTheDocument();
  });
});
