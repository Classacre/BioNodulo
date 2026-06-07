import { fireEvent, render, screen } from '@testing-library/react';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
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

describe('App palette command copy i18n', () => {
  beforeEach(() => {
    storage.clear();
    vi.stubGlobal('localStorage', localStorageStub);
    Element.prototype.scrollIntoView = vi.fn();
  });

  afterEach(async () => {
    const { setLanguage } = await import('../i18n');
    await setLanguage('en');
    storage.clear();
    vi.unstubAllGlobals();
  });

  it('renders command palette group headings from locale keys while keeping canonical groups searchable', async () => {
    const { CommandPalette } = await import('../components/ui/CommandPalette');
    const { setLanguage } = await import('../i18n');

    await setLanguage('es');

    render(
      <CommandPalette
        open
        onOpenChange={() => undefined}
        items={[
          {
            id: 'palette.clinical',
            label: 'Usar paleta Clinical',
            description: 'Tema clinico de alto contraste para estacion de trabajo.',
            group: 'Appearance',
            groupLabelKey: 'commandPalette.groups.appearance',
            onSelect: () => undefined,
          },
        ]}
      />,
    );

    expect(screen.getByRole('textbox', { name: 'Buscar comandos' })).toHaveAttribute(
      'placeholder',
      'Buscar comandos...',
    );
    expect(screen.getByText('Apariencia')).toBeInTheDocument();
    expect(screen.queryByText('Appearance')).not.toBeInTheDocument();

    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'Apariencia' } });

    expect(screen.getByRole('option', { name: /Usar paleta Clinical/ })).toBeInTheDocument();
  });

  it('keeps App palette commands behind i18n keys', async () => {
    const { default: i18n, setLanguage } = await import('../i18n');
    const appSource = readFileSync(resolve(__dirname, '../App.tsx'), 'utf8');

    await setLanguage('es');

    expect(i18n.t('palettes.clinical')).toBe('Clinica');
    expect(i18n.t('palettes.field')).toBe('Estacion de campo');
    expect(i18n.t('palettes.contrast')).toBe('Alto contraste');
    expect(i18n.t('commandPalette.commands.palette.use', { name: i18n.t('palettes.clinical') })).toBe('Usar paleta Clinica');
    expect(i18n.t('commandPalette.groups.appearance')).toBe('Apariencia');
    expect(appSource).toContain('paletteDisplayName(palette, t)');
    expect(appSource).toContain('commandPalette.commands.palette.use');
    expect(appSource).toContain('commandPalette.groups.appearance');
    expect(appSource).not.toContain('name: palette.name');
    expect(appSource).not.toContain('Use ${palette.name} palette');
  });
});
