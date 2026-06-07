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

describe('KeyboardShortcutsModal i18n', () => {
  beforeEach(() => {
    storage.clear();
    vi.stubGlobal('localStorage', localStorageStub);
  });

  afterEach(async () => {
    const { setLanguage } = await import('../i18n');
    const { resetAllKeybindings } = await import('../state/keybindings');
    cleanup();
    resetAllKeybindings();
    await setLanguage('en');
    storage.clear();
    vi.unstubAllGlobals();
  });

  it('renders shortcut action labels from the active locale and filters by localized text', async () => {
    const { setLanguage } = await import('../i18n');
    const { KeyboardShortcutsModal } = await import('../components/ui/KeyboardShortcutsModal');

    await setLanguage('es');

    render(<KeyboardShortcutsModal open onOpenChange={() => undefined} />);

    expect(screen.getByText('Abrir paleta de comandos')).toBeInTheDocument();
    expect(screen.queryByText('Open command palette')).not.toBeInTheDocument();
    expect(screen.getByText('Flujo de trabajo')).toBeInTheDocument();
    expect(screen.queryByText('Workflow')).not.toBeInTheDocument();
    expect(screen.getByText('Ejecutar flujo de trabajo')).toBeInTheDocument();
    expect(screen.queryByText('Ejecutar workflow')).not.toBeInTheDocument();

    fireEvent.change(screen.getByRole('textbox'), {
      target: { value: 'Eliminar nodos' },
    });

    expect(screen.getByText('Eliminar nodos seleccionados')).toBeInTheDocument();
    expect(screen.queryByText('Abrir paleta de comandos')).not.toBeInTheDocument();
  });

  it('renders shortcut modal shell controls and conflict summary from the active locale', async () => {
    const { setLanguage } = await import('../i18n');
    const { KeyboardShortcutsModal } = await import('../components/ui/KeyboardShortcutsModal');
    const { setKeybinding } = await import('../state/keybindings');

    await setLanguage('es');
    setKeybinding('workflow.run', 'Ctrl+K');

    render(<KeyboardShortcutsModal open onOpenChange={() => undefined} />);

    expect(screen.getByRole('textbox', { name: 'Buscar atajos de teclado' })).toHaveAttribute(
      'placeholder',
      'Buscar atajos...',
    );
    expect(screen.getByRole('button', { name: 'Restablecer todo' })).toBeInTheDocument();
    expect(screen.getByText('1 conflicto de atajo detectado')).toBeInTheDocument();
  });

  it('renders unassigned shortcut fallback from the active locale', async () => {
    const { setLanguage } = await import('../i18n');
    const { KeyboardShortcutsModal } = await import('../components/ui/KeyboardShortcutsModal');
    const { setKeybinding } = await import('../state/keybindings');

    await setLanguage('es');
    setKeybinding('workflow.export', '');

    render(<KeyboardShortcutsModal open onOpenChange={() => undefined} />);

    expect(screen.getByText('Sin atajo asignado')).toBeInTheDocument();
    expect(screen.queryByText('-')).not.toBeInTheDocument();
  });
});
