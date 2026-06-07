import { cleanup, fireEvent, render, screen } from '@testing-library/react';
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

describe('Dialog primitive', () => {
  beforeEach(() => {
    storage.clear();
    vi.stubGlobal('localStorage', localStorageStub);
  });

  afterEach(async () => {
    const { setLanguage } = await import('../i18n');
    cleanup();
    await setLanguage('en');
    storage.clear();
    vi.unstubAllGlobals();
  });

  it('renders dialog semantics and localized close control', async () => {
    const { setLanguage } = await import('../i18n');
    const { Dialog } = await import('../components/ui/Dialog');
    const onClose = vi.fn();

    await setLanguage('es');

    render(
      <Dialog
        title="Exportar"
        header={<p>Opciones</p>}
        footer={<button type="button">Guardar</button>}
        onClose={onClose}
      >
        <p>Contenido</p>
      </Dialog>,
    );

    const dialog = screen.getByRole('dialog', { name: 'Exportar' });
    expect(dialog).toHaveAttribute('aria-modal', 'true');
    expect(screen.getByText('Opciones')).toBeInTheDocument();
    expect(screen.getByText('Contenido')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Guardar' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Cerrar' })).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Cerrar' }));

    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('honors backdrop and Escape dismissal options independently', async () => {
    const { Dialog } = await import('../components/ui/Dialog');
    const onClose = vi.fn();

    render(
      <Dialog title="Settings" dismissOnBackdrop={false} onClose={onClose}>
        <button type="button">Focusable</button>
      </Dialog>,
    );

    const dialog = screen.getByRole('dialog', { name: 'Settings' });
    fireEvent.click(dialog.parentElement as HTMLElement);
    expect(onClose).not.toHaveBeenCalled();

    fireEvent.keyDown(dialog, { key: 'Escape' });
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('blocks all close paths when dismissable is false', async () => {
    const { Dialog } = await import('../components/ui/Dialog');
    const onClose = vi.fn();

    render(
      <Dialog title="Confirm install" dismissable={false} onClose={onClose}>
        <button type="button">Install</button>
      </Dialog>,
    );

    const dialog = screen.getByRole('dialog', { name: 'Confirm install' });
    expect(screen.queryByRole('button', { name: 'Close' })).not.toBeInTheDocument();

    fireEvent.click(dialog.parentElement as HTMLElement);
    fireEvent.keyDown(dialog, { key: 'Escape' });

    expect(onClose).not.toHaveBeenCalled();
  });

  it('dismisses only the top dialog on Escape when dialogs are stacked', async () => {
    const { Dialog } = await import('../components/ui/Dialog');
    const onParentClose = vi.fn();
    const onChildClose = vi.fn();

    render(
      <>
        <Dialog title="Parent dialog" onClose={onParentClose}>
          Parent body
        </Dialog>
        <Dialog title="Child dialog" onClose={onChildClose}>
          Child body
        </Dialog>
      </>,
    );

    const parent = screen.getByRole('dialog', { name: 'Parent dialog' });
    const child = screen.getByRole('dialog', { name: 'Child dialog' });

    expect(Number(child.parentElement?.style.zIndex)).toBeGreaterThan(Number(parent.parentElement?.style.zIndex));

    fireEvent.keyDown(parent, { key: 'Escape' });
    expect(onParentClose).not.toHaveBeenCalled();
    expect(onChildClose).not.toHaveBeenCalled();

    fireEvent.keyDown(child, { key: 'Escape' });
    expect(onParentClose).not.toHaveBeenCalled();
    expect(onChildClose).toHaveBeenCalledTimes(1);
  });
});
