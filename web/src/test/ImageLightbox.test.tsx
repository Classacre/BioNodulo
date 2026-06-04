import { fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { LightboxImage } from '../components/modals/ImageLightbox';

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

const images: LightboxImage[] = [
  { src: '/runs/r1/plot-a.png', alt: 'Plot A', filename: 'plot-a.png' },
  { src: '/runs/r1/plot-b.png', alt: 'Plot B', filename: 'plot-b.png' },
];

describe('ImageLightbox i18n', () => {
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

  it('renders image controls from the active locale and navigates images', async () => {
    const { default: ImageLightbox } = await import('../components/modals/ImageLightbox');
    const { setLanguage } = await import('../i18n');
    const onClose = vi.fn();

    await setLanguage('es');

    render(
      <ImageLightbox
        images={images}
        initialIndex={0}
        isOpen
        onClose={onClose}
      />,
    );

    expect(screen.getByRole('button', { name: 'Cerrar (Esc)' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Anterior (←)' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Siguiente (→)' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Guardar' })).toHaveAttribute('title', 'Guardar imagen');
    expect(screen.getByText('1 / 2')).toBeInTheDocument();
    expect(screen.getByText('plot-a.png')).toBeInTheDocument();
    expect(screen.getByAltText('Plot A')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Siguiente (→)' }));

    expect(screen.getByText('2 / 2')).toBeInTheDocument();
    expect(screen.getByText('plot-b.png')).toBeInTheDocument();
    expect(screen.getByAltText('Plot B')).toBeInTheDocument();

    fireEvent.keyDown(window, { key: 'Escape' });
    expect(onClose).toHaveBeenCalledTimes(1);
  });
});
