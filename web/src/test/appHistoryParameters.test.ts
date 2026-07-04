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

describe('App inline history workflow parameters', () => {
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

  it('tracks workflow parameters in snapshots, dedup signatures, and undo/redo restore', () => {
    const appSource = readFileSync(resolve(__dirname, '../App.tsx'), 'utf8');

    expect(appSource).toContain("parameters: Workflow['parameters']");
    expect(appSource).toContain('workflow.parameters ?? []');
    expect(appSource).toContain('parameters: wf.parameters');
    expect(appSource).toContain('activeWorkflow.parameters');
    expect(appSource.match(/parameters: state\.parameters/g)).toHaveLength(2);
  });

  it('prompts for workflow parameter overrides before submitting runs', () => {
    const appSource = readFileSync(resolve(__dirname, '../App.tsx'), 'utf8');

    expect(appSource).toContain("import { promptWorkflowRunParameters } from './utils/workflowParameters';");
    expect(appSource.match(/promptWorkflowRunParameters\(activeWorkflow\.parameters, promptDialog/g)).toHaveLength(2);
    expect(appSource.match(/parameters: parameterOverrides/g)).toHaveLength(2);
    expect(appSource).toContain('if (parameterOverrides === null)');
  });

  it('wires dry-run preview mode into App run submission without queueing a run record', () => {
    const appSource = readFileSync(resolve(__dirname, '../App.tsx'), 'utf8');

    expect(appSource).toContain("import { redactSecrets } from './utils/redaction';");
    expect(appSource).toContain('const [dryRunPreview, setDryRunPreview] = useState(false);');
    expect(appSource).toContain('dry_run: dryRunPreview');
    expect(appSource).toContain("if (dryRunPreview || result.status === 'dry_run')");
    expect(appSource).toContain("level: 'info'");
    expect(appSource).toContain("message: t('console.actions.dryRunPreviewLog'");
    expect(appSource).toContain('detail: JSON.stringify(redactSecrets({');
    expect(appSource).toContain('workflow_parameters: preview.workflow_parameters ?? {}');
    expect(appSource).toContain('continue;');
    expect(appSource).toContain('dryRunPreview={dryRunPreview}');
    expect(appSource).toContain('onDryRunPreviewChange={setDryRunPreview}');
  });

  it('wires resolved runtime checkpoints into App run resume options', () => {
    const appSource = readFileSync(resolve(__dirname, '../App.tsx'), 'utf8');

    expect(appSource).toContain('const [resumeCheckpoint, setResumeCheckpoint] = useState<');
    expect(appSource).toContain('resume_checkpoint: resumeCheckpoint?.checkpoint');
    expect(appSource).toContain('resumeCheckpointLabel={resumeCheckpoint?.label ?? null}');
    expect(appSource).toContain("onOpenRuntimeArtifacts={() => setRailTab('runtimeArtifacts')}");
    expect(appSource).toContain('onResumeCheckpointClear={() => setResumeCheckpoint(null)}');
    expect(appSource).toContain('onResumeCheckpointSelect={setResumeCheckpoint}');
  });

  it('passes sample-sheet workflow parameter overrides into queued runs', () => {
    const appSource = readFileSync(resolve(__dirname, '../App.tsx'), 'utf8');

    expect(appSource).toContain('parameters: sampleRun.parameters');
  });

  it('applies workflow parameters from collaboration documents', () => {
    const appSource = readFileSync(resolve(__dirname, '../App.tsx'), 'utf8');

    expect(appSource).toContain('parameters: remoteWorkflow.parameters');
  });

  it('keeps workflow parameter run prompt copy behind i18n keys', async () => {
    const { default: i18n, setLanguage } = await import('../i18n');
    const appSource = readFileSync(resolve(__dirname, '../App.tsx'), 'utf8');

    await setLanguage('es');

    expect(i18n.t('parameters.runPromptTitle')).toBe('Parametros del flujo de trabajo');
    expect(i18n.t('parameters.runPromptTitle')).not.toBe('Parametros del workflow');
    expect(i18n.t('parameters.runPromptConfirm')).toBe('Usar valor');
    expect(i18n.t('parameters.runPromptCancel')).toBe('Cancelar ejecucion');
    await setLanguage('en');
    expect(i18n.t('parameters.runPromptTitle')).toBe('Workflow parameters');
    expect(i18n.t('parameters.runPromptConfirm')).toBe('Use value');
    expect(i18n.t('parameters.runPromptCancel')).toBe('Cancel run');
    expect(appSource).toContain("title: t('parameters.runPromptTitle')");
    expect(appSource).toContain("confirmLabel: t('parameters.runPromptConfirm')");
    expect(appSource).toContain("cancelLabel: t('parameters.runPromptCancel')");
  });
});
