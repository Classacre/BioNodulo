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

describe('HtmlPreviewModal i18n', () => {
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

  it('renders preview toolbar actions from the active locale', async () => {
    const { default: HtmlPreviewModal } = await import('../components/modals/HtmlPreviewModal');
    const { setLanguage } = await import('../i18n');
    const onClose = vi.fn();
    const open = vi.fn();

    vi.stubGlobal('open', open);
    await setLanguage('es');

    render(
      <HtmlPreviewModal
        src="/reports/multiqc.html"
        filename="multiqc.html"
        isOpen
        onClose={onClose}
      />,
    );

    expect(screen.getByText('multiqc.html')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Guardar' })).toHaveAttribute('title', 'Descargar HTML');
    expect(screen.getByRole('button', { name: 'Abrir' })).toHaveAttribute('title', 'Abrir en una pestana nueva');
    expect(screen.getByRole('button', { name: 'Cerrar (Esc)' })).toBeInTheDocument();
    expect(screen.getByTitle('multiqc.html')).toHaveAttribute('sandbox', 'allow-scripts');

    fireEvent.click(screen.getByRole('button', { name: 'Abrir' }));
    expect(open).toHaveBeenCalledWith('/reports/multiqc.html', '_blank', 'noopener,noreferrer');

    fireEvent.keyDown(window, { key: 'Escape' });
    expect(onClose).toHaveBeenCalledTimes(1);
  });
});
