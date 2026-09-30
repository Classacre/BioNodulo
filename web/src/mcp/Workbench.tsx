import { useCallback, useEffect, useMemo, useReducer, useRef, useState } from 'react';
import { useAtomValue } from 'jotai';
import { useTranslation } from 'react-i18next';
import { normalizeObjectInfo } from '../hooks/data/useObjectInfo';
import WorkflowCanvas, { type WorkflowCanvasRef } from '../components/canvas/WorkflowCanvas';
import { ConfirmDialogHost, confirmDialog, Dialog } from '../components/ui';
import { selectedNodeIdAtom } from '../state/uiAtoms';
import { bootDone } from '../state/bootLoader';
import { dismissNotification, useNotifications } from '../state/notifications';
import { defaultsFor, groupNodesByCategory, saveToFile } from '../utils';
import { useNodeSearch } from '../utils/nodeSearch';
import { nodeCategoryDisplayLabel } from '../utils/nodeCategories';
import { contextDraft } from './context';
import { deriveCloudNodeStatuses, isTerminalCloudStatus } from '../utils/cloudRunStatus';
import type { NodeMetadata, ObjectInfo, Workflow } from '../types';
import {
  assertUploadOrigin,
  listItems,
  record,
  type OpenContext,
  type RecordValue,
  type WorkbenchHost,
} from './host';
import {
  draftReducer,
  initialDraft,
  readWorkflow,
  uploadBindings,
  type CloudWorkflow,
} from './draft';
import './workbench.css';

interface TeamFile {
  key: string;
  name: string;
  source: string;
  size: number;
  verificationPending?: boolean;
}
interface RunEvent {
  seq: number;
  type: string;
  payload: unknown;
}
interface RunOutput {
  key: string;
  name: string;
  size: number;
  sha256: string;
  url: string;
}
interface RunQuote {
  teamId?: string;
  workflow: CloudWorkflow;
  definition: Workflow;
  compute: { vcpu: number; ramGb: number };
  balance: RecordValue;
  estimate: RecordValue;
}
type Panel = 'tools' | 'workflows' | 'files' | 'runs';
const errorText = (error: unknown) => (error instanceof Error ? error.message : String(error));
const json = (value: unknown) => JSON.stringify(value, null, 2);
const noHistory = () => {};

export default function Workbench({ host }: { host: WorkbenchHost }) {
  const { t } = useTranslation();
  const categoryLabel = (category?: string) => nodeCategoryDisplayLabel(category, t, 'Other');
  const notifications = useNotifications();
  const [connected, setConnected] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [busy, setBusy] = useState('');
  const [teamId, setTeamId] = useState<string>();
  const [account, setAccount] = useState<RecordValue>({});
  const [catalog, setCatalog] = useState<ObjectInfo>({});
  const [workflows, setWorkflows] = useState<CloudWorkflow[]>([]);
  const [files, setFiles] = useState<TeamFile[]>([]);
  const [runs, setRuns] = useState<RecordValue[]>([]);
  const [panel, setPanel] = useState<Panel>('tools');
  const [sidebar, setSidebar] = useState(true);
  const [query, setQuery] = useState('');
  const [category, setCategory] = useState('');
  const [limit, setLimit] = useState(40);
  const [state, dispatch] = useReducer(draftReducer, undefined, initialDraft);
  const [runId, setRunId] = useState<string>();
  const [run, setRun] = useState<RecordValue>({});
  const [events, setEvents] = useState<RunEvent[]>([]);
  const [outputs, setOutputs] = useState<RunOutput[]>([]);
  const [runError, setRunError] = useState('');
  const [vcpu, setVcpu] = useState(1);
  const [ramGb, setRamGb] = useState(4);
  const [caps, setCaps] = useState<RecordValue>({});
  const [quote, setQuote] = useState<RunQuote>();
  const [prompt, setPrompt] = useState('');
  const [transfer, setTransfer] = useState<'import' | 'export'>();
  const [format, setFormat] = useState('json');
  const [text, setText] = useState('');
  const [exportReport, setExportReport] = useState<RecordValue>();
  const [validation, setValidation] = useState<RecordValue>();
  const selectedId = useAtomValue(selectedNodeIdAtom);
  const canvas = useRef<WorkflowCanvasRef>(null);
  const canvasContainer = useRef<HTMLDivElement>(null);
  const current = useRef({ state, teamId });
  current.current = { state, teamId };
  const generation = useRef(0);
  const createRequest = useRef(crypto.randomUUID());
  const runSequence = useRef(0);
  const scope = useCallback(
    (team = current.current.teamId): RecordValue => (team ? { team_id: team } : {}),
    [],
  );
  const operation = async (label: string, action: () => Promise<void>) => {
    setBusy(label);
    setError('');
    setNotice('');
    try {
      await action();
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy('');
    }
  };
  const refreshLibrary = useCallback(
    async (team?: string) => {
      const key = generation.current;
      const result = await host.tool('list_workflows', scope(team));
      if (key === generation.current) setWorkflows(listItems<CloudWorkflow>(result));
    },
    [host, scope],
  );
  const acceptContext = useCallback(
    async (context: OpenContext) => {
      if (
        current.current.state.dirty &&
        !(await confirmDialog({
          title: 'Open another workflow?',
          message:
            'Your draft has unsaved edits. Discard them and open the workflow requested by the host?',
          confirmLabel: 'Discard and open',
          tone: 'danger',
        }))
      )
        return;
      const key = ++generation.current;
      const team = context.team_id ?? current.current.teamId;
      const openingDraft = current.current.state.draft;
      if (context.workflow_id) {
        const saved =
          context.workflow ??
          (await host.tool('get_workflow', { ...scope(team), workflow_id: context.workflow_id }));
        if (key !== generation.current) return;
        if (current.current.state.dirty && current.current.state.draft !== openingDraft)
          throw new Error(
            'Your draft changed while opening the workflow. It was preserved; open the workflow again when ready.',
          );
        dispatch({ type: 'replace', saved: saved as unknown as CloudWorkflow });
      } else {
        dispatch({ type: 'new' });
        createRequest.current = crypto.randomUUID();
      }
      current.current.teamId = team;
      setTeamId(team);
      setQuote(undefined);
      setValidation(undefined);
      setRunId(context.run_id);
      setFiles([]);
      setRuns([]);
      await refreshLibrary(team);
    },
    [host, refreshLibrary, scope],
  );

  useEffect(() => {
    let disposed = false;
    let unsubscribe = () => {};
    const start = async () => {
      await host.connect();
      if (disposed) return;
      const [info, nodes] = await Promise.all([
        host.tool('get_account_info'),
        host.tool<{ catalog: ObjectInfo }>('get_editor_catalog'),
      ]);
      if (disposed) return;
      setAccount(info);
      // Registry keys are executable node identifiers; display aliases can differ.
      setCatalog(
        Object.fromEntries(
          Object.entries(normalizeObjectInfo(nodes.catalog)).map(([id, meta]) => [
            id,
            { ...meta, id },
          ]),
        ),
      );
      const defaultTeam = String(record(info.team).id ?? '') || undefined;
      current.current.teamId = defaultTeam;
      setTeamId(defaultTeam);
      setConnected(true);
      await refreshLibrary(defaultTeam).catch((e) => setError(errorText(e)));
      if (!disposed)
        unsubscribe = host.onOpen((context) => {
          void acceptContext(context).catch((e) => setError(errorText(e)));
        });
    };
    void start()
      .catch((e) => {
        if (!disposed) setError(errorText(e));
      })
      .finally(bootDone);
    return () => {
      disposed = true;
      unsubscribe();
    };
  }, [host, acceptContext, refreshLibrary]);

  // Poll only while visible. A remote update becomes a conflict, never a lost draft.
  useEffect(() => {
    if (!connected || !state.saved?.id) return;
    let stopped = false,
      pending = false;
    const id = state.saved.id;
    const poll = async () => {
      if (stopped || pending || document.visibilityState === 'hidden') return;
      pending = true;
      try {
        const saved = await host.tool<CloudWorkflow>('get_workflow', {
          ...scope(teamId),
          workflow_id: id,
        });
        if (!stopped) dispatch({ type: 'remote', saved });
      } catch (e) {
        if (!stopped) setError(`Workflow refresh: ${errorText(e)}`);
      } finally {
        pending = false;
      }
    };
    const timer = window.setInterval(() => {
      void poll();
    }, 8_000);
    document.addEventListener('visibilitychange', poll);
    return () => {
      stopped = true;
      clearInterval(timer);
      document.removeEventListener('visibilitychange', poll);
    };
  }, [host, connected, state.saved?.id, teamId, scope]);

  const modelContext = useCallback((): RecordValue => {
    const { state: snapshot, teamId: team } = current.current;
    const definition = contextDraft(snapshot.draft);
    return {
      app: 'BioNodulo',
      team_id: team,
      workflow_id: snapshot.saved?.id,
      updated_at: snapshot.saved?.updatedAt,
      dirty: snapshot.dirty,
      conflict: Boolean(snapshot.conflict),
      run_id: runId,
      selected_node_id: selectedId,
      draft:
        JSON.stringify(definition).length <= 100_000
          ? definition
          : {
              name: snapshot.draft.name,
              nodes: snapshot.draft.nodes.map((n) => ({ id: n.id, type: n.type })),
              edges: snapshot.draft.edges,
              parameters_omitted: true,
            },
    };
  }, [runId, selectedId]);
  useEffect(() => {
    if (!connected) return;
    const timer = window.setTimeout(() => {
      void host.context(modelContext()).catch(() => {});
    }, 600);
    return () => clearTimeout(timer);
  }, [host, connected, state, teamId, modelContext]);
  useEffect(() => {
    const warn = (event: BeforeUnloadEvent) => {
      if (current.current.state.dirty) event.preventDefault();
    };
    window.addEventListener('beforeunload', warn);
    return () => window.removeEventListener('beforeunload', warn);
  }, []);

  useEffect(() => {
    setRun({});
    setEvents([]);
    setOutputs([]);
    setRunError('');
    runSequence.current = 0;
    if (!connected || !runId) return;
    let stopped = false,
      pending = false,
      terminal = false;
    const poll = async () => {
      if (stopped || pending || terminal || document.visibilityState === 'hidden') return;
      pending = true;
      try {
        const [status, page] = await Promise.all([
          host.tool('get_run_status', { ...scope(teamId), run_id: runId }),
          host.tool<{ events: RunEvent[] }>('get_run_events', {
            ...scope(teamId),
            run_id: runId,
            after_seq: runSequence.current,
            limit: 500,
          }),
        ]);
        if (stopped) return;
        setRun(status);
        setRunError('');
        const incoming = page.events ?? [];
        runSequence.current = Math.max(runSequence.current, ...incoming.map((e) => e.seq));
        setEvents((previous) => [...previous, ...incoming].slice(-1000));
        // Drain event pages even for a run that finished before the first poll.
        terminal = isTerminalCloudStatus(String(status.status)) && incoming.length < 500;
        if (terminal && status.status === 'completed') {
          const result = await host.tool<{ outputs: RunOutput[] }>('get_run_outputs', {
            ...scope(teamId),
            run_id: runId,
          });
          if (!stopped) setOutputs(result.outputs);
        }
      } catch (e) {
        if (!stopped) setRunError(errorText(e));
      } finally {
        pending = false;
      }
    };
    void poll();
    const timer = window.setInterval(() => {
      void poll();
    }, 5_000);
    document.addEventListener('visibilitychange', poll);
    return () => {
      stopped = true;
      clearInterval(timer);
      document.removeEventListener('visibilitychange', poll);
    };
  }, [host, connected, runId, teamId, scope]);

  const edit = (patch: Partial<Workflow>) => {
    dispatch({ type: 'edit', patch });
    setValidation(undefined);
    setQuote(undefined);
  };
  const search = useNodeSearch(catalog, query);
  const categories = useMemo(() => Object.keys(groupNodesByCategory(catalog)).sort(), [catalog]);
  const matches = search.filter(({ meta }) => !category || meta.category === category);
  const statuses = useMemo(() => deriveCloudNodeStatuses(String(run.logs ?? '')), [run.logs]);
  const addNode = (meta: NodeMetadata, params = defaultsFor(meta)) => {
    const rect = canvasContainer.current?.getBoundingClientRect();
    const center =
      rect &&
      canvas.current?.screenToFlowPosition(rect.x + rect.width / 2, rect.y + rect.height / 2);
    edit({
      nodes: [
        ...state.draft.nodes,
        {
          id: `${meta.id}_${crypto.randomUUID().slice(0, 8)}`,
          type: meta.id,
          params,
          position: center ? [center.x, center.y] : [80, 80],
        },
      ],
    });
  };
  const save = async (copy = false) => {
    const snapshot = current.current.state;
    if (snapshot.conflict && !copy)
      throw new Error(
        'The saved workflow changed. Load the latest version or save your draft as a copy.',
      );
    const submitted = snapshot.draft;
    if (!submitted.name.trim()) throw new Error('Enter a workflow name before saving.');
    const key = generation.current;
    const saved = await host.tool<CloudWorkflow>(
      snapshot.saved && !copy ? 'update_workflow' : 'create_workflow',
      {
        ...scope(),
        name: submitted.name,
        description: submitted.description,
        definition: submitted,
        ...(snapshot.saved && !copy
          ? { workflow_id: snapshot.saved.id, expected_updated_at: snapshot.saved.updatedAt }
          : { client_request_id: createRequest.current }),
      },
    );
    if (key !== generation.current) return;
    dispatch({ type: 'saved', saved, submitted });
    createRequest.current = crypto.randomUUID();
    setNotice('Workflow saved.');
    await refreshLibrary(current.current.teamId);
  };
  const refreshPanel = async (next: Panel) => {
    setPanel(next);
    setSidebar(true);
    if (next === 'workflows') await refreshLibrary(teamId);
    if (next === 'files') setFiles(listItems<TeamFile>(await host.tool('list_files', scope())));
    if (next === 'runs') setRuns(listItems<RecordValue>(await host.tool('list_runs', scope())));
  };
  const prepareRun = async () => {
    const snapshot = current.current.state;
    if (!snapshot.saved || snapshot.dirty || snapshot.conflict)
      throw new Error('Save a conflict-free workflow before running.');
    const team = current.current.teamId;
    if (!Number.isInteger(vcpu) || vcpu < 1 || !Number.isInteger(ramGb) || ramGb < 1)
      throw new Error('CPU and RAM must be positive whole numbers.');
    const compute = { vcpu, ramGb };
    const [fresh, balance, estimate, validated] = await Promise.all([
      host.tool<CloudWorkflow>('get_workflow', { ...scope(team), workflow_id: snapshot.saved.id }),
      host.tool('get_credit_balance', scope(team)),
      host.tool('estimate_run_cost', { ...scope(team), compute }),
      host.tool('validate_workflow', { workflow: snapshot.draft }),
    ]);
    if (fresh.updatedAt !== snapshot.saved.updatedAt) {
      dispatch({ type: 'remote', saved: fresh });
      throw new Error('The saved workflow changed. Review it before running.');
    }
    setValidation(validated);
    setCaps(record(estimate.caps));
    if (validated.valid !== true)
      throw new Error('Workflow validation did not pass. Review the validation report.');
    if (estimate.allowed !== true)
      throw new Error(
        String(estimate.error ?? 'This compute profile is unavailable for the team.'),
      );
    if (!Number.isFinite(Number(estimate.creditPerSecond)) || Number(estimate.creditPerSecond) <= 0)
      throw new Error(
        'The server did not return a valid compute cost rate. Review cannot proceed.',
      );
    if (!(Number(balance.remaining) > 0))
      throw new Error('This team has no remaining compute credits.');
    if (current.current.state.draft !== snapshot.draft || current.current.teamId !== team)
      throw new Error('The draft changed while preparing the run. Save and review it again.');
    setQuote({
      teamId: team,
      workflow: fresh,
      definition: snapshot.draft,
      compute,
      balance,
      estimate,
    });
  };
  const submitRun = async () => {
    const approved = quote;
    setQuote(undefined); // One confirmation authorizes one attempt only.
    if (
      !approved ||
      current.current.state.dirty ||
      current.current.state.saved?.updatedAt !== approved.workflow.updatedAt ||
      current.current.teamId !== approved.teamId
    )
      throw new Error('The workflow changed. Review the run again.');
    const fresh = await host.tool<CloudWorkflow>('get_workflow', {
      ...scope(approved.teamId),
      workflow_id: approved.workflow.id,
    });
    if (fresh.updatedAt !== approved.workflow.updatedAt)
      throw new Error('The workflow was edited after confirmation. Review it again.');
    try {
      const result = await host.tool('submit_run', {
        ...scope(approved.teamId),
        workflow_id: approved.workflow.id,
        expected_workflow_updated_at: approved.workflow.updatedAt,
        compute: approved.compute,
        inputs: { artifacts: uploadBindings(approved.definition, approved.teamId) },
        confirm_credit_use: true,
      });
      const id = String(result.runId ?? result.id ?? '');
      if (!id) throw new Error('The server returned no run identifier.');
      setRunId(id);
      setNotice('Run submitted. Status and committed outputs will update here.');
    } catch (e) {
      throw new Error(
        `${errorText(e)} Submission was not retried. Check Runs before starting another run.`,
      );
    }
  };
  const upload = async (file: File) => {
    const allowed = (
      document.querySelector<HTMLMetaElement>('meta[name="bionodulo-upload-origins"]')?.content ??
      ''
    )
      .split(/\s+/)
      .filter(Boolean);
    if (!allowed.length)
      throw new Error(
        'Uploads are not enabled by this MCP host. Existing verified uploads can still be selected.',
      );
    const team = teamId,
      type = file.type || 'application/octet-stream';
    const presign = await host.tool<{ url: string; key: string }>('get_upload_url', {
      ...scope(team),
      filename: file.name,
      content_type: type,
      size_bytes: file.size,
    });
    const response = await fetch(assertUploadOrigin(presign.url, allowed), {
      method: 'PUT',
      headers: { 'Content-Type': type },
      body: file,
      credentials: 'omit',
      redirect: 'error',
    });
    if (!response.ok)
      throw new Error(`Upload failed (${response.status}). The file has not been marked ready.`);
    await host.tool('complete_upload', { ...scope(team), key: presign.key });
    if (team === current.current.teamId) await refreshPanel('files');
  };
  const transferWorkflow = async () => {
    if (transfer === 'import') {
      let imported: unknown;
      if (format === 'json') imported = JSON.parse(text);
      else {
        const result = await host.tool('import_workflow', { source: format, content: text });
        imported = result.workflow;
        setNotice(
          Array.isArray(result.warnings)
            ? result.warnings.join('\n')
            : 'Imported. Validate before running.',
        );
      }
      const workflow = readWorkflow(imported);
      if (
        state.dirty &&
        !(await confirmDialog({
          title: 'Replace the draft?',
          message: 'Import replaces the current draft. Its saved version remains available.',
          confirmLabel: 'Replace draft',
        }))
      )
        return;
      edit(workflow);
      setTransfer(undefined);
    } else {
      const result = await host.tool('export_workflow', {
        workflow: state.draft,
        format,
        name: state.draft.name.replace(/[^a-zA-Z0-9_-]/g, '_').slice(0, 100) || 'workflow',
      });
      setText(String(result.content ?? ''));
      setExportReport(result);
    }
  };

  return (
    <main className="mcp-workbench">
      <ConfirmDialogHost />
      <header className="mcp-header">
        <div>
          <strong>BioNodulo</strong>
          <span className="mcp-muted"> · Workbench</span>
        </div>
        <div className="mcp-account">
          {String(account.name ?? 'MCP connection')} ·{' '}
          {String(
            record(account.team).id === teamId ? record(account.team).name : (teamId ?? 'Team'),
          )}
          <small title={teamId}>{teamId}</small>
        </div>
        <span className="mcp-badge">{connected ? 'Host connected' : 'Connecting…'}</span>
      </header>
      {error && (
        <div role="alert" className="mcp-error">
          {error}
          <button aria-label="Dismiss error" onClick={() => setError('')}>
            ×
          </button>
        </div>
      )}
      {notice && (
        <div role="status" className="mcp-notice">
          {notice}
        </div>
      )}
      {notifications.slice(0, 3).map((item) => (
        <div
          key={item.id}
          role={item.tone === 'error' ? 'alert' : 'status'}
          className={item.tone === 'error' || item.tone === 'warning' ? 'mcp-error' : 'mcp-notice'}
        >
          <strong>{item.title}</strong> {item.message}
          {item.actions.map((action) => (
            <button key={action.label} onClick={() => action.onClick(item.id)}>
              {action.label}
            </button>
          ))}
          {item.dismissible && (
            <button aria-label="Dismiss notification" onClick={() => dismissNotification(item.id)}>
              ×
            </button>
          )}
        </div>
      ))}
      {!connected && (
        <p className="mcp-loading">
          Open BioNodulo from your MCP host to connect your account.{' '}
          {error && 'Reload this app after reconnecting the BioNodulo connector.'}
        </p>
      )}
      <div className="mcp-toolbar">
        <button onClick={() => setSidebar(!sidebar)} aria-expanded={sidebar}>
          Library
        </button>
        <input
          aria-label="Workflow name"
          value={state.draft.name}
          onChange={(e) => edit({ name: e.target.value })}
          maxLength={200}
        />
        <span className="mcp-badge">
          {state.conflict
            ? 'Conflict'
            : state.dirty
              ? 'Unsaved draft'
              : state.saved
                ? 'Saved'
                : 'New draft'}
        </span>
        <button
          disabled={!connected || !!busy || !!state.conflict}
          onClick={() => void operation('Saving', () => save())}
        >
          Save
        </button>
        <button
          disabled={!connected || !!busy}
          onClick={() =>
            void operation('Validating', async () =>
              setValidation(await host.tool('validate_workflow', { workflow: state.draft })),
            )
          }
        >
          Validate
        </button>
        <button
          disabled={!state.past.length}
          onClick={() => {
            dispatch({ type: 'undo' });
            setQuote(undefined);
          }}
        >
          Undo
        </button>
        <button
          disabled={!state.future.length}
          onClick={() => {
            dispatch({ type: 'redo' });
            setQuote(undefined);
          }}
        >
          Redo
        </button>
        <button onClick={() => canvas.current?.autoLayout()}>Auto layout</button>
        <button onClick={() => canvas.current?.fitView()}>Fit</button>
        <button
          disabled={!connected}
          onClick={() => {
            setTransfer('import');
            setText('');
            setFormat('json');
            setExportReport(undefined);
          }}
        >
          Import
        </button>
        <button
          disabled={!connected}
          onClick={() => {
            setTransfer('export');
            setText('');
            setFormat('json');
            setExportReport(undefined);
          }}
        >
          Export / references
        </button>
        <label>
          CPU{' '}
          <input
            className="mcp-compute"
            aria-label="CPU cores"
            type="number"
            min={1}
            max={Number(caps.maxVcpu) || undefined}
            value={vcpu}
            onChange={(e) => {
              setVcpu(Number(e.target.value));
              setQuote(undefined);
            }}
          />
        </label>
        <label>
          RAM GB{' '}
          <input
            className="mcp-compute"
            aria-label="RAM GB"
            type="number"
            min={1}
            max={Number(caps.maxRamGb) || undefined}
            value={ramGb}
            onChange={(e) => {
              setRamGb(Number(e.target.value));
              setQuote(undefined);
            }}
          />
        </label>
        {host.canFullscreen?.() && (
          <button
            onClick={() =>
              void operation('Expanding workbench', async () => {
                await host.fullscreen?.();
              })
            }
          >
            Fullscreen
          </button>
        )}
        <button
          className="mcp-primary"
          disabled={!connected || !!busy || state.dirty || !state.saved || !!state.conflict}
          onClick={() => void operation('Preparing run', prepareRun)}
        >
          Review run
        </button>
      </div>
      {state.conflict && (
        <div className="mcp-conflict" role="alert">
          The saved workflow changed while you were editing. Your draft is preserved.
          <button
            onClick={() =>
              void operation('Loading latest', async () => {
                if (
                  await confirmDialog({
                    title: 'Load latest version?',
                    message: 'Discard your unsaved draft and load the latest saved workflow?',
                    confirmLabel: 'Discard draft',
                    tone: 'danger',
                  })
                )
                  dispatch({ type: 'replace', saved: state.conflict! });
              })
            }
          >
            Load latest
          </button>
          <button disabled={!!busy} onClick={() => void operation('Saving copy', () => save(true))}>
            Save draft as copy
          </button>
        </div>
      )}
      <div className="mcp-body">
        {sidebar && (
          <aside className="mcp-library" aria-label="Workflow library">
            <nav>
              {(['tools', 'workflows', 'files', 'runs'] as const).map((item) => (
                <button
                  key={item}
                  aria-pressed={panel === item}
                  disabled={!connected || !!busy}
                  onClick={() => void operation('Loading library', () => refreshPanel(item))}
                >
                  {item}
                </button>
              ))}
            </nav>
            {panel === 'tools' && (
              <>
                <input
                  aria-label="Search nodes"
                  placeholder="Search nodes…"
                  value={query}
                  onChange={(e) => {
                    setQuery(e.target.value);
                    setLimit(40);
                  }}
                />
                <select
                  aria-label="Node category"
                  value={category}
                  onChange={(e) => {
                    setCategory(e.target.value);
                    setLimit(40);
                  }}
                >
                  <option value="">All categories</option>
                  {categories.map((c) => (
                    <option key={c} value={c}>
                      {categoryLabel(c)}
                    </option>
                  ))}
                </select>
                <p className="mcp-muted">
                  {matches.length} catalog nodes. Availability and execution depend on the tool and
                  environment.
                </p>
                <div className="mcp-list">
                  {matches.slice(0, limit).map(({ meta }) => (
                    <article key={meta.id}>
                      <button
                        className="mcp-add"
                        aria-label={`Add ${meta.display_name}`}
                        onClick={() => addNode(meta)}
                      >
                        ＋
                      </button>
                      <strong>{meta.display_name}</strong>
                      <small>{categoryLabel(meta.category)}</small>
                      <p>{meta.description}</p>
                      <code>{meta.id}</code>
                    </article>
                  ))}
                  {matches.length > limit && (
                    <button onClick={() => setLimit(limit + 40)}>Show more</button>
                  )}
                </div>
              </>
            )}
            {panel === 'workflows' && (
              <>
                <button
                  disabled={!!busy}
                  onClick={() =>
                    void operation('New workflow', () => acceptContext({ team_id: teamId }))
                  }
                >
                  New workflow
                </button>
                <div className="mcp-list">
                  {workflows.map((w) => (
                    <article key={w.id}>
                      <button
                        disabled={!!busy}
                        onClick={() =>
                          void operation('Opening workflow', async () => {
                            await acceptContext({ workflow_id: w.id, team_id: teamId });
                            window.setTimeout(() => canvas.current?.fitView(), 100);
                          })
                        }
                      >
                        {w.name}
                      </button>
                      <small>{w.updatedAt}</small>
                      <p>{w.description}</p>
                    </article>
                  ))}
                  {!workflows.length && <p>No saved workflows in this team.</p>}
                </div>
              </>
            )}
            {panel === 'files' && (
              <>
                <label className="mcp-upload">
                  Upload a file
                  <input
                    aria-label="Upload a file"
                    type="file"
                    disabled={!!busy}
                    onChange={(e) => {
                      const file = e.target.files?.[0];
                      e.target.value = '';
                      if (file) void operation('Uploading', () => upload(file));
                    }}
                  />
                </label>
                <p className="mcp-muted">
                  Select a verified upload to add an Input File node. Cloud outputs are downloadable
                  after the run commits them.
                </p>
                <div className="mcp-list">
                  {files.map((file) => (
                    <article key={file.key}>
                      <strong>{file.name}</strong>
                      <small>
                        {file.source} · {file.size.toLocaleString()} bytes
                      </small>
                      {file.verificationPending ? (
                        <button
                          disabled={!!busy}
                          onClick={() =>
                            void operation('Verifying upload', async () => {
                              await host.tool('complete_upload', { ...scope(), key: file.key });
                              await refreshPanel('files');
                            })
                          }
                        >
                          Verify upload
                        </button>
                      ) : (
                        file.source === 'upload' &&
                        catalog.input_file && (
                          <button
                            onClick={() =>
                              addNode(catalog.input_file, {
                                ...defaultsFor(catalog.input_file),
                                file: file.key,
                              })
                            }
                          >
                            Use as input
                          </button>
                        )
                      )}
                    </article>
                  ))}
                  {!files.length && <p>No files returned.</p>}
                </div>
              </>
            )}
            {panel === 'runs' && (
              <div className="mcp-list">
                {runs.map((item) => {
                  const r = Object.keys(record(item.run)).length ? record(item.run) : item;
                  return (
                    <article key={String(r.id)}>
                      <button onClick={() => setRunId(String(r.id))}>
                        {String(record(item.workflow).name ?? r.workflowName ?? r.id)}
                      </button>
                      <small>
                        {String(r.status)} · {String(r.createdAt ?? '')}
                      </small>
                    </article>
                  );
                })}
                {!runs.length && <p>No runs returned.</p>}
              </div>
            )}
          </aside>
        )}
        <section className="mcp-canvas" aria-label="Workflow canvas" ref={canvasContainer}>
          <WorkflowCanvas
            ref={canvas}
            nodes={state.draft.nodes}
            edges={state.draft.edges}
            objectInfo={catalog}
            workflowParameters={state.draft.parameters}
            workflowId={state.saved?.id ?? 'mcp-draft'}
            workflowName={state.draft.name}
            onNodesChange={(nodes) => edit({ nodes })}
            onEdgesChange={(edges) => edit({ edges })}
            onPushHistory={noHistory}
            onUndo={() => dispatch({ type: 'undo' })}
            onRedo={() => dispatch({ type: 'redo' })}
            snapToGrid
            showMinimap
            nodeStatusMap={statuses}
            onOpenNodeLibrary={() => {
              setSidebar(true);
              setPanel('tools');
            }}
          />
          {!state.draft.nodes.length && (
            <div className="mcp-empty">
              Add a node from the library, open a saved workflow, or ask your host assistant to
              create one.
            </div>
          )}
        </section>
      </div>
      <footer className="mcp-footer">
        <span>
          {state.draft.nodes.length} nodes · {state.draft.edges.length} connections
          {selectedId ? ` · Selected: ${selectedId}` : ''}
        </span>
        <span role="status">{busy || 'Changes save only when you choose Save'}</span>
      </footer>
      {validation && (
        <details className="mcp-details" open>
          <summary>Validation: {validation.valid === true ? 'passed' : 'needs attention'}</summary>
          <pre>{json(validation)}</pre>
        </details>
      )}
      {runId && (
        <section className="mcp-run" aria-label="Run monitor">
          <header>
            <strong>Run · {String(run.status ?? 'Loading…')}</strong>
            <code>{runId}</code>
            {!isTerminalCloudStatus(String(run.status)) && (
              <button
                disabled={!!busy}
                onClick={() =>
                  void operation('Cancelling run', async () => {
                    if (
                      await confirmDialog({
                        title: 'Cancel this run?',
                        message:
                          'Cancel the selected run? Credits already consumed are not refunded.',
                        confirmLabel: 'Cancel run',
                        tone: 'danger',
                      })
                    ) {
                      await host.tool('cancel_run', { ...scope(), run_id: runId });
                      setNotice('Cancellation requested.');
                    }
                  })
                }
              >
                Cancel run
              </button>
            )}
          </header>
          {runError && (
            <p role="alert" className="mcp-error">
              {runError}
              <button
                onClick={() =>
                  void operation('Refreshing outputs', async () => {
                    const data = await host.tool<{ outputs: RunOutput[] }>('get_run_outputs', {
                      ...scope(),
                      run_id: runId,
                    });
                    setOutputs(data.outputs);
                    setRunError('');
                  })
                }
              >
                Refresh committed outputs
              </button>
            </p>
          )}
          {run.errorMessage ? <p role="alert">{String(run.errorMessage)}</p> : null}
          <p className="mcp-muted">
            Credits used: {String(run.creditsUsed ?? 'pending')} · Outputs appear only after server
            verification.
          </p>
          <details>
            <summary>Live events and logs ({events.length} retained events)</summary>
            <pre>
              {String(run.logs ?? '') ||
                events.map((e) => `${e.seq} ${e.type} ${json(e.payload)}`).join('\n') ||
                'Waiting for persisted events…'}
            </pre>
          </details>
          <div className="mcp-outputs">
            {outputs.map((output) => (
              <article key={output.key}>
                <button
                  onClick={() => void operation('Opening output', () => host.openLink(output.url))}
                >
                  {output.name}
                </button>
                <small>
                  {output.size.toLocaleString()} bytes · SHA-256 {output.sha256}
                </small>
              </article>
            ))}
          </div>
        </section>
      )}
      <form
        className="mcp-assistant"
        onSubmit={(e) => {
          e.preventDefault();
          const request = prompt.trim();
          if (request)
            void operation('Sending to host assistant', async () => {
              await host.context(modelContext()).catch(() => {});
              await host.message(request);
              setPrompt('');
              setNotice(
                'Sent to your host assistant. Saved workflow changes will appear here; unsaved drafts remain protected.',
              );
            });
        }}
      >
        <label htmlFor="mcp-prompt">Host assistant</label>
        <input
          id="mcp-prompt"
          placeholder="Describe a workflow, ask about a node, or diagnose a run…"
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          maxLength={10000}
        />
        <button disabled={!connected || !!busy || !prompt.trim()}>Send</button>
      </form>
      {quote && (
        <Dialog title="Confirm compute credit use" onClose={() => setQuote(undefined)}>
          <div className="mcp-dialog-content">
            <p>
              <strong>{quote.workflow.name}</strong> · team {quote.teamId}
            </p>
            <p>
              Custom compute · {String(quote.estimate.vcpu)} vCPU · {String(quote.estimate.ramGb)}{' '}
              GB RAM
            </p>
            <p>
              Remaining: <strong>{String(quote.balance.remaining)} credits</strong>
            </p>
            <p>
              Rate: <strong>{String(quote.estimate.creditsPerHour)} credits/hour</strong> (
              {String(quote.estimate.creditPerSecond)} credits/second).
            </p>
            <p>
              The total depends on runtime. Starting this run spends this team's credits.
              Cancellation does not refund compute already used.
            </p>
            <button onClick={() => setQuote(undefined)}>Back</button>
            <button
              className="mcp-primary"
              disabled={!!busy}
              onClick={() => void operation('Submitting run', submitRun)}
            >
              Confirm and start run
            </button>
          </div>
        </Dialog>
      )}
      {transfer && (
        <Dialog
          title={transfer === 'import' ? 'Import workflow' : 'Export workflow or references'}
          onClose={() => setTransfer(undefined)}
        >
          <div className="mcp-dialog-content">
            <label>
              Format{' '}
              <select
                aria-label="Transfer format"
                value={format}
                onChange={(e) => {
                  setFormat(e.target.value);
                  setExportReport(undefined);
                  if (transfer === 'export') setText('');
                }}
              >
                {(transfer === 'import'
                  ? ['json', 'nextflow', 'snakemake', 'cwl', 'galaxy']
                  : ['json', 'nextflow', 'snakemake', 'cwl', 'galaxy', 'ris', 'bibtex', 'csv']
                ).map((f) => (
                  <option key={f} value={f}>
                    {f}
                  </option>
                ))}
              </select>
            </label>
            <textarea
              aria-label="Workflow content"
              value={text}
              readOnly={transfer === 'export'}
              onChange={(e) => setText(e.target.value.slice(0, 1_000_000))}
              placeholder={
                transfer === 'import'
                  ? 'Paste the workflow definition…'
                  : 'Generate to view exported content.'
              }
              rows={12}
            />
            <button
              disabled={!!busy || (transfer === 'import' && !text.trim())}
              onClick={() =>
                void operation(transfer === 'import' ? 'Importing' : 'Exporting', transferWorkflow)
              }
            >
              {transfer === 'import' ? 'Import into draft' : 'Generate'}
            </button>
            {transfer === 'export' && text && (
              <button
                onClick={() =>
                  saveToFile(
                    text,
                    String(exportReport?.filename ?? `workflow.${format}`),
                    'text/plain',
                  )
                }
              >
                Download
              </button>
            )}
            {exportReport && (
              <details>
                <summary>Portability and export report</summary>
                <pre>{json({ ...exportReport, content: undefined })}</pre>
              </details>
            )}
          </div>
        </Dialog>
      )}
    </main>
  );
}
