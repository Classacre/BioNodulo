import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { apiPost } from '../api/client';
import type { Workflow } from '../types';

vi.mock('../api/client', () => {
  class ApiError extends Error {}

  return {
    ApiError,
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
    expect(screen.getByText('La IA sugiere modificar el workflow.')).toBeInTheDocument();
    const applyButton = screen.getByRole('button', { name: 'Aplicar cambios' });
    expect(applyButton).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Copiar al lienzo/ })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Previsualizar JSON' })).toBeInTheDocument();

    fireEvent.click(applyButton);

    expect(onApplyWorkflow).toHaveBeenCalledWith(expect.objectContaining({ name: 'Suggested' }));
    expect(await screen.findByText('Workflow aplicado correctamente. Dime si necesitas algun ajuste.')).toBeInTheDocument();
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

    fireEvent.change(screen.getByPlaceholderText('Pregunta sobre workflows... (pega imagenes directamente)'), {
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

    fireEvent.paste(screen.getByPlaceholderText('Pregunta sobre workflows... (pega imagenes directamente)'), {
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

  it('renders local fallback responses from the active locale', async () => {
    const { default: AIWorkflowModal } = await import('../components/modals/AIWorkflowModal');
    const { setLanguage } = await import('../i18n');

    await setLanguage('es');

    async function expectFallback(prompt: string, expected: string) {
      storage.clear();
      vi.mocked(apiPost).mockRejectedValueOnce(new Error('offline'));

      render(
        <AIWorkflowModal
          workflow={workflow()}
          onClose={() => undefined}
          onApplyWorkflow={() => undefined}
        />,
      );

      fireEvent.change(screen.getByPlaceholderText('Pregunta sobre workflows... (pega imagenes directamente)'), {
        target: { value: prompt },
      });
      fireEvent.click(screen.getByRole('button', { name: 'Enviar' }));

      expect(await screen.findByText(expected)).toBeInTheDocument();
      cleanup();
    }

    await expectFallback(
      'rna workflow',
      'Para RNA-Seq, recomiendo: input_fastq -> fastp (recorte) -> STAR o HISAT2 (alinear) -> featureCounts (cuantificar). Agrega un nodo Sample Sheet para ejecuciones con multiples muestras. La plantilla RNA-Seq ya lo trae conectado.',
    );
    await expectFallback(
      'variant calling',
      'Para llamada de variantes: input_fastq -> fastp -> BWA-MEM -> samtools sort/index -> GATK HaplotypeCaller -> bcftools filter. La plantilla Variant Calling tambien incluye QC de BAM con samtools flagstat.',
    );
    await expectFallback(
      'something else',
      'Puedo ayudarte a disenar workflows de bioinformatica. Prueba preguntar sobre RNA-Seq, llamada de variantes, ensamblaje, metagenomica, ChIP-Seq, QC, filogenetica o analisis single-cell.',
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
      'aiWorkflow.localResponses.rna',
      'aiWorkflow.localResponses.variant',
      'aiWorkflow.localResponses.assembly',
      'aiWorkflow.localResponses.metagenomics',
      'aiWorkflow.localResponses.chipSeq',
      'aiWorkflow.localResponses.qc',
      'aiWorkflow.localResponses.phylogenetics',
      'aiWorkflow.localResponses.singleCell',
      'aiWorkflow.localResponses.plotting',
      'aiWorkflow.localResponses.default',
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
    ].forEach(text => expect(source).not.toContain(text));
  });
});
