import { fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import type { Workflow } from '../types';

vi.mock('../api/client', () => {
  class ApiError extends Error {}

  return {
    ApiError,
    apiPost: vi.fn(() => new Promise(() => undefined)),
  };
});

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
    version: '2.0',
    app: 'BioNodulo',
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

    expect(screen.getByText('Asistente de workflows con IA')).toBeInTheDocument();
    expect(screen.getByText('Hola! Puedo ayudarte a crear workflows de bioinformatica. En que tipo de analisis estas trabajando?')).toBeInTheDocument();
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

    expect(screen.getByRole('button', { name: 'Resumir mi workflow' })).toHaveAttribute(
      'title',
      'Usa get_workflow_summary y dime que hace mi workflow actual en 3-4 frases.',
    );
    expect(screen.getByRole('button', { name: 'Que fallo?' })).toHaveAttribute(
      'title',
      'Usa explain_last_failure y dime por que fallo la ejecucion mas reciente y como solucionarlo.',
    );
    expect(screen.getByRole('button', { name: 'Buscar QC faltante' })).toHaveAttribute(
      'title',
      'Revisa mi workflow y sugiere pasos de control de calidad que podrian faltar.',
    );
    expect(screen.getByRole('button', { name: 'Sugerir siguiente paso' })).toHaveAttribute(
      'title',
      'Segun el workflow actual, que siguiente paso de analisis deberia agregar?',
    );
    expect(screen.getByTitle('Adjuntar archivo')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('Pregunta sobre workflows... (pega imagenes directamente)')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Enviar' })).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Resumir mi workflow' }));

    expect(screen.getByDisplayValue('Usa get_workflow_summary y dime que hace mi workflow actual en 3-4 frases.')).toBeInTheDocument();
  });

  it('renders assistant step controls from the active locale', async () => {
    const { default: AIWorkflowModal } = await import('../components/modals/AIWorkflowModal');
    const { setLanguage } = await import('../i18n');

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
        onApplyWorkflow={() => undefined}
      />,
    );

    const reasoningToggle = screen.getByRole('button', { name: /Mostrar razonamiento/ });
    expect(reasoningToggle).toBeInTheDocument();
    fireEvent.click(reasoningToggle);
    expect(screen.getByRole('button', { name: /Ocultar razonamiento/ })).toBeInTheDocument();
    expect(screen.getByText('get_workflow_summary resultado')).toBeInTheDocument();
    expect(screen.getByText('Cambios propuestos')).toBeInTheDocument();
    expect(screen.getByText('La IA sugiere modificar el workflow.')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Aplicar cambios' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Copiar al lienzo/ })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Previsualizar JSON' })).toBeInTheDocument();
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

    fireEvent.change(screen.getByPlaceholderText('Pregunta sobre workflows... (pega imagenes directamente)'), {
      target: { value: 'Ayudame con QC' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Enviar' }));

    expect(await screen.findByText('Pensando...')).toBeInTheDocument();
    expect(screen.getAllByTitle('Detener generacion')).toHaveLength(2);
    expect(screen.getAllByRole('button', { name: /Detener/ })).toHaveLength(2);
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
      'aiWorkflow.steps.showReasoning',
      'aiWorkflow.steps.hideReasoning',
      'aiWorkflow.steps.toolResult',
      'aiWorkflow.steps.proposedChanges',
      'aiWorkflow.steps.proposalFallbackDescription',
      'aiWorkflow.steps.applyChanges',
      'aiWorkflow.steps.copyToCanvas',
      'aiWorkflow.steps.previewJson',
      'aiWorkflow.generation.thinking',
      'aiWorkflow.generation.stopTitle',
      'aiWorkflow.generation.stop',
      'aiWorkflow.generation.regenerateTitle',
      'aiWorkflow.generation.regenerate',
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
      'Hide reasoning',
      'Show reasoning',
      '${step.name} result',
      'Proposed changes',
      'The AI suggests modifying the workflow.',
      'Apply Changes',
      'Copy to Canvas',
      'Preview JSON',
      'Thinking...',
      'Stop generating',
      '>Stop<',
      'Re-run the previous question',
      '↻ Regenerate',
    ].forEach(text => expect(source).not.toContain(text));
  });
});
