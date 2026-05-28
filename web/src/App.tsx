import { useState, useCallback, useEffect, useRef, useMemo, lazy, Suspense } from 'react';
import { useAtom } from 'jotai';
import TopBar from './components/layout/TopBar';
import LeftRail, { type RailTab } from './components/layout/LeftRail';
import WorkflowTabs from './components/layout/WorkflowTabs';
import BottomConsole from './components/layout/BottomConsole';
import ErrorBoundary from './components/layout/ErrorBoundary';
import LiteGraphCanvas, { type LiteGraphCanvasRef } from './components/canvas/LiteGraphCanvas';
import WorkflowStatsOverlay from './components/canvas/WorkflowStatsOverlay';
import type { TemplateSaveDraft } from './components/panels/TemplatesPanel';
const SettingsPanel = lazy(() => import('./components/panels/SettingsPanel'));
const HelpWikiPanel = lazy(() => import('./components/panels/HelpWikiPanel'));
const TemplatesPanel = lazy(() => import('./components/panels/TemplatesPanel'));
const EnvironmentPanel = lazy(() => import('./components/panels/EnvironmentPanel'));
const HPCPanel = lazy(() => import('./components/panels/HPCPanel'));
const NodeLibraryPanel = lazy(() => import('./components/panels/NodeLibraryPanel'));
const WorkspacePanel = lazy(() => import('./components/panels/WorkspacePanel'));
import ExportModal from './components/modals/ExportModal';
import ImportModal from './components/modals/ImportModal';
import AIWorkflowModal from './components/modals/AIWorkflowModal';
import BatchSampleSheetModal from './components/modals/BatchSampleSheetModal';
import type { SampleSheetRun } from './components/modals/BatchSampleSheetModal';
import ImageLightbox from './components/modals/ImageLightbox';
import HtmlPreviewModal from './components/modals/HtmlPreviewModal';
import GettingStartedModal from './components/modals/GettingStartedModal';
const OutputDiffModal = lazy(() => import('./components/modals/OutputDiffModal'));
const BulkParamModal = lazy(() => import('./components/modals/BulkParamModal'));
const WorkflowDoctorModal = lazy(() => import('./components/modals/WorkflowDoctorModal'));
import MissingDependenciesBanner from './components/layout/MissingDependenciesBanner';
import HostPrerequisitesBanner from './components/layout/HostPrerequisitesBanner';
import Icon from './components/ui/Icon';
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
import { useSettings } from './hooks/useSettings';
import { useWorkflow } from './hooks/useWorkflow';
import { useObjectInfo } from './hooks/useObjectInfo';
import { useTheme } from './hooks/useTheme';
import { useWebSocket } from './hooks/useWebSocket';
import { useRegisteredCommands } from './hooks/useCommandPalette';
import { useGlobalShortcut, useKeybindings } from './hooks/useKeybindings';
import { usePaletteTheme } from './hooks/usePaletteTheme';
import { usePanelRegistry } from './state/panels';
import { rememberRecentWorkflow, refreshRecentThumbnail } from './state/recentWorkflows';
import { renderRecentThumbnail } from './utils/workflowThumbnail';
import { resolveWorkflowName, suggestWorkflowName } from './utils/workflowNaming';
import { buildShareUrl, readWorkflowFromHash, clearShareHash } from './utils/workflowShare';
import { logTelemetry } from './state/telemetry';
import { installDomOverlayBridge } from './state/overlays';
import {
  LiteGraphYjsBridge, useCollab, workflowToDoc, docToWorkflow,
  CollabBadge, ShareDialog,
  getUserColor, getAuthUser, getToken, initAuth, AuthDialog,
  CommentsPanel, VersionHistory, AuditLog,
} from './collab';
import { defaultsFor, valuesFromUnknownRecord } from './utils';
import { apiGet, apiPost, apiDelete, ApiError } from './api/client';
import { extractSubgraph, writeSubgraphBack, promoteWidget } from './utils/subgraph';
import { instantiateBlueprint } from './state/subgraphLibrary';
import { getLocalTemplateWorkflow } from './localTemplates';
import {
  authReadyAtom,
  authUserAtom,
  requestedWorkflowIdAtom,
  showAuthDialogAtom,
} from './state/appAtoms';
import type { Workflow, WorkflowNode, HPCConfig, TemplateInfo, LogEntry, ResolveReport, HostStatus, RunRecord, NodeStatus } from './types';
import type { AwarenessState, Comment, LivePresenceUser } from './collab';
import type { HPCStatus } from './components/layout/TopBar';

const EMPTY_COLLAB_USERS: AwarenessState[] = [];
const EMPTY_STRING_ARRAY: string[] = [];
const PANEL_WIDTHS_KEY = 'bionodulo.panel.widths';
const PANEL_FLOATS_KEY = 'bionodulo.panel.floats';
const PANEL_RIGHT_DOCKED_KEY = 'bionodulo.panel.rightDocked';
const AUTO_SAVE_LAST_KEY = 'bionodulo.autoSave.last';
type OpenPanelTab = Exclude<RailTab, null | 'console'>;
type FloatingPanelLayout = Record<string, { x: number; y: number }>;

function loadPanelWidths(): Record<string, number> {
  try {
    const raw = localStorage.getItem(PANEL_WIDTHS_KEY);
    return raw ? JSON.parse(raw) as Record<string, number> : {};
  } catch {
    return {};
  }
}

function loadFloatingPanels(): FloatingPanelLayout {
  try {
    const raw = localStorage.getItem(PANEL_FLOATS_KEY);
    return raw ? JSON.parse(raw) as FloatingPanelLayout : {};
  } catch {
    return {};
  }
}

function loadRightDockedPanels(): Record<string, true> {
  try {
    const raw = localStorage.getItem(PANEL_RIGHT_DOCKED_KEY);
    const parsed = raw ? JSON.parse(raw) as unknown : null;
    if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) return {};
    const result: Record<string, true> = {};
    for (const key of Object.keys(parsed as Record<string, unknown>)) {
      if ((parsed as Record<string, unknown>)[key]) result[key] = true;
    }
    return result;
  } catch {
    return {};
  }
}

function clampPanelWidth(width: number): number {
  return Math.max(280, Math.min(620, Math.round(width)));
}

function workflowNameSignature(workflows: Workflow[]): string {
  return JSON.stringify(workflows.map(workflow => [workflow.id ?? '', workflow.name || 'Untitled']));
}

function recordSignature(record: Record<string, string>): string {
  return JSON.stringify(Object.entries(record).sort(([a], [b]) => a.localeCompare(b)));
}

function nodeTypeSignature(nodes: WorkflowNode[]): string {
  return JSON.stringify(nodes.map(node => [node.id, node.type]));
}

function edgeTopologySignature(edges: Workflow['edges']): string {
  return JSON.stringify(edges.map(edge => [edge.from.node, edge.from.output, edge.to.node, edge.to.input]));
}

function nodeStatusSignature(statuses: NodeStatus[]): string {
  return JSON.stringify(statuses.map(status => [status.node_id, status.status]));
}

function previewsSignature(run: RunRecord | undefined): string {
  if (!run) return '';
  return JSON.stringify([run.run_id, Object.entries(run.previews ?? {}).sort(([a], [b]) => a.localeCompare(b))]);
}

function commentsSignature(comments: Comment[]): string {
  const visit = (items: Comment[]): unknown[] => items.map(comment => [
    comment.id,
    comment.node_id,
    comment.parent_id,
    comment.resolved,
    visit(comment.replies ?? []),
  ]);
  return JSON.stringify(visit(comments));
}

function createWorkflowId(): string {
  if (typeof crypto !== 'undefined' && crypto.randomUUID) {
    return crypto.randomUUID();
  }
  return `wf-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
}

function getRequestedWorkflowId(): string | null {
  const id = new URLSearchParams(window.location.search).get('workflow');
  if (!id || !/^[a-zA-Z0-9._:-]{1,160}$/.test(id)) return null;
  return id;
}

function withWorkflowId(workflow: Workflow, id = workflow.id || createWorkflowId()): Workflow {
  return { ...workflow, id };
}

function emptySharedWorkflow(id: string, name = 'Shared workflow'): Workflow {
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
    const r = await fetch(`/api/workflow_templates/${template.filename}`);
    const data = r.ok ? await r.json() as Workflow : getLocalTemplateWorkflow(template.filename);
    return data ? remapTemplateWorkflow(data) : null;
  } catch {
    const data = getLocalTemplateWorkflow(template.filename);
    return data ? remapTemplateWorkflow(data) : null;
  }
}

export default function App() {
  const { get, getBool, set, ready: settingsReady } = useSettings();
  const {
    workflows, activeIndex, activeWorkflow, validation, resolveReport, runs,
    setWorkflow, updateWorkflow, addTab, addWorkflow, closeTab, reorderWorkflows, setActiveIndex,
    validate, resolve, clearResolveReport, submitRun, addRun, updateRun, setRuns,
  } = useWorkflow();
  useTheme();
  const { palettes, setPalette } = usePaletteTheme();
  const { getBinding } = useKeybindings();
  const { objectInfo, loading: objectInfoLoading } = useObjectInfo();
  const registeredPanels = usePanelRegistry();

  // Authentication state
  const collabEnabled = getBool('bionodulo.collab.enabled');
  const initialRequestedWorkflowId = useMemo(() => getRequestedWorkflowId(), []);
  const [requestedWorkflowId, setRequestedWorkflowId] = useAtom(requestedWorkflowIdAtom);
  const [authUser, setAuthUser] = useAtom(authUserAtom);
  const [authReady, setAuthReady] = useAtom(authReadyAtom);
  const [showAuthDialog, setShowAuthDialog] = useAtom(showAuthDialogAtom);
  const effectiveRequestedWorkflowId = requestedWorkflowId || initialRequestedWorkflowId;

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

  // Initialize auth on mount
  useEffect(() => {
    let cancelled = false;
    if (!collabEnabled || !settingsReady) {
      setAuthReady(true);
      setShowAuthDialog(false);
      return;
    }
    setAuthReady(false);
    initAuth().then(valid => {
      if (cancelled) return;
      if (valid) {
        setAuthUser(getAuthUser());
        setShowAuthDialog(false);
      } else {
        setAuthUser(null);
        setShowAuthDialog(true);
      }
    }).finally(() => {
      if (!cancelled) setAuthReady(true);
    });
    return () => {
      cancelled = true;
    };
  }, [collabEnabled, settingsReady, setAuthReady, setAuthUser, setShowAuthDialog]);

  useEffect(() => {
    if (initialRequestedWorkflowId && requestedWorkflowId !== initialRequestedWorkflowId) {
      setRequestedWorkflowId(initialRequestedWorkflowId);
    }
  }, [initialRequestedWorkflowId, requestedWorkflowId, setRequestedWorkflowId]);

  // Handle login from AuthDialog
  const handleAuthLogin = useCallback((_name: string) => {
    setAuthUser(getAuthUser());
    setAuthReady(true);
    setShowAuthDialog(false);
  }, [setAuthReady, setAuthUser, setShowAuthDialog]);

  // Handle auth dialog close (without login)
  const handleAuthClose = useCallback(() => {
    // If user closes without logging in, keep current state
    // They can still use the app; collaboration just won't connect
    setShowAuthDialog(false);
  }, [setShowAuthDialog]);

  // Collaboration setup
  const currentUser = useMemo(() => (
    authUser
      ? { id: authUser.id, name: authUser.name, color: authUser.color }
      : { id: 'anonymous', name: 'You', color: getUserColor('anonymous') }
  ), [authUser?.color, authUser?.id, authUser?.name]);
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

  // Colab and copied room links pin each browser to the same Yjs room.
  useEffect(() => {
    if (!effectiveRequestedWorkflowId) return;
    if (activeWorkflow.id !== effectiveRequestedWorkflowId) {
      updateWorkflow(activeIndex, { id: effectiveRequestedWorkflowId });
    }
    if (!collabEnabled) {
      set('bionodulo.collab.enabled', true);
    }
  }, [activeWorkflow.id, activeIndex, collabEnabled, effectiveRequestedWorkflowId, set, updateWorkflow]);

  const requestedWorkflowPending = Boolean(effectiveRequestedWorkflowId && activeWorkflow.id !== effectiveRequestedWorkflowId);
  const collabWorkflowId = (
    collabEnabled
    && settingsReady
    && authReady
    && Boolean(authUser)
    && !requestedWorkflowPending
  ) ? activeWorkflowId : null;

  const {
    doc: collabDoc,
    localSessionId: collabSessionId,
    connected: collabConnected,
    connecting: collabConnecting,
    activeUsers: collabActiveUsers,
    setCursor: setCollabCursor,
    setSelection: setCollabSelection,
    setViewport: setCollabViewport,
    claimDrag: claimCollabDrag,
    releaseDrag: releaseCollabDrag,
    isShared: collabIsShared,
    error: collabError,
    reconnectAttempt: collabReconnectAttempt,
    offline: collabOffline,
  } = useCollab(collabWorkflowId, currentUser);

  const bridgeRef = useRef<LiteGraphYjsBridge | null>(null);
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
    const remoteHasWorkflow = yNodes.size > 0 || yEdges.size > 0 || yGroups.size > 0;
    if (remoteHasWorkflow) {
      const remoteWorkflow = docToWorkflow(collabDoc);
      updateWorkflowRef.current(activeIndex, {
        id: activeWorkflowId,
        name: remoteWorkflow.name || activeWorkflowRef.current.name,
        nodes: remoteWorkflow.nodes,
        edges: remoteWorkflow.edges,
        groups: remoteWorkflow.groups,
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
    const bridge = new LiteGraphYjsBridge(collabDoc, {
      onNodesChange: (nodes) => updateWorkflowRef.current(activeIndex, { nodes }),
      onEdgesChange: (edges) => updateWorkflowRef.current(activeIndex, { edges }),
      onGroupsChange: (groups) => updateWorkflowRef.current(activeIndex, { groups }),
      getNodes: () => activeWorkflowRef.current.nodes,
      getEdges: () => activeWorkflowRef.current.edges,
      getGroups: () => activeWorkflowRef.current.groups,
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

  const [showShareDialog, setShowShareDialog] = useState(false);
  // Phase 3 collaboration panels
  const [showComments, setShowComments] = useState(false);
  const [showVersions, setShowVersions] = useState(false);
  const [showAudit, setShowAudit] = useState(false);
  const [followingUserId, setFollowingUserId] = useState<string | null>(null);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [workflowComments, setWorkflowComments] = useState<Comment[]>([]);
  const [livePresenceUsers, setLivePresenceUsers] = useState<LivePresenceUser[]>([]);
  const [workflowNames, setWorkflowNames] = useState<Record<string, string>>({});

  const fetchWorkflowComments = useCallback(async () => {
    if (!collabEnabled || !activeWorkflowId) return;
    const token = getToken();
    if (!token) return;
    try {
      const response = await fetch(`/api/collab/workflows/${activeWorkflowId}/comments`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!response.ok) return;
      const data = await response.json() as { comments?: Comment[] };
      setWorkflowComments(data.comments ?? []);
    } catch {
      // Node comment pins are optional when collaboration is unavailable.
    }
  }, [activeWorkflowId, collabEnabled]);

  useEffect(() => {
    setWorkflowComments([]);
    void fetchWorkflowComments();
    if (!collabEnabled) return;
    const interval = setInterval(fetchWorkflowComments, 5000);
    return () => clearInterval(interval);
  }, [collabEnabled, fetchWorkflowComments]);

  const fetchLivePresence = useCallback(async () => {
    if (!collabEnabled) return;
    const token = getToken();
    if (!token) return;
    try {
      const response = await fetch('/api/collab/presence', {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!response.ok) return;
      const data = await response.json() as { users?: LivePresenceUser[] };
      setLivePresenceUsers(data.users ?? []);
    } catch {
      // Room-local awareness still drives collaborative cursor rendering.
    }
  }, [collabEnabled]);

  useEffect(() => {
    void fetchLivePresence();
    if (!collabEnabled) return;
    const interval = setInterval(fetchLivePresence, 3000);
    return () => clearInterval(interval);
  }, [collabEnabled, fetchLivePresence]);

  useEffect(() => {
    if (!followingUserId) return;
    const user = collabActiveUsers.find(candidate => (
      candidate.user.sessionId === followingUserId || candidate.user.id === followingUserId
    ));
    if (user?.viewport) {
      canvasRef.current?.setViewport(user.viewport);
    }
  }, [collabActiveUsers, followingUserId]);

  const publishCollabViewport = useCallback((viewOffset: { x: number; y: number }, viewScale: number) => {
    setCollabViewport({ ...viewOffset, scale: viewScale });
  }, [setCollabViewport]);

  const publishCollabNodeMove = useCallback((nodeId: string, position: [number, number]) => {
    bridgeRef.current?.onNodeMoved(nodeId, position);
  }, []);

  const handleCollabDragStart = useCallback((nodeId: string) => {
    bridgeRef.current?.onDragStart(nodeId);
    claimCollabDrag(nodeId);
  }, [claimCollabDrag]);

  const handleCollabDragEnd = useCallback(() => {
    bridgeRef.current?.onDragEnd();
    releaseCollabDrag();
  }, [releaseCollabDrag]);

  const publishCollabWorkflowSnapshot = useCallback(async (workflow: Workflow) => {
    if (!collabEnabled || !workflow.id) return;
    const token = getToken();
    if (!token) return;
    try {
      await fetch(`/api/collab/workflows/${encodeURIComponent(workflow.id)}/snapshot`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ workflow }),
      });
    } catch {
      // The socket bridge still handles normal collaboration when REST is unavailable.
    }
  }, [collabEnabled]);

  const fetchCollabSnapshot = useCallback(async (workflowId: string, fallbackName: string): Promise<Workflow | null> => {
    const token = getToken();
    if (!token) return null;
    const response = await fetch(`/api/collab/workflows/${encodeURIComponent(workflowId)}/snapshot`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!response.ok) return null;
    const data = await response.json() as { snapshot?: Record<string, unknown> };
    if (!data.snapshot) return null;
    return workflowFromCollabSnapshot(workflowId, data.snapshot, fallbackName);
  }, []);

  const followPresenceUser = useCallback(async (sessionId: string | null) => {
    if (!sessionId) {
      setFollowingUserId(null);
      return;
    }
    const presence = livePresenceUsers.find(user => user.session_id === sessionId)
      ?? livePresenceUsers.find(user => user.user_id === sessionId);
    if (presence?.workflow_id) {
      const workflowName = workflowNames[presence.workflow_id] || `Workflow ${presence.workflow_id.slice(0, 12)}`;
      let snapshotWorkflow: Workflow | null = null;
      try {
        snapshotWorkflow = await fetchCollabSnapshot(presence.workflow_id, workflowName);
      } catch {
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
  }, [activeIndex, activeWorkflowId, addWorkflow, collabActiveUsers, fetchCollabSnapshot, livePresenceUsers, setActiveIndex, setWorkflow, workflows, workflowNames]);

  // Host prerequisite status
  const [hostStatus, setHostStatus] = useState<HostStatus | null>(null);
  const [dismissedHostStatus, setDismissedHostStatus] = useState<HostStatus | null>(null);

  useEffect(() => {
    fetch('/api/host_status')
      .then(r => r.ok ? r.json() : null)
      .then(data => {
        if (data) setHostStatus(data as HostStatus);
      })
      .catch(() => { /* offline */ });
  }, []);

  const [logs, setLogs] = useState<LogEntry[]>([]);
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
  }, []);

  // Per-node run progress for inline canvas captions. Populated on node_start
  // events ({ current, total } parsed from the payload's "i/N" progress hint)
  // and cleared once the node finishes/errors so the caption only sits on
  // actively-running nodes.
  const [nodeRunProgress, setNodeRunProgress] = useState<Map<string, { current: number; total: number; startedAt: number }>>(() => new Map());
  const recordNodeStart = useCallback((nodeId: string, progress: string | undefined) => {
    const [currentStr, totalStr] = String(progress || '').split('/');
    const current = Number.parseInt(currentStr, 10);
    const total = Number.parseInt(totalStr, 10);
    setNodeRunProgress(prev => {
      const next = new Map(prev);
      next.set(nodeId, {
        current: Number.isFinite(current) ? current : 0,
        total: Number.isFinite(total) ? total : 0,
        startedAt: Date.now(),
      });
      return next;
    });
  }, []);
  const clearNodeRunProgress = useCallback((nodeId: string) => {
    setNodeRunProgress(prev => {
      if (!prev.has(nodeId)) return prev;
      const next = new Map(prev);
      next.delete(nodeId);
      return next;
    });
  }, []);

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

  // Load queue and execution history from backend on startup
  useEffect(() => {
    // Backend payload shape: snake-case fields (started_at, finished_at) and
    // mixed status strings — accept as Record<string, unknown> and narrow at
    // each call-site.
    type BackendRun = Record<string, unknown> & { run_id: string };
    Promise.all([
      apiGet<{ pending?: BackendRun[]; running?: BackendRun[] }>('/queue').catch(() => null),
      apiGet<{ history: BackendRun[] }>('/history').catch(() => null),
    ]).then(([queueData, historyData]) => {
      const allRuns: RunRecord[] = [];
      const seen = new Set<string>();

      // Queue items first (active runs)
      if (queueData) {
        const items = [...(queueData.pending || []), ...(queueData.running || [])];
        for (const h of items) {
          const run: RunRecord = {
            run_id: String(h.run_id),
            status: String(h.status) as RunRecord['status'],
            workflow_name: String(h.workflow_name || 'Untitled'),
            node_statuses: Array.isArray(h.node_statuses) ? h.node_statuses as NodeStatus[] : [],
            node_outputs: {},
            execution_plan: [],
            previews: (h.previews as Record<string, string>) || {},
            artifacts: (h.artifacts as Record<string, string>) || {},
            start_time: h.started_at ? new Date(Number(h.started_at) * 1000).toISOString() : undefined,
            end_time: h.finished_at ? new Date(Number(h.finished_at) * 1000).toISOString() : undefined,
          };
          allRuns.push(run);
          seen.add(run.run_id);
        }
      }

      // History items (completed runs)
      if (historyData && Array.isArray(historyData.history)) {
        for (const h of historyData.history) {
          const runId = String(h.run_id);
          if (seen.has(runId)) continue;
          allRuns.push({
            run_id: runId,
            status: String(h.status) as RunRecord['status'],
            workflow_name: String(h.workflow_name || 'Untitled'),
            node_statuses: Array.isArray(h.node_statuses) ? h.node_statuses as NodeStatus[] : [],
            node_outputs: {},
            execution_plan: [],
            previews: (h.previews as Record<string, string>) || {},
            artifacts: (h.artifacts as Record<string, string>) || {},
            start_time: h.started_at ? new Date(Number(h.started_at) * 1000).toISOString() : undefined,
            end_time: h.finished_at ? new Date(Number(h.finished_at) * 1000).toISOString() : undefined,
          });
          seen.add(runId);
        }
      }

      setRuns(allRuns);

      // Fetch logs for the most recent runs (queue + recent history)
      const runsToFetch = allRuns.slice(0, 10);
      for (const run of runsToFetch) {
        fetch(`/api/runs/${run.run_id}/logs`)
          .then(r => r.ok ? r.json() : null)
          .then((logData: { logs?: Array<Record<string, unknown>>; run_id?: string } | null) => {
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
  }, [setRuns, addLog, setLogs]);

  // History stack for undo/redo
  const canvasRef = useRef<LiteGraphCanvasRef>(null);
  const historyRef = useRef<{ nodes: WorkflowNode[]; edges: Workflow['edges']; groups: Workflow['groups']; viewport?: { x: number; y: number; scale: number } }[]>([]);
  const historyIndexRef = useRef(-1);
  const pendingStateRef = useRef<Partial<Workflow>>({});

  useEffect(() => {
    historyRef.current = [];
    historyIndexRef.current = -1;
  }, [activeIndex]);

  // Structural fingerprint used to deduplicate identical successive snapshots
  // (e.g. when a drag commit reports the same coordinates twice). Deliberately
  // ignores viewport so pan/zoom alone doesn't burn a slot.
  const snapshotSignature = useCallback((snapshot: { nodes: WorkflowNode[]; edges: Workflow['edges']; groups: Workflow['groups']; viewport?: { x: number; y: number; scale: number } }) => {
    return JSON.stringify([
      snapshot.nodes.map(n => [n.id, n.type, n.position, n.params, n.ui]),
      snapshot.edges.map(e => [e.from.node, e.from.output, e.to.node, e.to.input]),
      snapshot.groups.map(g => [g.id, g.name, g.position, g.width, g.height, g.color, g.collapsed]),
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
  }, [activeWorkflow.nodes, activeWorkflow.edges, activeWorkflow.groups, pushHistory]);

  // Mirror ComfyUI's eager capture triggers: a mouseup or keyup signals that
  // a user gesture (drag, widget edit, key shortcut) just ended, so commit
  // any pending state instead of waiting for the 350 ms debounce.
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
    });
    if (state.viewport) canvasRef.current?.setViewport(state.viewport);
  }, [activeIndex, updateWorkflow]);

  const [consoleVisible, setConsoleVisible] = useState(false);
  const [railTab, setRailTabState] = useState<RailTab>(null);
  const [openPanelTabs, setOpenPanelTabs] = useState<OpenPanelTab[]>([]);
  const [panelWidths, setPanelWidths] = useState<Record<string, number>>(() => loadPanelWidths());
  const [floatingPanels, setFloatingPanels] = useState<FloatingPanelLayout>(() => loadFloatingPanels());
  const [rightDockedPanels, setRightDockedPanels] = useState<Record<string, true>>(() => loadRightDockedPanels());

  const toggleRightDocked = useCallback((tab: OpenPanelTab) => {
    setRightDockedPanels(prev => {
      const next = { ...prev };
      if (next[tab]) delete next[tab];
      else next[tab] = true;
      try {
        localStorage.setItem(PANEL_RIGHT_DOCKED_KEY, JSON.stringify(next));
      } catch {
        // localStorage failures are non-fatal for a UI preference.
      }
      return next;
    });
  }, []);
  const [showExport, setShowExport] = useState(false);
  const [showImport, setShowImport] = useState(false);
  const [showOutputDiff, setShowOutputDiff] = useState(false);
  const [showBulkParam, setShowBulkParam] = useState(false);
  const [showDoctor, setShowDoctor] = useState(false);

  const [showAI, setShowAI] = useState(false);
  const [showBatchSheet, setShowBatchSheet] = useState(false);
  const [showGettingStarted, setShowGettingStarted] = useState(false);
  const [showShortcuts, setShowShortcuts] = useState(false);

  // Image lightbox state
  const [lightboxOpen, setLightboxOpen] = useState(false);
  const [lightboxImages, setLightboxImages] = useState<{ src: string; alt: string; filename: string }[]>([]);
  const [lightboxIndex, setLightboxIndex] = useState(0);

  const openLightbox = useCallback((images: { src: string; alt: string; filename: string }[], index: number) => {
    setLightboxImages(images);
    setLightboxIndex(index);
    setLightboxOpen(true);
  }, []);

  // HTML preview modal state (full-screen sandboxed iframe viewer used by the
  // gallery and the workflow-doctor "open report" jump action).
  const [htmlPreviewState, setHtmlPreviewState] = useState<{ src: string; filename: string } | null>(null);
  const openHtmlPreview = useCallback((item: { src: string; filename: string }) => {
    setHtmlPreviewState({ src: item.src, filename: item.filename });
  }, []);
  const [isRunning, setIsRunning] = useState(false);
  const [batchCount, setBatchCount] = useState(1);
  // Subgraph navigation: a breadcrumb of (parent workflow, subgraph node id)
  // pairs. While the stack is non-empty the canvas renders the inner workflow
  // of the topmost subgraph node; exiting writes the edits back to the parent.
  type SubgraphFrame = { workflowId: string; parentWorkflow: Workflow; subgraphNodeId: string; subgraphName: string };
  const [subgraphPath, setSubgraphPath] = useState<SubgraphFrame[]>([]);
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
  const [focusMode, setFocusMode] = useState<boolean>(() => {
    try { return localStorage.getItem('bionodulo.focusMode') === '1'; } catch { return false; }
  });
  const toggleFocusMode = useCallback(() => {
    setFocusMode(prev => {
      const next = !prev;
      try { localStorage.setItem('bionodulo.focusMode', next ? '1' : '0'); } catch { /* ignore */ }
      return next;
    });
  }, []);
  type QueueMode = 'manual' | 'change' | 'instant';
  const [queueMode, setQueueModeState] = useState<QueueMode>(() => {
    try {
      const stored = localStorage.getItem('bionodulo.queueMode');
      if (stored === 'change' || stored === 'instant' || stored === 'manual') return stored;
    } catch { /* ignore */ }
    return 'manual';
  });
  const setQueueMode = useCallback((mode: QueueMode) => {
    setQueueModeState(mode);
    try { localStorage.setItem('bionodulo.queueMode', mode); } catch { /* ignore */ }
  }, []);
  const queueModeRef = useRef<QueueMode>(queueMode);
  useEffect(() => { queueModeRef.current = queueMode; }, [queueMode]);
  const [dismissedReport, setDismissedReport] = useState<ResolveReport | null>(null);
  const [dirty, setDirty] = useState(false);
  const [, setLastAutoSaveAt] = useState<string | null>(() => {
    try { return localStorage.getItem(AUTO_SAVE_LAST_KEY); } catch { return null; }
  });

  const setPanelWidth = useCallback((tab: OpenPanelTab, width: number) => {
    setPanelWidths(prev => {
      const next = { ...prev, [tab]: clampPanelWidth(width) };
      try { localStorage.setItem(PANEL_WIDTHS_KEY, JSON.stringify(next)); } catch { /* ignore */ }
      return next;
    });
  }, []);

  const startPanelResize = useCallback((tab: OpenPanelTab, startClientX: number, startWidth: number) => {
    const onMove = (event: MouseEvent) => {
      setPanelWidth(tab, startWidth + event.clientX - startClientX);
    };
    const onUp = () => {
      window.removeEventListener('mousemove', onMove);
      window.removeEventListener('mouseup', onUp);
    };
    window.addEventListener('mousemove', onMove);
    window.addEventListener('mouseup', onUp);
  }, [setPanelWidth]);

  const setFloatingPanel = useCallback((tab: OpenPanelTab, layout: { x: number; y: number } | null) => {
    setFloatingPanels(prev => {
      const next = { ...prev };
      if (layout) {
        next[tab] = {
          x: Math.max(12, Math.min(window.innerWidth - 320, Math.round(layout.x))),
          y: Math.max(8, Math.min(window.innerHeight - 180, Math.round(layout.y))),
        };
      } else {
        delete next[tab];
      }
      try { localStorage.setItem(PANEL_FLOATS_KEY, JSON.stringify(next)); } catch { /* ignore */ }
      return next;
    });
  }, []);

  const toggleFloatingPanel = useCallback((tab: OpenPanelTab, index: number) => {
    if (floatingPanels[tab]) {
      setFloatingPanel(tab, null);
      return;
    }
    setFloatingPanel(tab, { x: 80 + index * 28, y: 72 + index * 24 });
  }, [floatingPanels, setFloatingPanel]);

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
        setFloatingPanels(prev => {
          if (!(tab in prev)) return prev;
          const next = { ...prev };
          delete next[tab];
          try { localStorage.setItem(PANEL_FLOATS_KEY, JSON.stringify(next)); } catch { /* ignore */ }
          return next;
        });
        setRightDockedPanels(prev => {
          const next = { ...prev };
          if (zone === 'right') next[tab] = true;
          else delete next[tab];
          try { localStorage.setItem(PANEL_RIGHT_DOCKED_KEY, JSON.stringify(next)); } catch { /* ignore */ }
          return next;
        });
      }
    };
    window.addEventListener('mousemove', onMove);
    window.addEventListener('mouseup', onUp);
  }, [setFloatingPanel]);

  const setRailTab = useCallback((next: RailTab | ((prev: RailTab) => RailTab)) => {
    setRailTabState(prev => {
      const resolved = typeof next === 'function' ? next(prev) : next;
      if (resolved && resolved !== 'console') {
        setOpenPanelTabs(current => (
          current.includes(resolved) ? current : [...current, resolved]
        ));
      } else if (resolved === null && prev && prev !== 'console') {
        setOpenPanelTabs(current => current.filter(tab => tab !== prev));
      } else if (resolved === 'console') {
        setConsoleVisible(true);
      }
      return resolved;
    });
  }, []);

  // WebSocket connection for real-time logs
  const wsUrl = useMemo(() => {
    const token = getToken();
    const proto = window.location.protocol === 'https:' ? 'wss' : 'ws';
    const params = token ? `?token=${encodeURIComponent(token)}` : '';
    return `${proto}://${window.location.host}/ws${params}`;
  }, [authUser?.id]);
  const { onMessage } = useWebSocket(wsUrl);

  useEffect(() => {
    const unsub = onMessage((msg: unknown) => {
      const data = msg as Record<string, unknown>;
      const payload = (typeof data.data === 'object' && data.data !== null) ? data.data as Record<string, unknown> : {};
      const ts = String(payload.timestamp || new Date().toISOString());

      // --- Install events (pixi + dependency installer) ---
      if (data.type === 'install.log') {
        addLog({
          run_id: 'install-pixi',
          node_id: 'host',
          level: (payload.level as LogEntry['level']) || 'info',
          message: String(payload.message || ''),
          timestamp: ts,
        });
        return;
      }
      if (data.type === 'install.progress') {
        addLog({
          run_id: String(payload.job_id || 'dependency-install'),
          node_id: 'host',
          level: (payload.level as LogEntry['level']) || 'info',
          message: String(payload.message || ''),
          timestamp: ts,
        });
        return;
      }

      // --- Workflow execution logs ---
      if (data.type === 'log' && payload.message) {
        addLog({
          run_id: String(payload.run_id || data.source || 'workflow'),
          node_id: String(payload.node_id || 'engine'),
          level: (payload.level as LogEntry['level']) || 'info',
          message: String(payload.message),
          timestamp: ts,
        });
        return;
      }

      // --- Execution lifecycle events ---
      const runId = String(payload.run_id || data.source || 'workflow');
      if (data.type === 'start') {
        addLog({ run_id: runId, node_id: 'engine', level: 'info', message: `Workflow started (${payload.total_nodes} nodes)`, timestamp: ts });
      } else if (data.type === 'node_start') {
        updateNodeRunStatus(runId, String(payload.node_id), 'running');
        recordNodeStart(String(payload.node_id), payload.progress as string | undefined);
        addLog({ run_id: runId, node_id: String(payload.node_id), level: 'info', message: `Node start [${payload.progress}] ${payload.node_type}`, timestamp: ts });
      } else if (data.type === 'node_complete') {
        updateNodeRunStatus(runId, String(payload.node_id), 'completed');
        clearNodeRunProgress(String(payload.node_id));
        addLog({ run_id: runId, node_id: String(payload.node_id), level: 'success', message: `Node completed`, timestamp: ts });
      } else if (data.type === 'node_error') {
        updateNodeRunStatus(runId, String(payload.node_id), 'error', String(payload.error || 'Node error'));
        clearNodeRunProgress(String(payload.node_id));
        addLog({ run_id: runId, node_id: String(payload.node_id), level: 'error', message: `Node error: ${payload.error}`, timestamp: ts });
      } else if (data.type === 'node_skip') {
        updateNodeRunStatus(runId, String(payload.node_id), 'skipped');
        clearNodeRunProgress(String(payload.node_id));
        addLog({ run_id: runId, node_id: String(payload.node_id), level: 'warn', message: `Node skipped (${payload.reason})`, timestamp: ts });
      } else if (data.type === 'node_bypass') {
        updateNodeRunStatus(runId, String(payload.node_id), 'skipped');
        clearNodeRunProgress(String(payload.node_id));
        addLog({ run_id: runId, node_id: String(payload.node_id), level: 'warn', message: `Node bypassed`, timestamp: ts });
      } else if (data.type === 'node_cache_hit') {
        updateNodeRunStatus(runId, String(payload.node_id), 'cached');
        clearNodeRunProgress(String(payload.node_id));
        addLog({ run_id: runId, node_id: String(payload.node_id), level: 'info', message: `Cache hit — skipping execution`, timestamp: ts });
      } else if (data.type === 'complete') {
        addLog({ run_id: runId, node_id: 'engine', level: payload.status === 'completed' ? 'success' : 'error', message: `Workflow ${payload.status}`, timestamp: ts });
      } else if (data.type === 'error') {
        addLog({ run_id: runId, node_id: 'engine', level: 'error', message: `Workflow error: ${payload.message}`, timestamp: ts });
      } else if (data.type === 'cancelled') {
        addLog({ run_id: runId, node_id: String(payload.node_id || 'engine'), level: 'warn', message: `Workflow cancelled`, timestamp: ts });
      }

      // --- Preview events ---
      else if (data.type === 'preview') {
        const previewRunId = String(payload.run_id || data.source || '');
        const nodeId = String(payload.node_id || '');
        const path = String(payload.path || '');
        if (previewRunId && nodeId && path) {
          updateRun(previewRunId, {
            previews: {
              ...(runs.find(r => r.run_id === previewRunId)?.previews || {}),
              [nodeId]: path,
            },
          });
        }
      }

      // --- Queue events ---
      else if (data.type === 'queue_submit') {
        addLog({ run_id: String(payload.run_id), node_id: 'queue', level: 'info', message: `Run submitted`, timestamp: ts });
      } else if (data.type === 'queue_start') {
        addLog({ run_id: String(payload.run_id), node_id: 'queue', level: 'info', message: `Run started`, timestamp: ts });
        updateRun(String(payload.run_id), { status: 'running', start_time: ts });
      } else if (data.type === 'queue_finish') {
        addLog({ run_id: String(payload.run_id), node_id: 'queue', level: 'success', message: `Run finished (${payload.status})`, timestamp: ts });
        const finalStatus = payload.status === 'completed' ? 'completed' : payload.status === 'failed' ? 'error' : 'cancelled';
        const finishedRunId = String(payload.run_id);
        updateRun(finishedRunId, { status: finalStatus, end_time: ts });
        // A failed run drops out of the active queue automatically (the queue
        // view filters on pending/running) but stays in history. Surface a
        // toast so the user notices the failure without scanning the console.
        if (finalStatus === 'error') {
          const failedRun = runs.find(r => r.run_id === finishedRunId);
          const wfName = failedRun?.workflow_name || 'Workflow';
          toast.error('Run failed', {
            message: `${wfName} — see the console for details.`,
          });
        }
        // Fetch full run details to populate previews/artifacts
        fetch(`/api/runs/${finishedRunId}`)
          .then(r => r.ok ? r.json() : null)
          .then((runData: Record<string, unknown> | null) => {
            if (!runData) return;
            const result = runData.result as Record<string, unknown> | undefined;
            if (!result) return;
            const previews: Record<string, string> = {};
            const previewList = result.previews as Array<{ node_id?: string; path?: string }> | undefined;
            if (previewList) {
              for (const p of previewList) {
                if (p.node_id && p.path) previews[p.node_id] = p.path;
              }
            }
            const artifacts: Record<string, string> = {};
            const artifactList = result.artifacts as Array<{ node_id?: string; path?: string }> | undefined;
            if (artifactList) {
              for (const a of artifactList) {
                if (a.node_id && a.path) artifacts[a.node_id] = a.path;
              }
            }
            updateRun(finishedRunId, { previews, artifacts });
          })
          .catch(() => { /* ignore */ });
      } else if (data.type === 'queue_error') {
        addLog({ run_id: String(payload.run_id), node_id: 'queue', level: 'error', message: `Run error: ${payload.error}`, timestamp: ts });
        updateRun(String(payload.run_id), { status: 'error', end_time: ts });
        // queue_error fires for errors that don't go through queue_finish
        // (early validation failures, executor crashes). Always toast.
        const erroredRunId = String(payload.run_id);
        const erroredRun = runs.find(r => r.run_id === erroredRunId);
        const wfName = erroredRun?.workflow_name || 'Workflow';
        const errMsg = typeof payload.error === 'string' && payload.error
          ? payload.error.split('\n')[0].slice(0, 160)
          : 'see the console for details';
        toast.error('Run failed', { message: `${wfName} — ${errMsg}` });
      } else if (data.type === 'queue_interrupt') {
        addLog({ run_id: String(payload.run_id), node_id: 'queue', level: 'warn', message: `Run interrupted`, timestamp: ts });
        updateRun(String(payload.run_id), { status: 'cancelled', end_time: ts });
      }
    });
    return unsub;
  }, [onMessage, addLog, runs, updateRun, updateNodeRunStatus]);
  const [hpcStatus, setHpcStatus] = useState<HPCStatus>('off');

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
  const collabPresenceEnabled = getBool('bionodulo.collab.presence');
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

  // Fetch HPC status from backend
  useEffect(() => {
    const checkHpcStatus = async () => {
      try {
        const r = await fetch('/api/hpc/status');
        if (r.ok) {
          const data = await r.json() as { status?: HPCStatus; connected?: boolean };
          setHpcStatus(data.status || (data.connected ? 'on' : 'off'));
        } else {
          setHpcStatus('off');
        }
      } catch {
        setHpcStatus('off');
      }
    };
    checkHpcStatus();
    // Poll every 30 seconds
    const interval = setInterval(checkHpcStatus, 30000);
    return () => clearInterval(interval);
  }, [hpcEnabled, hpcConfig.backend, hpcConfig.partition]);

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

  const handleGroupsChange = useCallback((groups: Workflow['groups']) => {
    if (bridgeRef.current) {
      bridgeRef.current.onGroupsChanged(groups);
    }
    pendingStateRef.current = { ...pendingStateRef.current, groups };
    setDirty(true);
    updateActive({ groups });
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
        toast.warning('No input_file node registered; cannot wire pasted file');
        return;
      }
      for (let i = 0; i < files.length; i += 1) {
        const file = files[i];
        const form = new FormData();
        form.append('file', file, file.name || `pasted_${Date.now()}`);
        form.append('subdir', 'uploads');
        try {
          const response = await fetch('/api/workspace/upload', { method: 'POST', body: form });
          if (!response.ok) throw new Error(`HTTP ${response.status}`);
          const data = await response.json() as { path?: string; original_name?: string; content_type?: string };
          if (!data.path) throw new Error('Upload response missing path');
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
          toast.success('Pasted file added', {
            message: `${data.original_name || file.name} (${data.content_type || 'file'})`,
          });
        } catch (err) {
          toast.error('Could not upload pasted file', { message: err instanceof Error ? err.message : String(err) });
        }
      }
    };
    window.addEventListener('paste', handler);
    return () => window.removeEventListener('paste', handler);
  }, [handleNodesChange, objectInfo, pushHistory]);

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
        const tokens = firstError.match(/[A-Za-z0-9_\-]+/g) || [];
        const targetId = tokens.find(token => nodeIds.has(token));
        toast.error(`Validation failed (${v.errors.length})`, {
          message: firstError,
          actions: targetId
            ? [{ label: 'Jump to node', onClick: () => canvasRef.current?.focusNode(targetId), dismiss: true }]
            : undefined,
        });
        setIsRunning(false);
        return;
      }
      const count = Math.max(1, Math.min(99, batchCount));
      for (let index = 0; index < count; index += 1) {
        const batchName = count > 1
          ? `${activeWorkflow.name || 'Untitled'} (${index + 1}/${count})`
          : activeWorkflow.name || 'Untitled';
        const result = await submitRun(activeWorkflow, { no_cache: !cacheEnabled, name: batchName });
        addRun({
          run_id: result.run_id,
          status: 'pending',
          workflow_name: result.workflow_name || batchName,
          node_statuses: [],
          node_outputs: {},
          execution_plan: [],
          previews: {},
          artifacts: {},
          start_time: new Date().toISOString(),
        });
      }
      toast.success(count > 1 ? `${count} runs queued` : 'Run queued');
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      addLog({
        run_id: 'workflow',
        node_id: 'engine',
        level: 'error',
        message: `Run failed: ${msg}`,
        timestamp: new Date().toISOString(),
      });
      // Auto-open console so the user sees the error
      setConsoleVisible(true);
      setRailTab('console');
    }
    setIsRunning(false);
  }, [activeWorkflow, validate, submitRun, cacheEnabled, addLog, addRun, batchCount, setRailTab]);

  const handleBatchSheetSubmit = useCallback(async (runs: SampleSheetRun[]) => {
    if (runs.length === 0) return;
    setIsRunning(true);
    try {
      await validate(activeWorkflow);
      for (const sampleRun of runs) {
        const result = await submitRun(sampleRun.workflow, {
          no_cache: !cacheEnabled,
          name: sampleRun.name,
        });
        addRun({
          run_id: result.run_id,
          status: 'pending',
          workflow_name: result.workflow_name || sampleRun.name,
          node_statuses: [],
          node_outputs: {},
          execution_plan: [],
          previews: {},
          artifacts: {},
          start_time: new Date().toISOString(),
        });
      }
      toast.success(`${runs.length} runs queued from sample sheet`);
      setConsoleVisible(true);
      setRailTab('console');
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      toast.error('Sample sheet batch failed', { message: msg });
      addLog({
        run_id: 'workflow',
        node_id: 'engine',
        level: 'error',
        message: `Sample sheet batch failed: ${msg}`,
        timestamp: new Date().toISOString(),
      });
    } finally {
      setIsRunning(false);
    }
  }, [activeWorkflow, addLog, addRun, cacheEnabled, setRailTab, submitRun, validate]);

  const handleRunSelected = useCallback(async (nodeIds: string[]) => {
    if (nodeIds.length === 0) return;
    setIsRunning(true);
    try {
      await validate(activeWorkflow);
      const result = await submitRun(activeWorkflow, {
        no_cache: !cacheEnabled,
        target_nodes: nodeIds,
        name: `${activeWorkflow.name || 'Untitled'} (selection)`,
      });
      addRun({
        run_id: result.run_id,
        status: 'pending',
        workflow_name: result.workflow_name || `${activeWorkflow.name || 'Untitled'} (selection)`,
        node_statuses: [],
        node_outputs: {},
        execution_plan: nodeIds,
        previews: {},
        artifacts: {},
        start_time: new Date().toISOString(),
      });
      setConsoleVisible(true);
      setRailTab('console');
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      addLog({
        run_id: 'workflow',
        node_id: 'engine',
        level: 'error',
        message: `Selected run failed: ${msg}`,
        timestamp: new Date().toISOString(),
      });
      setConsoleVisible(true);
      setRailTab('console');
    }
    setIsRunning(false);
  }, [activeWorkflow, addLog, addRun, cacheEnabled, submitRun, validate, setRailTab]);

  const handleSaveSnippet = useCallback(async () => {
    const selectedIds = canvasRef.current?.getSelectedNodeIds() ?? [];
    if (selectedIds.length === 0) {
      toast.info('Select at least one node to save as a snippet');
      return;
    }
    const idSet = new Set(selectedIds);
    const snippetNodes = activeWorkflow.nodes.filter(n => idSet.has(n.id));
    const snippetEdges = activeWorkflow.edges.filter(e => idSet.has(e.from.node) && idSet.has(e.to.node));
    const defaultName = snippetNodes.length === 1
      ? `${snippetNodes[0].ui?.title || snippetNodes[0].type} snippet`
      : `${snippetNodes.length}-node snippet`;
    const name = await promptDialog({
      title: 'Save selection as snippet',
      message: 'The selected nodes and the edges between them will be saved locally for reuse.',
      inputLabel: 'Snippet name',
      defaultValue: defaultName,
    });
    if (!name) return;
    const { saveWorkflowSnippet } = await import('./state/workflowSnippets');
    saveWorkflowSnippet({ name, nodes: snippetNodes, edges: snippetEdges });
    toast.success('Snippet saved', { message: `${snippetNodes.length} nodes` });
  }, [activeWorkflow]);

  const handleInsertSnippet = useCallback(async () => {
    const { listWorkflowSnippets, instantiateSnippet } = await import('./state/workflowSnippets');
    const snippets = listWorkflowSnippets();
    if (snippets.length === 0) {
      toast.info('No snippets yet — select nodes and run "Save selection as snippet"');
      return;
    }
    // Quick "pick one" via prompt — full chooser modal is a future polish item.
    const labels = snippets.map((s, i) => `${i + 1}. ${s.name} (${s.nodes.length}n)`).join('\n');
    const choice = await promptDialog({
      title: 'Insert snippet',
      message: `Pick a snippet by number:\n${labels}`,
      inputLabel: 'Number',
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
    toast.success('Snippet inserted', { message: `${snippet.name}` });
  }, [activeWorkflow, activeIndex, updateWorkflow]);

  const handleCreateSubgraph = useCallback(async (nodeIds: string[]) => {
    if (nodeIds.length === 0) return;
    // Compute a position for the new subgraph node — centred on the average
    // position of the selection, so it lands where the nodes used to live.
    const selectedNodes = activeWorkflow.nodes.filter(n => nodeIds.includes(n.id));
    const avgX = selectedNodes.reduce((sum, n) => sum + n.position[0], 0) / Math.max(1, selectedNodes.length);
    const avgY = selectedNodes.reduce((sum, n) => sum + n.position[1], 0) / Math.max(1, selectedNodes.length);
    const subgraphName = `${activeWorkflow.name || 'Untitled'} block`;
    const result = extractSubgraph(activeWorkflow, nodeIds, subgraphName, [Math.round(avgX), Math.round(avgY)]);
    const nextParent: Workflow = {
      ...activeWorkflow,
      nodes: result.nodes,
      edges: result.edges,
      groups: result.outerGroups,
    };
    updateWorkflow(activeIndex, nextParent);
    setRailTab(null);
    toast.success('Selection converted to subgraph', { message: subgraphName });
    requestAnimationFrame(() => {
      requestAnimationFrame(() => canvasRef.current?.fitView());
    });
  }, [activeIndex, activeWorkflow, setRailTab, updateWorkflow]);

  const handlePromoteWidgets = useCallback((innerNodeId: string) => {
    if (subgraphPath.length === 0) {
      toast.info('Enter a subgraph first to promote its widgets');
      return;
    }
    const innerNode = activeWorkflow.nodes.find(n => n.id === innerNodeId);
    if (!innerNode) return;
    const required = (innerNode.node_info?.input_types?.required || {}) as Record<string, unknown>;
    const optional = (innerNode.node_info?.input_types?.optional || {}) as Record<string, unknown>;
    const allSpecs = { ...required, ...optional };
    const isInteractive = (spec: unknown): boolean => {
      if (Array.isArray(spec)) {
        const t = spec[0];
        const config = (spec[1] && typeof spec[1] === 'object') ? spec[1] as Record<string, unknown> : {};
        if (t === 'BOOLEAN') return true;
        if (Array.isArray(t)) return true;
        if (Array.isArray(config.options) && config.options.length) return true;
        if (t === 'INT' || t === 'FLOAT') return true;
        if (t === 'STRING' && !config.forceInput) return true;
        return false;
      }
      if (spec && typeof spec === 'object') {
        const s = spec as { type?: string; options?: unknown[]; forceInput?: boolean };
        if (s.type === 'BOOLEAN') return true;
        if (Array.isArray(s.options) && s.options.length) return true;
        if (s.type === 'INT' || s.type === 'FLOAT') return true;
        if (s.type === 'STRING' && !s.forceInput) return true;
      }
      return false;
    };

    setSubgraphPath(prev => {
      if (prev.length === 0) return prev;
      const top = prev[prev.length - 1];
      // Write current inner edits back into the parent's subgraph node first,
      // so promotions land on the same snapshot the user is editing.
      let parent = writeSubgraphBack(top.parentWorkflow, top.subgraphNodeId, activeWorkflow);
      let added = 0;
      for (const [key, spec] of Object.entries(allSpecs)) {
        if (!isInteractive(spec)) continue;
        parent = promoteWidget(parent, top.subgraphNodeId, innerNodeId, key, spec);
        added += 1;
      }
      if (added === 0) {
        toast.info(`${innerNode.ui?.title || innerNode.type} has no promotable widgets`);
        return prev;
      }
      toast.success(`Promoted ${added} widget${added === 1 ? '' : 's'} to ${top.subgraphName}`);
      const updatedFrames = prev.slice(0, -1).concat({ ...top, parentWorkflow: parent });
      return updatedFrames;
    });
  }, [activeWorkflow, subgraphPath]);

  const handleEnterSubgraph = useCallback((nodeId: string) => {    const node = activeWorkflow.nodes.find(n => n.id === nodeId);
    if (!node || node.type !== 'subgraph') return;
    const innerWorkflow = (node.params?.workflow as Workflow | undefined);
    if (!innerWorkflow) {
      toast.warning('Subgraph has no embedded workflow');
      return;
    }
    // Push the parent snapshot onto the breadcrumb and swap the current tab's
    // contents with the inner workflow. The tab id stays the same so the
    // collab room / autosave keep tracking the parent workflow correctly.
    setSubgraphPath(prev => [
      ...prev,
      {
        workflowId: activeWorkflow.id || activeWorkflowId,
        parentWorkflow: activeWorkflow,
        subgraphNodeId: nodeId,
        subgraphName: String(node.ui?.title || node.node_info?.display_name || 'Subgraph'),
      },
    ]);
    const inner: Workflow = {
      ...innerWorkflow,
      id: activeWorkflow.id || activeWorkflowId,
      name: String(node.ui?.title || innerWorkflow.name || 'Subgraph'),
    };
    setWorkflow(activeIndex, () => inner);
    requestAnimationFrame(() => {
      requestAnimationFrame(() => canvasRef.current?.fitView());
    });
  }, [activeIndex, activeWorkflow, activeWorkflowId, setWorkflow]);

  const handleExitSubgraph = useCallback((depth: number) => {
    if (subgraphPath.length === 0) return;
    setSubgraphPath(prev => {
      let parent = prev[prev.length - 1]?.parentWorkflow;
      let popped = prev.slice();
      // Walk frames from the top down, writing the current inner workflow back
      // into each parent's subgraph node as we unwind to the target depth.
      let inner = activeWorkflow;
      while (popped.length > depth) {
        const frame = popped[popped.length - 1];
        const updatedParent = writeSubgraphBack(frame.parentWorkflow, frame.subgraphNodeId, inner);
        inner = updatedParent;
        parent = updatedParent;
        popped = popped.slice(0, -1);
      }
      if (parent) {
        setWorkflow(activeIndex, () => parent!);
      }
      return popped;
    });
    requestAnimationFrame(() => {
      requestAnimationFrame(() => canvasRef.current?.fitView());
    });
  }, [activeIndex, activeWorkflow, setWorkflow, subgraphPath]);

  // Reset the subgraph navigation whenever the user switches to a different
  // workflow tab — the breadcrumb is per-tab and would otherwise dangle.
  // We also restore the saved viewport for the incoming tab here.
  const prevActiveIndexRef = useRef(activeIndex);
  useEffect(() => {
    setSubgraphPath([]);
    // Save the outgoing tab's viewport.
    const prev = prevActiveIndexRef.current;
    if (prev !== activeIndex) {
      const prevWorkflow = workflows[prev];
      const prevId = prevWorkflow?.id;
      if (prevId) {
        const vp = canvasRef.current?.getViewport?.();
        if (vp) {
          viewportByWorkflowRef.current[prevId] = vp;
          persistViewportStore();
        }
      }
    }
    prevActiveIndexRef.current = activeIndex;
    // Restore the incoming tab's viewport, if any. Wait two RAFs so the
    // canvas has finished laying out the new workflow's nodes before we set
    // the viewport — otherwise fitView from elsewhere could clobber us.
    const incomingId = workflows[activeIndex]?.id;
    if (incomingId) {
      const saved = viewportByWorkflowRef.current[incomingId];
      if (saved) {
        requestAnimationFrame(() => {
          requestAnimationFrame(() => canvasRef.current?.setViewport(saved));
        });
      }
    }
  }, [activeIndex, persistViewportStore, workflows]);

  const handleCancelRun = useCallback(async (run: RunRecord) => {
    const ok = await confirmDialog({
      title: 'Cancel run?',
      message: `Cancel ${run.workflow_name || run.run_id}?`,
      confirmLabel: 'Cancel Run',
      tone: 'danger',
    });
    if (!ok) return;
    try {
      const response = await fetch(`/api/queue/${encodeURIComponent(run.run_id)}/cancel`, { method: 'POST' });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      updateRun(run.run_id, { status: 'cancelled', end_time: new Date().toISOString() });
      toast.warning('Run cancelled', { message: run.workflow_name || run.run_id });
    } catch (err) {
      toast.error('Could not cancel run', { message: err instanceof Error ? err.message : String(err) });
    }
  }, [updateRun]);

  const handleLoadRunWorkflow = useCallback(async (run: RunRecord) => {
    try {
      const response = await fetch(`/api/runs/${encodeURIComponent(run.run_id)}`);
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const data = await response.json() as { workflow?: Workflow; workflow_name?: string };
      const workflow = data.workflow;
      if (!workflow || !Array.isArray(workflow.nodes)) {
        throw new Error('Run does not have an associated workflow snapshot');
      }
      const named: Workflow = {
        ...workflow,
        name: workflow.name || `${run.workflow_name || 'Run'} ${run.run_id.slice(0, 8)}`,
      };
      addWorkflow(withWorkflowId(named));
      toast.success('Workflow loaded from run', { message: named.name });
      requestAnimationFrame(() => {
        requestAnimationFrame(() => canvasRef.current?.fitView());
      });
    } catch (err) {
      toast.error('Could not load workflow', { message: err instanceof Error ? err.message : String(err) });
    }
  }, [addWorkflow]);

  const handleRetryRun = useCallback(async (run: RunRecord) => {
    try {
      const response = await fetch(`/api/runs/${encodeURIComponent(run.run_id)}/retry`, { method: 'POST' });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const data = await response.json() as { run_id: string; status?: string };
      addRun({
        run_id: data.run_id,
        status: 'pending',
        workflow_name: `${run.workflow_name || 'Untitled'} (retry)`,
        node_statuses: [],
        node_outputs: {},
        execution_plan: run.execution_plan ?? [],
        previews: {},
        artifacts: {},
        start_time: new Date().toISOString(),
      });
      setConsoleVisible(true);
      setRailTab('console');
      toast.success('Retry queued', { message: data.run_id });
    } catch (err) {
      toast.error('Could not retry run', { message: err instanceof Error ? err.message : String(err) });
    }
  }, [addRun, setRailTab]);

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
      toast.error('Could not reorder queue', { message: err instanceof Error ? err.message : String(err) });
    }
  }, [queuedRuns, setRuns]);

  const handleClearQueue = useCallback(async () => {
    const ok = await confirmDialog({
      title: 'Clear queue?',
      message: 'Remove all pending runs from the queue?',
      confirmLabel: 'Clear Queue',
      tone: 'warning',
    });
    if (!ok) return;
    try {
      await apiPost('/queue/clear');
      setRuns(prev => prev.filter(run => run.status !== 'pending'));
      toast.success('Queue cleared');
    } catch (err) {
      toast.error('Could not clear queue', { message: err instanceof Error ? err.message : String(err) });
    }
  }, [setRuns]);

  const handleClearHistory = useCallback(async () => {
    const ok = await confirmDialog({
      title: 'Clear history?',
      message: 'Remove all completed runs from history? This cannot be undone.',
      confirmLabel: 'Clear History',
      tone: 'warning',
    });
    if (!ok) return;
    try {
      await apiPost('/history/clear');
      setRuns(prev => prev.filter(run => run.status === 'pending' || run.status === 'running'));
      toast.success('History cleared');
    } catch (err) {
      toast.error('Could not clear history', { message: err instanceof Error ? err.message : String(err) });
    }
  }, [setRuns]);

  const handleDeleteHistoryEntry = useCallback(async (run: RunRecord) => {
    try {
      await apiDelete(`/history/${encodeURIComponent(run.run_id)}`);
      setRuns(prev => prev.filter(r => r.run_id !== run.run_id));
    } catch (err) {
      const detail = err instanceof ApiError ? `${err.status} ${err.statusText}` : err instanceof Error ? err.message : String(err);
      toast.error('Could not delete run', { message: detail });
    }
  }, [setRuns]);

  const handleSaveTemplate = useCallback(async (draft: TemplateSaveDraft) => {
    const token = getToken();
    if (!collabEnabled || !token || !activeWorkflowId) {
      await alertDialog({
        title: 'Template sharing unavailable',
        message: 'Enable collaboration and sign in to save shared workflow templates.',
      });
      return;
    }
    try {
      await publishCollabWorkflowSnapshot(activeWorkflow);
      const response = await fetch('/api/collab/templates', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          workflow_id: activeWorkflowId,
          title: draft.name,
          description: draft.description,
          category: draft.category,
          tags: draft.tags,
          is_public: false,
        }),
      });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      toast.success('Template saved', { message: draft.name });
    } catch (err) {
      toast.error('Could not save template', { message: err instanceof Error ? err.message : String(err) });
    }
  }, [activeWorkflow, activeWorkflowId, collabEnabled, publishCollabWorkflowSnapshot]);

  const handleToggleQueue = useCallback(() => {
    const isVisible = consoleVisible || railTab === 'console';
    if (isVisible) {
      setConsoleVisible(false);
      if (railTab === 'console') setRailTab(null);
    } else {
      setConsoleVisible(true);
      setRailTab('console');
    }
  }, [consoleVisible, railTab, setRailTab]);

  const handleLoadTemplate = useCallback(async (template: TemplateInfo) => {
    logTelemetry('template.load', { id: template.id, name: template.name, category: template.category });
    const wf = await fetchTemplateWorkflow(template);
    if (!wf) {
      return;
    }
    if (collabEnabled) {
      // Keep a shared room on the same workflow id. Opening a new tab here
      // strands collaborators, presence, and comments in different rooms.
      const sharedWorkflow = withWorkflowId(wf, activeWorkflowId);
      updateWorkflow(activeIndex, sharedWorkflow);
      if (collabDoc) {
        workflowToDoc(sharedWorkflow, collabDoc);
      }
      void publishCollabWorkflowSnapshot(sharedWorkflow);
    } else {
      addWorkflow(withWorkflowId(wf));
    }
    rememberRecentWorkflow({
      id: wf.id || activeWorkflowId,
      name: wf.name || template.name || 'Untitled',
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
  }, [activeIndex, activeWorkflowId, addWorkflow, collabDoc, collabEnabled, publishCollabWorkflowSnapshot, updateWorkflow]);

  const handleImport = useCallback((wf: Workflow) => {
    logTelemetry('workflow.import', { name: wf.name, nodes: wf.nodes?.length ?? 0 });
    if (collabEnabled) {
      const sharedWorkflow = withWorkflowId(wf, activeWorkflowId);
      updateWorkflow(activeIndex, sharedWorkflow);
      if (collabDoc) {
        workflowToDoc(sharedWorkflow, collabDoc);
      }
      void publishCollabWorkflowSnapshot(sharedWorkflow);
    } else {
      addWorkflow(withWorkflowId(wf));
    }
    rememberRecentWorkflow({
      id: wf.id || activeWorkflowId,
      name: wf.name || 'Imported workflow',
      source: 'import',
      thumbnailUrl: renderRecentThumbnail(wf),
      nodeCount: wf.nodes?.length ?? 0,
    });
    // Auto-fit view after nodes render
    requestAnimationFrame(() => {
      requestAnimationFrame(() => canvasRef.current?.fitView());
    });
    // Resolve is auto-triggered by the activeWorkflow useEffect
  }, [activeIndex, activeWorkflowId, addWorkflow, collabDoc, collabEnabled, publishCollabWorkflowSnapshot, updateWorkflow]);

  // Replay any URL-hash workflow that mount stashed before handleImport
  // existed. Runs once handleImport stabilises.
  useEffect(() => {
    const pending = pendingHashWorkflowRef.current;
    if (!pending) return;
    pendingHashWorkflowRef.current = null;
    handleImport(pending);
    toast.success('Loaded workflow from URL', { message: pending.name || 'untitled' });
  }, [handleImport]);

  const handleApplyWorkflow = useCallback((wf: Workflow) => {
    const sharedWorkflow = withWorkflowId(wf, activeWorkflowId);
    setWorkflow(activeIndex, () => sharedWorkflow);
    if (collabEnabled) {
      if (collabDoc) {
        workflowToDoc(sharedWorkflow, collabDoc);
      }
      void publishCollabWorkflowSnapshot(sharedWorkflow);
    }
  }, [activeIndex, activeWorkflowId, collabDoc, collabEnabled, publishCollabWorkflowSnapshot, setWorkflow]);

  const handleRenameTab = useCallback((index: number, name: string) => {
    updateWorkflow(index, { name });
  }, [updateWorkflow]);

  const handleDuplicateTab = useCallback((index: number) => {
    const wf = workflows[index];
    if (!wf) return;
    const dup: Workflow = {
      ...wf,
      id: createWorkflowId(),
      name: `${wf.name || 'Untitled'} (copy)`,
      nodes: wf.nodes.map(n => ({ ...n, id: `${n.type}_${Date.now()}_${Math.random().toString(36).slice(2, 7)}` })),
    };
    addWorkflow(dup);
  }, [workflows, addWorkflow]);

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
        label: 'Run workflow',
        description: activeWorkflow.name || 'Current workflow',
        group: 'Workflow',
        shortcut: getBinding('workflow.run') ?? undefined,
        onSelect: () => void handleRun(),
      },
      {
        id: 'workflow.runSelected',
        label: 'Run selected nodes',
        description: 'Execute selected nodes and their dependencies',
        group: 'Workflow',
        onSelect: () => canvasRef.current?.executeSelected(),
      },
      {
        id: 'workflow.extractSelection',
        label: 'Create subgraph from selection',
        description: 'Open selected nodes as a new workflow tab',
        group: 'Workflow',
        onSelect: () => canvasRef.current?.createSubgraphFromSelection(),
      },
      {
        id: 'workflow.saveSnippet',
        label: 'Save selection as snippet',
        description: 'Capture selected nodes + their interconnections to the snippet library',
        group: 'Workflow',
        onSelect: () => handleSaveSnippet(),
      },
      {
        id: 'workflow.insertSnippet',
        label: 'Insert snippet…',
        description: 'Pick from saved snippets and stamp at canvas centre',
        group: 'Workflow',
        onSelect: () => handleInsertSnippet(),
      },
      {
        id: 'workflow.doctor',
        label: 'Run workflow doctor',
        description: 'Scan the current workflow for missing inputs, unused outputs, and dependency hints',
        group: 'Workflow',
        onSelect: () => setShowDoctor(true),
      },
      {
        id: 'workflow.copyShareUrl',
        label: 'Copy share URL',
        description: 'Encode the current workflow into a URL hash and copy to clipboard',
        group: 'Workflow',
        onSelect: async () => {
          const url = buildShareUrl(activeWorkflow);
          if (!url) { toast.error('Could not build share URL'); return; }
          if (url.length > 32_000) {
            toast.warning('URL exceeds 32 KB', { message: 'Some chat tools may truncate. Consider exporting instead.' });
          }
          try {
            await navigator.clipboard.writeText(url);
            toast.success('Share URL copied', { message: `${(url.length / 1024).toFixed(1)} KB` });
          } catch {
            // Some browsers block clipboard from non-user gestures — surface
            // the URL inline as a fallback.
            await alertDialog({ title: 'Share URL', message: url });
          }
        },
      },
      {
        id: 'workflow.autoName',
        label: 'Suggest workflow name',
        description: 'Rename the current tab based on the dominant tools in the workflow',
        group: 'Workflow',
        onSelect: () => {
          const suggestion = suggestWorkflowName(activeWorkflow);
          if (!suggestion) {
            toast.info('Add a few real nodes before auto-naming');
            return;
          }
          handleRenameTab(activeIndex, suggestion);
          toast.success('Workflow renamed', { message: suggestion });
        },
      },
      {
        id: 'edit.bulkParams',
        label: 'Bulk edit parameters (selection)…',
        description: 'Edit parameters shared across all selected nodes at once',
        group: 'Edit',
        onSelect: () => {
          const selected = canvasRef.current?.getSelectedNodeIds() ?? [];
          if (selected.length < 2) {
            toast.info('Select 2+ nodes to bulk-edit their shared parameters');
            return;
          }
          setShowBulkParam(true);
        },
      },
      {
        id: 'workflow.export',
        label: 'Export workflow',
        group: 'Workflow',
        shortcut: getBinding('workflow.export') ?? undefined,
        onSelect: () => setShowExport(true),
      },
      {
        id: 'workflow.import',
        label: 'Import workflow',
        group: 'Workflow',
        shortcut: getBinding('workflow.import') ?? undefined,
        onSelect: () => setShowImport(true),
      },
      {
        id: 'nodes.search',
        label: 'Search nodes',
        description: 'Open the fuzzy node library',
        group: 'Panels',
        shortcut: getBinding('nodes.search') ?? undefined,
        onSelect: () => setRailTab('nodes'),
      },
      {
        id: 'rail.workspace',
        label: 'Open workspace',
        group: 'Panels',
        shortcut: getBinding('rail.workspace') ?? undefined,
        onSelect: () => togglePanel('data'),
      },
      {
        id: 'rail.nodes',
        label: 'Open nodes',
        group: 'Panels',
        shortcut: getBinding('rail.nodes') ?? undefined,
        onSelect: () => togglePanel('nodes'),
      },
      {
        id: 'rail.templates',
        label: 'Open templates',
        group: 'Panels',
        shortcut: getBinding('rail.templates') ?? undefined,
        onSelect: () => togglePanel('templates'),
      },
      {
        id: 'rail.environment',
        label: 'Open environments',
        group: 'Panels',
        shortcut: getBinding('rail.environment') ?? undefined,
        onSelect: () => togglePanel('environments'),
      },
      {
        id: 'rail.hpc',
        label: 'Open HPC',
        group: 'Panels',
        shortcut: getBinding('rail.hpc') ?? undefined,
        onSelect: () => togglePanel('hpc'),
      },
      {
        id: 'rail.help',
        label: 'Open help',
        group: 'Panels',
        shortcut: getBinding('rail.help') ?? undefined,
        onSelect: () => togglePanel('help'),
      },
      {
        id: 'rail.console',
        label: 'Open console',
        group: 'Panels',
        shortcut: getBinding('rail.console') ?? undefined,
        onSelect: () => togglePanel('console'),
      },
      {
        id: 'console.toggle',
        label: 'Toggle console',
        group: 'Panels',
        shortcut: getBinding('console.toggle') ?? undefined,
        onSelect: handleToggleQueue,
      },
      {
        id: 'settings.toggle',
        label: 'Toggle settings',
        group: 'Panels',
        shortcut: getBinding('settings.toggle') ?? undefined,
        onSelect: () => togglePanel('settings'),
      },
      {
        id: 'ai.open',
        label: 'Open AI workflow builder',
        group: 'Tools',
        shortcut: getBinding('ai.open') ?? undefined,
        onSelect: () => setShowAI(true),
      },
      {
        id: 'shortcuts.open',
        label: 'Keyboard shortcuts',
        group: 'Tools',
        shortcut: getBinding('shortcuts.open') ?? undefined,
        onSelect: () => setShowShortcuts(true),
      },
      // --- View / canvas ----------------------------------------------------
      {
        id: 'view.focusMode',
        label: focusMode ? 'Exit focus mode' : 'Enter focus mode',
        description: 'Hide chrome and maximize the canvas',
        group: 'View',
        shortcut: getBinding('view.focusMode') ?? undefined,
        onSelect: toggleFocusMode,
      },
      {
        id: 'view.fitAll',
        label: 'Fit all nodes',
        description: 'Frame every node in the current workflow',
        group: 'View',
        onSelect: () => canvasRef.current?.fitView(),
      },
      {
        id: 'view.fitSelection',
        label: 'Fit selection',
        description: 'Frame only selected nodes',
        group: 'View',
        onSelect: () => {
          const ids = canvasRef.current?.getSelectedNodeIds() ?? [];
          if (ids.length === 0) {
            toast.info('Select a node first');
            return;
          }
          canvasRef.current?.focusNode(ids[0]);
        },
      },
      {
        id: 'view.toggleMinimap',
        label: 'Toggle minimap',
        group: 'View',
        onSelect: () => set('bionodulo.showMinimap', !getBool('bionodulo.showMinimap')),
      },
      {
        id: 'view.toggleLinks',
        label: 'Toggle link visibility',
        group: 'View',
        onSelect: () => set('bionodulo.linksHidden', !getBool('bionodulo.linksHidden')),
      },
      {
        id: 'view.toggleSnapGrid',
        label: 'Toggle snap-to-grid',
        group: 'View',
        onSelect: () => set('bionodulo.snapToGrid', !getBool('bionodulo.snapToGrid')),
      },
      {
        id: 'view.toggleLockViewport',
        label: 'Toggle viewport lock',
        group: 'View',
        onSelect: () => set('bionodulo.viewportLocked', !getBool('bionodulo.viewportLocked')),
      },
      // --- History ----------------------------------------------------------
      {
        id: 'edit.undo',
        label: 'Undo',
        group: 'Edit',
        shortcut: 'Ctrl+Z',
        onSelect: undo,
      },
      {
        id: 'edit.redo',
        label: 'Redo',
        group: 'Edit',
        shortcut: 'Ctrl+Shift+Z',
        onSelect: redo,
      },
      {
        id: 'edit.autoLayout',
        label: 'Auto-layout (selected nodes)',
        description: 'Arrange selected nodes (or all nodes) in topological columns',
        group: 'Edit',
        onSelect: () => canvasRef.current?.autoLayout(),
      },
      // --- Workflow tabs ----------------------------------------------------
      {
        id: 'workflow.new',
        label: 'New workflow tab',
        group: 'Workflow',
        onSelect: addTab,
      },
      {
        id: 'workflow.closeTab',
        label: 'Close current workflow tab',
        group: 'Workflow',
        onSelect: () => closeTab(activeIndex),
      },
      {
        id: 'workflow.duplicateTab',
        label: 'Duplicate current workflow tab',
        group: 'Workflow',
        onSelect: () => handleDuplicateTab(activeIndex),
      },
      {
        id: 'workflow.batchSheet',
        label: 'Batch from sample sheet...',
        description: 'Queue one run per CSV/TSV row',
        group: 'Workflow',
        onSelect: () => setShowBatchSheet(true),
      },
      // --- Cache / runtime --------------------------------------------------
      {
        id: 'cache.toggle',
        label: 'Toggle execution cache',
        group: 'Workflow',
        onSelect: () => set('bionodulo.cacheEnabled', !getBool('bionodulo.cacheEnabled')),
      },
      {
        id: 'cache.clear',
        label: 'Clear execution cache',
        group: 'Workflow',
        onSelect: async () => {
          try {
            const response = await fetch('/api/cache/clear', { method: 'POST' });
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            const data = await response.json();
            toast.success('Cache cleared', { message: `${data.entries_deleted || 0} entries` });
          } catch (err) {
            toast.error('Could not clear cache', { message: err instanceof Error ? err.message : String(err) });
          }
        },
      },
      {
        id: 'queue.clear',
        label: 'Clear pending queue',
        group: 'Workflow',
        onSelect: () => void handleClearQueue(),
      },
      // --- Logs / console ---------------------------------------------------
      {
        id: 'logs.clear',
        label: 'Clear console logs',
        group: 'Tools',
        onSelect: clearLogs,
      },
      // --- Help / onboarding ------------------------------------------------
      {
        id: 'help.gettingStarted',
        label: 'Open Getting Started',
        group: 'Tools',
        onSelect: () => setShowGettingStarted(true),
      },
      {
        id: 'help.shortcuts',
        label: 'Open keyboard shortcuts (alias)',
        group: 'Tools',
        onSelect: () => setShowShortcuts(true),
      },
    ];

    const paletteCommands = palettes.map(palette => ({
      id: `palette.${palette.id}`,
      label: `Use ${palette.name} palette`,
      description: palette.description,
      group: 'Appearance',
      onSelect: () => setPalette(palette.id),
    }));

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
  // type plus "Open recent: {Name}" entries so Ctrl+P doubles as a way to
  // create nodes and reopen workflows without leaving the keyboard. Capped
  // to keep the palette snappy — the regular Node Library + Getting Started
  // panels remain the place for full browsing.
  const NODE_PALETTE_LIMIT = 40;
  const dynamicCommands = useMemo<CommandItem[]>(() => {
    const items: CommandItem[] = [];
    const metas = Object.values(objectInfo).slice(0, NODE_PALETTE_LIMIT);
    for (const meta of metas) {
      items.push({
        id: `addNode.${meta.id}`,
        label: `Add: ${meta.display_name}`,
        description: meta.description || meta.category,
        group: 'Add Node',
        keywords: [meta.id, meta.category, ...(meta.requires_external_tools || [])],
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
          label: `Open recent: ${entry.name}`,
          description: entry.filename || 'recent workflow',
          group: 'Workflow',
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
  }, [objectInfo, activeWorkflow, activeIndex, updateWorkflow, handleLoadTemplate]);
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

  // Auto-queue: 'change' mode debounces a run when the workflow becomes dirty;
  // 'instant' mode re-runs as soon as the most recent run finishes successfully.
  const handleRunRef = useRef(handleRun);
  useEffect(() => { handleRunRef.current = handleRun; }, [handleRun]);

  useEffect(() => {
    if (queueMode !== 'change') return;
    if (!dirty || isRunning) return;
    // Skip auto-queue when the workflow is empty *of executable nodes*. Notes
    // alone shouldn't trigger a backend run.
    const realNodes = (activeWorkflow.nodes || []).filter(
      n => n.type !== 'note' && n.type !== 'reroute',
    );
    if (realNodes.length === 0) return;
    const timer = setTimeout(() => { void handleRunRef.current(); }, 1500);
    return () => clearTimeout(timer);
  }, [queueMode, dirty, isRunning, activeWorkflow.nodes]);

  const lastInstantRunRef = useRef<string | null>(null);
  useEffect(() => {
    if (queueMode !== 'instant') return;
    if (isRunning) return;
    const latest = runs[0];
    if (!latest) return;
    if (latest.status !== 'completed') return;
    if (lastInstantRunRef.current === latest.run_id) return;
    lastInstantRunRef.current = latest.run_id;
    // Tiny delay so the UI can settle and the user can still cancel
    // the auto-queue by switching mode before the next run fires.
    const timer = setTimeout(() => { void handleRunRef.current(); }, 250);
    return () => clearTimeout(timer);
  }, [queueMode, isRunning, runs]);

  useEffect(() => {
    if (autoSaveSetting === 'off') return;
    const seconds = parseInt(autoSaveSetting.replace('s', ''), 10);
    if (!Number.isFinite(seconds) || seconds <= 0) return;
    const timer = setInterval(() => {
      const workflow = latestWorkflowRef.current;
      try {
        localStorage.setItem(AUTO_SAVE_LAST_KEY, new Date().toISOString());
      } catch { /* ignore */ }
      if (collabEnabled) {
        void publishCollabWorkflowSnapshot(workflow);
      }
      // Keep the recents thumbnail current so reopening from Getting Started
      // reflects the current shape of the workflow, not the moment of import.
      if (workflow?.id && (workflow.nodes?.length ?? 0) > 0) {
        const thumbnail = renderRecentThumbnail(workflow);
        if (thumbnail) {
          refreshRecentThumbnail(workflow.id, thumbnail, {
            name: workflow.name,
            nodeCount: workflow.nodes?.length ?? 0,
          });
        }
      }
      const savedAt = new Date().toISOString();
      setLastAutoSaveAt(savedAt);
      setDirty(false);
    }, seconds * 1000);
    return () => clearInterval(timer);
  }, [autoSaveSetting, collabEnabled, publishCollabWorkflowSnapshot]);

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
  const tabNames = useMemo(() => workflows.map(w => w.name || 'Untitled'), [workflowNamesKey]);
  const activeNodeTypeKey = useMemo(() => nodeTypeSignature(activeWorkflow.nodes), [activeWorkflow.nodes]);
  const activeEdgeTopologyKey = useMemo(() => edgeTopologySignature(activeWorkflow.edges), [activeWorkflow.edges]);
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
  const latestPreviewsKey = useMemo(() => previewsSignature(runs[0]), [runs]);
  const nodePreviewsMap = useMemo(() => {
    const latest = runs[0];
    if (!latest) return undefined;
    const map = new Map<string, string>();
    for (const node of activeWorkflow.nodes) {
      if (node.type !== 'image_preview') continue;
      const incoming = activeWorkflow.edges.find(edge => edge.to.node === node.id);
      if (!incoming) continue;
      const sourceNodeId = incoming.from.node;
      const path = latest.previews?.[sourceNodeId];
      if (path) {
        map.set(node.id, `/api/previews/${latest.run_id}/${sourceNodeId}?path=${encodeURIComponent(path)}`);
      }
    }
    return map;
  }, [activeEdgeTopologyKey, activeNodeTypeKey, latestPreviewsKey]);
  const nodeHtmlPreviewsMap = useMemo(() => {
    const latest = runs[0];
    if (!latest) return undefined;
    const map = new Map<string, string>();
    for (const node of activeWorkflow.nodes) {
      if (node.type !== 'html_preview') continue;
      const incoming = activeWorkflow.edges.find(edge => edge.to.node === node.id);
      if (!incoming) continue;
      const sourceNodeId = incoming.from.node;
      const path = latest.previews?.[sourceNodeId];
      if (path && /\.html?$/i.test(path)) {
        map.set(node.id, `/api/previews/${latest.run_id}/${sourceNodeId}?path=${encodeURIComponent(path)}`);
      }
    }
    return map;
  }, [activeEdgeTopologyKey, activeNodeTypeKey, latestPreviewsKey]);
  const workflowCommentsKey = useMemo(() => commentsSignature(workflowComments), [workflowComments]);
  const nodeCommentsMap = useMemo(() => {
    const map = new Map<string, { count: number; unresolved: boolean }>();
    const add = (comment: Comment) => {
      if (!comment.node_id) return;
      const previous = map.get(comment.node_id) ?? { count: 0, unresolved: false };
      map.set(comment.node_id, {
        count: previous.count + 1,
        unresolved: previous.unresolved || !comment.resolved,
      });
      comment.replies?.forEach(add);
    };
    workflowComments.forEach(add);
    return map;
  }, [workflowCommentsKey]);
  const liveWorkflowNamesKey = useMemo(() => recordSignature(workflowNames), [workflowNames]);
  const knownWorkflowNames = useMemo(() => ({
    ...Object.fromEntries(workflows.filter(workflow => workflow.id).map(workflow => [workflow.id!, workflow.name || 'Untitled'])),
    ...workflowNames,
  }), [liveWorkflowNamesKey, workflowNamesKey]);
  const canvasCollabUsers = useMemo(
    () => (collabEnabled && collabPresenceEnabled ? collabActiveUsers : EMPTY_COLLAB_USERS),
    [collabActiveUsers, collabEnabled, collabPresenceEnabled],
  );
  const appShellClassName = useMemo(() => ([
    'app-shell',
    showAI ? 'ai-open' : '',
    showComments ? 'comments-open' : '',
    (consoleVisible || railTab === 'console') ? 'console-open' : '',
    focusMode ? 'focus-mode' : '',
  ].filter(Boolean).join(' ')), [consoleVisible, focusMode, railTab, showAI, showComments]);
  // Total pixel width of all panels currently docked to the RIGHT edge —
  // exposed as `--right-panel-inset` so .minimap / .canvas-controls slide
  // left to stay visible instead of being clipped by the panel.
  const rightPanelInset = useMemo(() => {
    let total = 0;
    for (const tab of openPanelTabs) {
      if (!rightDockedPanels[tab] || floatingPanels[tab]) continue;
      total += (panelWidths[tab] ?? 340);
    }
    return total;
  }, [openPanelTabs, rightDockedPanels, floatingPanels, panelWidths]);
  // NOTE: The "Unsaved changes / Autosave" pill that used to live in the top
  // bar was removed in Wave L. The amber dot on each workflow tab now carries
  // the dirty signal, and pre-flight save state is still surfaced inline when
  // it matters (e.g. close-tab confirm dialog), so a global pill became noise.

  const closePanel = useCallback((tab: OpenPanelTab) => {
    setOpenPanelTabs(current => current.filter(item => item !== tab));
    setRailTabState(prev => (prev === tab ? null : prev));
  }, []);

  const renderPanelContent = (tab: OpenPanelTab) => {
    if (tab === 'settings') return <SettingsPanel onClose={() => closePanel(tab)} />;
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
        }
        : null;
      return <HelpWikiPanel onClose={() => closePanel(tab)} selectedNode={helpSelectedNode} objectInfo={objectInfo} />;
    }
    if (tab === 'templates') {
      return (
        <TemplatesPanel
          onClose={() => closePanel(tab)}
          onLoadTemplate={handleLoadTemplate}
          onSaveTemplate={handleSaveTemplate}
          showSaveTemplateAction
          saveTemplateInitialName={resolveWorkflowName(activeWorkflow)}
          saveTemplateInitialDescription={activeWorkflow.description || ''}
        />
      );
    }
    if (tab === 'environments') return <EnvironmentPanel onClose={() => closePanel(tab)} currentWorkflow={activeWorkflow} />;
    if (tab === 'hpc') {
      return (
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
      );
    }
    if (tab === 'nodes') {
      return (
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
      );
    }
    if (tab === 'data') {
      return (
        <WorkspacePanel
          onClose={() => closePanel(tab)}
          onOpenSettings={() => setRailTab('settings')}
          onImportWorkflow={handleImport}
        />
      );
    }
    const registered = registeredPanels.find(panel => panel.id === tab);
    if (registered) {
      return registered.render();
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
      <KeyboardShortcutsModal open={showShortcuts} onOpenChange={setShowShortcuts} />

      {draggingPanelTab && (
        <>
          <div className={`panel-dropzone panel-dropzone-left ${panelDropZone === 'left' ? 'is-active' : ''}`}>
            <Icon name="dockPanel" size={18} />
            <span>Dock left</span>
          </div>
          <div className={`panel-dropzone panel-dropzone-right ${panelDropZone === 'right' ? 'is-active' : ''}`}>
            <Icon name="dockPanel" size={18} />
            <span>Dock right</span>
          </div>
        </>
      )}

      <TopBar
        validationValid={validation.valid}
        validationErrors={validation.errors}
        onRun={handleRun}
        onExport={() => setShowExport(true)}
        onAI={() => setShowAI(true)}
        onBatchSheet={() => setShowBatchSheet(true)}
        hpcStatus={hpcStatus}
        hpcEnabled={hpcEnabled}
        isRunning={isRunning}
        queueMode={queueMode}
        onQueueModeChange={setQueueMode}
        queueCount={queueCount}
        batchCount={batchCount}
        onToggleQueue={handleToggleQueue}
        onBatchCountChange={(count) => setBatchCount(Math.max(1, Math.min(99, count)))}
        collabControls={collabEnabled ? (
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
            onShare={() => setShowShareDialog(true)}
            onFollow={followPresenceUser}
            onOpenComments={() => setShowComments(v => !v)}
            onOpenVersions={() => setShowVersions(v => !v)}
            onOpenAudit={() => setShowAudit(v => !v)}
            onOpenSettings={() => setRailTab('settings')}
            reconnectAttempt={collabReconnectAttempt}
            error={collabError}
            offline={collabOffline}
          />
        ) : null}
      />

      <AuthDialog
        isOpen={showAuthDialog}
        onLogin={handleAuthLogin}
        onClose={handleAuthClose}
      />

      <WorkflowTabs
        tabs={tabNames}
        active={activeIndex}
        onChange={setActiveIndex}
        onClose={async (index) => {
          // Guard the active tab if it has unsaved changes; other tabs
          // currently don't track dirtiness individually so we close them
          // without confirmation (autosave covers the common case).
          if (index === activeIndex && dirty) {
            const wfName = workflows[index]?.name || 'this workflow';
            const ok = await confirmDialog({
              title: 'Close tab with unsaved changes?',
              message: `${wfName} has unsaved changes. Close anyway?`,
              confirmLabel: 'Close',
              tone: 'danger',
            });
            if (!ok) return;
          }
          closeTab(index);
        }}
        onAdd={addTab}
        onRename={handleRenameTab}
        onDuplicate={handleDuplicateTab}
        onReorder={handleReorderTabs}
        dirtyIndices={dirty ? new Set([activeIndex]) : undefined}
      />

      <LeftRail active={railTab} onChange={setRailTab} />

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
              const r = await fetch(`/api/workspace/file?path=${encodeURIComponent(workflowPath)}`);
              if (!r.ok) return;
              const text = await r.text();
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
              toast.warning('No input_file node registered; cannot create node for dropped file');
              return;
            }
            const vp = canvasRef.current?.getViewport();
            const target = e.currentTarget as HTMLElement;
            const rect = target.getBoundingClientRect();
            const cx = e.clientX - rect.left;
            const cy = e.clientY - rect.top;
            const world = vp
              ? { x: (cx - vp.x) / vp.scale, y: (cy - vp.y) / vp.scale }
              : { x: cx, y: cy };
            const fileName = filePath.split(/[\\/]/).pop() || 'file';
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
            toast.success('File dropped', { message: fileName });
          }
        }}
      >
        {subgraphPath.length > 0 && (
          <div
            style={{
              position: 'absolute',
              top: 8,
              left: 8,
              right: 8,
              zIndex: 12,
              display: 'flex',
              alignItems: 'center',
              gap: 4,
              padding: '6px 10px',
              borderRadius: 8,
              background: 'color-mix(in srgb, var(--surface) 94%, transparent)',
              border: '1px solid var(--border)',
              boxShadow: 'var(--shadow)',
              fontSize: 12,
              color: 'var(--text)',
            }}
          >
            <span style={{ color: 'var(--muted)' }}>Subgraph:</span>
            <button
              type="button"
              onClick={() => handleExitSubgraph(0)}
              style={{
                background: 'transparent', border: 'none', color: 'var(--text)',
                cursor: 'pointer', padding: '2px 6px', borderRadius: 4,
              }}
              title="Back to top-level workflow"
            >
              {subgraphPath[0]?.parentWorkflow?.name || 'Workflow'}
            </button>
            {subgraphPath.map((frame, idx) => (
              <span key={`${frame.subgraphNodeId}-${idx}`} style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
                <span style={{ color: 'var(--muted)' }}>›</span>
                {idx < subgraphPath.length - 1 ? (
                  <button
                    type="button"
                    onClick={() => handleExitSubgraph(idx + 1)}
                    style={{
                      background: 'transparent', border: 'none', color: 'var(--text)',
                      cursor: 'pointer', padding: '2px 6px', borderRadius: 4,
                    }}
                  >
                    {frame.subgraphName}
                  </button>
                ) : (
                  <span style={{ fontWeight: 600, padding: '2px 6px' }}>{frame.subgraphName}</span>
                )}
              </span>
            ))}
          </div>
        )}
        {hostStatus && !hostStatus.ready && hostStatus !== dismissedHostStatus && (
          <HostPrerequisitesBanner
            status={hostStatus}
            onDismiss={() => setDismissedHostStatus(hostStatus)}
            onOpenConsole={() => { setConsoleVisible(true); setRailTab('console'); }}
            onRecheck={async () => {
              const r = await fetch('/api/host_status');
              if (r.ok) setHostStatus(await r.json() as HostStatus);
            }}
          />
        )}
        {resolveReport && resolveReport.has_issues && resolveReport !== dismissedReport && (
          <MissingDependenciesBanner
            report={resolveReport}
            workflow={activeWorkflow}
            onDismiss={() => setDismissedReport(resolveReport)}
            onOpenConsole={() => { setConsoleVisible(true); setRailTab('console'); }}
            onResolve={() => { resolve(activeWorkflow); }}
          />
        )}
        <LiteGraphCanvas
          ref={canvasRef}
          nodes={activeWorkflow.nodes}
          edges={activeWorkflow.edges}
          groups={activeWorkflow.groups}
          objectInfo={objectInfo}
          onNodesChange={handleNodesChange}
          onEdgesChange={handleEdgesChange}
          onGroupsChange={handleGroupsChange}
          onPushHistory={pushHistory}
          onUndo={undo}
          onRedo={redo}
          snapToGrid={getBool('bionodulo.snapToGrid')}
          showMinimap={getBool('bionodulo.showMinimap')}
          viewportLocked={getBool('bionodulo.viewportLocked')}
          linksHidden={getBool('bionodulo.linksHidden')}
          onToggleMinimap={() => set('bionodulo.showMinimap', !getBool('bionodulo.showMinimap'))}
          onToggleLinksHidden={() => set('bionodulo.linksHidden', !getBool('bionodulo.linksHidden'))}
          nodeStatusMap={nodeStatusMap}
          nodeProgressMap={nodeRunProgress}
          nodeErrorsMap={nodeErrorsMap}
          missingDependencyNodeIds={missingDependencyNodeIds}
          nodeCommentsMap={nodeCommentsMap}
          nodeComments={workflowComments}
          collabWorkflowId={collabEnabled ? activeWorkflowId : undefined}
          currentCollabUser={collabEnabled ? currentUser : undefined}
          onNodeCommentsChange={() => void fetchWorkflowComments()}
          collabUsers={canvasCollabUsers}
          nodePreviewsMap={nodePreviewsMap}
          nodeHtmlPreviewsMap={nodeHtmlPreviewsMap}
          onCollabCursor={collabEnabled ? setCollabCursor : undefined}
          onViewportChange={collabEnabled ? publishCollabViewport : undefined}
          onCollabSelection={(selection) => {
            setSelectedNodeId(selection.nodeIds[0] ?? null);
            setCollabSelection(selection);
          }}
          onCollabNodeMove={collabEnabled ? publishCollabNodeMove : undefined}
          onCollabDragStart={collabEnabled ? handleCollabDragStart : undefined}
          onCollabDragEnd={collabEnabled ? handleCollabDragEnd : undefined}
          onExecuteSelected={handleRunSelected}
          onCreateSubgraph={handleCreateSubgraph}
          onEnterSubgraph={handleEnterSubgraph}
          onPromoteWidgets={handlePromoteWidgets}
        />

        {/* Registered rail panels: docked panels stack from the left edge by
            default, but each panel can be flipped to the right edge so two
            related panels (e.g. node library + node info) can sit side by
            side without the user having to float either of them. */}
        {(() => {
          const leftPanels = openPanelTabs.filter(tab => !rightDockedPanels[tab] && !floatingPanels[tab]);
          const rightPanels = openPanelTabs.filter(tab => rightDockedPanels[tab] && !floatingPanels[tab]);
          const floatingTabs = openPanelTabs.filter(tab => floatingPanels[tab]);
          const renderPanel = (tab: OpenPanelTab, side: 'left' | 'right' | 'float', offset: number) => {
            const index = openPanelTabs.indexOf(tab);
            const width = panelWidths[tab] ?? 340;
            const floating = floatingPanels[tab];
            const isRight = side === 'right';
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
                <Suspense fallback={<div className="panel-suspense-fallback"><Spinner size="lg" label={`Loading ${tab}…`} /></div>}>
                  <div className="rail-panel-toolbar">
                    {!floating && (
                      <button
                        className="rail-panel-dock-side"
                        onClick={() => toggleRightDocked(tab)}
                        title={isRight ? 'Dock to left side' : 'Dock to right side'}
                        aria-label={isRight ? 'Move panel to left side' : 'Move panel to right side'}
                        type="button"
                      >
                        <Icon name={isRight ? 'chevronLeft' : 'chevronRight'} size={13} />
                      </button>
                    )}
                    <button
                      className="rail-panel-float"
                      onClick={() => toggleFloatingPanel(tab, index)}
                      title={floating ? 'Dock panel' : 'Float panel'}
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
                  aria-label={`Resize ${tab} panel`}
                  onMouseDown={event => startPanelResize(tab, event.clientX, width)}
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

        <WorkflowStatsOverlay workflow={activeWorkflow} hidden={focusMode} />
        {focusMode && (
          <button
            type="button"
            className="focus-mode-exit"
            onClick={toggleFocusMode}
            title="Exit focus mode"
          >
            Exit focus mode <kbd>{getBinding('view.focusMode') ?? 'Ctrl+.'}</kbd>
          </button>
        )}
        {(consoleVisible || railTab === 'console') && (
          <ErrorBoundary>
            <BottomConsole
              logs={logs}
              queue={queuedRuns}
              history={runs}
              onClose={() => { setConsoleVisible(false); if (railTab === 'console') setRailTab(null); }}
              onOpenLightbox={openLightbox}
              onOpenHtmlPreview={openHtmlPreview}
              onClearLogs={clearLogs}
              onCancelRun={handleCancelRun}
              onRetryRun={handleRetryRun}
              onLoadRunWorkflow={handleLoadRunWorkflow}
              onDeleteHistoryEntry={handleDeleteHistoryEntry}
              onMoveRun={handleMoveRun}
              onClearQueue={handleClearQueue}
              onClearHistory={handleClearHistory}
              onCompareRuns={() => setShowOutputDiff(true)}
              batchCount={batchCount}
              nodeIdToName={nodeIdToNameMap}
            />
          </ErrorBoundary>
        )}
      </div>

      <ShareDialog
        workflowId={activeWorkflowId}
        isOpen={showShareDialog}
        onClose={() => setShowShareDialog(false)}
      />

      {/* Phase 3 Collaboration Panels */}
      <CommentsPanel
        workflowId={activeWorkflowId}
        selectedNodeId={null}
        currentUser={currentUser}
        isOpen={showComments}
        onClose={() => setShowComments(false)}
        onFocusNode={(nodeId) => {
          setSelectedNodeId(nodeId);
          canvasRef.current?.focusNode(nodeId);
        }}
        onCommentsChange={setWorkflowComments}
        onWorkflowNamesChange={setWorkflowNames}
      />
      <VersionHistory
        workflowId={activeWorkflowId}
        isOpen={showVersions}
        onClose={() => setShowVersions(false)}
        onRestore={(versionJson) => {
          if (versionJson && typeof versionJson === 'object') {
            const v = versionJson as Record<string, unknown>;
            const nextWorkflow = {
              ...activeWorkflowRef.current,
              id: activeWorkflowId,
              nodes: valuesFromUnknownRecord<WorkflowNode>(v.nodes),
              edges: valuesFromUnknownRecord<Workflow['edges'][number]>(v.edges),
              groups: valuesFromUnknownRecord<Workflow['groups'][number]>(v.groups),
            };
            if (bridgeRef.current) {
              bridgeRef.current.onNodesChanged(nextWorkflow.nodes);
              bridgeRef.current.onEdgesChanged(nextWorkflow.edges);
              bridgeRef.current.onGroupsChanged(nextWorkflow.groups);
            }
            updateWorkflow(activeIndex, nextWorkflow);
            void publishCollabWorkflowSnapshot(nextWorkflow);
          }
        }}
      />
      <AuditLog
        workflowId={activeWorkflowId}
        isOpen={showAudit}
        onClose={() => setShowAudit(false)}
      />

      {/* Modals */}
      {showExport && <ExportModal workflow={activeWorkflow} onClose={() => setShowExport(false)} />}
      {showImport && <ImportModal onImport={handleImport} onClose={() => setShowImport(false)} />}
      {showOutputDiff && (
        <Suspense fallback={<div className="modal-overlay"><Spinner size="lg" label="Loading run diff" /></div>}>
          <OutputDiffModal runs={runs} onClose={() => setShowOutputDiff(false)} />
        </Suspense>
      )}
      {showDoctor && (
        <Suspense fallback={<div className="modal-overlay"><Spinner size="lg" label="Loading doctor" /></div>}>
          <WorkflowDoctorModal
            workflow={activeWorkflow}
            objectInfo={objectInfo}
            onClose={() => setShowDoctor(false)}
            onJumpToNode={(id) => { canvasRef.current?.focusNode(id); setShowDoctor(false); }}
          />
        </Suspense>
      )}
      {showBulkParam && (() => {
        const selectedIds = canvasRef.current?.getSelectedNodeIds() ?? [];
        const selectedNodes = activeWorkflow.nodes.filter(n => selectedIds.includes(n.id));
        return (
          <Suspense fallback={<div className="modal-overlay"><Spinner size="lg" label="Loading bulk editor" /></div>}>
            <BulkParamModal
              nodes={selectedNodes}
              onClose={() => setShowBulkParam(false)}
              onApply={(changes) => {
                if (changes.length === 0) return;
                const idSet = new Set(selectedIds);
                const nextNodes = activeWorkflow.nodes.map(n => {
                  if (!idSet.has(n.id)) return n;
                  const nextParams = { ...n.params };
                  for (const { key, value } of changes) {
                    if (!Object.prototype.hasOwnProperty.call(nextParams, key)) continue;
                    nextParams[key] = value;
                  }
                  return { ...n, params: nextParams };
                });
                updateWorkflow(activeIndex, { ...activeWorkflow, nodes: nextNodes });
                toast.success('Bulk edit applied', { message: `${changes.length} param${changes.length === 1 ? '' : 's'} → ${selectedNodes.length} node${selectedNodes.length === 1 ? '' : 's'}` });
              }}
            />
          </Suspense>
        );
      })()}
      {showAI && (
        <AIWorkflowModal
          workflow={activeWorkflow}
          onClose={() => setShowAI(false)}
          onApplyWorkflow={handleApplyWorkflow}
        />
      )}
      {showBatchSheet && (
        <BatchSampleSheetModal
          workflow={activeWorkflow}
          onClose={() => setShowBatchSheet(false)}
          onSubmit={handleBatchSheetSubmit}
        />
      )}
      {showGettingStarted && (
        <GettingStartedModal
          onClose={() => {
            set('bionodulo.getting_started.dismissed', true);
            setShowGettingStarted(false);
          }}
          onDontShowAgain={(hide) => {
            set('bionodulo.getting_started.show_on_startup', !hide);
          }}
          collabEnabled={collabEnabled}
          onSetCollabEnabled={(enabled) => {
            set('bionodulo.collab.enabled', enabled);
            if (!enabled) {
              setShowAuthDialog(false);
            } else if (!authUser) {
              setShowAuthDialog(true);
            }
          }}
          showOnStartup={getBool('bionodulo.getting_started.show_on_startup')}
          onOpenRecent={async (entry) => {
            if (entry.source === 'template' && entry.filename) {
              const template = {
                id: entry.id,
                name: entry.name,
                filename: entry.filename,
                description: '',
                node_count: entry.nodeCount ?? 0,
              } as TemplateInfo;
              await handleLoadTemplate(template);
            } else if (collabEnabled) {
              setRequestedWorkflowId(entry.id);
            }
          }}
        />
      )}
      <ImageLightbox
        images={lightboxImages}
        initialIndex={lightboxIndex}
        isOpen={lightboxOpen}
        onClose={() => setLightboxOpen(false)}
      />
      <HtmlPreviewModal
        src={htmlPreviewState?.src ?? ''}
        filename={htmlPreviewState?.filename ?? ''}
        isOpen={htmlPreviewState !== null}
        onClose={() => setHtmlPreviewState(null)}
      />

    </div>
  );
}
