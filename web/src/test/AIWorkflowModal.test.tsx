import { fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { apiGet, apiPost } from '../api/client';
import type { Workflow } from '../types';

vi.mock('../api/client', () => {
  class ApiError extends Error {}

  return {
    ApiError,
    apiGet: vi.fn(() => Promise.resolve({ skills: [] })),
    apiPost: vi.fn((_path: string, _json?: unknown, init?: { signal?: AbortSignal }) =>
      new Promise((_resolve, reject) => {
        if (init?.signal?.aborted) {
          reject(new DOMException('Aborted', 'AbortError'));
          return;
        }
        init?.signal?.addEventListener(
          'abort',
          () => reject(new DOMException('Aborted', 'AbortError')),
          { once: true },
        );
      }),
    ),
  };
});

const loggingMock = vi.hoisted(() => ({
  logError: vi.fn(),
}));

vi.mock('../state/logging', () => loggingMock);

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

function workflow(partial: Partial<Workflow> = {}): Workflow {
  return {
    id: partial.id,
    version: partial.version ?? '2.0',
    app: partial.app ?? 'BioNodulo',
    name: partial.name ?? 'Test workflow',
    description: partial.description ?? '',
    nodes: partial.nodes ?? [],
    edges: partial.edges ?? [],
    groups: partial.groups ?? [],
    outputs: partial.outputs ?? {},
    environment: partial.environment,
    dependencies: partial.dependencies,
  };
}

describe('AIWorkflowModal i18n', () => {
  beforeEach(() => {
    storage.clear();
    loggingMock.logError.mockReset();
    vi.stubGlobal('localStorage', localStorageStub);
    Element.prototype.scrollIntoView = vi.fn();
  });

  afterEach(async () => {
    const { setLanguage } = await import('../i18n');
    await setLanguage('en');
    storage.clear();
    vi.unstubAllGlobals();
  });

  it('renders shell and session chrome from the active locale', async () => {
    const { default: AIWorkflowModal } = await import('../components/modals/AIWorkflowModal');
    const { setLanguage } = await import('../i18n');

    await setLanguage('es');

    render(
      <AIWorkflowModal
        workflow={workflow()}
        onClose={() => undefined}
        onApplyWorkflow={() => undefined}
      />,
    );

    expect(screen.getByText('Asistente de flujos de trabajo con IA')).toBeInTheDocument();
    expect(screen.getByText('Hola! Puedo ayudarte a crear flujos de trabajo de bioinformatica. En que tipo de analisis estas trabajando?')).toBeInTheDocument();
    expect(screen.queryByText('Asistente de workflows con IA')).not.toBeInTheDocument();
    expect(screen.queryByText(/crear workflows de bioinformatica/i)).not.toBeInTheDocument();
    expect(screen.getByTitle('Sesiones')).toBeInTheDocument();
    expect(screen.getByTitle('Cerrar')).toBeInTheDocument();

    fireEvent.click(screen.getByTitle('Sesiones'));

    expect(screen.getByText('Sesiones de chat')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Nuevo/ })).toBeInTheDocument();
    expect(screen.getByText('Nuevo chat')).toBeInTheDocument();
    expect(screen.getByText('1 mensaje')).toBeInTheDocument();
    expect(screen.getByTitle('Cambiar nombre')).toBeInTheDocument();
    expect(screen.getByTitle('Eliminar')).toBeInTheDocument();
  });

  it('renders quick prompts and input controls from the active locale', async () => {
    const { default: AIWorkflowModal } = await import('../components/modals/AIWorkflowModal');
    const { setLanguage } = await import('../i18n');

    await setLanguage('es');

    render(
      <AIWorkflowModal
        workflow={workflow()}
        onClose={() => undefined}
        onApplyWorkflow={() => undefined}
      />,
    );

    expect(screen.getByRole('button', { name: 'Resumir mi flujo de trabajo' })).toHaveAttribute(
      'title',
      'Usa get_workflow_summary y dime que hace mi flujo de trabajo actual en 3-4 frases.',
    );
    expect(screen.getByRole('button', { name: 'Que fallo?' })).toHaveAttribute(
      'title',
      'Usa explain_last_failure y dime por que fallo la ejecucion mas reciente y como solucionarlo.',
    );
    expect(screen.getByRole('button', { name: 'Buscar QC faltante' })).toHaveAttribute(
      'title',
      'Revisa mi flujo de trabajo y sugiere pasos de control de calidad que podrian faltar.',
    );
    expect(screen.getByRole('button', { name: 'Sugerir siguiente paso' })).toHaveAttribute(
      'title',
      'Segun el flujo de trabajo actual, que siguiente paso de analisis deberia agregar?',
    );
    expect(screen.getByTitle('Adjuntar archivo')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('Pregunta sobre flujos de trabajo... (pega imagenes directamente)')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Enviar' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Resumir mi workflow' })).not.toBeInTheDocument();
    expect(screen.queryByPlaceholderText('Pregunta sobre workflows... (pega imagenes directamente)')).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Resumir mi flujo de trabajo' }));

    expect(screen.getByDisplayValue('Usa get_workflow_summary y dime que hace mi flujo de trabajo actual en 3-4 frases.')).toBeInTheDocument();
    expect(screen.queryByDisplayValue('Usa get_workflow_summary y dime que hace mi workflow actual en 3-4 frases.')).not.toBeInTheDocument();
  });

  it('renders assistant step controls from the active locale', async () => {
    const { default: AIWorkflowModal } = await import('../components/modals/AIWorkflowModal');
    const { setLanguage } = await import('../i18n');
    const onApplyWorkflow = vi.fn();

    await setLanguage('es');
    storage.set('bionodulo-ai-sessions', JSON.stringify([{
      id: 'session-1',
      name: 'Run help',
      createdAt: Date.now(),
      turns: [{
        role: 'assistant',
        model: 'test-model',
        steps: [
          { type: 'thinking', content: 'Reasoning text' },
          { type: 'tool_result', name: 'get_workflow_summary', content: '', result: { ok: true } },
          { type: 'propose_changes', content: '', workflow: workflow({ name: 'Suggested' }) },
        ],
      }],
    }]));

    render(
      <AIWorkflowModal
        workflow={workflow()}
        onClose={() => undefined}
        onApplyWorkflow={onApplyWorkflow}
      />,
    );

    const reasoningToggle = screen.getByRole('button', { name: /Mostrar razonamiento/ });
    expect(reasoningToggle).toBeInTheDocument();
    fireEvent.click(reasoningToggle);
    expect(screen.getByRole('button', { name: /Ocultar razonamiento/ })).toBeInTheDocument();
    expect(screen.getByText('get_workflow_summary resultado')).toBeInTheDocument();
    expect(screen.getByText('Cambios propuestos')).toBeInTheDocument();
    expect(screen.getByText('La IA sugiere modificar el flujo de trabajo.')).toBeInTheDocument();
    expect(screen.queryByText('La IA sugiere modificar el workflow.')).not.toBeInTheDocument();
    const applyButton = screen.getByRole('button', { name: 'Aplicar cambios' });
    expect(applyButton).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Copiar al lienzo/ })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Previsualizar JSON' })).toBeInTheDocument();

    fireEvent.click(applyButton);

    expect(onApplyWorkflow).toHaveBeenCalledWith(expect.objectContaining({ name: 'Suggested' }));
    expect(await screen.findByText('Flujo de trabajo aplicado correctamente. Dime si necesitas algun ajuste.')).toBeInTheDocument();
    expect(screen.queryByText('Workflow aplicado correctamente. Dime si necesitas algun ajuste.')).not.toBeInTheDocument();
  });

  it('applies current workflow metadata when proposed workflow omits workflow data', async () => {
    const { default: AIWorkflowModal } = await import('../components/modals/AIWorkflowModal');
    const onApplyWorkflow = vi.fn();
    const activeWorkflow = workflow({
      id: 'wf-active',
      version: '2.5',
      app: 'BioNodulo',
      name: 'RNA QC Pipeline',
      description: 'Current tab description',
      nodes: [{ id: 'existing-node', type: 'fastqc', x: 0, y: 0 }],
      edges: [],
    });

    vi.mocked(apiPost).mockResolvedValueOnce({
      model: 'test-model',
      steps: [{
        type: 'propose_changes',
        content: '',
        workflow: {
          nodes: [{ id: 'new-node', type: 'multiqc', x: 10, y: 10 }],
          edges: [],
        },
      }],
    });

    render(
      <AIWorkflowModal
        workflow={activeWorkflow}
        onClose={() => undefined}
        onApplyWorkflow={onApplyWorkflow}
      />,
    );

    fireEvent.change(screen.getByPlaceholderText('Ask about workflows... (Paste images directly)'), {
      target: { value: 'Add MultiQC' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Send' }));
    fireEvent.click(await screen.findByRole('button', { name: 'Apply Changes' }));

    expect(onApplyWorkflow).toHaveBeenCalledWith(expect.objectContaining({
      id: 'wf-active',
      version: '2.5',
      app: 'BioNodulo',
      name: 'RNA QC Pipeline',
      description: 'Current tab description',
      nodes: [expect.objectContaining({ id: 'new-node', type: 'multiqc' })],
      edges: [],
    }));
    expect(onApplyWorkflow).not.toHaveBeenCalledWith(expect.objectContaining({ name: 'Untitled' }));
  });

  it('applies the active locale untitled fallback when no workflow name is available', async () => {
    const { default: AIWorkflowModal } = await import('../components/modals/AIWorkflowModal');
    const { setLanguage } = await import('../i18n');
    const onApplyWorkflow = vi.fn();

    await setLanguage('es');
    vi.mocked(apiPost).mockResolvedValueOnce({
      model: 'test-model',
      steps: [{
        type: 'propose_changes',
        content: '',
        workflow: {
          nodes: [],
          edges: [],
        },
      }],
    });

    render(
      <AIWorkflowModal
        workflow={workflow({ name: '' })}
        onClose={() => undefined}
        onApplyWorkflow={onApplyWorkflow}
      />,
    );

    fireEvent.change(screen.getByPlaceholderText('Pregunta sobre flujos de trabajo... (pega imagenes directamente)'), {
      target: { value: 'Crear workflow sin nombre' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Enviar' }));
    fireEvent.click(await screen.findByRole('button', { name: 'Aplicar cambios' }));

    expect(onApplyWorkflow).toHaveBeenCalledWith(expect.objectContaining({ name: 'Sin titulo' }));
    expect(onApplyWorkflow).not.toHaveBeenCalledWith(expect.objectContaining({ name: 'Untitled' }));
  });

  it('keeps explicit proposed workflow metadata from the AI response', async () => {
    const { default: AIWorkflowModal } = await import('../components/modals/AIWorkflowModal');
    const onApplyWorkflow = vi.fn();

    vi.mocked(apiPost).mockResolvedValueOnce({
      model: 'test-model',
      steps: [{
        type: 'propose_changes',
        content: '',
        workflow: {
          id: 'wf-proposed',
          version: '3.0',
          app: 'External Builder',
          name: 'AI Renamed Workflow',
          description: 'AI generated metadata',
          nodes: [],
          edges: [],
        },
      }],
    });

    render(
      <AIWorkflowModal
        workflow={workflow({ id: 'wf-active', name: 'RNA QC Pipeline' })}
        onClose={() => undefined}
        onApplyWorkflow={onApplyWorkflow}
      />,
    );

    fireEvent.change(screen.getByPlaceholderText('Ask about workflows... (Paste images directly)'), {
      target: { value: 'Rename it' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Send' }));
    fireEvent.click(await screen.findByRole('button', { name: 'Apply Changes' }));

    expect(onApplyWorkflow).toHaveBeenCalledWith(expect.objectContaining({
      id: 'wf-proposed',
      version: '3.0',
      app: 'External Builder',
      name: 'AI Renamed Workflow',
      description: 'AI generated metadata',
    }));
  });

  it('renders sending controls from the active locale', async () => {
    const { default: AIWorkflowModal } = await import('../components/modals/AIWorkflowModal');
    const { setLanguage } = await import('../i18n');

    await setLanguage('es');

    render(
      <AIWorkflowModal
        workflow={workflow()}
        onClose={() => undefined}
        onApplyWorkflow={() => undefined}
      />,
    );

    fireEvent.change(screen.getByPlaceholderText('Pregunta sobre flujos de trabajo... (pega imagenes directamente)'), {
      target: { value: 'Ayudame con QC' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Enviar' }));

    expect(await screen.findByText('Pensando...')).toBeInTheDocument();
    expect(screen.getAllByTitle('Detener generacion')).toHaveLength(2);
    expect(screen.getAllByRole('button', { name: /Detener/ })).toHaveLength(2);
  });

  it('renders stopped assistant note from the active locale', async () => {
    const { default: AIWorkflowModal } = await import('../components/modals/AIWorkflowModal');
    const { setLanguage } = await import('../i18n');

    await setLanguage('es');

    render(
      <AIWorkflowModal
        workflow={workflow()}
        onClose={() => undefined}
        onApplyWorkflow={() => undefined}
      />,
    );

    fireEvent.change(screen.getByPlaceholderText('Pregunta sobre flujos de trabajo... (pega imagenes directamente)'), {
      target: { value: 'Ayudame con QC' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Enviar' }));

    const stopButtons = await screen.findAllByRole('button', { name: /Detener/ });
    fireEvent.click(stopButtons[0]);

    expect(await screen.findByText('Generacion detenida por el usuario.')).toBeInTheDocument();
  });

  it('renders regenerate controls from the active locale', async () => {
    const { default: AIWorkflowModal } = await import('../components/modals/AIWorkflowModal');
    const { setLanguage } = await import('../i18n');

    await setLanguage('es');
    storage.set('bionodulo-ai-sessions', JSON.stringify([{
      id: 'session-1',
      name: 'Run help',
      createdAt: Date.now(),
      turns: [
        { role: 'user', content: 'Revisa mi workflow' },
        { role: 'assistant', content: 'Respuesta previa' },
      ],
    }]));

    render(
      <AIWorkflowModal
        workflow={workflow()}
        onClose={() => undefined}
        onApplyWorkflow={() => undefined}
      />,
    );

    expect(screen.getByRole('button', { name: /Regenerar/ })).toHaveAttribute(
      'title',
      'Volver a ejecutar la pregunta anterior',
    );
  });

  it('renders pasted canvas node prompt from the active locale', async () => {
    const { default: AIWorkflowModal } = await import('../components/modals/AIWorkflowModal');
    const { setLanguage } = await import('../i18n');

    await setLanguage('es');

    render(
      <AIWorkflowModal
        workflow={workflow()}
        onClose={() => undefined}
        onApplyWorkflow={() => undefined}
      />,
    );

    fireEvent.paste(screen.getByPlaceholderText('Pregunta sobre flujos de trabajo... (pega imagenes directamente)'), {
      clipboardData: {
        getData: (type: string) =>
          type === 'text'
            ? 'bionodulo_clipboard:{"nodes":[{"type":"fastqc"},{"type":"multiqc"}],"edges":[{"from":"a","to":"b"}]}'
            : '',
        items: [],
      },
    });

    expect(await screen.findByDisplayValue('Aqui estan mis nodos seleccionados (2 nodos, 1 arista): fastqc, multiqc')).toBeInTheDocument();
  });

  it('renders an honest error turn (never canned text) when the backend fails', async () => {
    const { default: AIWorkflowModal } = await import('../components/modals/AIWorkflowModal');
    const { setLanguage } = await import('../i18n');

    await setLanguage('es');
    const chatError = new Error('offline');
    vi.mocked(apiPost).mockRejectedValueOnce(chatError);

    render(
      <AIWorkflowModal
        workflow={workflow()}
        onClose={() => undefined}
        onApplyWorkflow={() => undefined}
      />,
    );

    fireEvent.change(screen.getByPlaceholderText('Pregunta sobre flujos de trabajo... (pega imagenes directamente)'), {
      target: { value: 'rna workflow' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Enviar' }));

    expect(await screen.findByText('La solicitud al asistente fallo: offline')).toBeInTheDocument();
    expect(screen.getByText('Revisa tu conexion o inicia sesion, luego intentalo de nuevo.')).toBeInTheDocument();
    expect(loggingMock.logError).toHaveBeenCalledWith('aiWorkflow.chat', chatError);
    // The canned local responses must never mask a backend failure.
    expect(screen.queryByText(/Para RNA-Seq, recomiendo/)).not.toBeInTheDocument();
  });

  it('logs unexpected chat failures and renders them as error turns too', async () => {
    const { default: AIWorkflowModal } = await import('../components/modals/AIWorkflowModal');
    const thrownValue = 'unexpected-chat-failure';

    vi.mocked(apiPost).mockRejectedValueOnce(thrownValue);

    render(
      <AIWorkflowModal
        workflow={workflow()}
        onClose={() => undefined}
        onApplyWorkflow={() => undefined}
      />,
    );

    fireEvent.change(screen.getByPlaceholderText('Ask about workflows... (Paste images directly)'), {
      target: { value: 'rna workflow' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Send' }));

    expect(await screen.findByText('The assistant request failed: unexpected-chat-failure')).toBeInTheDocument();
    expect(screen.getByText('Check your connection or sign-in status, then try again.')).toBeInTheDocument();
    expect(loggingMock.logError).toHaveBeenCalledWith('aiWorkflow.chat.fallback', thrownValue);
    expect(screen.queryByText(/For RNA-Seq, I recommend/)).not.toBeInTheDocument();
  });

  it('suggests skills for slash commands and inserts the selection without sending', async () => {
    const { default: AIWorkflowModal } = await import('../components/modals/AIWorkflowModal');

    // Call history accumulates across tests in this file — reset so the
    // "did not send" assertion below only covers this test.
    vi.mocked(apiPost).mockClear();
    vi.mocked(apiGet).mockResolvedValue({
      skills: [
        { name: 'qc-report', description: 'Aggregate QC metrics', source: 'user' },
        { name: 'rnaseq', description: 'RNA-seq pipeline helper', source: 'bundled' },
      ],
    });

    render(
      <AIWorkflowModal
        workflow={workflow()}
        onClose={() => undefined}
        onApplyWorkflow={() => undefined}
      />,
    );

    const chatInput = screen.getByPlaceholderText('Ask about workflows... (Paste images directly)');
    fireEvent.change(chatInput, { target: { value: '/' } });

    // Both skills listed once the fetch resolves.
    expect(await screen.findByText('/rnaseq')).toBeInTheDocument();
    expect(screen.getByText('/qc-report')).toBeInTheDocument();
    expect(screen.getByRole('listbox')).toBeInTheDocument();

    // Prefix filtering narrows the list.
    fireEvent.change(chatInput, { target: { value: '/rn' } });
    expect(screen.getByText('/rnaseq')).toBeInTheDocument();
    expect(screen.queryByText('/qc-report')).not.toBeInTheDocument();

    // Enter inserts the command; it does NOT send the message.
    fireEvent.keyDown(chatInput, { key: 'Enter' });
    expect(chatInput).toHaveValue('/rnaseq ');
    expect(screen.queryByRole('listbox')).not.toBeInTheDocument();
    expect(apiPost).not.toHaveBeenCalled();

    // Typing a normal message hides the dropdown for good.
    fireEvent.change(chatInput, { target: { value: 'hello' } });
    expect(screen.queryByRole('listbox')).not.toBeInTheDocument();
  });

  it('renders the missing model fallback from the active locale', async () => {
    const { default: AIWorkflowModal } = await import('../components/modals/AIWorkflowModal');
    const { setLanguage } = await import('../i18n');

    await setLanguage('es');
    vi.mocked(apiPost).mockResolvedValueOnce({
      steps: [{ type: 'reply', content: 'Listo' }],
    });

    render(
      <AIWorkflowModal
        workflow={workflow()}
        onClose={() => undefined}
        onApplyWorkflow={() => undefined}
      />,
    );

    fireEvent.change(screen.getByPlaceholderText('Pregunta sobre flujos de trabajo... (pega imagenes directamente)'), {
      target: { value: 'Ayudame con QC' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Enviar' }));

    expect(await screen.findByText('Modelo desconocido')).toBeInTheDocument();
    expect(screen.queryByText('unknown')).not.toBeInTheDocument();
  });

  it('keeps AI workflow shell copy behind i18n keys', () => {
    const source = readFileSync(resolve(__dirname, '../components/modals/AIWorkflowModal.tsx'), 'utf8');

    [
      'aiWorkflow.title',
      'aiWorkflow.defaultSessionName',
      'aiWorkflow.greeting',
      'aiWorkflow.sessions.openTitle',
      'aiWorkflow.sessions.menuTitle',
      'aiWorkflow.sessions.newSession',
      'aiWorkflow.sessions.messageCount',
      'aiWorkflow.quickPrompts.summary.label',
      'aiWorkflow.quickPrompts.summary.prompt',
      'aiWorkflow.quickPrompts.failure.label',
      'aiWorkflow.quickPrompts.failure.prompt',
      'aiWorkflow.quickPrompts.missingQc.label',
      'aiWorkflow.quickPrompts.missingQc.prompt',
      'aiWorkflow.quickPrompts.nextStep.label',
      'aiWorkflow.quickPrompts.nextStep.prompt',
      'aiWorkflow.input.attachFileTitle',
      'aiWorkflow.input.placeholder',
      'aiWorkflow.input.send',
      'aiWorkflow.input.pastedNodes.prompt',
      'aiWorkflow.input.pastedNodes.nodeLabel',
      'aiWorkflow.input.pastedNodes.edgeSuffix',
      'aiWorkflow.input.pastedNodes.edgeLabel',
      'aiWorkflow.steps.showReasoning',
      'aiWorkflow.steps.hideReasoning',
      'aiWorkflow.steps.toolResult',
      'aiWorkflow.steps.proposedChanges',
      'aiWorkflow.steps.proposalFallbackDescription',
      'aiWorkflow.steps.applyChanges',
      'aiWorkflow.steps.copyToCanvas',
      'aiWorkflow.steps.previewJson',
      'aiWorkflow.steps.applySuccess',
      'aiWorkflow.generation.thinking',
      'aiWorkflow.generation.stopTitle',
      'aiWorkflow.generation.stop',
      'aiWorkflow.generation.stopped',
      'aiWorkflow.generation.regenerateTitle',
      'aiWorkflow.generation.regenerate',
      'aiWorkflow.modelUnknown',
      'aiWorkflow.error.backend',
      'aiWorkflow.error.hint',
      'aiWorkflow.popout.openTitle',
      'aiWorkflow.popout.dockTitle',
      'aiWorkflow.skills.listLabel',
      'common.untitled',
      'common.close',
      'common.rename',
      'common.delete',
    ].forEach(key => expect(source).toContain(key));

    [
      'AI Workflow Assistant',
      "title=\"Sessions\"",
      'Chat Sessions',
      'New Chat',
      '> New<',
      'Hello! I can help you build bioinformatics workflows.',
      '${s.turns.length} msgs',
      'title="Close"',
      'title="Rename"',
      'title="Delete"',
      'Summarize my workflow',
      'Use get_workflow_summary and tell me what my current workflow does in 3-4 sentences.',
      'What went wrong?',
      'Use explain_last_failure and tell me why the most recent run failed and how to fix it.',
      'Find missing QC',
      'Look at my workflow and suggest any quality-control steps I might be missing.',
      'Suggest next step',
      'Based on the current workflow, what is the next analysis step I should add?',
      'title="Attach file"',
      'placeholder="Ask about workflows... (Paste images directly)"',
      '>Send<',
      'Here are my selected nodes',
      '${nodeCount} nodes',
      '${edgeCount} edges',
      'Hide reasoning',
      'Show reasoning',
      '${step.name} result',
      'Proposed changes',
      'The AI suggests modifying the workflow.',
      'Apply Changes',
      'Copy to Canvas',
      'Preview JSON',
      'Workflow applied successfully! Let me know if you need any adjustments.',
      'Thinking...',
      'Stop generating',
      '>Stop<',
      '_Stopped by user._',
      'Re-run the previous question',
      '↻ Regenerate',
      'The assistant request failed',
      'Open in window',
      'Dock to drawer',
      "model: data.model || 'unknown'",
      'For RNA-Seq, I recommend',
      'For variant calling:',
      'For assembly:',
      'For metagenomics:',
      'For ChIP-Seq:',
      'For QC:',
      'For phylogenetics:',
      'For single-cell:',
      'For plotting:',
      'I can help you design bioinformatics workflows!',
      "'Untitled'",
    ].forEach(text => expect(source).not.toContain(text));
  });
});
