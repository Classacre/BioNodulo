import { fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

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

describe('GettingStartedModal i18n', () => {
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

  it('renders the getting-started shell and welcome intro from the active locale', async () => {
    const { default: GettingStartedModal } = await import('../components/modals/GettingStartedModal');
    const { setLanguage } = await import('../i18n');

    await setLanguage('es');

    render(
      <GettingStartedModal
        onClose={() => undefined}
        onDontShowAgain={() => undefined}
        showOnStartup
      />,
    );

    expect(screen.getByRole('dialog', { name: 'Primeros pasos' })).toBeInTheDocument();
    expect(screen.getByText('BioNodulo v2')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Bienvenida' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Novedades' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Recursos' })).toBeInTheDocument();
    expect(screen.getByText(/constructor visual de workflows para bioinformatica/)).toBeInTheDocument();
    expect(screen.getByText(/Crea, ejecuta y comparte pipelines reproducibles/)).toBeInTheDocument();
    expect(screen.getByLabelText('Ocultar al inicio')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Cerrar' })).toBeInTheDocument();
  });

  it('renders getting-started resource links from the active locale', async () => {
    const { default: GettingStartedModal } = await import('../components/modals/GettingStartedModal');
    const { setLanguage } = await import('../i18n');

    await setLanguage('es');

    render(
      <GettingStartedModal
        onClose={() => undefined}
        onDontShowAgain={() => undefined}
        showOnStartup
      />,
    );

    fireEvent.click(screen.getByRole('button', { name: 'Recursos' }));

    expect(screen.getByText('Wiki y documentacion')).toBeInTheDocument();
    expect(screen.getByText('Aprende a crear workflows y usar nodos')).toBeInTheDocument();
    expect(screen.getByText('Repositorio de GitHub')).toBeInTheDocument();
    expect(screen.getByText('Codigo fuente, releases e incidencias')).toBeInTheDocument();
    expect(screen.getByText('Reportar una incidencia')).toBeInTheDocument();
    expect(screen.getByText('Reportes de bugs y solicitudes de funciones')).toBeInTheDocument();
    expect(screen.getByText('Ayuda en la app')).toBeInTheDocument();
    expect(screen.getByText('Abrir el panel Ayuda y Wiki')).toBeInTheDocument();
  });

  it('keeps the getting-started shell copy behind i18n keys', () => {
    const source = readFileSync(resolve(__dirname, '../components/modals/GettingStartedModal.tsx'), 'utf8');

    [
      'gettingStarted.title',
      'gettingStarted.tabs.welcome',
      'gettingStarted.tabs.news',
      'gettingStarted.tabs.resources',
      'gettingStarted.welcomeIntro',
      'gettingStarted.welcomeBuildShare',
      'gettingStarted.resources.wikiTitle',
      'gettingStarted.resources.githubDescription',
      'gettingStarted.resources.issueTitle',
      'gettingStarted.resources.inAppHelpDescription',
      'gettingStarted.hideOnStartup',
      'common.close',
    ].forEach(key => expect(source).toContain(key));

    [
      "label: 'Welcome'",
      'label: "What\\\'s New"',
      "label: 'Resources'",
      'aria-label="Getting started"',
      '>Getting Started<',
      'Welcome to <strong>BioNodulo</strong>',
      'Build, run, and share reproducible pipelines using a node-based canvas.',
      'Wiki & Documentation',
      'Learn how to build workflows and use nodes',
      'GitHub Repository',
      'Source code, releases, and issues',
      'Report an Issue',
      'Bug reports and feature requests',
      'In-App Help',
      'Open the Help & Wiki panel',
      '>Hide on startup<',
      '>Close<',
    ].forEach(text => expect(source).not.toContain(text));
  });
});
