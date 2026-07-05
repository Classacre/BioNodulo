import { useState, useCallback, useEffect, useRef, useMemo, lazy, Suspense, type ReactNode } from 'react';
import { useAtom, useAtomValue, useSetAtom } from 'jotai';
import { useTranslation } from 'react-i18next';
import TopBar from './components/layout/TopBar';
import LeftRail, { type RailTab } from './components/layout/LeftRail';
import WorkflowTabs from './components/layout/WorkflowTabs';
import BottomConsole from './components/layout/BottomConsole';
import RunsDrawer from './components/layout/RunsDrawer';
import ErrorBoundary from './components/layout/ErrorBoundary';
import WorkflowCanvas, { type WorkflowCanvasRef } from './components/canvas/WorkflowCanvas';
import type { TemplateSaveDraft } from './components/panels/TemplatesPanel';
// localStorage key for persisted cloud-editor console logs (survive refresh).
const CLOUD_LOGS_KEY = 'bionodulo.cloud.logs';

// Cloud editor live collaboration (Yjs over the Cloudflare Durable-Objects
// Worker). When set, collab "rooms" are implicit (team + workflow) — there is no
// local FastAPI room/share backend to call.
const CLOUD_COLLAB = (import.meta.env.VITE_COLLAB_PROVIDER || '').trim() === 'durable-objects';

const SettingsPanel = lazy(() => import('./components/panels/SettingsPanel'));
const HelpWikiPanel = lazy(() => import('./components/panels/HelpWikiPanel'));
const TemplatesPanel = lazy(() => import('./components/panels/TemplatesPanel'));
const EnvironmentPanel = lazy(() => import('./components/panels/EnvironmentPanel'));
const RuntimeArtifactsPanel = lazy(() => import('./components/panels/RuntimeArtifactsPanel'));
const HPCPanel = lazy(() => import('./components/panels/HPCPanel'));
const NodeLibraryPanel = lazy(() => import('./components/panels/NodeLibraryPanel'));
const WorkspacePanel = lazy(() => import('./components/panels/WorkspacePanel'));
const UserPanel = lazy(() => import('./components/panels/UserPanel'));
const ComputePanel = lazy(() => import('./components/panels/ComputePanel'));
import type { SampleSheetRun } from './components/modals/BatchSampleSheetModal';
import MissingDependenciesBanner from './components/layout/MissingDependenciesBanner';
import HostPrerequisitesBanner from './components/layout/HostPrerequisitesBanner';
import Icon from './components/ui/Icon';
import TransferWindow from './components/cloud/TransferWindow';
import { collectLocalFilePaths, baseName } from './utils/workflowFiles';
import { localFileSize, uploadWorkspaceFileToCloud } from './api/cloudFiles';
import {
  CommandPaletteHost,
  ConfirmDialogHost,
  KeyboardShortcutsModal,
  NotificationHost,
  Spinner,
  alertDialog,
  confirmDialog,
  promptDialog,
  toast,
  toggleCommandPalette,
  type CommandItem,
} from './components/ui';
import { useSettings } from './hooks/settings';
import { useObjectInfo } from './hooks/data';
import { useWebSocket } from './hooks/useWebSocket';
import { usePanelLayout } from './hooks/usePanelLayout';
import { useHPC } from './hooks/useHPC';
import { useAutoSave, useQueueMode, useWorkflow, useWorkflowMessages, useDependencyInstall, installProgressMessage } from './hooks/workflow';
import type { CheckpointRecord } from './hooks/workflow/useWorkflowRuntimeArtifacts';
import { useAuth, useCollabPolling } from './hooks/collab';
import { useCloudConfig, useClerkAuth } from './hooks/cloud';
import { useGlobalShortcut, useKeybindings, useRegisteredCommands } from './hooks/ui';
import { usePaletteTheme } from './hooks/usePaletteTheme';
import { logError } from './state/logging';
import { bootProgress, bootDone } from './state/bootLoader';
import { usePanelRegistry } from './state/panels';
import { paletteDisplayName } from './state/palettes';
import { rememberRecentWorkflow } from './state/recentWorkflows';
import { renderRecentThumbnail } from './utils/workflowThumbnail';
import { resolveWorkflowName, suggestWorkflowName } from './utils/workflowNaming';
import { buildShareUrl, readWorkflowFromHash, clearShareHash } from './utils/workflowShare';
import { nodeCategoryDisplayLabel } from './utils/nodeCategories';
import { redactSecrets } from './utils/redaction';
import {
  CLOUD_CREDITS_POLL_HIDDEN_MS,
  CLOUD_CREDITS_POLL_VISIBLE_MS,
  CLOUD_RUN_POLL_HIDDEN_MS,
  CLOUD_RUN_POLL_VISIBLE_MS,
  startVisibilityAwarePolling,
} from './utils/pollingPolicy';
import { makeConsoleActionCopy } from './utils/consoleActionCopy';
import { makeAppFileActionCopy } from './utils/appFileActionCopy';
import { promptWorkflowRunParameters } from './utils/workflowParameters';
import { makeAppCollabCopy } from './collab/appCollabCopy';
import { appWebSocketUrl } from './utils/appBase';
import { logTelemetry } from './state/telemetry';
import { installDomOverlayBridge } from './state/overlays';
import {
  buildCollabRoomUrl,
  clearCollabLinkParams,
  parseCollabLinkTarget,
  readCollabLinkTarget,
  type CollabLinkTarget,
} from './collab/shareLinks';
import {
  WorkflowYjsBridge, useCollab, workflowToDoc, docToWorkflow,
  CollabBadge,
  getUserColor, getToken, AuthDialog,
} from './collab';
import { defaultsFor, valuesFromUnknownRecord } from './utils';
import { apiGet, apiGetText, apiPost, apiDelete, ApiError } from './api/client';
import { getCloudRun, getCloudCredits } from './api/website';
import {
  mapCloudRunStatus,
  isTerminalCloudStatus,
  deriveCloudNodeStatuses,
  buildCloudNodeStatuses,
  nodeIdFromTag,
  stripNodeTag,
} from './utils/cloudRunStatus';
import InviteDialog from './collab/InviteDialog';
const OpenWorkflowModal = lazy(() => import('./components/modals/OpenWorkflowModal'));
import { safeValidateHostStatus, safeValidateRunsList } from './api/validators';
import { instantiateBlueprint } from './state/subgraphLibrary';
import { getLocalTemplateWorkflow } from './localTemplates';
import {
  requestedWorkflowIdAtom,
  computeSpecAtom,
} from './state/appAtoms';
import { specToRunBody } from './utils/computeSpec';
import {
  showExportAtom,
  showImportAtom,
  showBulkParamAtom,
  showDoctorAtom,
  showAIAtom,
  showBatchSheetAtom,
  showGettingStartedAtom,
  showShortcutsAtom,
  showShareDialogAtom,
  showInviteDialogAtom,
  showCommentsAtom,
  showOpenWorkflowAtom,
  selectedNodeIdAtom,
  consoleVisibleAtom,
  focusModeAtom,
} from './state/uiAtoms';
import {
  batchCountAtom,
  hostStatusAtom,
  isRunningAtom,
  logsAtom,
  nodeRunProgressAtom,
} from './state/runAtoms';
import { Modals } from './components/modals/Modals';
import type { Workflow, WorkflowNode, HPCConfig, TemplateInfo, LogEntry, ResolveReport, HostStatus, RunRecord, NodeStatus } from './types';
import type { Comment, LivePresenceUser } from './collab';

const EMPTY_STRING_ARRAY: string[] = [];
type OpenPanelTab = Exclude<RailTab, null | 'console'>;
const CENTER_MENU_TABS = new Set<OpenPanelTab>(['settings', 'templates']);
const isCenterMenuTab = (tab: OpenPanelTab): boolean => CENTER_MENU_TABS.has(tab);
const PANEL_LABEL_KEYS: Partial<Record<OpenPanelTab, string>> = {
  data: 'panels.workspace',
  nodes: 'panels.nodes',
  templates: 'panels.templates',
  environments: 'panels.environment',
  runtimeArtifacts: 'panels.runtimeArtifacts',
  help: 'panels.helpWiki',
  settings: 'panels.settings',
  hpc: 'panels.hpc',
  user: 'panels.account',
  compute: 'panels.compute',
};
type AppHistorySnapshot = {
  nodes: WorkflowNode[];
  edges: Workflow['edges'];
  groups: Workflow['groups'];
  parameters: Workflow['parameters'];
  viewport?: { x: number; y: number; scale: number };
};

function workflowNameSignature(workflows: Workflow[]): string {
  return JSON.stringify(workflows.map(workflow => [workflow.id ?? '', workflow.name || 'Untitled']));
}

function recordSignature(record: Record<string, string>): string {
  return JSON.stringify(Object.entries(record).sort(([a], [b]) => a.localeCompare(b)));
}

function workflowExecutionPlan(workflow: Workflow, targetNodes?: string[]): string[] {
  const executable = workflow.nodes
    .filter(node => node.type !== 'note' && node.type !== 'reroute')
    .map(node => node.id);
  if (!targetNodes || targetNodes.length === 0) return executable;
  const targets = new Set(targetNodes);
  return executable.filter(nodeId => targets.has(nodeId));
}

function nodeTypeSignature(nodes: WorkflowNode[]): string {
  return JSON.stringify(nodes.map(node => [node.id, node.type]));
}

function nodeStatusSignature(statuses: NodeStatus[]): string {
  return JSON.stringify(statuses.map(status => [status.node_id, status.status]));
}

function createWorkflowId(): string {
  if (typeof crypto !== 'undefined' && crypto.randomUUID) {
    return crypto.randomUUID();
  }
  return `wf-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
}

function withWorkflowId(workflow: Workflow, id = workflow.id || createWorkflowId()): Workflow {
  return { ...workflow, id };
}

function emptySharedWorkflow(id: string, name: string): Workflow {
  return {
    id,
    version: '2.0',
    app: 'bionodulo',
    name,
    description: '',
    nodes: [],
    edges: [],
    groups: [],
    outputs: {},
  };
}

function workflowFromCollabSnapshot(workflowId: string, snapshot: Record<string, unknown>, fallbackName: string): Workflow {
  const meta = (snapshot.meta && typeof snapshot.meta === 'object' ? snapshot.meta : {}) as Record<string, unknown>;
  return {
    id: workflowId,
    version: String(meta.version || '2.0'),
    app: 'bionodulo',
    name: String(meta.name || fallbackName),
    description: '',
    nodes: valuesFromUnknownRecord<WorkflowNode>(snapshot.nodes),
    edges: valuesFromUnknownRecord<Workflow['edges'][number]>(snapshot.edges),
    groups: valuesFromUnknownRecord<Workflow['groups'][number]>(snapshot.groups),
    outputs: {},
  };
}

function remapTemplateWorkflow(data: Workflow): Workflow {
  const oldToNew = new Map<string, string>();
  data.nodes = data.nodes.map((n, i) => {
    const newId = `${n.type}_${Date.now()}_${i}`;
    oldToNew.set(n.id, newId);
    return { ...n, id: newId };
  });
  data.edges = data.edges.map(e => ({
    ...e,
    from: { ...e.from, node: oldToNew.get(e.from.node) || e.from.node },
    to: { ...e.to, node: oldToNew.get(e.to.node) || e.to.node },
  }));
  return data;
}

async function fetchTemplateWorkflow(template: TemplateInfo): Promise<Workflow | null> {
  try {
    const data = await apiGet<Workflow>(`/api/workflow_templates/${template.filename}`);
    return data ? remapTemplateWorkflow(data) : null;
  } catch {
    const data = getLocalTemplateWorkflow(template.filename);
    return data ? remapTemplateWorkflow(data) : null;
  }
}

export default function App() {
  const { t, i18n } = useTranslation();
  const { get, getBool, set, ready: settingsReady } = useSettings();
  const {
    workflows, activeIndex, activeWorkflow, validation, resolveReport, runs,
    setWorkflow, updateWorkflow, addTab, addWorkflow, closeTab, reorderWorkflows, setActiveIndex,
    openCloudWorkflow, newCloudWorkflow,
    validate, resolve, clearResolveReport, submitRun, addRun, updateRun, setRuns,
  } = useWorkflow();
  // Theme is fully owned by the palette system (usePaletteTheme + state/palettes),
  // which applies the active palette and its light/dark class on load and on change.
  const { palettes, setPalette } = usePaletteTheme();
  const { getBinding } = useKeybindings();
  const { objectInfo, loading: objectInfoLoading, error: objectInfoError, refresh: refreshObjectInfo } = useObjectInfo();
  const registeredPanels = usePanelRegistry();

  // Surface node-registry load failures. An empty/failed registry silently
  // strips node ports and drops every edge (nodes render but nothing connects),
  // so instead of failing quiet we show a persistent, actionable notification.
  // A 401 means the editor session isn't authenticated — prompt sign-in; any
  // other error offers a retry. The registry keeps its last-good value, so an
  // already-loaded canvas stays intact behind the banner.
  const objectInfoErrorShownRef = useRef(false);
  useEffect(() => {
    if (!objectInfoError) {
      objectInfoErrorShownRef.current = false;
      toast.dismiss('object-info-error');
      return;
    }
    if (objectInfoErrorShownRef.current) return;
    objectInfoErrorShownRef.current = true;
    const status = objectInfoError instanceof ApiError ? objectInfoError.status : 0;
    const isAuth = status === 401 || status === 403;
    toast.show({
      id: 'object-info-error',
      tone: 'error',
      dismissible: true,
      duration: 0,
      title: isAuth ? t('objectInfo.authErrorTitle') : t('objectInfo.loadErrorTitle'),
      message: isAuth ? t('objectInfo.authErrorMessage') : t('objectInfo.loadErrorMessage'),
      actions: [
        {
          label: t('objectInfo.retry'),
          onClick: () => { objectInfoErrorShownRef.current = false; void refreshObjectInfo(); },
          dismiss: true,
        },
      ],
    });
  }, [objectInfoError, refreshObjectInfo, t]);

  // Drive the inline boot loader (index.html) as the app initializes, then
  // dismiss it once the node registry + settings have resolved (both settle even
  // offline, so the loader never hangs waiting on the backend).
  const bootDoneRef = useRef(false);
  useEffect(() => {
    bootProgress(settingsReady ? 70 : 55, t('boot.loadingSettings'));
  }, [settingsReady, t]);
  useEffect(() => {
    if (!objectInfoLoading) bootProgress(90, t('boot.loadingNodes'));
  }, [objectInfoLoading, t]);
  useEffect(() => {
    if (bootDoneRef.current) return;
    if (settingsReady && !objectInfoLoading) {
      bootDoneRef.current = true;
      bootProgress(100, t('boot.ready'));
      bootDone();
    }
  }, [settingsReady, objectInfoLoading, t]);

  const consoleActionCopy = useMemo(() => makeConsoleActionCopy(t), [t]);
  const appFileActionCopy = useMemo(() => makeAppFileActionCopy(t), [t]);
  const appCollabCopy = useMemo(() => makeAppCollabCopy(t), [t]);

  // Authentication state — extracted to useAuth.
  const collabEnabled = getBool('bionodulo.collab.enabled');
  const initialCollabTarget = useMemo(() => readCollabLinkTarget(), []);
  const initialRequestedWorkflowId = initialCollabTarget?.workflowId ?? null;
  const [collabInvite, setCollabInvite] = useState<CollabLinkTarget | null>(initialCollabTarget);
  const [collabPublicBaseUrl, setCollabPublicBaseUrl] = useState<string | null>(null);
  const [collabRoomActive, setCollabRoomActive] = useState(false);
  const [pendingCollabAction, setPendingCollabAction] = useState<
    { type: 'create' } | { type: 'join'; target: CollabLinkTarget } | null
  >(null);
  const [requestedWorkflowId, setRequestedWorkflowId] = useAtom(requestedWorkflowIdAtom);
  // Selected cloud compute spec (Compute panel) sent with the next cloud run.
  const computeSpec = useAtomValue(computeSpecAtom);
  // Cloud-launch config (auto-login + account snapshot). No-op in local mode.
  const { cloudConfig, cloudMode, editorMode } = useCloudConfig();
  // True once /api/config has resolved (success or fallback). Host-only boot
  // polls wait for this so they don't fire in the sub-second window before
  // editorMode is known — otherwise the cloud editor briefly hits host-only
  // endpoints (/host_status, /queue, /history, /system_stats) the Lambda can't
  // serve. `null` = not yet fetched.
  const configResolved = cloudConfig !== null;
  // Host-only features run only in a resolved, non-editor config.
  const hostFeaturesEnabled = configResolved && !editorMode;
  // Optional Clerk sign-in for self-host when a publishable key is configured
  // and we are not in cloud auto-login mode. No-op otherwise.
  const clerk = useClerkAuth();
  const {
    authUser,
    authReady,
    showAuthDialog,
    setShowAuthDialog,
    handleAuthLogin,
    handleAuthClose,
    // Editor mode is also an auto-login context: identity comes from the website
    // session (seeded into authUser via /api/me), so treat it like cloudMode for
    // auth — mark ready, never show the guest dialog, never null authUser.
  } = useAuth({ collabEnabled, settingsReady, cloudMode: cloudMode || editorMode });
  const setShowShareDialog = useSetAtom(showShareDialogAtom);
  const setShowInviteDialog = useSetAtom(showInviteDialogAtom);
  const setShowOpenWorkflow = useSetAtom(showOpenWorkflowAtom);
  const effectiveRequestedWorkflowId = requestedWorkflowId || initialRequestedWorkflowId;
  const resetCollabOnStartupRef = useRef(false);

  useEffect(() => {
    if (!settingsReady || resetCollabOnStartupRef.current) return;
    resetCollabOnStartupRef.current = true;
    if (getBool('bionodulo.collab.enabled')) {
      set('bionodulo.collab.enabled', false);
    }
  }, [getBool, set, settingsReady]);

  useEffect(() => installDomOverlayBridge(), []);

  // Stash the hash payload at app mount so we can replay it once
  // handleImport is wired up. We strip the hash immediately so a refresh
  // doesn't keep stomping the workspace if the import fails mid-flight.
  const pendingHashWorkflowRef = useRef<Workflow | null>(null);
  useEffect(() => {
    const wf = readWorkflowFromHash();
    if (!wf) return;
    pendingHashWorkflowRef.current = wf;
    clearShareHash();
  }, []);

  useEffect(() => {
    if (initialRequestedWorkflowId && requestedWorkflowId !== initialRequestedWorkflowId) {
      setRequestedWorkflowId(initialRequestedWorkflowId);
    }
  }, [initialRequestedWorkflowId, requestedWorkflowId, setRequestedWorkflowId]);

  // Collaboration setup
  const currentUser = useMemo(() => (
    authUser
      ? { id: authUser.id, name: authUser.name, color: authUser.color }
      : { id: 'anonymous', name: appCollabCopy.anonymousUserName, color: getUserColor('anonymous') }
  ), [appCollabCopy.anonymousUserName, authUser?.color, authUser?.id, authUser?.name]);
  const pendingWorkflowIdsRef = useRef<WeakMap<Workflow, string>>(new WeakMap());
  const activeWorkflowId = useMemo(() => {
    if (activeWorkflow.id) return activeWorkflow.id;
    const existing = pendingWorkflowIdsRef.current.get(activeWorkflow);
    if (existing) return existing;
    const id = createWorkflowId();
    pendingWorkflowIdsRef.current.set(activeWorkflow, id);
    return id;
  }, [activeWorkflow]);

  useEffect(() => {
    if (!activeWorkflow.id) {
      updateWorkflow(activeIndex, { id: activeWorkflowId });
    }
  }, [activeWorkflow.id, activeWorkflowId, activeIndex, updateWorkflow]);

  // Copied collaboration links pin the local tab to a room ID, but do not
  // connect until the user explicitly joins from the Collaboration menu.
  useEffect(() => {
    if (!effectiveRequestedWorkflowId) return;
    if (activeWorkflow.id !== effectiveRequestedWorkflowId) {
      updateWorkflow(activeIndex, { id: effectiveRequestedWorkflowId });
    }
  }, [activeWorkflow.id, activeIndex, effectiveRequestedWorkflowId, updateWorkflow]);

  const requestedWorkflowPending = Boolean(effectiveRequestedWorkflowId && activeWorkflow.id !== effectiveRequestedWorkflowId);
  const collabWorkflowId = (
    collabEnabled
    && collabRoomActive
    && settingsReady
    && authReady
    && Boolean(authUser)
    && !requestedWorkflowPending
  ) ? activeWorkflowId : null;
  const collabSessionActive = Boolean(collabWorkflowId);

  const {
    doc: collabDoc,
    localSessionId: collabSessionId,
    connected: collabConnected,
    connecting: collabConnecting,
    activeUsers: collabActiveUsers,
    setCursor: setCollabCursor,
    setSelection: setCollabSelection,
    claimDrag: claimCollabDrag,
    releaseDrag: releaseCollabDrag,
    isShared: collabIsShared,
    error: collabError,
    reconnectAttempt: collabReconnectAttempt,
    offline: collabOffline,
  } = useCollab(collabWorkflowId, currentUser);

  const bridgeRef = useRef<WorkflowYjsBridge | null>(null);
  const suppressLocalSeedForWorkflowRef = useRef<string | null>(null);
  const activeWorkflowRef = useRef(activeWorkflow);
  const updateWorkflowRef = useRef(updateWorkflow);

  useEffect(() => { activeWorkflowRef.current = activeWorkflow; }, [activeWorkflow]);
  useEffect(() => { updateWorkflowRef.current = updateWorkflow; }, [updateWorkflow]);

  useEffect(() => {
    if (!collabDoc || collabConnecting) {
      bridgeRef.current?.unbind();
      bridgeRef.current = null;
      return;
    }
    const yNodes = collabDoc.getMap('nodes');
    const yEdges = collabDoc.getMap('edges');
    const yGroups = collabDoc.getMap('groups');
    const yComments = collabDoc.getMap('comments');
    const remoteHasWorkflow = yNodes.size > 0 || yEdges.size > 0 || yGroups.size > 0 || yComments.size > 0;
    if (remoteHasWorkflow) {
      const remoteWorkflow = docToWorkflow(collabDoc);
      updateWorkflowRef.current(activeIndex, {
        id: activeWorkflowId,
        name: remoteWorkflow.name || activeWorkflowRef.current.name,
        nodes: remoteWorkflow.nodes,
        edges: remoteWorkflow.edges,
        groups: remoteWorkflow.groups,
        parameters: remoteWorkflow.parameters,
        comments: remoteWorkflow.comments,
      });
    } else if (
      suppressLocalSeedForWorkflowRef.current !== activeWorkflowId
      && activeWorkflowRef.current.nodes.length > 0
    ) {
      workflowToDoc(activeWorkflowRef.current, collabDoc);
    }
    if (suppressLocalSeedForWorkflowRef.current === activeWorkflowId) {
      suppressLocalSeedForWorkflowRef.current = null;
    }
    const bridge = new WorkflowYjsBridge(collabDoc, {
      onNodesChange: (nodes) => updateWorkflowRef.current(activeIndex, { nodes }),
      onEdgesChange: (edges) => updateWorkflowRef.current(activeIndex, { edges }),
      onGroupsChange: (groups) => updateWorkflowRef.current(activeIndex, { groups }),
      onCommentsChange: (comments) => updateWorkflowRef.current(activeIndex, { comments }),
      getNodes: () => activeWorkflowRef.current.nodes,
      getEdges: () => activeWorkflowRef.current.edges,
      getGroups: () => activeWorkflowRef.current.groups,
      getComments: () => activeWorkflowRef.current.comments ?? [],
      onDragStart: claimCollabDrag,
      onDragEnd: releaseCollabDrag,
    });
    bridge.bind();
    bridgeRef.current = bridge;
    return () => {
      bridge.unbind();
      bridgeRef.current = null;
    };
  }, [activeWorkflowId, collabDoc, collabConnecting, activeIndex, claimCollabDrag, releaseCollabDrag]);

  // Phase 3 collaboration panels — App reads showAI / showComments for shell
  // class toggling.
  const showComments = useAtomValue(showCommentsAtom);
  const [followingUserId, setFollowingUserId] = useState<string | null>(null);
  const selectedNodeId = useAtomValue(selectedNodeIdAtom);
  const [livePresenceUsers, setLivePresenceUsers] = useState<LivePresenceUser[]>([]);
  // Cross-workflow display names came from the (removed) comments REST feed; in
  // single-doc collab there is one workflow, so this stays empty and lookups
  // fall back to the active tab names.
  const workflowNames = useMemo<Record<string, string>>(() => ({}), []);

  // Comments are part of the workflow (persisted with it) and sync in real time
  // through the collab Yjs doc when a session is active (bridge wiring below).
  const workflowComments = useMemo<Comment[]>(() => activeWorkflow.comments ?? [], [activeWorkflow.comments]);

  const applyComments = useCallback((next: Comment[]) => {
    updateWorkflow(activeIndex, { comments: next });
    bridgeRef.current?.onCommentsChanged(next);
  }, [activeIndex, updateWorkflow]);

  const handleAddComment = useCallback((content: string, nodeId: string | null, parentId: string | null) => {
    const now = new Date().toISOString();
    const comment: Comment = {
      id: createWorkflowId(),
      workflow_id: activeWorkflowId,
      node_id: nodeId,
      parent_id: parentId,
      user_id: currentUser.id,
      user_name: currentUser.name,
      user_color: currentUser.color,
      content,
      resolved: false,
      created_at: now,
      updated_at: now,
      replies: [],
    };
    applyComments([...(activeWorkflow.comments ?? []), comment]);
  }, [activeWorkflow.comments, activeWorkflowId, currentUser, applyComments]);

  const handleResolveComment = useCallback((id: string) => {
    applyComments((activeWorkflow.comments ?? []).map(c => (c.id === id ? { ...c, resolved: true, updated_at: new Date().toISOString() } : c)));
  }, [activeWorkflow.comments, applyComments]);

  const handleDeleteComment = useCallback((id: string) => {
    applyComments((activeWorkflow.comments ?? []).filter(c => c.id !== id && c.parent_id !== id));
  }, [activeWorkflow.comments, applyComments]);

  useCollabPolling({ collabEnabled: collabSessionActive, setLivePresenceUsers });

  useEffect(() => {
    if (!followingUserId) return;
    const user = collabActiveUsers.find(candidate => (
      candidate.user.sessionId === followingUserId || candidate.user.id === followingUserId
    ));
    if (user?.viewport) {
      canvasRef.current?.setViewport(user.viewport);
    }
  }, [collabActiveUsers, followingUserId]);

  const publishCollabWorkflowSnapshot = useCallback(async (workflow: Workflow) => {
    if (!collabSessionActive || !workflow.id) return;
    const token = getToken();
    if (!token) return;
    try {
      await apiPost(`/api/collab/workflows/${encodeURIComponent(workflow.id)}/snapshot`, { workflow });
    } catch (err) {
      logError('collab.snapshot.publish', err);
      // The socket bridge still handles normal collaboration when REST is unavailable.
    }
  }, [collabSessionActive]);

  const fetchCollabSnapshot = useCallback(async (workflowId: string, fallbackName: string): Promise<Workflow | null> => {
    const token = getToken();
    if (!token) return null;
    let data: { snapshot?: Record<string, unknown> };
    try {
      data = await apiGet<{ snapshot?: Record<string, unknown> }>(
        `/api/collab/workflows/${encodeURIComponent(workflowId)}/snapshot`,
      );
    } catch {
      return null;
    }
    if (!data.snapshot) return null;
    return workflowFromCollabSnapshot(workflowId, data.snapshot, fallbackName);
  }, []);

  const activeInviteToken = collabInvite?.workflowId === activeWorkflowId
    ? collabInvite.inviteToken ?? null
    : null;
  const activeCollabJoinTarget = collabInvite?.workflowId === activeWorkflowId ? collabInvite : undefined;
  const collabShareLink = useMemo(
    () => buildCollabRoomUrl(activeWorkflowId, activeInviteToken, collabPublicBaseUrl),
    [activeWorkflowId, activeInviteToken, collabPublicBaseUrl],
  );
  const hasPendingJoinLink = Boolean(
    effectiveRequestedWorkflowId
    && !collabEnabled
    && activeWorkflowId === effectiveRequestedWorkflowId,
  );

  const requestCollabAuth = useCallback((action: { type: 'create' } | { type: 'join'; target: CollabLinkTarget }) => {
    set('bionodulo.collab.enabled', true);
    setPendingCollabAction(action);
    setShowAuthDialog(true);
  }, [set, setShowAuthDialog]);

  const handleCreateCollabSession = useCallback(async () => {
    if (!authUser) {
      requestCollabAuth({ type: 'create' });
      return;
    }
    // Cloud editor: the "room" is the team's workflow (no local FastAPI room /
    // share-link backend). Turning collaboration on connects to the shared doc;
    // teammates collaborate by opening the same workflow — prompt to invite one.
    if (CLOUD_COLLAB) {
      set('bionodulo.collab.enabled', true);
      setCollabRoomActive(true);
      setShowInviteDialog(true);
      toast.success(appCollabCopy.toast.linkReady, {
        message: t('collab.cloudCollabOn', { defaultValue: 'Live collaboration is on. Invite teammates to edit together.' }),
      });
      return;
    }
    const workflowForRoom = withWorkflowId(activeWorkflow, activeWorkflowId);
    if (activeWorkflow.id !== activeWorkflowId) {
      updateWorkflow(activeIndex, workflowForRoom);
    }
    set('bionodulo.collab.enabled', true);
    let publicBaseUrl = collabPublicBaseUrl;
    try {
      const room = await apiPost<{
        workflow_id: string;
        invite_token: string;
        role: string;
        public_url?: string | null;
      }>('/api/collab/rooms', { workflow_id: activeWorkflowId, role: 'editor' });
      publicBaseUrl = room.public_url || publicBaseUrl;
      setCollabPublicBaseUrl(publicBaseUrl || null);
      setCollabInvite({ workflowId: room.workflow_id, inviteToken: room.invite_token });
      await apiPost(`/api/collab/workflows/${encodeURIComponent(room.workflow_id)}/snapshot`, {
        workflow: workflowForRoom,
      });
      setCollabRoomActive(true);
      const url = buildCollabRoomUrl(room.workflow_id, room.invite_token, publicBaseUrl);
      try {
        if (!navigator.clipboard) throw new Error('Clipboard unavailable');
        await navigator.clipboard.writeText(url);
        toast.success(appCollabCopy.toast.linkCopied, {
          message: appCollabCopy.createLinkCopiedMessage(Boolean(publicBaseUrl)),
        });
      } catch {
        toast.success(appCollabCopy.toast.linkReady, {
          message: appCollabCopy.createLinkReadyMessage(Boolean(publicBaseUrl)),
        });
      }
      setShowShareDialog(true);
    } catch (err) {
      set('bionodulo.collab.enabled', false);
      setCollabRoomActive(false);
      toast.error(appCollabCopy.error.createLinkFailed, { message: err instanceof Error ? err.message : String(err) });
      logError('collab.room.create', err);
    }
  }, [
    activeIndex,
    activeWorkflow,
    activeWorkflow.id,
    activeWorkflowId,
    appCollabCopy,
    authUser,
    collabSessionActive,
    collabPublicBaseUrl,
    setCollabRoomActive,
    requestCollabAuth,
    set,
    setShowShareDialog,
    setShowInviteDialog,
    t,
    updateWorkflow,
  ]);

  const handleJoinCollabSession = useCallback(async (target?: CollabLinkTarget) => {
    let joinTarget = target;
    if (!joinTarget) {
      const value = await promptDialog(appCollabCopy.joinPrompt());
      if (!value) return;
      joinTarget = parseCollabLinkTarget(value) ?? undefined;
    }
    if (!joinTarget) {
      toast.error(appCollabCopy.error.invalidLinkTitle, { message: appCollabCopy.error.invalidLinkMessage });
      return;
    }
    setRequestedWorkflowId(joinTarget.workflowId);
    if (activeWorkflow.id !== joinTarget.workflowId) {
      updateWorkflow(activeIndex, { id: joinTarget.workflowId });
    }
    if (!authUser) {
      requestCollabAuth({ type: 'join', target: joinTarget });
      return;
    }
    // Cloud editor: joining == opening the team's workflow; the room token is
    // fetched on connect. No local FastAPI join call.
    if (CLOUD_COLLAB) {
      set('bionodulo.collab.enabled', true);
      setCollabRoomActive(true);
      toast.success(appCollabCopy.toast.joined, {
        message: t('collab.cloudCollabOn', { defaultValue: 'Live collaboration is on. Invite teammates to edit together.' }),
      });
      return;
    }
    set('bionodulo.collab.enabled', true);
    try {
      const joined = await apiPost<{ workflow_id: string; role: string }>('/api/collab/rooms/join', {
        workflow_id: joinTarget.workflowId,
        invite_token: joinTarget.inviteToken || null,
      });
      setCollabInvite(joinTarget.inviteToken ? joinTarget : null);
      setCollabRoomActive(true);
      toast.success(appCollabCopy.toast.joined, { message: appCollabCopy.connectedAsRole(joined.role) });
    } catch (err) {
      set('bionodulo.collab.enabled', false);
      setCollabRoomActive(false);
      toast.error(appCollabCopy.error.joinFailed, { message: err instanceof Error ? err.message : String(err) });
      logError('collab.room.join', err);
    }
  }, [
    activeIndex,
    activeWorkflow.id,
    appCollabCopy,
    authUser,
    requestCollabAuth,
    set,
    setCollabRoomActive,
    setRequestedWorkflowId,
    t,
    updateWorkflow,
  ]);

  useEffect(() => {
    if (!pendingCollabAction || !authReady || !authUser) return;
    const action = pendingCollabAction;
    setPendingCollabAction(null);
    if (action.type === 'create') {
      void handleCreateCollabSession();
    } else {
      void handleJoinCollabSession(action.target);
    }
  }, [authReady, authUser, handleCreateCollabSession, handleJoinCollabSession, pendingCollabAction]);

  const handleLeaveCollabSession = useCallback(() => {
    set('bionodulo.collab.enabled', false);
    setCollabRoomActive(false);
    setRequestedWorkflowId(null);
    setPendingCollabAction(null);
    clearCollabLinkParams();
    toast.info(appCollabCopy.toast.stopped, { message: appCollabCopy.toast.offlineModeRestored });
  }, [appCollabCopy, set, setCollabRoomActive, setRequestedWorkflowId]);

  const handleCollabAuthClose = useCallback(() => {
    if (pendingCollabAction && !authUser) {
      setPendingCollabAction(null);
      setCollabRoomActive(false);
      set('bionodulo.collab.enabled', false);
    }
    handleAuthClose();
  }, [authUser, handleAuthClose, pendingCollabAction, set, setCollabRoomActive]);

  const followPresenceUser = useCallback(async (sessionId: string | null) => {
    if (!sessionId) {
      setFollowingUserId(null);
      return;
    }
    const presence = livePresenceUsers.find(user => user.session_id === sessionId)
      ?? livePresenceUsers.find(user => user.user_id === sessionId);
    if (presence?.workflow_id) {
      const workflowName = workflowNames[presence.workflow_id] || appCollabCopy.workflowFallback(presence.workflow_id);
      let snapshotWorkflow: Workflow | null = null;
      try {
        snapshotWorkflow = await fetchCollabSnapshot(presence.workflow_id, workflowName);
      } catch (err) {
        logError('collab.snapshot.fetch', err);
        // Realtime sync remains the source of truth if the snapshot endpoint is unavailable.
      }
      if (presence.workflow_id !== activeWorkflowId) {
        const targetWorkflow = snapshotWorkflow ?? emptySharedWorkflow(presence.workflow_id, workflowName);
        const existingIndex = workflows.findIndex(workflow => workflow.id === presence.workflow_id);
        suppressLocalSeedForWorkflowRef.current = presence.workflow_id;
        if (existingIndex >= 0) {
          if (snapshotWorkflow) {
            setWorkflow(existingIndex, () => snapshotWorkflow);
          }
          setActiveIndex(existingIndex);
        } else {
          addWorkflow(targetWorkflow);
        }
        const url = new URL(window.location.href);
        url.searchParams.set('workflow', presence.workflow_id);
        window.history.replaceState({}, '', url);
      } else if (snapshotWorkflow) {
        setWorkflow(activeIndex, () => snapshotWorkflow);
      }
      if (snapshotWorkflow) {
        requestAnimationFrame(() => {
          requestAnimationFrame(() => canvasRef.current?.fitView());
        });
      }
      const targetAwareness = collabActiveUsers.find(candidate => (
        candidate.user.sessionId === presence.session_id || candidate.user.id === presence.user_id
      ));
      if (targetAwareness?.viewport) {
        canvasRef.current?.setViewport(targetAwareness.viewport);
      }
    }
    setFollowingUserId(presence?.session_id ?? sessionId);
  }, [activeIndex, activeWorkflowId, addWorkflow, appCollabCopy, collabActiveUsers, fetchCollabSnapshot, livePresenceUsers, setActiveIndex, setWorkflow, workflows, workflowNames]);

  // Host prerequisite status
  const [hostStatus, setHostStatus] = useAtom(hostStatusAtom);
  const [dismissedHostStatus, setDismissedHostStatus] = useState<HostStatus | null>(null);

  useEffect(() => {
    if (!hostFeaturesEnabled) return; // no host prerequisites in the cloud editor
    apiGet<unknown>('/api/host_status')
      .then(raw => {
        const result = safeValidateHostStatus(raw);
        if (result.ok) setHostStatus(result.value as HostStatus);
        else logError('host_status.validate', result.error);
      })
      .catch(() => { /* offline */ });
  }, [hostFeaturesEnabled]);

  const setLogs = useSetAtom(logsAtom);
  const MAX_LOGS = 5000;
  const addLog = useCallback((entry: LogEntry) => {
    setLogs(prev => {
      const next = [...prev, entry];
      if (next.length > MAX_LOGS) next.splice(0, next.length - MAX_LOGS);
      return next;
    });
  }, []);
  const clearLogs = useCallback(() => {
    setLogs([]);
    if (editorMode) { try { localStorage.removeItem(CLOUD_LOGS_KEY); } catch { /* ignore */ } }
  }, [editorMode]);

  // Cloud editor: the console logs live in volatile atom state, so a page
  // refresh wiped them — unhelpful when a run is executing on Batch. Persist a
  // capped tail to localStorage and restore it once on load.
  const logs = useAtomValue(logsAtom);
  const cloudLogsRestoredRef = useRef(false);
  useEffect(() => {
    if (!editorMode || cloudLogsRestoredRef.current) return;
    cloudLogsRestoredRef.current = true;
    try {
      const raw = localStorage.getItem(CLOUD_LOGS_KEY);
      if (raw) {
        const arr = JSON.parse(raw) as LogEntry[];
        if (Array.isArray(arr) && arr.length > 0) setLogs(arr);
      }
    } catch { /* corrupt/unavailable storage */ }
  }, [editorMode, setLogs]);
  useEffect(() => {
    if (!editorMode || !cloudLogsRestoredRef.current) return;
    const id = setTimeout(() => {
      try { localStorage.setItem(CLOUD_LOGS_KEY, JSON.stringify(logs.slice(-1000))); } catch { /* quota */ }
    }, 800);
    return () => clearTimeout(id);
  }, [logs, editorMode]);

  // Remaining team credits, shown in the Cloud badge. Polled in the cloud editor
  // (same-origin cookie) AND in the locally-run app when signed into a cloud
  // account (cross-origin bearer; configureWebsiteApi set the absolute base).
  const [cloudCredits, setCloudCredits] = useState<number | null>(null);
  const creditsEligible = editorMode || (Boolean(authUser) && Boolean(cloudConfig?.accountUrl));
  useEffect(() => {
    if (!creditsEligible) return;
    let cancelled = false;
    const refresh = async () => {
      const credits = await getCloudCredits();
      if (!cancelled && credits) setCloudCredits(credits.remaining);
    };
    const stopPolling = startVisibilityAwarePolling(
      refresh,
      CLOUD_CREDITS_POLL_VISIBLE_MS,
      CLOUD_CREDITS_POLL_HIDDEN_MS,
    );
    return () => {
      cancelled = true;
      stopPolling();
    };
  }, [creditsEligible]);

  // Per-node run progress for inline canvas captions. Populated on node_start
  // events ({ current, total } parsed from the payload's "i/N" progress hint)
  // and cleared once the node finishes/errors so the caption only sits on
  // actively-running nodes.
  const setNodeRunProgress = useSetAtom(nodeRunProgressAtom);
  const recordNodeStart = useCallback((nodeId: string, progress: string | undefined) => {
    const [currentStr, totalStr] = String(progress || '').split('/');
    const current = Number.parseInt(currentStr, 10);
    const total = Number.parseInt(totalStr, 10);
    setNodeRunProgress(prev => ({
      ...prev,
      [nodeId]: {
        current: Number.isFinite(current) ? current : 0,
        total: Number.isFinite(total) ? total : 0,
        startedAt: Date.now(),
      },
    }));
  }, [setNodeRunProgress]);
  const clearNodeRunProgress = useCallback((nodeId: string) => {
    setNodeRunProgress(prev => {
      if (!Object.prototype.hasOwnProperty.call(prev, nodeId)) return prev;
      const next = { ...prev };
      delete next[nodeId];
      return next;
    });
  }, [setNodeRunProgress]);

  const updateNodeRunStatus = useCallback((runId: string, nodeId: string, status: NodeStatus['status'], error?: string) => {
    setRuns(prev => prev.map(run => {
      if (run.run_id !== runId) return run;
      const existing = run.node_statuses.find(node => node.node_id === nodeId);
      const nodeStatus = { ...existing, node_id: nodeId, status, ...(error ? { error } : {}) };
      return {
        ...run,
        node_statuses: existing
          ? run.node_statuses.map(node => node.node_id === nodeId ? nodeStatus : node)
          : [...run.node_statuses, nodeStatus],
      };
    }));
  }, [setRuns]);

  // Load queue and execution history from backend on startup. The cloud editor
  // has no local run queue/history (runs execute on Batch and are tracked in the
  // dashboard), so skip these polled endpoints entirely in editor mode.
  useEffect(() => {
    if (!hostFeaturesEnabled) return;
    Promise.all([
      apiGet<unknown>('/queue').catch(() => null),
      apiGet<unknown>('/history').catch(() => null),
    ]).then(([queueData, historyData]) => {
      const allRuns: RunRecord[] = [];
      const seen = new Set<string>();
      const validatedQueue = queueData ? safeValidateRunsList(queueData) : null;
      const validatedHistory = historyData ? safeValidateRunsList(historyData) : null;
      const queueRuns = validatedQueue?.ok ? validatedQueue.value : [];
      const historyRuns = validatedHistory?.ok ? validatedHistory.value : [];
      const toRunRecord = (h: typeof queueRuns[number]): RunRecord => ({
        run_id: h.run_id,
        status: h.status as RunRecord['status'],
        workflow_name: h.workflow_name || t('console.untitledWorkflow'),
        node_statuses: h.node_statuses as NodeStatus[],
        node_outputs: {},
        execution_plan: h.execution_plan,
        previews: h.previews as Record<string, string>,
        artifacts: h.artifacts as Record<string, string>,
        start_time: h.start_time,
        end_time: h.end_time,
        error: h.error,
      });

      // Queue items first (active runs)
      for (const h of queueRuns) {
        const run = toRunRecord(h);
        allRuns.push(run);
        seen.add(run.run_id);
      }

      // History items (completed runs)
      for (const h of historyRuns) {
        if (seen.has(h.run_id)) continue;
        const run = toRunRecord(h);
        allRuns.push(run);
        seen.add(run.run_id);
      }

      setRuns(allRuns);

      // Fetch logs for the most recent runs (queue + recent history)
      const runsToFetch = allRuns.slice(0, 10);
      for (const run of runsToFetch) {
        apiGet<{ logs?: Array<Record<string, unknown>>; run_id?: string }>(`/api/runs/${run.run_id}/logs`)
          .then((logData) => {
            if (!logData || !Array.isArray(logData.logs)) return;
            const newLogs: LogEntry[] = logData.logs.map(l => ({
              run_id: String(l.run_id || run.run_id),
              node_id: String(l.node_id || 'engine'),
              level: (l.level as LogEntry['level']) || 'info',
              message: String(l.message || ''),
              timestamp: String(l.timestamp || new Date().toISOString()),
            }));
            setLogs(prev => [...prev, ...newLogs]);
          })
          .catch(() => { /* ignore */ });
      }
    }).catch(() => { /* offline */ });
  }, [setRuns, addLog, setLogs, t, hostFeaturesEnabled]);

  // History stack for undo/redo
  const canvasRef = useRef<WorkflowCanvasRef>(null);
  const historyRef = useRef<AppHistorySnapshot[]>([]);
  const historyIndexRef = useRef(-1);
  const pendingStateRef = useRef<Partial<Workflow>>({});

  useEffect(() => {
    historyRef.current = [];
    historyIndexRef.current = -1;
  }, [activeIndex]);

  // Structural fingerprint used to deduplicate identical successive snapshots
  // (e.g. when a drag commit reports the same coordinates twice). Deliberately
  // ignores viewport so pan/zoom alone doesn't burn a slot.
  const snapshotSignature = useCallback((workflow: AppHistorySnapshot) => {
    return JSON.stringify([
      workflow.nodes.map(n => [n.id, n.type, n.position, n.params, n.ui]),
      workflow.edges.map(e => [e.from.node, e.from.output, e.to.node, e.to.input]),
      workflow.groups.map(g => [g.id, g.name, g.position, g.width, g.height, g.color, g.collapsed]),
      workflow.parameters ?? [],
    ]);
  }, []);

  const pushHistory = useCallback(() => {
    const pending = pendingStateRef.current;
    if (Object.keys(pending).length === 0) return;
    pendingStateRef.current = {};
    const wf = { ...activeWorkflow, ...pending };
    const snapshot = {
      nodes: wf.nodes,
      edges: wf.edges,
      groups: wf.groups,
      parameters: wf.parameters,
      viewport: canvasRef.current?.getViewport?.(),
    };
    const tip = historyRef.current[historyIndexRef.current];
    if (tip && snapshotSignature(tip) === snapshotSignature(snapshot)) {
      // No-op push: stack tip is already identical (deduplication).
      // Still refresh the viewport on the tip so future undo restores the
      // latest pan/zoom even when the graph structure hasn't changed.
      if (snapshot.viewport) tip.viewport = snapshot.viewport;
      return;
    }
    const next = historyRef.current.slice(0, historyIndexRef.current + 1);
    next.push({ ...snapshot });
    if (next.length > 50) next.shift();
    historyRef.current = next;
    historyIndexRef.current = next.length - 1;
  }, [activeWorkflow, snapshotSignature]);

  // Auto-history: whenever the active workflow's structure changes, queue a
  // debounced push so callers no longer have to remember onPushHistory(). The
  // dedup check above ensures double-pushes from explicit + auto are harmless.
  useEffect(() => {
    if (Object.keys(pendingStateRef.current).length === 0) return;
    const timer = setTimeout(() => pushHistory(), 350);
    return () => clearTimeout(timer);
  }, [activeWorkflow.nodes, activeWorkflow.edges, activeWorkflow.groups, activeWorkflow.parameters, pushHistory]);

  // Capture eagerly on mouseup/keyup so a completed drag, widget edit, or
  // key shortcut commits pending state instead of waiting for the debounce.
  useEffect(() => {
    const flush = () => {
      if (Object.keys(pendingStateRef.current).length > 0) pushHistory();
    };
    window.addEventListener('mouseup', flush);
    window.addEventListener('keyup', flush);
    return () => {
      window.removeEventListener('mouseup', flush);
      window.removeEventListener('keyup', flush);
    };
  }, [pushHistory]);

  const undo = useCallback(() => {
    if (historyIndexRef.current <= 0) return;
    historyIndexRef.current -= 1;
    const state = historyRef.current[historyIndexRef.current];
    if (bridgeRef.current) {
      bridgeRef.current.onNodesChanged(state.nodes);
      bridgeRef.current.onEdgesChanged(state.edges);
      bridgeRef.current.onGroupsChanged(state.groups);
    }
    updateWorkflow(activeIndex, {
      nodes: state.nodes,
      edges: state.edges,
      groups: state.groups,
      parameters: state.parameters,
    });
    if (state.viewport) canvasRef.current?.setViewport(state.viewport);
  }, [activeIndex, updateWorkflow]);

  const redo = useCallback(() => {
    if (historyIndexRef.current >= historyRef.current.length - 1) return;
    historyIndexRef.current += 1;
    const state = historyRef.current[historyIndexRef.current];
    if (bridgeRef.current) {
      bridgeRef.current.onNodesChanged(state.nodes);
      bridgeRef.current.onEdgesChanged(state.edges);
      bridgeRef.current.onGroupsChanged(state.groups);
    }
    updateWorkflow(activeIndex, {
      nodes: state.nodes,
      edges: state.edges,
      groups: state.groups,
      parameters: state.parameters,
    });
    if (state.viewport) canvasRef.current?.setViewport(state.viewport);
  }, [activeIndex, updateWorkflow]);

  const consoleVisible = useAtomValue(consoleVisibleAtom);
  const setConsoleVisible = useSetAtom(consoleVisibleAtom);
  const [runsDrawerOpen, setRunsDrawerOpen] = useState(false);
  const [railTab, setRailTabState] = useState<RailTab>(null);

  // Panel layout state — extracted to usePanelLayout.
  const {
    openPanelTabs,
    setOpenPanelTabs,
    panelWidths,
    setPanelWidth,
    floatingPanels,
    setFloatingPanel,
    toggleFloatingPanel,
    rightDockedPanels,
    toggleRightDocked,
  } = usePanelLayout();

  const setShowExport = useSetAtom(showExportAtom);
  const setShowImport = useSetAtom(showImportAtom);
  const setShowBulkParam = useSetAtom(showBulkParamAtom);
  const setShowDoctor = useSetAtom(showDoctorAtom);

  // App reads showAI for shell class; setter is passed to TopBar.
  const showAI = useAtomValue(showAIAtom);
  const setShowAI = useSetAtom(showAIAtom);
  const setShowBatchSheet = useSetAtom(showBatchSheetAtom);
  const setShowGettingStarted = useSetAtom(showGettingStartedAtom);
  const [showShortcuts, setShowShortcuts] = useAtom(showShortcutsAtom);
  const [dryRunPreview, setDryRunPreview] = useState(false);
  const [resumeCheckpoint, setResumeCheckpoint] = useState<{
    label: string;
    checkpoint: CheckpointRecord;
  } | null>(null);

  const isRunning = useAtomValue(isRunningAtom);
  const batchCount = useAtomValue(batchCountAtom);
  const setIsRunning = useSetAtom(isRunningAtom);
  // Viewport-per-workflow-tab: switching tabs restores the pan/zoom you left
  // them in instead of always re-fitting. Keyed by workflow id; survives a
  // page reload via localStorage.
  const VIEWPORT_STORE_KEY = 'bionodulo.viewport.byWorkflow';
  const viewportByWorkflowRef = useRef<Record<string, { x: number; y: number; scale: number }>>({});
  // Hydrate on first render only — refs don't trigger re-renders so this is
  // safe to do unconditionally per mount.
  const viewportHydratedRef = useRef(false);
  if (!viewportHydratedRef.current) {
    viewportHydratedRef.current = true;
    try {
      const raw = localStorage.getItem(VIEWPORT_STORE_KEY);
      if (raw) viewportByWorkflowRef.current = JSON.parse(raw);
    } catch { /* ignore */ }
  }
  const persistViewportStore = useCallback(() => {
    try { localStorage.setItem(VIEWPORT_STORE_KEY, JSON.stringify(viewportByWorkflowRef.current)); } catch { /* ignore */ }
  }, []);
  const focusMode = useAtomValue(focusModeAtom);
  const setFocusMode = useSetAtom(focusModeAtom);
  const toggleFocusMode = useCallback(() => {
    setFocusMode(prev => !prev);
  }, [setFocusMode]);
  const [dismissedReport, setDismissedReport] = useState<ResolveReport | null>(null);
  const [dirty, setDirty] = useState(false);

  const startPanelResize = useCallback((tab: OpenPanelTab, startClientX: number, startWidth: number, isRight = false) => {
    const sign = isRight ? -1 : 1;
    const onMove = (event: MouseEvent | TouchEvent) => {
      const clientX = 'touches' in event
        ? event.touches[0]?.clientX ?? startClientX
        : (event as MouseEvent).clientX;
      setPanelWidth(tab, startWidth + sign * (clientX - startClientX));
    };
    const onUp = () => {
      window.removeEventListener('mousemove', onMove);
      window.removeEventListener('mouseup', onUp);
      window.removeEventListener('touchmove', onMove);
      window.removeEventListener('touchend', onUp);
      window.removeEventListener('touchcancel', onUp);
    };
    window.addEventListener('mousemove', onMove);
    window.addEventListener('mouseup', onUp);
    window.addEventListener('touchmove', onMove, { passive: true });
    window.addEventListener('touchend', onUp);
    window.addEventListener('touchcancel', onUp);
  }, [setPanelWidth]);

  // Keyboard-driven panel resize so the separator can be focused and arrow-
  // keys nudge the width. Step is 16px (1× snap grid).
  const handlePanelResizeKey = useCallback((tab: OpenPanelTab, isRight: boolean, event: React.KeyboardEvent) => {
    const step = event.shiftKey ? 64 : 16;
    let delta: number;
    if (event.key === 'ArrowLeft') delta = isRight ? step : -step;
    else if (event.key === 'ArrowRight') delta = isRight ? -step : step;
    else if (event.key === 'Home') {
      event.preventDefault();
      setPanelWidth(tab, 280);
      return;
    } else if (event.key === 'End') {
      event.preventDefault();
      setPanelWidth(tab, 560);
      return;
    } else {
      return;
    }
    event.preventDefault();
    const current = panelWidths[tab] ?? 340;
    setPanelWidth(tab, current + delta);
  }, [panelWidths, setPanelWidth]);

  const [draggingPanelTab, setDraggingPanelTab] = useState<OpenPanelTab | null>(null);
  const [panelDropZone, setPanelDropZone] = useState<'left' | 'right' | null>(null);
  const startPanelDrag = useCallback((tab: OpenPanelTab, startClientX: number, startClientY: number, origin: { x: number; y: number }) => {
    setDraggingPanelTab(tab);
    document.body.classList.add('is-dragging-panel');
    const detectZone = (clientX: number): 'left' | 'right' | null => {
      // 80-pixel hot zones along each canvas edge act as dock targets.
      const width = window.innerWidth;
      if (clientX < 80) return 'left';
      if (clientX > width - 80) return 'right';
      return null;
    };
    const onMove = (event: MouseEvent) => {
      setFloatingPanel(tab, {
        x: origin.x + event.clientX - startClientX,
        y: origin.y + event.clientY - startClientY,
      });
      setPanelDropZone(detectZone(event.clientX));
    };
    const onUp = (event: MouseEvent) => {
      window.removeEventListener('mousemove', onMove);
      window.removeEventListener('mouseup', onUp);
      const zone = detectZone(event.clientX);
      setPanelDropZone(null);
      setDraggingPanelTab(null);
      document.body.classList.remove('is-dragging-panel');
      // Drop on an edge: snap-dock the panel to that side and clear the
      // float position so it goes back into the docked stack.
      if (zone) {
        setFloatingPanel(tab, null);
        if (zone === 'right' && !rightDockedPanels[tab]) {
          toggleRightDocked(tab);
        } else if (zone === 'left' && rightDockedPanels[tab]) {
          toggleRightDocked(tab);
        }
      }
    };
    window.addEventListener('mousemove', onMove);
    window.addEventListener('mouseup', onUp);
  }, [setFloatingPanel, rightDockedPanels, toggleRightDocked]);

  const setRailTab = useCallback((next: RailTab | ((prev: RailTab) => RailTab)) => {
    setRailTabState(prev => {
      const resolved = typeof next === 'function' ? next(prev) : next;
      if (resolved && resolved !== 'console') {
        setOpenPanelTabs(current => {
          const tab = resolved as OpenPanelTab;
          const withoutCenterMenus = current.filter(item => !isCenterMenuTab(item));
          return withoutCenterMenus.includes(tab) ? withoutCenterMenus : [...withoutCenterMenus, tab];
        });
      } else if (resolved === null && prev && prev !== 'console') {
        setOpenPanelTabs(current => current.filter(tab => tab !== prev));
      } else if (resolved === 'console') {
        setConsoleVisible(true);
      }
      return resolved;
    });
  }, []);

  // WebSocket connection for real-time logs. The cloud editor (editorMode) has
  // no such socket — it's served statically and the Lambda can't hold a WS — so
  // we pass null to avoid an endless failed-reconnect loop against /build/ws.
  const wsUrl = useMemo(() => {
    if (!hostFeaturesEnabled) return null;
    const token = getToken();
    const params = token ? `?token=${encodeURIComponent(token)}` : '';
    return appWebSocketUrl('/ws', params);
  }, [authUser?.id, hostFeaturesEnabled]);
  const { onMessage } = useWebSocket(wsUrl);

  useWorkflowMessages({
    onMessage,
    addLog,
    runs,
    updateRun,
    setRuns,
    updateNodeRunStatus,
    recordNodeStart,
    clearNodeRunProgress,
  });

  // Getting Started modal visibility
  useEffect(() => {
    const dismissed = getBool('bionodulo.getting_started.dismissed');
    const showOnStartup = getBool('bionodulo.getting_started.show_on_startup');
    if (!dismissed && showOnStartup) {
      // Small delay so the app shell renders first
      const t = setTimeout(() => setShowGettingStarted(true), 400);
      return () => clearTimeout(t);
    }
  }, [getBool]);

  // Listen for custom event from Getting Started modal to open help
  useEffect(() => {
    const handler = (e: Event) => {
      const detail = (e as CustomEvent).detail;
      setRailTab('help');
      // Store preferred help page in session if needed
      if (detail) {
        sessionStorage.setItem('bionodulo.help_page', detail);
      }
    };
    window.addEventListener('bionodulo:open-help', handler);
    return () => window.removeEventListener('bionodulo:open-help', handler);
  }, []);

  const queuedRuns = useMemo(
    () => runs.filter(r => r.status === 'pending' || r.status === 'running'),
    [runs],
  );
  const queueCount = queuedRuns.length;

  // Friendly name lookup for log lines: prefer the user-set node title, fall
  // back to the type. Built from every node across every open workflow tab so
  // logs from a historic run still resolve names from whichever tab still has
  // the source node loaded.
  const nodeIdToNameMap = useMemo(() => {
    const map = new Map<string, string>();
    for (const wf of workflows) {
      for (const node of wf.nodes || []) {
        const name = (node.ui?.title && node.ui.title.trim()) || node.type;
        if (node.id && name) map.set(node.id, name);
      }
    }
    return map;
  }, [workflows]);

  const autoSaveSetting = String(get('bionodulo.autoSave') || 'off');
  const cacheEnabled = getBool('bionodulo.cacheEnabled');
  const hpcEnabled = getBool('bionodulo.hpc.enabled');
  const hpcBackend = ((get('bionodulo.hpc.backend') as string) || 'slurm') as HPCConfig['backend'];
  const hpcPartition = (get('bionodulo.hpc.partition') as string) || '';
  const hpcAccount = (get('bionodulo.hpc.account') as string) || '';
  const hpcModulesSetting = get('bionodulo.hpc.modules') as string[] | undefined;
  const hpcModulesKey = JSON.stringify(hpcModulesSetting ?? EMPTY_STRING_ARRAY);
  const hpcModules = useMemo(
    () => (Array.isArray(hpcModulesSetting) ? hpcModulesSetting : EMPTY_STRING_ARRAY),
    [hpcModulesKey],
  );
  const hpcContainer = (get('bionodulo.hpc.container') as string) || '';
  const hpcWalltime = (get('bionodulo.hpc.walltime') as string) || '01:00:00';
  const hpcCpusPerTask = (get('bionodulo.hpc.cpus_per_task') as number) || 4;
  const hpcMemPerCpu = (get('bionodulo.hpc.mem_per_cpu') as string) || '4G';
  const hpcConfig: HPCConfig = useMemo(() => ({
    enabled: hpcEnabled,
    backend: hpcBackend,
    partition: hpcPartition,
    account: hpcAccount,
    modules: hpcModules,
    container: hpcContainer,
    walltime: hpcWalltime,
    cpus_per_task: hpcCpusPerTask,
    mem_per_cpu: hpcMemPerCpu,
  }), [
    hpcAccount,
    hpcBackend,
    hpcContainer,
    hpcCpusPerTask,
    hpcEnabled,
    hpcMemPerCpu,
    hpcModules,
    hpcPartition,
    hpcWalltime,
  ]);

  // HPC status polling — extracted to useHPC.
  const { hpcStatus } = useHPC({
    hpcEnabled,
    hpcBackend,
    hpcPartition,
  });

  const updateActive = useCallback((partial: Partial<Workflow>) => {
    updateWorkflow(activeIndex, partial);
  }, [activeIndex, updateWorkflow]);

  const handleNodesChange = useCallback((nodes: WorkflowNode[]) => {
    if (bridgeRef.current) {
      bridgeRef.current.onNodesChanged(nodes);
    }
    pendingStateRef.current = { ...pendingStateRef.current, nodes };
    setDirty(true);
    updateActive({ nodes });
    // Auto-clear error overlays for any node whose params changed. Compare
    // against the previous active workflow so dismissals only fire on real
    // edits (not on selection/UI churn).
    const previousById = new Map(activeWorkflowRef.current.nodes.map(n => [n.id, n]));
    setDismissedErrorNodeIds(prev => {
      let next = prev;
      for (const node of nodes) {
        const previous = previousById.get(node.id);
        if (!previous) continue;
        if (previous.params === node.params) continue;
        if (JSON.stringify(previous.params) === JSON.stringify(node.params)) continue;
        if (!next.has(node.id)) {
          if (next === prev) next = new Set(prev);
          next.add(node.id);
        }
      }
      return next;
    });
  }, [updateActive]);

  const handleEdgesChange = useCallback((edges: Workflow['edges']) => {
    if (bridgeRef.current) {
      bridgeRef.current.onEdgesChanged(edges);
    }
    pendingStateRef.current = { ...pendingStateRef.current, edges };
    setDirty(true);
    updateActive({ edges });
  }, [updateActive]);

  // Media paste: pasting a clipboard image / audio / generic file blob
  // (Ctrl+V outside any text input) uploads it to the workspace and spawns
  // an input_file node wired to the new path.
  useEffect(() => {
    const handler = async (event: ClipboardEvent) => {
      const target = event.target as HTMLElement | null;
      if (target) {
        const tag = target.tagName.toLowerCase();
        if (tag === 'input' || tag === 'textarea' || tag === 'select' || target.isContentEditable) return;
      }
      const items = event.clipboardData?.items;
      if (!items) return;
      const files: File[] = [];
      for (const item of Array.from(items)) {
        if (item.kind !== 'file') continue;
        const file = item.getAsFile();
        if (file) files.push(file);
      }
      if (files.length === 0) return;
      event.preventDefault();
      const meta = objectInfo.input_file;
      if (!meta) {
        toast.warning(appFileActionCopy.error.missingInputFileForPaste);
        return;
      }
      for (let i = 0; i < files.length; i += 1) {
        const file = files[i];
        const form = new FormData();
        form.append('file', file, file.name || `pasted_${Date.now()}`);
        form.append('subdir', 'uploads');
        try {
          const data = await apiPost<{ path?: string; original_name?: string; content_type?: string }>(
            '/api/workspace/upload',
            undefined,
            { body: form },
          );
          if (!data.path) throw new Error(appFileActionCopy.error.uploadResponseMissingPath);
          const baseX = 200 + Math.random() * 40;
          const baseY = 200 + i * 120;
          const newNode: WorkflowNode = {
            id: `${meta.id}_${Date.now()}_${i}`,
            type: meta.id,
            position: [baseX, baseY],
            params: { ...defaultsFor(meta), path: data.path },
            node_info: meta,
            ui: { title: data.original_name || meta.display_name },
          };
          handleNodesChange([...activeWorkflowRef.current.nodes, newNode]);
          pushHistory();
          toast.success(appFileActionCopy.toast.pastedFileAdded, {
            message: `${data.original_name || file.name} (${data.content_type || appFileActionCopy.fileTypeFallback})`,
          });
        } catch (err) {
          toast.error(appFileActionCopy.error.couldNotUploadPastedFile, { message: err instanceof Error ? err.message : String(err) });
        }
      }
    };
    window.addEventListener('paste', handler);
    return () => window.removeEventListener('paste', handler);
  }, [appFileActionCopy, handleNodesChange, objectInfo, pushHistory]);

  // Auto-install dependencies on Run. The toast id is held in a ref so the
  // hook's progress callback can keep updating the same non-blocking toast.
  const installToastIdRef = useRef<string | null>(null);
  const { install: installDependencies } = useDependencyInstall((status) => {
    const id = installToastIdRef.current;
    if (!id) return;
    const detail = installProgressMessage(status.message, t);
    toast.update(id, {
      message: status.current_step
        ? (detail ? `${status.current_step} — ${detail}` : status.current_step)
        : (detail || t('resolveReport.installing')),
      progress: typeof status.percent === 'number' ? status.percent : null,
    });
  });

  // Ensure the workflow env is installed before submitting a run. Returns true
  // when it is safe to proceed (env ready or install succeeded), false to abort.
  const ensureDependenciesInstalled = useCallback(async (workflow: Workflow): Promise<boolean> => {
    const report = await resolve(workflow);
    // If resolve failed (network/etc) we don't block the run — let submitRun
    // surface any real error. Only act on a definitive "env not ready".
    if (!report || report.env_ready) return true;
    const toastId = toast.loading(t('resolveReport.installing'), { progress: 0 });
    installToastIdRef.current = toastId;
    try {
      const ok = await installDependencies(workflow);
      if (ok) {
        toast.update(toastId, {
          tone: 'success',
          title: t('resolveReport.envReady'),
          message: undefined,
          progress: 100,
          duration: 3000,
        });
        return true;
      }
      toast.update(toastId, {
        tone: 'error',
        title: t('console.actions.installFailed'),
        message: report.summary || undefined,
        progress: null,
        duration: 8000,
      });
      return false;
    } finally {
      installToastIdRef.current = null;
    }
  }, [resolve, installDependencies, t]);

  // Cloud runs execute on AWS Batch; their progress is reported by the worker
  // to the website DB. Poll the run snapshot and stream newly-appended log lines
  // into the editor console so the user sees dependency install + node progress
  // without leaving the editor. (SSE can't bridge the worker callbacks to the
  // browser without Redis, so we poll the persisted snapshot.)
  const pollCloudRun = useCallback((runId: string) => {
    if (!runId) return;
    const lineRe = /^\[.*?\]\s+(\w+):\s+([\s\S]*)$/;
    let lastLen = 0;
    let stopped = false;
    let stopPolling: (() => void) | null = null;
    const tick = async () => {
      if (stopped) return;
      const snap = await getCloudRun(runId);
      if (snap) {
        if (typeof snap.logs === 'string' && snap.logs.length > lastLen) {
          const fresh = snap.logs.slice(lastLen);
          lastLen = snap.logs.length;
          for (const raw of fresh.split('\n')) {
            const line = raw.trim();
            if (!line) continue;
            const m = lineRe.exec(line);
            const lvl = (m?.[1] || 'INFO').toUpperCase();
            const body = m ? m[2] : line;
            const taggedNode = nodeIdFromTag(body);
            addLog({
              run_id: runId,
              node_id: taggedNode || 'cloud',
              level: lvl === 'ERROR' ? 'error' : lvl === 'WARN' || lvl === 'WARNING' ? 'warn' : 'info',
              message: stripNodeTag(body),
              timestamp: new Date().toISOString(),
            });
          }
        }
        // Drive the runs drawer + canvas node coloring from the accumulated log
        // blob (the only durable per-node record the snapshot carries).
        const mappedStatus = mapCloudRunStatus(snap.status);
        const derived = deriveCloudNodeStatuses(typeof snap.logs === 'string' ? snap.logs : '');
        updateRun(runId, {
          status: mappedStatus,
          node_statuses: buildCloudNodeStatuses(
            workflowExecutionPlan(activeWorkflow),
            derived,
            mappedStatus,
            snap.errorMessage,
          ),
          error: snap.errorMessage || undefined,
          ...(isTerminalCloudStatus(snap.status) ? { end_time: snap.completedAt || new Date().toISOString() } : {}),
        });
        if (isTerminalCloudStatus(snap.status)) {
          stopped = true;
          stopPolling?.();
          addLog({
            run_id: runId,
            node_id: 'cloud',
            level: snap.status === 'completed' ? 'info' : 'error',
            message: snap.status === 'completed'
              ? t('console.actions.cloudRunCompleted', { defaultValue: 'Cloud run completed.' })
              : t('console.actions.cloudRunEnded', { defaultValue: `Cloud run ${snap.status}.`, status: snap.status }),
            detail: snap.errorMessage || undefined,
            timestamp: new Date().toISOString(),
          });
          return;
        }
      }
    };
    stopPolling = startVisibilityAwarePolling(
      tick,
      CLOUD_RUN_POLL_VISIBLE_MS,
      CLOUD_RUN_POLL_HIDDEN_MS,
    );
  }, [addLog, updateRun, activeWorkflow, t]);

  const handleRun = useCallback(async () => {
    setIsRunning(true);
    logTelemetry('workflow.run.start', {
      workflow: activeWorkflow.name,
      nodes: activeWorkflow.nodes?.length ?? 0,
      batch: batchCount,
      cacheEnabled,
    });
    try {
      const v = await validate(activeWorkflow);
      if (v && v.valid === false && Array.isArray(v.errors) && v.errors.length > 0) {
        // Try to extract a node id from the first error so the "Jump" action
        // can centre the canvas on it. Errors are free-form strings, so we
        // match any token that exists in the current workflow's node ids.
        const firstError = String(v.errors[0]);
        const nodeIds = new Set(activeWorkflow.nodes.map(n => n.id));
        const tokens = firstError.match(/[A-Za-z0-9_-]+/g) || [];
        const targetId = tokens.find(token => nodeIds.has(token));
        toast.error(t('console.actions.validationFailed', { count: v.errors.length }), {
          message: firstError,
          actions: targetId
            ? [{ label: t('console.actions.jumpToNode'), onClick: () => canvasRef.current?.focusNode(targetId), dismiss: true }]
            : undefined,
        });
        setIsRunning(false);
        return;
      }
      const parameterOverrides = await promptWorkflowRunParameters(activeWorkflow.parameters, promptDialog, {
        title: t('parameters.runPromptTitle'),
        message: parameter => (
          parameter.description
            ? `${parameter.name} (${parameter.type}) — ${parameter.description}`
            : `${parameter.name} (${parameter.type})`
        ),
        confirmLabel: t('parameters.runPromptConfirm'),
        cancelLabel: t('parameters.runPromptCancel'),
      });
      if (parameterOverrides === null) {
        setIsRunning(false);
        return;
      }
      // Auto-install missing dependencies before running unless the user opted
      // into the manual prompt-before-install flow (banner + Install button).
      // SKIP in the cloud editor: there is no local installer — the AWS Batch
      // worker installs the workflow's environment as part of the run.
      if (!editorMode && !getBool('bionodulo.dependencies.promptBeforeInstall')) {
        const ready = await ensureDependenciesInstalled(activeWorkflow);
        if (!ready) {
          setConsoleVisible(true);
          setRailTab('console');
          setIsRunning(false);
          return;
        }
      }
      const count = dryRunPreview ? 1 : Math.max(1, Math.min(99, batchCount));
      for (let index = 0; index < count; index += 1) {
        const workflowFallbackName = activeWorkflow.name || t('common.untitled');
        const batchName = count > 1
          ? `${workflowFallbackName} (${index + 1}/${count})`
          : workflowFallbackName;
        const result = await submitRun(activeWorkflow, {
          no_cache: !cacheEnabled,
          name: batchName,
          parameters: parameterOverrides,
          dry_run: dryRunPreview,
          resume_checkpoint: resumeCheckpoint?.checkpoint,
          compute: specToRunBody(computeSpec),
        });
        if (dryRunPreview || result.status === 'dry_run') {
          const preview = result as RunRecord & {
            execution_order?: string[];
            nodes?: Record<string, unknown>;
            resume_checkpoint?: unknown;
            workflow_parameters?: Record<string, unknown>;
          };
          const executionOrder = Array.isArray(preview.execution_order)
            ? preview.execution_order
            : (Array.isArray(preview.execution_plan) ? preview.execution_plan : []);
          addLog({
            run_id: result.run_id,
            node_id: 'engine',
            level: 'info',
            message: t('console.actions.dryRunPreviewLog', {
              count: executionOrder.length,
              nodeWord: t(executionOrder.length === 1 ? 'console.nodesCount' : 'console.nodesCount_plural', {
                count: executionOrder.length,
              }),
              plannedWord: t(executionOrder.length === 1
                ? 'console.actions.dryRunPreviewPlannedOne'
                : 'console.actions.dryRunPreviewPlannedMany'),
            }),
            detail: JSON.stringify(redactSecrets({
              execution_order: executionOrder,
              nodes: preview.nodes ?? {},
              workflow_parameters: preview.workflow_parameters ?? {},
              resume_checkpoint: preview.resume_checkpoint ?? null,
            }), null, 2),
            timestamp: new Date().toISOString(),
          });
          setConsoleVisible(true);
          setRailTab('console');
          continue;
        }
        // Cloud editor: the run was submitted to the cloud Batch runner and is
        // tracked in the dashboard, not as a local in-app run.
        const cloudResult = result as RunRecord & { cloud?: boolean; dashboard_url?: string };
        if (cloudResult.cloud) {
          addLog({
            run_id: result.run_id || 'cloud',
            node_id: 'engine',
            level: 'info',
            message: t('console.actions.cloudRunSubmitted', {
              defaultValue: 'Run submitted to the cloud — streaming progress below.',
            }),
            detail: cloudResult.dashboard_url || '',
            timestamp: new Date().toISOString(),
          });
          setConsoleVisible(true);
          setRailTab('console');
          // Register the cloud run in the drawer so it shows status + drives
          // canvas node coloring, then stream the worker's progress (dependency
          // install + node logs) into both the console and node statuses by
          // polling the run snapshot until it reaches a terminal state.
          if (result.run_id) {
            addRun({
              run_id: result.run_id,
              status: 'pending',
              workflow_name: result.workflow_name || batchName,
              node_statuses: [],
              node_outputs: {},
              execution_plan: workflowExecutionPlan(activeWorkflow),
              previews: {},
              artifacts: {},
              start_time: new Date().toISOString(),
              options: { cloud: true, dashboard_url: cloudResult.dashboard_url },
            });
            pollCloudRun(result.run_id);
          }
          continue;
        }
        addRun({
          run_id: result.run_id,
          status: 'pending',
          workflow_name: result.workflow_name || batchName,
          node_statuses: [],
          node_outputs: {},
          execution_plan: workflowExecutionPlan(activeWorkflow),
          previews: {},
          artifacts: {},
          start_time: new Date().toISOString(),
        });
      }
      if (dryRunPreview) {
        toast.info(t('console.actions.dryRunPreviewGenerated'), {
          message: t('console.actions.dryRunPreviewMessage'),
        });
      } else {
        toast.success(count > 1
          ? t('console.actions.runsQueued', { count })
          : t('console.actions.runQueued'));
        setRunsDrawerOpen(true);
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      addLog({
        run_id: 'workflow',
        node_id: 'engine',
        level: 'error',
        message: t('console.actions.runFailedLog', { message: msg }),
        timestamp: new Date().toISOString(),
      });
      // Auto-open console so the user sees the error
      setConsoleVisible(true);
      setRailTab('console');
    }
    setIsRunning(false);
  }, [activeWorkflow, validate, submitRun, cacheEnabled, addLog, addRun, batchCount, dryRunPreview, resumeCheckpoint?.checkpoint, setConsoleVisible, setRailTab, t, getBool, ensureDependenciesInstalled, editorMode, pollCloudRun, computeSpec]);

  const handleBatchSheetSubmit = useCallback(async (runs: SampleSheetRun[]) => {
    if (runs.length === 0) return;
    setIsRunning(true);
    try {
      await validate(activeWorkflow);
      for (const sampleRun of runs) {
        const result = await submitRun(sampleRun.workflow, {
          no_cache: !cacheEnabled,
          name: sampleRun.name,
          parameters: sampleRun.parameters,
        });
        addRun({
          run_id: result.run_id,
          status: 'pending',
          workflow_name: result.workflow_name || sampleRun.name,
          node_statuses: [],
          node_outputs: {},
          execution_plan: workflowExecutionPlan(sampleRun.workflow),
          previews: {},
          artifacts: {},
          start_time: new Date().toISOString(),
        });
      }
      toast.success(t('console.actions.sampleSheetRunsQueued', { count: runs.length }));
      setRunsDrawerOpen(true);
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      toast.error(t('console.actions.sampleSheetBatchFailed'), { message: msg });
      addLog({
        run_id: 'workflow',
        node_id: 'engine',
        level: 'error',
        message: t('console.actions.sampleSheetBatchFailedLog', { message: msg }),
        timestamp: new Date().toISOString(),
      });
    } finally {
      setIsRunning(false);
    }
  }, [activeWorkflow, addLog, addRun, cacheEnabled, setRailTab, submitRun, t, validate]);

  // Local "Run on Cloud": send the current workflow to BioNodulo Cloud (persist
  // to the team DB + submit to the Batch runner) instead of running it on this
  // machine. Requires a signed-in cloud account; otherwise opens sign-in. Phase 1
  // handles workflows with no local-file inputs (file pre-flight upload lands in
  // Phase 2, sharing the transfer engine).
  const handleRunOnCloud = useCallback(async () => {
    const signedIn = Boolean(authUser) || Boolean(cloudConfig?.user);
    if (!signedIn) {
      if (clerk.clerkEnabled) clerk.openSignIn();
      else toast.info(t('console.actions.cloudSignInRequired', { defaultValue: 'Sign in to BioNodulo Cloud first.' }));
      setRailTab('user');
      return;
    }
    if (!editorMode && !cloudConfig?.accountUrl) {
      toast.error(t('console.actions.cloudNotConfigured', { defaultValue: 'BioNodulo Cloud is not configured.' }));
      return;
    }
    setIsRunning(true);
    try {
      await validate(activeWorkflow);
      // Pre-flight: upload any referenced LOCAL workspace files to the cloud so
      // the run can reach them. Files <50 MB upload silently; if any is >=50 MB
      // the user confirms first. The uploaded key map rides along as run inputs.
      let inputs: Record<string, unknown> | undefined;
      const localPaths = collectLocalFilePaths(activeWorkflow);
      if (localPaths.length > 0) {
        const sizes = await Promise.all(localPaths.map(async p => ({ path: p, size: await localFileSize(p) })));
        const big = sizes.filter(s => s.size >= 50 * 1024 * 1024);
        if (big.length > 0) {
          const ok = await confirmDialog(t('console.actions.cloudLargeFilesConfirm', {
            defaultValue: 'Files over 50 MB will be uploaded to the cloud before running the workflow. Continue?',
          }));
          if (!ok) { setIsRunning(false); return; }
        }
        const fileKeys: Record<string, string> = {};
        for (const { path } of sizes) {
          const key = await uploadWorkspaceFileToCloud(path, baseName(path)).catch(() => null);
          if (key) fileKeys[path] = key;
        }
        if (Object.keys(fileKeys).length > 0) inputs = { files: fileKeys };
      }
      const result = await submitRun(activeWorkflow, {
        forceCloud: true,
        name: activeWorkflow.name,
        compute: specToRunBody(computeSpec),
        inputs,
      }) as RunRecord & { cloud?: boolean; dashboard_url?: string };
      addLog({
        run_id: result.run_id || 'cloud', node_id: 'engine', level: 'info',
        message: t('console.actions.cloudRunSubmitted', { defaultValue: 'Run submitted to the cloud — streaming progress below.' }),
        detail: result.dashboard_url || '', timestamp: new Date().toISOString(),
      });
      setConsoleVisible(true);
      setRailTab('console');
      if (result.run_id) {
        addRun({
          run_id: result.run_id, status: 'pending',
          workflow_name: result.workflow_name || activeWorkflow.name,
          node_statuses: [], node_outputs: {},
          execution_plan: workflowExecutionPlan(activeWorkflow),
          previews: {}, artifacts: {}, start_time: new Date().toISOString(),
          options: { cloud: true, dashboard_url: result.dashboard_url },
        });
        pollCloudRun(result.run_id);
        setRunsDrawerOpen(true);
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      toast.error(t('console.actions.cloudRunFailed', { defaultValue: 'Cloud run failed' }), { message: msg });
      addLog({ run_id: 'cloud', node_id: 'engine', level: 'error', message: msg, timestamp: new Date().toISOString() });
      setConsoleVisible(true);
      setRailTab('console');
    } finally {
      setIsRunning(false);
    }
  }, [authUser, cloudConfig, clerk, editorMode, validate, activeWorkflow, submitRun, computeSpec, addLog, addRun, pollCloudRun, setConsoleVisible, setRailTab, setRunsDrawerOpen, setIsRunning, t]);

  const handleRunSelected = useCallback(async (nodeIds: string[]) => {
    if (nodeIds.length === 0) return;
    setIsRunning(true);
    try {
      const v = await validate(activeWorkflow);
      if (v && v.valid === false && Array.isArray(v.errors) && v.errors.length > 0) {
        const firstError = String(v.errors[0]);
        const knownIds = new Set(activeWorkflow.nodes.map(n => n.id));
        const tokens = firstError.match(/[A-Za-z0-9_-]+/g) || [];
        const targetId = tokens.find(token => knownIds.has(token));
        toast.error(t('console.actions.validationFailed', { count: v.errors.length }), {
          message: firstError,
          actions: targetId
            ? [{ label: t('console.actions.jumpToNode'), onClick: () => canvasRef.current?.focusNode(targetId), dismiss: true }]
            : undefined,
        });
        setIsRunning(false);
        return;
      }
      const parameterOverrides = await promptWorkflowRunParameters(activeWorkflow.parameters, promptDialog, {
        title: t('parameters.runPromptTitle'),
        message: parameter => (
          parameter.description
            ? `${parameter.name} (${parameter.type}) — ${parameter.description}`
            : `${parameter.name} (${parameter.type})`
        ),
        confirmLabel: t('parameters.runPromptConfirm'),
        cancelLabel: t('parameters.runPromptCancel'),
      });
      if (parameterOverrides === null) {
        setIsRunning(false);
        return;
      }
      const result = await submitRun(activeWorkflow, {
        no_cache: !cacheEnabled,
        target_nodes: nodeIds,
        name: `${activeWorkflow.name || t('common.untitled')} (${t('workflowNaming.selectionSuffix')})`,
        parameters: parameterOverrides,
      });
      addRun({
        run_id: result.run_id,
        status: 'pending',
        workflow_name: result.workflow_name || `${activeWorkflow.name || t('common.untitled')} (${t('workflowNaming.selectionSuffix')})`,
        node_statuses: [],
        node_outputs: {},
        execution_plan: workflowExecutionPlan(activeWorkflow, nodeIds),
        previews: {},
        artifacts: {},
        start_time: new Date().toISOString(),
      });
      setRunsDrawerOpen(true);
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      addLog({
        run_id: 'workflow',
        node_id: 'engine',
        level: 'error',
        message: t('console.actions.selectedRunFailedLog', { message: msg }),
        timestamp: new Date().toISOString(),
      });
      setConsoleVisible(true);
      setRailTab('console');
    }
    setIsRunning(false);
  }, [activeWorkflow, addLog, addRun, cacheEnabled, submitRun, validate, setRailTab, t]);

  const handleSaveSnippet = useCallback(async () => {
    const selectedIds = canvasRef.current?.getSelectedNodeIds() ?? [];
    if (selectedIds.length === 0) {
      toast.info(t('snippets.selectAtLeastOne'));
      return;
    }
    const idSet = new Set(selectedIds);
    const snippetNodes = activeWorkflow.nodes.filter(n => idSet.has(n.id));
    const snippetEdges = activeWorkflow.edges.filter(e => idSet.has(e.from.node) && idSet.has(e.to.node));
    const defaultName = snippetNodes.length === 1
      ? t('snippets.singleDefaultName', { name: snippetNodes[0].ui?.title || snippetNodes[0].type })
      : t('snippets.multiDefaultName', { count: snippetNodes.length });
    const name = await promptDialog({
      title: t('snippets.savePromptTitle'),
      message: t('snippets.savePromptMessage'),
      inputLabel: t('snippets.savePromptInputLabel'),
      defaultValue: defaultName,
    });
    if (!name) return;
    const { saveWorkflowSnippet } = await import('./state/workflowSnippets');
    saveWorkflowSnippet({ name, nodes: snippetNodes, edges: snippetEdges });
    toast.success(t('snippets.savedTitle'), { message: t('snippets.savedMessage', { count: snippetNodes.length }) });
  }, [activeWorkflow, t]);

  const handleInsertSnippet = useCallback(async () => {
    const { listWorkflowSnippets, instantiateSnippet } = await import('./state/workflowSnippets');
    const snippets = listWorkflowSnippets();
    if (snippets.length === 0) {
      toast.info(t('snippets.emptyLibrary'));
      return;
    }
    // Quick "pick one" via prompt — full chooser modal is a future polish item.
    const labels = snippets.map((s, i) => `${i + 1}. ${s.name} (${s.nodes.length}n)`).join('\n');
    const choice = await promptDialog({
      title: t('snippets.insertPromptTitle'),
      message: t('snippets.insertPromptMessage', { labels }),
      inputLabel: t('snippets.insertPromptInputLabel'),
      defaultValue: '1',
    });
    const index = Math.max(1, Math.min(snippets.length, parseInt(choice || '1', 10))) - 1;
    if (Number.isNaN(index)) return;
    const snippet = snippets[index];
    const vp = canvasRef.current?.getViewport();
    const centreWorld = vp
      ? { x: (-vp.x + window.innerWidth / 2) / vp.scale, y: (-vp.y + window.innerHeight / 2) / vp.scale }
      : { x: 100, y: 100 };
    const { nodes: newNodes, edges: newEdges } = instantiateSnippet(snippet, centreWorld);
    const next: Workflow = {
      ...activeWorkflow,
      nodes: [...activeWorkflow.nodes, ...newNodes],
      edges: [...activeWorkflow.edges, ...newEdges],
    };
    updateWorkflow(activeIndex, next);
    toast.success(t('snippets.insertedTitle'), { message: `${snippet.name}` });
  }, [activeWorkflow, activeIndex, t, updateWorkflow]);

  // Restore the saved viewport whenever the user switches workflow tabs.
  const prevActiveIndexRef = useRef(activeIndex);
  const workflowsRef = useRef(workflows);
  useEffect(() => { workflowsRef.current = workflows; }, [workflows]);
  useEffect(() => {
    // Runs ONLY on a tab switch (activeIndex change). It must NOT depend on
    // `workflows` — that changes on every node drag/edit, which would re-run this
    // and snap the camera (setViewport/fitView) mid-interaction. Read the latest
    // workflows via ref instead.
    const prev = prevActiveIndexRef.current;
    if (prev === activeIndex) return;
    const wfs = workflowsRef.current;
    // Save the outgoing tab's viewport.
    const prevId = wfs[prev]?.id;
    if (prevId) {
      const vp = canvasRef.current?.getViewport?.();
      if (vp) {
        viewportByWorkflowRef.current[prevId] = vp;
        persistViewportStore();
      }
    }
    prevActiveIndexRef.current = activeIndex;
    // Restore the incoming tab's viewport, if any. Wait two RAFs so the
    // canvas has finished laying out the new workflow's nodes before we set
    // the viewport — otherwise fitView from elsewhere could clobber us.
    const incomingId = wfs[activeIndex]?.id;
    if (incomingId) {
      const saved = viewportByWorkflowRef.current[incomingId];
      const incomingHasNodes = (wfs[activeIndex]?.nodes?.length ?? 0) > 0;
      requestAnimationFrame(() => {
        requestAnimationFrame(() => {
          if (saved) {
            canvasRef.current?.setViewport(saved);
          } else if (incomingHasNodes) {
            // No stored viewport (first open of a workflow this session): fit to
            // the nodes rather than leaving the canvas at the origin, where a
            // workflow saved far from (0,0) would render blank until a manual fit.
            canvasRef.current?.fitView();
          }
        });
      });
    }
  }, [activeIndex, persistViewportStore]);

  const handleCancelRun = useCallback(async (run: RunRecord) => {
    const ok = await confirmDialog(consoleActionCopy.cancelRunDialog(run));
    if (!ok) return;
    try {
      await apiPost(`/api/queue/${encodeURIComponent(run.run_id)}/cancel`);
      updateRun(run.run_id, { status: 'cancelled', end_time: new Date().toISOString() });
      toast.warning(consoleActionCopy.toast.runCancelled, { message: run.workflow_name || run.run_id });
    } catch (err) {
      logError('app.queue.cancel', err);
      toast.error(consoleActionCopy.error.couldNotCancelRun, { message: err instanceof Error ? err.message : String(err) });
    }
  }, [consoleActionCopy, updateRun]);

  const handleLoadRunWorkflow = useCallback(async (run: RunRecord) => {
    try {
      const data = await apiGet<{ workflow?: Workflow; workflow_name?: string }>(
        `/api/runs/${encodeURIComponent(run.run_id)}`,
      );
      const workflow = data.workflow;
      if (!workflow || !Array.isArray(workflow.nodes)) {
        throw new Error(consoleActionCopy.error.noRunWorkflowSnapshot);
      }
      const named: Workflow = {
        ...workflow,
        name: workflow.name || run.workflow_name || consoleActionCopy.loadedRunWorkflowName(run),
      };
      addWorkflow(withWorkflowId(named));
      toast.success(consoleActionCopy.toast.workflowLoadedFromRun, { message: named.name });
      requestAnimationFrame(() => {
        requestAnimationFrame(() => canvasRef.current?.fitView());
      });
    } catch (err) {
      logError('app.run.loadWorkflow', err);
      toast.error(consoleActionCopy.error.couldNotLoadWorkflow, { message: err instanceof Error ? err.message : String(err) });
    }
  }, [addWorkflow, consoleActionCopy]);

  const handleRetryRun = useCallback(async (run: RunRecord) => {
    try {
      const data = await apiPost<{ run_id: string; status?: string }>(
        `/api/runs/${encodeURIComponent(run.run_id)}/retry`,
      );
      addRun({
        run_id: data.run_id,
        status: 'pending',
        workflow_name: consoleActionCopy.retryWorkflowName(run),
        node_statuses: [],
        node_outputs: {},
        execution_plan: run.execution_plan ?? [],
        previews: {},
        artifacts: {},
        start_time: new Date().toISOString(),
      });
      setRunsDrawerOpen(true);
      toast.success(consoleActionCopy.toast.retryQueued, { message: data.run_id });
    } catch (err) {
      logError('app.run.retry', err);
      toast.error(consoleActionCopy.error.couldNotRetryRun, { message: err instanceof Error ? err.message : String(err) });
    }
  }, [addRun, consoleActionCopy]);

  const handleMoveRun = useCallback(async (run: RunRecord, direction: 'up' | 'down') => {
    const pending = queuedRuns.filter(candidate => candidate.status === 'pending');
    const currentIndex = pending.findIndex(candidate => candidate.run_id === run.run_id);
    if (currentIndex < 0) return;
    const nextIndex = direction === 'up' ? Math.max(0, currentIndex - 1) : Math.min(pending.length - 1, currentIndex + 1);
    if (nextIndex === currentIndex) return;
    try {
      await apiPost('/queue/reorder', { run_id: run.run_id, index: nextIndex });
      setRuns(prev => {
        const next = [...prev];
        const from = next.findIndex(candidate => candidate.run_id === run.run_id);
        const targetRunId = pending[nextIndex]?.run_id;
        const to = next.findIndex(candidate => candidate.run_id === targetRunId);
        if (from < 0 || to < 0) return prev;
        const [removed] = next.splice(from, 1);
        next.splice(to, 0, removed);
        return next;
      });
    } catch (err) {
      logError('app.queue.reorder', err);
      toast.error(consoleActionCopy.error.couldNotReorderQueue, { message: err instanceof Error ? err.message : String(err) });
    }
  }, [consoleActionCopy, queuedRuns, setRuns]);

  const handleClearQueue = useCallback(async () => {
    const ok = await confirmDialog(consoleActionCopy.clearQueueDialog());
    if (!ok) return;
    try {
      await apiPost('/queue/clear');
      setRuns(prev => prev.filter(run => run.status !== 'pending'));
      toast.success(consoleActionCopy.toast.queueCleared);
    } catch (err) {
      logError('app.queue.clear', err);
      toast.error(consoleActionCopy.error.couldNotClearQueue, { message: err instanceof Error ? err.message : String(err) });
    }
  }, [consoleActionCopy, setRuns]);

  const handleClearHistory = useCallback(async () => {
    const ok = await confirmDialog(consoleActionCopy.clearHistoryDialog());
    if (!ok) return;
    try {
      await apiPost('/history/clear');
      setRuns(prev => prev.filter(run => run.status === 'pending' || run.status === 'running'));
      toast.success(consoleActionCopy.toast.historyCleared);
    } catch (err) {
      logError('app.history.clear', err);
      toast.error(consoleActionCopy.error.couldNotClearHistory, { message: err instanceof Error ? err.message : String(err) });
    }
  }, [consoleActionCopy, setRuns]);

  const handleDeleteHistoryEntry = useCallback(async (run: RunRecord) => {
    try {
      await apiDelete(`/history/${encodeURIComponent(run.run_id)}`);
      setRuns(prev => prev.filter(r => r.run_id !== run.run_id));
    } catch (err) {
      logError('app.history.delete', err);
      const detail = err instanceof ApiError ? `${err.status} ${err.statusText}` : err instanceof Error ? err.message : String(err);
      toast.error(consoleActionCopy.error.couldNotDeleteRun, { message: detail });
    }
  }, [consoleActionCopy, setRuns]);

  const handleSaveTemplate = useCallback(async (draft: TemplateSaveDraft) => {
    const token = getToken();
    if (!collabSessionActive || !token || !activeWorkflowId) {
      await alertDialog(appCollabCopy.saveTemplateUnavailableDialog());
      return;
    }
    try {
      await publishCollabWorkflowSnapshot(activeWorkflow);
      await apiPost('/api/collab/templates', {
        workflow_id: activeWorkflowId,
        title: draft.name,
        description: draft.description,
        category: draft.category,
        tags: draft.tags,
        is_public: false,
      });
      toast.success(appCollabCopy.toast.templateSaved, { message: draft.name });
    } catch (err) {
      logError('app.template.save', err);
      toast.error(appCollabCopy.error.saveTemplateFailed, { message: err instanceof Error ? err.message : String(err) });
    }
  }, [activeWorkflow, activeWorkflowId, appCollabCopy, collabSessionActive, publishCollabWorkflowSnapshot]);

  const handleToggleQueue = useCallback(() => {
    setRunsDrawerOpen(open => !open);
  }, []);

  const handleLoadTemplate = useCallback(async (template: TemplateInfo) => {
    logTelemetry('template.load', { id: template.id, name: template.name, category: template.category });
    const wf = await fetchTemplateWorkflow(template);
    if (!wf) {
      return;
    }
    if (collabSessionActive || editorMode) {
      // Keep the SAME workflow id and replace its content. Collab needs this so
      // a shared room stays on one id; the cloud editor needs it so the template
      // persists to the DB-backed workflow (a new client-id tab would 404 on
      // autosave and be lost on reload).
      const sharedWorkflow = withWorkflowId(wf, activeWorkflowId);
      updateWorkflow(activeIndex, sharedWorkflow);
      if (collabSessionActive) {
        if (collabDoc) {
          workflowToDoc(sharedWorkflow, collabDoc);
        }
        void publishCollabWorkflowSnapshot(sharedWorkflow);
      }
    } else {
      addWorkflow(withWorkflowId(wf));
    }
    rememberRecentWorkflow({
      id: wf.id || activeWorkflowId,
      name: wf.name || template.name || t('common.untitled'),
      source: 'template',
      filename: template.filename,
      thumbnailUrl: (template as { thumbnail_url?: string }).thumbnail_url || renderRecentThumbnail(wf),
      nodeCount: wf.nodes?.length ?? 0,
    });
    // Auto-fit view after nodes render
    requestAnimationFrame(() => {
      requestAnimationFrame(() => canvasRef.current?.fitView());
    });
    // Resolve is auto-triggered by the activeWorkflow useEffect
  }, [activeIndex, activeWorkflowId, addWorkflow, collabDoc, collabSessionActive, editorMode, publishCollabWorkflowSnapshot, t, updateWorkflow]);

  const handleImport = useCallback((wf: Workflow) => {
    logTelemetry('workflow.import', { name: wf.name, nodes: wf.nodes?.length ?? 0 });
    if (collabSessionActive || editorMode) {
      const sharedWorkflow = withWorkflowId(wf, activeWorkflowId);
      updateWorkflow(activeIndex, sharedWorkflow);
      if (collabSessionActive) {
        if (collabDoc) {
          workflowToDoc(sharedWorkflow, collabDoc);
        }
        void publishCollabWorkflowSnapshot(sharedWorkflow);
      }
    } else {
      addWorkflow(withWorkflowId(wf));
    }
    rememberRecentWorkflow({
      id: wf.id || activeWorkflowId,
      name: wf.name || t('workflowImport.importedFallbackName'),
      source: 'import',
      thumbnailUrl: renderRecentThumbnail(wf),
      nodeCount: wf.nodes?.length ?? 0,
    });
    // Auto-fit view after nodes render
    requestAnimationFrame(() => {
      requestAnimationFrame(() => canvasRef.current?.fitView());
    });
    // Resolve is auto-triggered by the activeWorkflow useEffect
  }, [activeIndex, activeWorkflowId, addWorkflow, collabDoc, collabSessionActive, editorMode, publishCollabWorkflowSnapshot, t, updateWorkflow]);

  // Replay any URL-hash workflow that mount stashed before handleImport
  // existed. Runs once handleImport stabilises.
  useEffect(() => {
    const pending = pendingHashWorkflowRef.current;
    if (!pending) return;
    pendingHashWorkflowRef.current = null;
    handleImport(pending);
    toast.success(t('workflowImport.loadedFromUrl'), { message: pending.name || t('workflowImport.untitledLower') });
  }, [handleImport, t]);

  const handleApplyWorkflow = useCallback((wf: Workflow) => {
    const sharedWorkflow = withWorkflowId(wf, activeWorkflowId);
    setWorkflow(activeIndex, () => sharedWorkflow);
    if (collabSessionActive) {
      if (collabDoc) {
        workflowToDoc(sharedWorkflow, collabDoc);
      }
      void publishCollabWorkflowSnapshot(sharedWorkflow);
    }
  }, [activeIndex, activeWorkflowId, collabDoc, collabSessionActive, publishCollabWorkflowSnapshot, setWorkflow]);

  const handleRenameTab = useCallback((index: number, name: string) => {
    updateWorkflow(index, { name });
  }, [updateWorkflow]);

  const handleDuplicateTab = useCallback((index: number) => {
    const wf = workflows[index];
    if (!wf) return;
    const dup: Workflow = {
      ...wf,
      id: createWorkflowId(),
      name: t('workflowTabs.duplicateName', { name: wf.name || t('common.untitled') }),
      nodes: wf.nodes.map(n => ({ ...n, id: `${n.type}_${Date.now()}_${Math.random().toString(36).slice(2, 7)}` })),
    };
    addWorkflow(dup);
  }, [workflows, addWorkflow, t]);

  const handleReorderTabs = useCallback((from: number, to: number) => {
    reorderWorkflows(from, to);
  }, [reorderWorkflows]);

  const togglePanel = useCallback((tab: Exclude<RailTab, null>) => {
    if (tab === 'console') {
      handleToggleQueue();
      return;
    }
    setRailTab(prev => prev === tab ? null : tab);
  }, [handleToggleQueue, setRailTab]);

  const appCommands = useMemo<CommandItem[]>(() => {
    const baseCommands: CommandItem[] = [
      {
        id: 'workflow.run',
        label: t('commandPalette.commands.workflow.run'),
        description: activeWorkflow.name || t('commandPalette.commands.workflow.currentWorkflow'),
        group: 'Workflow',
        groupLabelKey: 'commandPalette.groups.workflow',
        shortcut: getBinding('workflow.run') ?? undefined,
        onSelect: () => void handleRun(),
      },
      {
        id: 'workflow.runSelected',
        label: t('commandPalette.commands.workflow.runSelected'),
        description: t('commandPalette.commands.workflow.runSelectedDescription'),
        group: 'Workflow',
        groupLabelKey: 'commandPalette.groups.workflow',
        onSelect: () => canvasRef.current?.executeSelected(),
      },
      {
        id: 'workflow.groupSelection',
        label: t('canvas.group.create'),
        description: t('canvas.group.createDescription'),
        group: 'Workflow',
        groupLabelKey: 'commandPalette.groups.workflow',
        onSelect: () => canvasRef.current?.createGroupFromSelection(),
      },
      {
        id: 'workflow.saveSnippet',
        label: t('snippets.savePromptTitle'),
        description: t('snippets.saveCommandDescription'),
        group: 'Workflow',
        groupLabelKey: 'commandPalette.groups.workflow',
        onSelect: () => handleSaveSnippet(),
      },
      {
        id: 'workflow.insertSnippet',
        label: t('snippets.insertCommandLabel'),
        description: t('snippets.insertCommandDescription'),
        group: 'Workflow',
        groupLabelKey: 'commandPalette.groups.workflow',
        onSelect: () => handleInsertSnippet(),
      },
      {
        id: 'workflow.doctor',
        label: t('commandPalette.commands.workflow.doctor'),
        description: t('commandPalette.commands.workflow.doctorDescription'),
        group: 'Workflow',
        groupLabelKey: 'commandPalette.groups.workflow',
        onSelect: () => setShowDoctor(true),
      },
      {
        id: 'workflow.copyShareUrl',
        label: t('commandPalette.commands.share.copyUrl'),
        description: t('commandPalette.commands.share.copyUrlDescription'),
        group: 'Workflow',
        groupLabelKey: 'commandPalette.groups.workflow',
        onSelect: async () => {
          const url = buildShareUrl(activeWorkflow);
          if (!url) { toast.error(t('workflowShare.copyUrlBuildError')); return; }
          if (url.length > 32_000) {
            toast.warning(t('workflowShare.copyUrlTooLarge'), { message: t('workflowShare.copyUrlTooLargeMessage') });
          }
          try {
            await navigator.clipboard.writeText(url);
            const shareUrlSize = new Intl.NumberFormat(i18n.language, {
              minimumFractionDigits: 1,
              maximumFractionDigits: 1,
            }).format(url.length / 1024);
            toast.success(t('workflowShare.copyUrlCopied'), {
              message: t('workflowShare.copyUrlSizeKB', { size: shareUrlSize }),
            });
          } catch {
            // Some browsers block clipboard from non-user gestures — surface
            // the URL inline as a fallback.
            await alertDialog({ title: t('workflowShare.copyUrlDialogTitle'), message: url });
          }
        },
      },
      {
        id: 'workflow.autoName',
        label: t('commandPalette.commands.workflow.autoName'),
        description: t('commandPalette.commands.workflow.autoNameDescription'),
        group: 'Workflow',
        groupLabelKey: 'commandPalette.groups.workflow',
        onSelect: () => {
          const suggestion = suggestWorkflowName(activeWorkflow);
          if (!suggestion) {
            toast.info(t('workflowNaming.toast.needsNodes'));
            return;
          }
          handleRenameTab(activeIndex, suggestion);
          toast.success(t('workflowNaming.toast.renamed'), { message: suggestion });
        },
      },
      {
        id: 'edit.bulkParams',
        label: t('commandPalette.commands.edit.bulkParams'),
        description: t('commandPalette.commands.edit.bulkParamsDescription'),
        group: 'Edit',
        groupLabelKey: 'commandPalette.groups.edit',
        onSelect: () => {
          const selected = canvasRef.current?.getSelectedNodeIds() ?? [];
          if (selected.length < 2) {
            toast.info(t('paramBulk.selectAtLeastTwo'));
            return;
          }
          setShowBulkParam(true);
        },
      },
      {
        id: 'workflow.export',
        label: t('commandPalette.commands.workflow.export'),
        group: 'Workflow',
        groupLabelKey: 'commandPalette.groups.workflow',
        shortcut: getBinding('workflow.export') ?? undefined,
        onSelect: () => setShowExport(true),
      },
      {
        id: 'workflow.import',
        label: t('commandPalette.commands.workflow.import'),
        group: 'Workflow',
        groupLabelKey: 'commandPalette.groups.workflow',
        shortcut: getBinding('workflow.import') ?? undefined,
        onSelect: () => setShowImport(true),
      },
      {
        id: 'nodes.search',
        label: t('commandPalette.commands.nodes.search'),
        description: t('commandPalette.commands.nodes.searchDescription'),
        group: 'Panels',
        groupLabelKey: 'commandPalette.groups.panels',
        shortcut: getBinding('nodes.search') ?? undefined,
        onSelect: () => setRailTab('nodes'),
      },
      {
        id: 'rail.workspace',
        label: t('commandPalette.commands.rail.workspace'),
        group: 'Panels',
        groupLabelKey: 'commandPalette.groups.panels',
        shortcut: getBinding('rail.workspace') ?? undefined,
        onSelect: () => togglePanel('data'),
      },
      {
        id: 'rail.nodes',
        label: t('commandPalette.commands.rail.nodes'),
        group: 'Panels',
        groupLabelKey: 'commandPalette.groups.panels',
        shortcut: getBinding('rail.nodes') ?? undefined,
        onSelect: () => togglePanel('nodes'),
      },
      {
        id: 'rail.templates',
        label: t('commandPalette.commands.rail.templates'),
        group: 'Panels',
        groupLabelKey: 'commandPalette.groups.panels',
        shortcut: getBinding('rail.templates') ?? undefined,
        onSelect: () => togglePanel('templates'),
      },
      {
        id: 'rail.environment',
        label: t('commandPalette.commands.rail.environment'),
        group: 'Panels',
        groupLabelKey: 'commandPalette.groups.panels',
        shortcut: getBinding('rail.environment') ?? undefined,
        onSelect: () => togglePanel('environments'),
      },
      {
        id: 'rail.runtimeArtifacts',
        label: t('commandPalette.commands.rail.runtimeArtifacts'),
        group: 'Panels',
        groupLabelKey: 'commandPalette.groups.panels',
        onSelect: () => togglePanel('runtimeArtifacts'),
      },
      {
        id: 'rail.hpc',
        label: t('commandPalette.commands.rail.hpc'),
        group: 'Panels',
        groupLabelKey: 'commandPalette.groups.panels',
        shortcut: getBinding('rail.hpc') ?? undefined,
        onSelect: () => togglePanel('hpc'),
      },
      {
        id: 'rail.help',
        label: t('commandPalette.commands.rail.help'),
        group: 'Panels',
        groupLabelKey: 'commandPalette.groups.panels',
        shortcut: getBinding('rail.help') ?? undefined,
        onSelect: () => togglePanel('help'),
      },
      {
        id: 'rail.console',
        label: t('commandPalette.commands.rail.console'),
        group: 'Panels',
        groupLabelKey: 'commandPalette.groups.panels',
        shortcut: getBinding('rail.console') ?? undefined,
        onSelect: () => togglePanel('console'),
      },
      {
        id: 'console.toggle',
        label: t('commandPalette.commands.console.toggle'),
        group: 'Panels',
        groupLabelKey: 'commandPalette.groups.panels',
        shortcut: getBinding('console.toggle') ?? undefined,
        onSelect: handleToggleQueue,
      },
      {
        id: 'settings.toggle',
        label: t('commandPalette.commands.settings.toggle'),
        group: 'Panels',
        groupLabelKey: 'commandPalette.groups.panels',
        shortcut: getBinding('settings.toggle') ?? undefined,
        onSelect: () => togglePanel('settings'),
      },
      {
        id: 'ai.open',
        label: t('commandPalette.commands.ai.open'),
        group: 'Tools',
        groupLabelKey: 'commandPalette.groups.tools',
        shortcut: getBinding('ai.open') ?? undefined,
        onSelect: () => setShowAI(true),
      },
      {
        id: 'shortcuts.open',
        label: t('commandPalette.commands.shortcuts.open'),
        group: 'Tools',
        groupLabelKey: 'commandPalette.groups.tools',
        shortcut: getBinding('shortcuts.open') ?? undefined,
        onSelect: () => setShowShortcuts(true),
      },
      // --- View / canvas ----------------------------------------------------
      {
        id: 'view.focusMode',
        label: focusMode
          ? t('commandPalette.commands.view.exitFocusMode')
          : t('commandPalette.commands.view.enterFocusMode'),
        description: t('commandPalette.commands.view.focusModeDescription'),
        group: 'View',
        groupLabelKey: 'commandPalette.groups.view',
        shortcut: getBinding('view.focusMode') ?? undefined,
        onSelect: toggleFocusMode,
      },
      {
        id: 'view.fitAll',
        label: t('commandPalette.commands.view.fitAll'),
        description: t('commandPalette.commands.view.fitAllDescription'),
        group: 'View',
        groupLabelKey: 'commandPalette.groups.view',
        onSelect: () => canvasRef.current?.fitView(),
      },
      {
        id: 'view.fitSelection',
        label: t('commandPalette.commands.view.fitSelection'),
        description: t('commandPalette.commands.view.fitSelectionDescription'),
        group: 'View',
        groupLabelKey: 'commandPalette.groups.view',
        onSelect: () => {
          const ids = canvasRef.current?.getSelectedNodeIds() ?? [];
          if (ids.length === 0) {
            toast.info(t('canvas.selectNodeFirst'));
            return;
          }
          canvasRef.current?.focusNode(ids[0]);
        },
      },
      {
        id: 'view.toggleMinimap',
        label: t('commandPalette.commands.view.toggleMinimap'),
        group: 'View',
        groupLabelKey: 'commandPalette.groups.view',
        onSelect: () => set('bionodulo.showMinimap', !getBool('bionodulo.showMinimap')),
      },
      {
        id: 'view.toggleLinks',
        label: t('commandPalette.commands.view.toggleLinks'),
        group: 'View',
        groupLabelKey: 'commandPalette.groups.view',
        onSelect: () => set('bionodulo.linksHidden', !getBool('bionodulo.linksHidden')),
      },
      {
        id: 'view.toggleSnapGrid',
        label: t('commandPalette.commands.view.toggleSnapGrid'),
        group: 'View',
        groupLabelKey: 'commandPalette.groups.view',
        onSelect: () => set('bionodulo.snapToGrid', !getBool('bionodulo.snapToGrid')),
      },
      {
        id: 'view.toggleLockViewport',
        label: t('commandPalette.commands.view.toggleLockViewport'),
        group: 'View',
        groupLabelKey: 'commandPalette.groups.view',
        onSelect: () => set('bionodulo.viewportLocked', !getBool('bionodulo.viewportLocked')),
      },
      // --- History ----------------------------------------------------------
      {
        id: 'edit.undo',
        label: t('commandPalette.commands.edit.undo'),
        group: 'Edit',
        groupLabelKey: 'commandPalette.groups.edit',
        shortcut: 'Ctrl+Z',
        onSelect: undo,
      },
      {
        id: 'edit.redo',
        label: t('commandPalette.commands.edit.redo'),
        group: 'Edit',
        groupLabelKey: 'commandPalette.groups.edit',
        shortcut: 'Ctrl+Shift+Z',
        onSelect: redo,
      },
      {
        id: 'edit.autoLayout',
        label: t('commandPalette.commands.edit.autoLayout'),
        description: t('commandPalette.commands.edit.autoLayoutDescription'),
        group: 'Edit',
        groupLabelKey: 'commandPalette.groups.edit',
        onSelect: () => canvasRef.current?.autoLayout(),
      },
      // --- Workflow tabs ----------------------------------------------------
      {
        id: 'workflow.new',
        label: t('commandPalette.commands.workflow.newTab'),
        group: 'Workflow',
        groupLabelKey: 'commandPalette.groups.workflow',
        onSelect: addTab,
      },
      {
        id: 'workflow.closeTab',
        label: t('commandPalette.commands.workflow.closeTab'),
        group: 'Workflow',
        groupLabelKey: 'commandPalette.groups.workflow',
        onSelect: () => closeTab(activeIndex),
      },
      {
        id: 'workflow.duplicateTab',
        label: t('workflowTabs.duplicateCurrent'),
        group: 'Workflow',
        groupLabelKey: 'commandPalette.groups.workflow',
        onSelect: () => handleDuplicateTab(activeIndex),
      },
      {
        id: 'workflow.batchSheet',
        label: t('commandPalette.commands.workflow.batchSheet'),
        description: t('commandPalette.commands.workflow.batchSheetDescription'),
        group: 'Workflow',
        groupLabelKey: 'commandPalette.groups.workflow',
        onSelect: () => setShowBatchSheet(true),
      },
      // --- Cache / runtime --------------------------------------------------
      {
        id: 'cache.toggle',
        label: t('commandPalette.commands.cache.toggle'),
        group: 'Workflow',
        groupLabelKey: 'commandPalette.groups.workflow',
        onSelect: () => set('bionodulo.cacheEnabled', !getBool('bionodulo.cacheEnabled')),
      },
      {
        id: 'cache.clear',
        label: t('commandPalette.commands.cache.clear'),
        group: 'Workflow',
        groupLabelKey: 'commandPalette.groups.workflow',
        onSelect: async () => {
          try {
            const data = await apiPost<{ entries_deleted?: number }>('/api/cache/clear');
            toast.success(t('settings.cache.clearedTitle'), {
              message: t('settings.cache.entriesDeleted', { count: data.entries_deleted || 0 }),
            });
          } catch (err) {
            logError('app.cache.clear', err);
            toast.error(t('settings.cache.clearFailed'), { message: err instanceof Error ? err.message : String(err) });
          }
        },
      },
      {
        id: 'queue.clear',
        label: t('commandPalette.commands.queue.clear'),
        group: 'Workflow',
        groupLabelKey: 'commandPalette.groups.workflow',
        onSelect: () => void handleClearQueue(),
      },
      // --- Logs / console ---------------------------------------------------
      {
        id: 'logs.clear',
        label: t('commandPalette.commands.logs.clear'),
        group: 'Tools',
        groupLabelKey: 'commandPalette.groups.tools',
        onSelect: clearLogs,
      },
      // --- Help / onboarding ------------------------------------------------
      {
        id: 'help.gettingStarted',
        label: t('commandPalette.commands.help.gettingStarted'),
        group: 'Tools',
        groupLabelKey: 'commandPalette.groups.tools',
        onSelect: () => setShowGettingStarted(true),
      },
      {
        id: 'help.shortcuts',
        label: t('commandPalette.commands.help.shortcutsAlias'),
        group: 'Tools',
        groupLabelKey: 'commandPalette.groups.tools',
        onSelect: () => setShowShortcuts(true),
      },
    ];

    const paletteCommands = palettes.map(palette => {
      const name = paletteDisplayName(palette, t);
      return {
        id: `palette.${palette.id}`,
        label: t('commandPalette.commands.palette.use', { name }),
        description: palette.descriptionKey
          ? t(palette.descriptionKey, { defaultValue: palette.description })
          : palette.description,
        group: 'Appearance',
        groupLabelKey: 'commandPalette.groups.appearance',
        onSelect: () => setPalette(palette.id),
      };
    });

    return [...baseCommands, ...paletteCommands];
  }, [
    activeIndex,
    activeWorkflow.name,
    addTab,
    clearLogs,
    closeTab,
    focusMode,
    get,
    getBinding,
    getBool,
    handleClearQueue,
    handleDuplicateTab,
    handleRun,
    handleToggleQueue,
    i18n.language,
    t,
    palettes,
    redo,
    set,
    setPalette,
    setRailTab,
    toggleFocusMode,
    togglePanel,
    undo,
  ]);

  useRegisteredCommands('app', appCommands);

  // Unified search: surface "Add {Node}" entries for every registered node
  // type plus recent-workflow entries so Ctrl+P doubles as a way to
  // create nodes and reopen workflows without leaving the keyboard.
  const dynamicCommands = useMemo<CommandItem[]>(() => {
    const items: CommandItem[] = [];
    const metas = Object.values(objectInfo);
    for (const meta of metas) {
      items.push({
        id: `addNode.${meta.id}`,
        label: t('nodePalette.addNodeTitle', { name: meta.display_name }),
        description: meta.description || nodeCategoryDisplayLabel(meta.category, t, t('nodePalette.otherCategory')),
        group: 'Add Node',
        groupLabelKey: 'nodePalette.addNode',
        keywords: [meta.id, meta.category, ...(meta.search_aliases || []), ...(meta.requires_external_tools || [])],
        onSelect: () => {
          const vp = canvasRef.current?.getViewport();
          const world = vp
            ? { x: (-vp.x + window.innerWidth / 2) / vp.scale, y: (-vp.y + window.innerHeight / 2) / vp.scale }
            : { x: 100, y: 100 };
          const newNode: WorkflowNode = {
            id: `${meta.id}_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`,
            type: meta.id,
            position: [Math.round(world.x), Math.round(world.y)],
            params: defaultsFor(meta),
            node_info: meta,
            ui: { title: meta.display_name },
          };
          updateWorkflow(activeIndex, { ...activeWorkflow, nodes: [...activeWorkflow.nodes, newNode] });
        },
      });
    }
    // Recent workflows: dynamic require to avoid pulling the module on first
    // paint if nothing is open yet.
    try {
      const recents = JSON.parse(localStorage.getItem('bionodulo.recentWorkflows') || '[]') as Array<{ id: string; name: string; filename?: string }>;
      for (const entry of recents.slice(0, 12)) {
        items.push({
          id: `recent.${entry.id}`,
          label: t('commandPalette.openRecentWorkflow', { name: entry.name }),
          description: entry.filename || t('commandPalette.recentWorkflowFallback'),
          group: 'Workflow',
          groupLabelKey: 'commandPalette.groups.workflow',
          onSelect: async () => {
            if (entry.filename) {
              const template = { id: entry.id, name: entry.name, filename: entry.filename, category: '', tags: [], tools: [], description: '', node_count: 0 } as TemplateInfo;
              await handleLoadTemplate(template);
            }
          },
        });
      }
    } catch { /* ignore */ }
    return items;
  }, [objectInfo, activeWorkflow, activeIndex, updateWorkflow, handleLoadTemplate, t]);
  useRegisteredCommands('dynamic', dynamicCommands);

  useGlobalShortcut('commandPalette.open', () => toggleCommandPalette());
  useGlobalShortcut('shortcuts.open', () => setShowShortcuts(true));
  useGlobalShortcut('view.focusMode', toggleFocusMode);
  useGlobalShortcut('nodes.search', () => setRailTab('nodes'));
  useGlobalShortcut('workflow.run', () => { void handleRun(); });
  useGlobalShortcut('workflow.export', () => setShowExport(true));
  useGlobalShortcut('workflow.import', () => setShowImport(true));
  useGlobalShortcut('settings.toggle', () => togglePanel('settings'));
  useGlobalShortcut('console.toggle', handleToggleQueue);
  useGlobalShortcut('ai.open', () => setShowAI(true));
  useGlobalShortcut('rail.workspace', () => togglePanel('data'));
  useGlobalShortcut('rail.nodes', () => togglePanel('nodes'));
  useGlobalShortcut('rail.templates', () => togglePanel('templates'));
  useGlobalShortcut('rail.environment', () => togglePanel('environments'));
  useGlobalShortcut('rail.hpc', () => togglePanel('hpc'));
  useGlobalShortcut('rail.help', () => togglePanel('help'));
  useGlobalShortcut('rail.console', () => togglePanel('console'));

  const latestWorkflowRef = useRef(activeWorkflow);
  useEffect(() => {
    latestWorkflowRef.current = activeWorkflow;
  }, [activeWorkflow]);

  // Auto-save timer — extracted to useAutoSave.
  useAutoSave({
    autoSaveSetting,
    collabEnabled: collabSessionActive,
    latestWorkflow: latestWorkflowRef.current,
    publishCollabWorkflowSnapshot,
    setDirty,
  });

  const workflowResolveKey = useMemo(() => JSON.stringify({
    id: activeWorkflow.id,
    nodes: activeWorkflow.nodes.map(node => [
      node.id,
      node.type,
      node.params,
      node.ui?.muted,
      node.ui?.bypassed,
    ]),
    edges: activeWorkflow.edges.map(edge => [
      edge.from.node,
      edge.from.output,
      edge.to.node,
      edge.to.input,
    ]),
  }), [activeWorkflow.id, activeWorkflow.nodes, activeWorkflow.edges]);

  // Auto-validate and resolve on workflow change. Notes / reroutes are
  // visual-only and the backend executor already filters them out, so a
  // workflow that contains only notes should be treated as "empty" for
  // resolve/validate purposes.
  useEffect(() => {
    const realNodes = (latestWorkflowRef.current.nodes || []).filter(
      n => n.type !== 'note' && n.type !== 'reroute',
    );
    if (realNodes.length === 0) {
      clearResolveReport();
      return;
    }
    const timer = setTimeout(() => {
      const workflow = latestWorkflowRef.current;
      validate(workflow);
      void resolve(workflow);
    }, 2000);
    return () => clearTimeout(timer);
  }, [workflowResolveKey, validate, resolve, clearResolveReport]);

  const { queueMode, setQueueMode } = useQueueMode({
    dirty,
    isRunning,
    activeNodes: activeWorkflow.nodes,
    runs,
    triggerRun: handleRun,
  });

  useEffect(() => {
    const handler = (event: BeforeUnloadEvent) => {
      // Snapshot the current tab's viewport so refreshing doesn't reset it.
      const currentId = workflows[activeIndex]?.id;
      if (currentId) {
        const vp = canvasRef.current?.getViewport?.();
        if (vp) {
          viewportByWorkflowRef.current[currentId] = vp;
          persistViewportStore();
        }
      }
      if (!dirty) return;
      event.preventDefault();
      event.returnValue = '';
    };
    window.addEventListener('beforeunload', handler);
    return () => window.removeEventListener('beforeunload', handler);
  }, [activeIndex, dirty, persistViewportStore, workflows]);

  // Reset banners when workflow changes
  useEffect(() => {
    setDismissedReport(null);
    clearResolveReport();
  }, [activeIndex, clearResolveReport]);

  const workflowNamesKey = useMemo(() => workflowNameSignature(workflows), [workflows]);
  const tabNames = useMemo(() => workflows.map(w => w.name || t('common.untitled')), [workflowNamesKey, t]);
  const activeNodeTypeKey = useMemo(() => nodeTypeSignature(activeWorkflow.nodes), [activeWorkflow.nodes]);
  const missingTypesKey = useMemo(() => {
    const missingTypes = new Set<string>();
    for (const item of resolveReport?.missing_nodes ?? []) missingTypes.add(item.node_type);
    for (const item of resolveReport?.missing_executables ?? []) item.node_types.forEach(type => missingTypes.add(type));
    for (const item of resolveReport?.missing_packages ?? []) item.node_types.forEach(type => missingTypes.add(type));
    for (const item of resolveReport?.missing_r_packages ?? []) item.node_types.forEach(type => missingTypes.add(type));
    return JSON.stringify([...missingTypes].sort());
  }, [resolveReport]);
  const missingDependencyNodeIds = useMemo(() => {
    const missingTypes = new Set<string>(JSON.parse(missingTypesKey) as string[]);
    return new Set(activeWorkflow.nodes.filter(node => missingTypes.has(node.type)).map(node => node.id));
  }, [activeNodeTypeKey, missingTypesKey]);
  const latestNodeStatuses = runs[0]?.node_statuses ?? [];
  const latestNodeStatusKey = useMemo(() => nodeStatusSignature(latestNodeStatuses), [latestNodeStatuses]);
  const nodeStatusMap = useMemo<Map<string, NodeStatus['status']>>(() => (
    new Map(latestNodeStatuses.map(ns => [ns.node_id, ns.status]))
  ), [latestNodeStatusKey]);
  // Node error messages from the latest run. Cleared per-node when the user
  // edits that node so a stale "missing arg" message doesn't linger after a
  // fix. The clear happens in handleNodesChange below.
  const [dismissedErrorNodeIds, setDismissedErrorNodeIds] = useState<Set<string>>(new Set());
  const nodeErrorsMap = useMemo<Map<string, string>>(() => {
    const map = new Map<string, string>();
    for (const ns of latestNodeStatuses) {
      if (ns.status === 'error' && ns.error && !dismissedErrorNodeIds.has(ns.node_id)) {
        map.set(ns.node_id, ns.error);
      }
    }
    return map;
  }, [latestNodeStatusKey, dismissedErrorNodeIds]);
  // Clear dismissed errors when a new run starts so a fresh failure on the
  // same node surfaces again.
  const latestRunId = runs[0]?.run_id;
  useEffect(() => {
    setDismissedErrorNodeIds(new Set());
  }, [latestRunId]);
  // A node renders an inline preview when it registered one under its own id
  // (image_preview, html_preview, table_preview, text_preview, and any
  // analysis node that self-registers a summary), branching by file extension.
  // For the wired image_preview/html_preview nodes we also fall back to the
  // upstream producer's auto-registered output for backward compatibility.
  const liveWorkflowNamesKey = useMemo(() => recordSignature(workflowNames), [workflowNames]);
  const knownWorkflowNames = useMemo(() => ({
    ...Object.fromEntries(workflows.filter(workflow => workflow.id).map(workflow => [workflow.id!, workflow.name || t('common.untitled')])),
    ...workflowNames,
  }), [liveWorkflowNamesKey, t, workflowNamesKey]);
  const appShellClassName = useMemo(() => ([
    'app-shell',
    showAI ? 'ai-open' : '',
    showComments ? 'comments-open' : '',
    runsDrawerOpen ? 'runs-drawer-open' : '',
    (consoleVisible || railTab === 'console') ? 'console-open' : '',
    focusMode ? 'focus-mode' : '',
  ].filter(Boolean).join(' ')), [consoleVisible, focusMode, railTab, runsDrawerOpen, showAI, showComments]);
  // Total pixel width of all panels currently docked to the RIGHT edge —
  // exposed as `--right-panel-inset` so .minimap / .canvas-controls slide
  // left to stay visible instead of being clipped by the panel.
  const rightPanelInset = useMemo(() => {
    let total = runsDrawerOpen ? 380 : 0;
    for (const tab of openPanelTabs) {
      if (isCenterMenuTab(tab)) continue;
      if (!rightDockedPanels[tab] || floatingPanels[tab]) continue;
      total += (panelWidths[tab] ?? 340);
    }
    return total;
  }, [openPanelTabs, rightDockedPanels, floatingPanels, panelWidths, runsDrawerOpen]);
  // NOTE: The "Unsaved changes / Autosave" pill that used to live in the top
  // bar was removed in Wave L. The amber dot on each workflow tab now carries
  // the dirty signal, and pre-flight save state is still surfaced inline when
  // it matters (e.g. close-tab confirm dialog), so a global pill became noise.

  const closePanel = useCallback((tab: OpenPanelTab) => {
    setOpenPanelTabs(current => current.filter(item => item !== tab));
    setRailTabState(prev => (prev === tab ? null : prev));
  }, []);

  const getPanelLabel = useCallback((tab: OpenPanelTab) => {
    const key = PANEL_LABEL_KEYS[tab];
    if (key) return t(key);
    return registeredPanels.find(panel => panel.id === tab)?.title || String(tab);
  }, [registeredPanels, t]);

  const renderPanelContent = (tab: OpenPanelTab) => {
    const wrap = (name: string, node: ReactNode): ReactNode => (
      <ErrorBoundary name={name} variant="inline" resetKeys={[tab]}>{node}</ErrorBoundary>
    );
    if (tab === 'settings') {
      return wrap('settings', (
        <SettingsPanel
          onClose={() => closePanel(tab)}
          collabEnabled={collabEnabled}
          collabConnected={collabConnected}
          collabConnecting={collabConnecting}
          collabShareLink={collabShareLink}
          hasJoinLink={hasPendingJoinLink}
          onCreateCollabSession={handleCreateCollabSession}
          onJoinCollabSession={() => void handleJoinCollabSession(activeCollabJoinTarget)}
          onLeaveCollabSession={handleLeaveCollabSession}
        />
      ));
    }
    if (tab === 'help') {
      const selected = selectedNodeId
        ? activeWorkflow.nodes.find(n => n.id === selectedNodeId)
        : null;
      const helpSelectedNode = selected
        ? {
          id: selected.id,
          type: selected.type,
          meta: objectInfo[selected.type],
          title: selected.ui?.title || objectInfo[selected.type]?.display_name || selected.type,
          params: selected.params,
        }
        : null;
      return wrap('help', <HelpWikiPanel onClose={() => closePanel(tab)} selectedNode={helpSelectedNode} objectInfo={objectInfo} />);
    }
    if (tab === 'templates') {
      return wrap('templates', (
        <TemplatesPanel
          onClose={() => closePanel(tab)}
          onLoadTemplate={handleLoadTemplate}
          onSaveTemplate={handleSaveTemplate}
          showSaveTemplateAction
          saveTemplateInitialName={resolveWorkflowName(activeWorkflow)}
          saveTemplateInitialDescription={activeWorkflow.description || ''}
        />
      ));
    }
    if (tab === 'environments') return wrap('environments', <EnvironmentPanel onClose={() => closePanel(tab)} currentWorkflow={activeWorkflow} />);
    if (tab === 'runtimeArtifacts') return wrap('runtimeArtifacts', (
      <RuntimeArtifactsPanel
        onClose={() => closePanel(tab)}
        onResumeCheckpointSelect={setResumeCheckpoint}
      />
    ));
    if (tab === 'hpc') {
      return wrap('hpc', (
        <HPCPanel
          config={hpcConfig}
          onChange={(cfg) => {
            set('bionodulo.hpc.enabled', cfg.enabled);
            set('bionodulo.hpc.backend', cfg.backend);
            set('bionodulo.hpc.partition', cfg.partition || '');
            set('bionodulo.hpc.account', cfg.account || '');
            set('bionodulo.hpc.modules', cfg.modules || []);
            set('bionodulo.hpc.container', cfg.container || '');
            set('bionodulo.hpc.walltime', cfg.walltime || '01:00:00');
            set('bionodulo.hpc.cpus_per_task', cfg.cpus_per_task || 4);
            set('bionodulo.hpc.mem_per_cpu', cfg.mem_per_cpu || '4G');
          }}
          onClose={() => closePanel(tab)}
        />
      ));
    }
    if (tab === 'nodes') {
      return wrap('nodes', (
        <NodeLibraryPanel
          objectInfo={objectInfo}
          loading={objectInfoLoading}
          onAddNode={(meta) => {
            const newNode: WorkflowNode = {
              id: `${meta.id}_${Date.now()}`,
              type: meta.id,
              position: [200 + Math.random() * 40, 200 + Math.random() * 40],
              params: defaultsFor(meta),
              node_info: meta,
              ui: { title: meta.display_name },
            };
            handleNodesChange([...activeWorkflow.nodes, newNode]);
            pushHistory();
          }}
          onAddBlueprint={(bp) => {
            const newNode = instantiateBlueprint(bp, [200 + Math.random() * 40, 200 + Math.random() * 40]);
            handleNodesChange([...activeWorkflow.nodes, newNode]);
            pushHistory();
          }}
          onClose={() => closePanel(tab)}
        />
      ));
    }
    if (tab === 'data') {
      return wrap('data', (
        <WorkspacePanel
          onClose={() => closePanel(tab)}
          onOpenSettings={() => setRailTab('settings')}
          onImportWorkflow={handleImport}
        />
      ));
    }
    if (tab === 'user') {
      return wrap('user', <UserPanel onClose={() => closePanel(tab)} />);
    }
    if (tab === 'compute') {
      return wrap('compute', <ComputePanel onClose={() => closePanel(tab)} />);
    }
    const registered = registeredPanels.find(panel => panel.id === tab);
    if (registered) {
      return wrap(`plugin.${tab}`, registered.render());
    }
    return null;
  };

  return (
    <div
      className={appShellClassName}
      style={{ '--right-panel-inset': `${rightPanelInset}px` } as Record<string, string>}
    >
      <NotificationHost />
      <ConfirmDialogHost />
      <CommandPaletteHost />
      <TransferWindow />
      <KeyboardShortcutsModal open={showShortcuts} onOpenChange={setShowShortcuts} />

      {draggingPanelTab && (
        <>
          <div className={`panel-dropzone panel-dropzone-left ${panelDropZone === 'left' ? 'is-active' : ''}`}>
            <Icon name="dockPanel" size={18} />
            <span>{t('panels.dockLeftDropzone')}</span>
          </div>
          <div className={`panel-dropzone panel-dropzone-right ${panelDropZone === 'right' ? 'is-active' : ''}`}>
            <Icon name="dockPanel" size={18} />
            <span>{t('panels.dockRightDropzone')}</span>
          </div>
        </>
      )}

      <TopBar
        validationValid={validation.valid}
        validationErrors={validation.errors}
        onRun={handleRun}
        hpcStatus={hpcStatus}
        hpcEnabled={hpcEnabled}
        queueMode={queueMode}
        onQueueModeChange={setQueueMode}
        queueCount={queueCount}
        onToggleQueue={handleToggleQueue}
        onRunOnCloud={editorMode ? undefined : handleRunOnCloud}
        dryRunPreview={dryRunPreview}
        onDryRunPreviewChange={setDryRunPreview}
        editorMode={editorMode}
        resumeCheckpointLabel={resumeCheckpoint?.label ?? null}
        onOpenRuntimeArtifacts={() => setRailTab('runtimeArtifacts')}
        onResumeCheckpointClear={() => setResumeCheckpoint(null)}
        cloudAccount={cloudMode && cloudConfig ? {
          userName: cloudConfig.user?.name ?? '',
          userEmail: cloudConfig.user?.email ?? '',
          plan: cloudConfig.plan,
          creditsRemaining: cloudConfig.credits?.remaining ?? null,
          accountUrl: cloudConfig.accountUrl,
        } : null}
        collabControls={(
          <CollabBadge
            enabled={collabEnabled}
            connected={collabConnected}
            connecting={collabConnecting}
            activeUsers={collabActiveUsers}
            liveUsers={livePresenceUsers}
            currentUserId={currentUser.id}
            currentSessionId={collabSessionId}
            currentWorkflowId={activeWorkflowId}
            workflowNames={knownWorkflowNames}
            followingUserId={followingUserId}
            isShared={collabIsShared}
            onFollow={followPresenceUser}
            onOpenSettings={() => setRailTab('settings')}
            onCreateSession={handleCreateCollabSession}
            onJoinSession={() => void handleJoinCollabSession(activeCollabJoinTarget)}
            onLeaveSession={handleLeaveCollabSession}
            hasJoinLink={hasPendingJoinLink}
            shareLink={collabShareLink}
            reconnectAttempt={collabReconnectAttempt}
            error={collabError}
            offline={collabOffline}
            editorMode={editorMode}
            credits={cloudCredits}
            canInvite={Boolean(authUser) && (editorMode || Boolean(cloudConfig?.accountUrl))}
          />
        )}
      />

      <AuthDialog
        isOpen={showAuthDialog}
        onLogin={handleAuthLogin}
        onClose={handleCollabAuthClose}
      />

      <InviteDialog />
      {editorMode && (
        <Suspense fallback={null}>
          <OpenWorkflowModal onOpen={(id) => void openCloudWorkflow(id)} onNew={() => void newCloudWorkflow()} />
        </Suspense>
      )}

      <WorkflowTabs
        tabs={tabNames}
        active={activeIndex}
        onChange={setActiveIndex}
        onClose={async (index) => {
          // Guard the active tab if it has unsaved changes; other tabs
          // currently don't track dirtiness individually so we close them
          // without confirmation (autosave covers the common case).
          if (index === activeIndex && dirty) {
            const wfName = workflows[index]?.name || t('workflowTabs.thisWorkflow');
            const ok = await confirmDialog({
              title: t('workflowTabs.closeUnsavedTitle'),
              message: t('workflowTabs.closeUnsavedMessage', { name: wfName }),
              confirmLabel: t('common.close'),
              tone: 'danger',
            });
            if (!ok) return;
          }
          closeTab(index);
        }}
        onAdd={editorMode ? () => setShowOpenWorkflow(true) : addTab}
        onRename={handleRenameTab}
        onDuplicate={handleDuplicateTab}
        onReorder={handleReorderTabs}
        dirtyIndices={dirty ? new Set([activeIndex]) : undefined}
      />

      <LeftRail active={railTab} onChange={setRailTab} />

      <RunsDrawer
        open={runsDrawerOpen}
        queue={queuedRuns}
        history={runs}
        onClose={() => setRunsDrawerOpen(false)}
        onCancelRun={handleCancelRun}
        onRetryRun={handleRetryRun}
        onLoadRunWorkflow={handleLoadRunWorkflow}
        onDeleteHistoryEntry={handleDeleteHistoryEntry}
        onMoveRun={handleMoveRun}
        onClearQueue={handleClearQueue}
        onClearHistory={handleClearHistory}
      />

      <div
        className="main-canvas"
        onDragOver={(e) => {
          const types = e.dataTransfer.types;
          if (
            types.includes('application/bionodulo-workflow-path')
            || types.includes('application/bionodulo-workspace-file')
          ) {
            e.preventDefault();
            e.dataTransfer.dropEffect = 'copy';
          }
        }}
        onDrop={async (e) => {
          // Workflow JSON drop: import the workflow into the active tab.
          const workflowPath = e.dataTransfer.getData('application/bionodulo-workflow-path');
          if (workflowPath) {
            e.preventDefault();
            try {
              const text = await apiGetText(`/api/workspace/file?path=${encodeURIComponent(workflowPath)}`);
              const wf = JSON.parse(text);
              if (wf && (wf.nodes || Array.isArray(wf))) {
                handleImport(wf);
              }
            } catch { /* ignore */ }
            return;
          }
          // Workspace file drop: spawn an input_file node wired to the path so
          // the user can drop e.g. a FASTQ and have it ready to feed into the
          // first downstream node. Lands at the drop location in world coords.
          const filePath = e.dataTransfer.getData('application/bionodulo-workspace-file');
          if (filePath) {
            e.preventDefault();
            const inputMeta = objectInfo['input_file'];
            if (!inputMeta) {
              toast.warning(appFileActionCopy.error.missingInputFileForDrop);
              return;
            }
            // Native React Flow screen->flow projection places the node exactly
            // under the drop point at any pan/zoom (no manual viewport math).
            const world = canvasRef.current?.screenToFlowPosition(e.clientX, e.clientY)
              ?? { x: e.clientX, y: e.clientY };
            const fileName = filePath.split(/[\\/]/).pop() || appFileActionCopy.fileTypeFallback;
            const newNode: WorkflowNode = {
              id: `input_file_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`,
              type: 'input_file',
              position: [Math.round(world.x), Math.round(world.y)],
              params: { ...defaultsFor(inputMeta), path: filePath },
              node_info: inputMeta,
              ui: { title: fileName },
            };
            const next: Workflow = { ...activeWorkflow, nodes: [...activeWorkflow.nodes, newNode] };
            updateWorkflow(activeIndex, next);
            toast.success(appFileActionCopy.toast.fileDropped, { message: fileName });
          }
        }}
      >
        {!cloudMode && !editorMode && hostStatus && !hostStatus.ready && hostStatus !== dismissedHostStatus && (
          <HostPrerequisitesBanner
            status={hostStatus}
            onDismiss={() => setDismissedHostStatus(hostStatus)}
            onOpenConsole={() => { setConsoleVisible(true); setRailTab('console'); }}
            onRecheck={async () => {
              try {
                const raw = await apiGet<unknown>('/api/host_status');
                const result = safeValidateHostStatus(raw);
                if (result.ok) setHostStatus(result.value as HostStatus);
                else logError('host_status.recheck.validate', result.error);
              } catch { /* offline */ }
            }}
          />
        )}
        {getBool('bionodulo.dependencies.promptBeforeInstall') && resolveReport && resolveReport.has_issues && resolveReport !== dismissedReport && (
          <MissingDependenciesBanner
            report={resolveReport}
            workflow={activeWorkflow}
            onDismiss={() => setDismissedReport(resolveReport)}
            onOpenConsole={() => { setConsoleVisible(true); setRailTab('console'); }}
            onResolve={() => { resolve(activeWorkflow); }}
          />
        )}
        <WorkflowCanvas
          ref={canvasRef}
          nodes={activeWorkflow.nodes}
          edges={activeWorkflow.edges}
          objectInfo={objectInfo}
          workflowParameters={activeWorkflow.parameters ?? []}
          onNodesChange={handleNodesChange}
          onEdgesChange={handleEdgesChange}
          onPushHistory={pushHistory}
          onUndo={undo}
          onRedo={redo}
          snapToGrid={getBool('bionodulo.snapToGrid')}
          showMinimap={getBool('bionodulo.showMinimap')}
          nodeStatusMap={nodeStatusMap}
          nodeErrorsMap={nodeErrorsMap}
          missingDependencyNodeIds={missingDependencyNodeIds}
          onExecuteSelected={handleRunSelected}
          onOpenNodeLibrary={() => setRailTab('nodes')}
          collabSessionActive={collabSessionActive}
          collabUsers={collabActiveUsers}
          currentUserId={currentUser.id}
          currentUserName={currentUser.name}
          currentUserColor={currentUser.color}
          onCollabCursor={collabSessionActive ? setCollabCursor : undefined}
          onCollabSelection={collabSessionActive ? setCollabSelection : undefined}
          nodeComments={workflowComments}
          onAddComment={handleAddComment}
          onResolveComment={handleResolveComment}
          onDeleteComment={handleDeleteComment}
        />

        {/* Registered rail panels: docked panels stack from the left edge by
            default, but each panel can be flipped to the right edge so two
            related panels (e.g. node library + node info) can sit side by
            side without the user having to float either of them. */}
        {(() => {
          const leftPanels = openPanelTabs.filter(tab => !isCenterMenuTab(tab) && !rightDockedPanels[tab] && !floatingPanels[tab]);
          const rightPanels = openPanelTabs.filter(tab => !isCenterMenuTab(tab) && rightDockedPanels[tab] && !floatingPanels[tab]);
          const floatingTabs = openPanelTabs.filter(tab => !isCenterMenuTab(tab) && floatingPanels[tab]);
          const renderPanel = (tab: OpenPanelTab, side: 'left' | 'right' | 'float', offset: number) => {
            const index = openPanelTabs.indexOf(tab);
            const width = panelWidths[tab] ?? 340;
            const floating = floatingPanels[tab];
            const isRight = side === 'right';
            const panelLabel = getPanelLabel(tab);
            const style = floating
              ? { left: floating.x, top: floating.y, width }
              : isRight
                ? { right: offset, width }
                : { left: offset, width };
            return (
              <div
                key={tab}
                className={`rail-panel-wrap ${floating ? 'floating' : ''} ${isRight ? 'docked-right' : ''} ${draggingPanelTab === tab ? 'is-dragging' : ''}`}
                style={style}
              >
                {floating && (
                  <div
                    className="rail-panel-drag-handle"
                    onMouseDown={event => startPanelDrag(tab, event.clientX, event.clientY, floating)}
                    role="presentation"
                  />
                )}
                {/* Toolbar + content share a single Suspense boundary so the
                    float / dock buttons no longer flash onscreen before the
                    lazy panel chunk has resolved. The fallback covers the
                    full panel area until the real UI is ready. */}
                <Suspense fallback={<div className="panel-suspense-fallback"><Spinner size="lg" label={t('panels.loadingPanel', { name: panelLabel })} /></div>}>
                  <div className="rail-panel-toolbar">
                    {!floating && (
                      <button
                        className="rail-panel-dock-side"
                        onClick={() => toggleRightDocked(tab)}
                        title={isRight ? t('panels.dockToLeftSide') : t('panels.dockToRightSide')}
                        aria-label={isRight ? t('panels.moveToLeftSide') : t('panels.moveToRightSide')}
                        type="button"
                      >
                        <Icon name={isRight ? 'chevronLeft' : 'chevronRight'} size={13} />
                      </button>
                    )}
                    <button
                      className="rail-panel-float"
                      onClick={() => toggleFloatingPanel(tab, index)}
                      title={floating ? t('panels.dockPanel') : t('panels.floatPanel')}
                      type="button"
                    >
                      <Icon name={floating ? 'dockPanel' : 'floatPanel'} size={13} />
                    </button>
                  </div>
                  {renderPanelContent(tab)}
                </Suspense>
                <div
                  className={`rail-panel-resizer ${isRight ? 'on-left' : ''}`}
                  role="separator"
                  aria-label={t('panels.resizePanel', { name: panelLabel })}
                  aria-orientation="vertical"
                  aria-valuenow={width}
                  aria-valuemin={280}
                  aria-valuemax={560}
                  tabIndex={0}
                  onMouseDown={event => startPanelResize(tab, event.clientX, width, isRight)}
                  onTouchStart={event => {
                    const t = event.touches[0];
                    if (t) startPanelResize(tab, t.clientX, width, isRight);
                  }}
                  onKeyDown={event => handlePanelResizeKey(tab, isRight, event)}
                />
              </div>
            );
          };
          const leftRendered = leftPanels.map((tab, idx) => {
            const offset = leftPanels.slice(0, idx).reduce((total, item) => total + (panelWidths[item] ?? 340), 0);
            return renderPanel(tab, 'left', offset);
          });
          const rightRendered = rightPanels.map((tab, idx) => {
            const offset = rightPanels.slice(0, idx).reduce((total, item) => total + (panelWidths[item] ?? 340), 0);
            return renderPanel(tab, 'right', offset);
          });
          const floatingRendered = floatingTabs.map(tab => renderPanel(tab, 'float', 0));
          return [...leftRendered, ...rightRendered, ...floatingRendered];
        })()}

        {openPanelTabs.filter(isCenterMenuTab).map(tab => (
          <Suspense key={`center-menu-${tab}`} fallback={<div className="modal-overlay"><Spinner size="lg" label={t('panels.loadingPanel', { name: getPanelLabel(tab) })} /></div>}>
            {renderPanelContent(tab)}
          </Suspense>
        ))}

        {focusMode && (
          <button
            type="button"
            className="focus-mode-exit"
            onClick={toggleFocusMode}
            title={t('commandPalette.commands.view.exitFocusMode')}
          >
            {t('commandPalette.commands.view.exitFocusMode')} <kbd>{getBinding('view.focusMode') ?? 'Ctrl+.'}</kbd>
          </button>
        )}
        {(consoleVisible || railTab === 'console') && (
          <ErrorBoundary name="console" variant="inline" resetKeys={[railTab, consoleVisible]}>
            <BottomConsole
              queue={queuedRuns}
              history={runs}
              onClose={() => { setConsoleVisible(false); if (railTab === 'console') setRailTab(null); }}
              onClearLogs={clearLogs}
              nodeIdToName={nodeIdToNameMap}
              editorMode={editorMode}
            />
          </ErrorBoundary>
        )}
      </div>

      <Modals ctx={{
        activeWorkflow,
        activeWorkflowId,
        activeIndex,
        updateWorkflow,
        activeWorkflowRef,
        bridgeRef,
        canvasRef,
        runs,
        objectInfo,
        currentUser,
        collabEnabled,
        collabInviteToken: activeInviteToken,
        collabShareLink,
        onCreateCollabSession: handleCreateCollabSession,
        getBool,
        set,
        handleImport,
        handleApplyWorkflow,
        handleBatchSheetSubmit,
        handleLoadTemplate,
        publishCollabWorkflowSnapshot,
        comments: workflowComments,
        onAddComment: handleAddComment,
        onResolveComment: handleResolveComment,
        onDeleteComment: handleDeleteComment,
      }} />

    </div>
  );
}
