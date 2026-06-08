import { fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

const storage = new Map<string, string>();
const loggingMock = vi.hoisted(() => ({
  logError: vi.fn(),
}));

vi.mock('../state/logging', () => loggingMock);

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
    loggingMock.logError.mockReset();
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
    expect(screen.getByText(/constructor visual de flujos de trabajo para bioinformatica/)).toBeInTheDocument();
    expect(screen.queryByText(/constructor visual de workflows para bioinformatica/)).not.toBeInTheDocument();
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
    expect(screen.getByText('Aprende a crear flujos de trabajo y usar nodos')).toBeInTheDocument();
    expect(screen.queryByText('Aprende a crear workflows y usar nodos')).not.toBeInTheDocument();
    expect(screen.getByText('Repositorio de GitHub')).toBeInTheDocument();
    expect(screen.getByText('Codigo fuente, releases e incidencias')).toBeInTheDocument();
    expect(screen.getByText('Reportar una incidencia')).toBeInTheDocument();
    expect(screen.getByText('Reportes de bugs y solicitudes de funciones')).toBeInTheDocument();
    expect(screen.getByText('Ayuda en la app')).toBeInTheDocument();
    expect(screen.getByText('Abrir el panel Ayuda y Wiki')).toBeInTheDocument();
  });

  it('renders getting-started quick-start guidance from the active locale', async () => {
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

    const expectFullText = (text: string) => {
      expect(screen.getByText((_, node) => node?.textContent === text)).toBeInTheDocument();
    };

    expect(screen.getByText('Inicio rapido')).toBeInTheDocument();
    expectFullText('Abre el panel Plantillas (Ctrl+3) para cargar un pipeline integrado.');
    expect(screen.getByText('Haz doble clic en un nodo para configurar sus parametros.')).toBeInTheDocument();
    expectFullText('Presiona Ctrl+R para validar y ejecutar tu flujo de trabajo.');
    expectFullText('Mira los registros en tiempo real en la Consola (Ctrl+`).');
    expectFullText('Consejo: usa el Asistente de IA (Ctrl+Shift+A) para generar flujos de trabajo desde descripciones en lenguaje natural.');
    expect(screen.queryByText((_, node) => node?.textContent === 'Presiona Ctrl+R para validar y ejecutar tu workflow.')).not.toBeInTheDocument();
    expect(screen.queryByText((_, node) => node?.textContent === 'Consejo: usa el Asistente de IA (Ctrl+Shift+A) para generar workflows desde descripciones en lenguaje natural.')).not.toBeInTheDocument();
  });

  it('renders getting-started recents and news status from the active locale', async () => {
    const { default: GettingStartedModal } = await import('../components/modals/GettingStartedModal');
    const { setLanguage } = await import('../i18n');

    await setLanguage('es');
    const olderOpenedAt = new Date('2026-05-03T09:30:00.000Z').getTime();
    storage.set('bionodulo.recentWorkflows', JSON.stringify([
      {
        id: 'recent-1',
        name: 'RNA QC',
        source: 'template',
        openedAt: Date.now() - 2 * 60 * 1000,
        nodeCount: 3,
        tags: ['rna'],
      },
      {
        id: 'recent-2',
        name: 'Older workflow',
        source: 'manual',
        openedAt: olderOpenedAt,
        nodeCount: 1,
        tags: [],
      },
    ]));
    storage.set('bionodulo.releases.cache', JSON.stringify({
      fetchedAt: Date.now(),
      releases: [{
        version: 'BioNodulo 3.0',
        date: '2026-01-01',
        url: 'https://example.com/release',
        items: ['Cached release item'],
      }],
    }));

    render(
      <GettingStartedModal
        onClose={() => undefined}
        onDontShowAgain={() => undefined}
        onOpenRecent={() => undefined}
        showOnStartup
      />,
    );

    expect(screen.getByText('Flujos de trabajo recientes')).toBeInTheDocument();
    expect(screen.queryByText('Workflows recientes')).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Todo' })).toBeInTheDocument();
    expect(screen.getByTitle('Abrir RNA QC')).toBeInTheDocument();
    expect(screen.getByText((_, node) => node?.textContent === 'Plantilla - 3 nodos - hace 2 min')).toBeInTheDocument();
    expect(screen.getByTitle('Abrir Older workflow')).toBeInTheDocument();
    expect(screen.getByText((_, node) => node?.textContent === `Manual - 1 nodo - ${new Date(olderOpenedAt).toLocaleDateString('es')}`)).toBeInTheDocument();
    expect(screen.queryByText((_, node) => node?.textContent === `Manual - 1 nodo - ${new Date(olderOpenedAt).toLocaleDateString()}`)).not.toBeInTheDocument();
    expect(screen.getAllByTitle('Editar etiquetas')).toHaveLength(2);
    expect(screen.getAllByTitle('Olvidar esta entrada')).toHaveLength(2);

    fireEvent.click(screen.getAllByTitle('Editar etiquetas')[0]);

    expect(screen.getByLabelText('Editar etiquetas (separadas por comas)')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('etiqueta1, etiqueta2')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Novedades' }));

    expect(screen.getByText('Desde releases de GitHub - 1 entrada')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Actualizar' })).toHaveAttribute('title', 'Volver a cargar notas de version');
    expect(screen.getByRole('link', { name: 'Ver en GitHub' })).toHaveAttribute('href', 'https://example.com/release');
    expect(screen.getByText('Cached release item')).toBeInTheDocument();
    expect(screen.queryByTitle('Volver a cargar release notes')).not.toBeInTheDocument();
  });

  it('renders bundled release notes from the active locale when live releases fail', async () => {
    const { default: GettingStartedModal } = await import('../components/modals/GettingStartedModal');
    const { default: i18n, setLanguage } = await import('../i18n');

    await setLanguage('es');
    const releaseError = new TypeError('offline');
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(releaseError));

    render(
      <GettingStartedModal
        onClose={() => undefined}
        onDontShowAgain={() => undefined}
        showOnStartup
      />,
    );

    fireEvent.click(screen.getByRole('button', { name: 'Novedades' }));

    expect(await screen.findByText('Modo sin conexion - mostrando changelog incluido')).toBeInTheDocument();
    expect(loggingMock.logError).toHaveBeenCalledWith('gettingStarted.releases.fetch', releaseError);
    expect(i18n.t('gettingStarted.changelog.v2.items.commandPalette')).toBe('Paleta de comandos, atajos, notificaciones, dialogos y flujo de paneles de BioNodulo');
    expect(i18n.t('gettingStarted.changelog.v2.items.templates')).toBe('Redisenio de galeria de plantillas con previsualizaciones, ranking de busqueda, etiquetas y resumenes de pasos del flujo de trabajo');
    expect(i18n.t('gettingStarted.changelog.alpha15.items.isolatedEnvironments')).toBe('Entornos aislados por flujo de trabajo con entornos direccionados por contenido');
    expect(i18n.t('gettingStarted.changelog.alpha11.items.workflowExport')).toBe('Exportacion de flujos de trabajo a Snakemake, NextFlow, CWL y Galaxy');
    expect(i18n.t('gettingStarted.changelog.alpha10.items.workflowCanvas')).toBe('Lienzo de flujos de trabajo con nodos bioinformaticos personalizados');
    expect(screen.getByText('Paleta de comandos, atajos, notificaciones, dialogos y flujo de paneles de BioNodulo')).toBeInTheDocument();
    expect(screen.getByText('Redisenio de galeria de plantillas con previsualizaciones, ranking de busqueda, etiquetas y resumenes de pasos del flujo de trabajo')).toBeInTheDocument();
    expect(screen.getByText('Redisenio completo del panel de entornos con migracion a pixi')).toBeInTheDocument();
    expect(screen.getByText('Entornos aislados por flujo de trabajo con entornos direccionados por contenido')).toBeInTheDocument();
    expect(screen.getByText('Soporte HPC para sistemas de colas (SLURM, PBS, SGE)')).toBeInTheDocument();
    expect(screen.getByText('Asistente de IA con llamadas a herramientas para construir flujos de trabajo')).toBeInTheDocument();
    expect(screen.getByText('Exportacion de flujos de trabajo a Snakemake, NextFlow, CWL y Galaxy')).toBeInTheDocument();
    expect(screen.queryByText('Asistente de IA con llamadas a herramientas para construir workflows')).not.toBeInTheDocument();
    expect(screen.getByText('Panel superpuesto de monitor de hardware')).toBeInTheDocument();
    expect(screen.getByText('Version inicial de BioNodulo v2')).toBeInTheDocument();
    expect(screen.getByText('Lienzo de flujos de trabajo con nodos bioinformaticos personalizados')).toBeInTheDocument();
    expect(screen.queryByText('Redisenio de galeria de plantillas con previsualizaciones, ranking de busqueda, etiquetas y resumenes de pasos del workflow')).not.toBeInTheDocument();
    expect(screen.queryByText('Entornos aislados por workflow con entornos direccionados por contenido')).not.toBeInTheDocument();
    expect(screen.queryByText('Exportacion de workflows a Snakemake, NextFlow, CWL y Galaxy')).not.toBeInTheDocument();
    expect(screen.queryByText('Lienzo de workflows con nodos bioinformaticos personalizados')).not.toBeInTheDocument();
    expect(screen.queryByText('BioNodulo command palette, keybindings, toasts, dialogs, and panel workflow')).not.toBeInTheDocument();
    expect(screen.queryByText(/toasts/)).not.toBeInTheDocument();
    expect(screen.queryByText(/Rework/)).not.toBeInTheDocument();
    expect(screen.queryByText(/backend/)).not.toBeInTheDocument();
    expect(screen.queryByText(/Overlay/)).not.toBeInTheDocument();
  });

  it('renders missing GitHub release names from the active locale', async () => {
    const { default: GettingStartedModal } = await import('../components/modals/GettingStartedModal');
    const { setLanguage } = await import('../i18n');

    await setLanguage('es');
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve([{
        published_at: '2026-02-01T00:00:00Z',
        body: '- Release body item',
      }]),
    }));

    render(
      <GettingStartedModal
        onClose={() => undefined}
        onDontShowAgain={() => undefined}
        showOnStartup
      />,
    );

    fireEvent.click(screen.getByRole('button', { name: 'Novedades' }));

    expect(await screen.findByText('Sin release')).toBeInTheDocument();
    expect(screen.queryByText('unreleased')).not.toBeInTheDocument();
  });

  it('keeps the getting-started shell copy behind i18n keys', () => {
    const source = readFileSync(resolve(__dirname, '../components/modals/GettingStartedModal.tsx'), 'utf8');

    expect(source).toContain("import Dialog from '../ui/Dialog';");
    expect(source).toContain('<Dialog');
    expect(source).not.toContain("import { useFocusTrap } from '../../hooks/ui';");
    expect(source).not.toContain('<div className="modal-overlay"');
    expect(source).not.toContain('role="dialog"');

    [
      'gettingStarted.title',
      'gettingStarted.tabs.welcome',
      'gettingStarted.tabs.news',
      'gettingStarted.tabs.resources',
      'gettingStarted.welcomeIntro',
      'gettingStarted.welcomeBuildShare',
      'gettingStarted.quickStartTitle',
      'gettingStarted.quickStartTemplatesPrefix',
      'gettingStarted.quickStartTemplatesPanel',
      'gettingStarted.quickStartTemplatesShortcutPrefix',
      'gettingStarted.quickStartTemplatesSuffix',
      'gettingStarted.quickStartConfigureNode',
      'gettingStarted.quickStartRunPrefix',
      'gettingStarted.quickStartRunSuffix',
      'gettingStarted.quickStartConsolePrefix',
      'gettingStarted.quickStartConsole',
      'gettingStarted.quickStartConsoleSuffix',
      'gettingStarted.aiTipPrefix',
      'gettingStarted.aiAssistant',
      'gettingStarted.aiTipSuffix',
      'gettingStarted.recentsTitle',
      'gettingStarted.recentsAll',
      'gettingStarted.recentOpenTitle',
      'gettingStarted.recentMeta',
      'gettingStarted.recentSource.template',
      'gettingStarted.recentNodeCount',
      'gettingStarted.recentMinutesAgo',
      'gettingStarted.recentEditTagsTitle',
      'gettingStarted.recentForgetTitle',
      'gettingStarted.newsLiveStatus',
      'gettingStarted.newsFetching',
      'gettingStarted.newsOffline',
      'gettingStarted.newsBundled',
      'gettingStarted.newsRefetchTitle',
      'gettingStarted.newsViewOnGitHub',
      'gettingStarted.newsUnreleased',
      'gettingStarted.changelog.v2.items.commandPalette',
      'gettingStarted.changelog.alpha10.items.initialRelease',
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
      '>Quick Start<',
      'Open the <strong>Templates</strong> panel',
      'Double-click a node to configure its parameters.',
      'Press <kbd>Ctrl+R</kbd> to validate and run your workflow.',
      'Watch real-time logs in the <strong>Console</strong>',
      'Tip: Use the <strong>AI Assistant</strong>',
      '>Recent workflows<',
      '>All<',
      'title={`Open ${entry.name}`}',
      '${entry.nodeCount ?? 0} nodes',
      'placeholder="tag1, tag2"',
      'aria-label="Edit tags (comma-separated)"',
      'title="Edit tags"',
      'title="Forget this entry"',
      'Live from GitHub releases',
      'Fetching latest releases',
      'Offline mode',
      'setReleasesError(err instanceof Error ? err.message : String(err))',
      'Showing bundled changelog',
      "|| 'unreleased'",
      'BioNodulo command palette, keybindings, toasts, dialogs, and panel workflow',
      'Resizable/floating side panels with improved dock controls',
      'AI assistant with tool-calling for workflow building',
      'Initial BioNodulo v2 release',
      'title="Refetch release notes"',
      '>Refresh<',
      '>View on GitHub<',
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
