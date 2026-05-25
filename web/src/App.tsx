import { useState, useCallback, useEffect, useRef, useMemo } from 'react';
import { useAtom } from 'jotai';
import TopBar from './components/layout/TopBar';
import LeftRail, { type RailTab } from './components/layout/LeftRail';
import WorkflowTabs from './components/layout/WorkflowTabs';
import BottomConsole from './components/layout/BottomConsole';
import ErrorBoundary from './components/layout/ErrorBoundary';
import LiteGraphCanvas, { type LiteGraphCanvasRef } from './components/canvas/LiteGraphCanvas';
import HardwareMonitor from './components/canvas/HardwareMonitor';
import SettingsPanel from './components/panels/SettingsPanel';
import HelpWikiPanel from './components/panels/HelpWikiPanel';
import TemplatesPanel from './components/panels/TemplatesPanel';
import EnvironmentPanel from './components/panels/EnvironmentPanel';
import HPCPanel from './components/panels/HPCPanel';
import NodeLibraryPanel from './components/panels/NodeLibraryPanel';
import WorkspacePanel from './components/panels/WorkspacePanel';
import ExportModal from './components/modals/ExportModal';
import ImportModal from './components/modals/ImportModal';
import AIWorkflowModal from './components/modals/AIWorkflowModal';
import ImageLightbox from './components/modals/ImageLightbox';
import GettingStartedModal from './components/modals/GettingStartedModal';
import MissingDependenciesBanner from './components/layout/MissingDependenciesBanner';
import HostPrerequisitesBanner from './components/layout/HostPrerequisitesBanner';
import { useSettings } from './hooks/useSettings';
import { useWorkflow } from './hooks/useWorkflow';
import { useObjectInfo } from './hooks/useObjectInfo';
import { useTheme } from './hooks/useTheme';
import { useWebSocket } from './hooks/useWebSocket';
import {
  LiteGraphYjsBridge, useCollab, workflowToDoc, docToWorkflow,
  CollabBadge, ShareDialog,
  getUserColor, getAuthUser, getToken, initAuth, AuthDialog,
  CommentsPanel, VersionHistory, AuditLog,
} from './collab';
import { defaultsFor, valuesFromUnknownRecord } from './utils';
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
    version: 'Alpha 1.5',
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
    version: String(meta.version || 'Alpha 1.5'),
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
  const { objectInfo } = useObjectInfo();

  // Authentication state
  const collabEnabled = getBool('bionodulo.collab.enabled');
  const initialRequestedWorkflowId = useMemo(() => getRequestedWorkflowId(), []);
  const [requestedWorkflowId, setRequestedWorkflowId] = useAtom(requestedWorkflowIdAtom);
  const [authUser, setAuthUser] = useAtom(authUserAtom);
  const [authReady, setAuthReady] = useAtom(authReadyAtom);
  const [showAuthDialog, setShowAuthDialog] = useAtom(showAuthDialogAtom);
  const effectiveRequestedWorkflowId = requestedWorkflowId || initialRequestedWorkflowId;

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
    shareWorkflow,
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
    Promise.all([
      fetch('/api/queue').then(r => r.ok ? r.json() : null),
      fetch('/api/history').then(r => r.ok ? r.json() : null),
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
  const historyRef = useRef<{ nodes: WorkflowNode[]; edges: Workflow['edges']; groups: Workflow['groups'] }[]>([]);
  const historyIndexRef = useRef(-1);
  const pendingStateRef = useRef<Partial<Workflow>>({});

  useEffect(() => {
    historyRef.current = [];
    historyIndexRef.current = -1;
  }, [activeIndex]);

  const pushHistory = useCallback(() => {
    const pending = pendingStateRef.current;
    if (Object.keys(pending).length === 0) return;
    pendingStateRef.current = {};
    const wf = { ...activeWorkflow, ...pending };
    const snapshot = {
      nodes: wf.nodes,
      edges: wf.edges,
      groups: wf.groups,
    };
    const next = historyRef.current.slice(0, historyIndexRef.current + 1);
    next.push({ ...snapshot });
    if (next.length > 50) next.shift();
    historyRef.current = next;
    historyIndexRef.current = next.length - 1;
  }, [activeWorkflow]);

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
  }, [activeIndex, updateWorkflow]);

  const [railTab, setRailTab] = useState<RailTab>(null);
  const [consoleVisible, setConsoleVisible] = useState(false);
  const [showExport, setShowExport] = useState(false);
  const [showImport, setShowImport] = useState(false);

  const [showAI, setShowAI] = useState(false);
  const [showGettingStarted, setShowGettingStarted] = useState(false);

  // Image lightbox state
  const [lightboxOpen, setLightboxOpen] = useState(false);
  const [lightboxImages, setLightboxImages] = useState<{ src: string; alt: string; filename: string }[]>([]);
  const [lightboxIndex, setLightboxIndex] = useState(0);

  const openLightbox = useCallback((images: { src: string; alt: string; filename: string }[], index: number) => {
    setLightboxImages(images);
    setLightboxIndex(index);
    setLightboxOpen(true);
  }, []);
  const [isRunning, setIsRunning] = useState(false);
  const [dismissedReport, setDismissedReport] = useState<ResolveReport | null>(null);

  // WebSocket connection for real-time logs
  const wsUrl = `${window.location.protocol === 'https:' ? 'wss' : 'ws'}://${window.location.host}/ws`;
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
        addLog({ run_id: runId, node_id: String(payload.node_id), level: 'info', message: `Node start [${payload.progress}] ${payload.node_type}`, timestamp: ts });
      } else if (data.type === 'node_complete') {
        updateNodeRunStatus(runId, String(payload.node_id), 'completed');
        addLog({ run_id: runId, node_id: String(payload.node_id), level: 'success', message: `Node completed`, timestamp: ts });
      } else if (data.type === 'node_error') {
        updateNodeRunStatus(runId, String(payload.node_id), 'error', String(payload.error || 'Node error'));
        addLog({ run_id: runId, node_id: String(payload.node_id), level: 'error', message: `Node error: ${payload.error}`, timestamp: ts });
      } else if (data.type === 'node_skip') {
        updateNodeRunStatus(runId, String(payload.node_id), 'skipped');
        addLog({ run_id: runId, node_id: String(payload.node_id), level: 'warn', message: `Node skipped (${payload.reason})`, timestamp: ts });
      } else if (data.type === 'node_bypass') {
        updateNodeRunStatus(runId, String(payload.node_id), 'skipped');
        addLog({ run_id: runId, node_id: String(payload.node_id), level: 'warn', message: `Node bypassed`, timestamp: ts });
      } else if (data.type === 'node_cache_hit') {
        updateNodeRunStatus(runId, String(payload.node_id), 'cached');
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
    updateActive({ nodes });
  }, [updateActive]);

  const handleEdgesChange = useCallback((edges: Workflow['edges']) => {
    if (bridgeRef.current) {
      bridgeRef.current.onEdgesChanged(edges);
    }
    pendingStateRef.current = { ...pendingStateRef.current, edges };
    updateActive({ edges });
  }, [updateActive]);

  const handleGroupsChange = useCallback((groups: Workflow['groups']) => {
    if (bridgeRef.current) {
      bridgeRef.current.onGroupsChanged(groups);
    }
    pendingStateRef.current = { ...pendingStateRef.current, groups };
    updateActive({ groups });
  }, [updateActive]);

  const handleRun = useCallback(async () => {
    setIsRunning(true);
    try {
      await validate(activeWorkflow);
      const result = await submitRun(activeWorkflow, { no_cache: !cacheEnabled });
      // Add to local runs so it appears in console immediately
      addRun({
        run_id: result.run_id,
        status: 'pending',
        workflow_name: result.workflow_name || activeWorkflow.name || 'Untitled',
        node_statuses: [],
        node_outputs: {},
        execution_plan: [],
        previews: {},
        artifacts: {},
        start_time: new Date().toISOString(),
      });
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
  }, [activeWorkflow, validate, submitRun, cacheEnabled, addLog, addRun]);

  const handleToggleQueue = useCallback(() => {
    const isVisible = consoleVisible || railTab === 'console';
    if (isVisible) {
      setConsoleVisible(false);
      if (railTab === 'console') setRailTab(null);
    } else {
      setConsoleVisible(true);
      setRailTab('console');
    }
  }, [consoleVisible, railTab]);

  const handleLoadTemplate = useCallback(async (template: TemplateInfo) => {
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
    // Auto-fit view after nodes render
    requestAnimationFrame(() => {
      requestAnimationFrame(() => canvasRef.current?.fitView());
    });
    // Resolve is auto-triggered by the activeWorkflow useEffect
  }, [activeIndex, activeWorkflowId, addWorkflow, collabDoc, collabEnabled, publishCollabWorkflowSnapshot, updateWorkflow]);

  const handleImport = useCallback((wf: Workflow) => {
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
    // Auto-fit view after nodes render
    requestAnimationFrame(() => {
      requestAnimationFrame(() => canvasRef.current?.fitView());
    });
    // Resolve is auto-triggered by the activeWorkflow useEffect
  }, [activeIndex, activeWorkflowId, addWorkflow, collabDoc, collabEnabled, publishCollabWorkflowSnapshot, updateWorkflow]);

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

  // Keyboard shortcuts
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return;

      const key = e.key.toLowerCase();
      const isCtrl = e.ctrlKey || e.metaKey;

      if (isCtrl && key === 'f') { e.preventDefault(); setRailTab('nodes'); }
      else if (isCtrl && key === 'r') { e.preventDefault(); handleRun(); }
      else if (isCtrl && key === 'e') { e.preventDefault(); setShowExport(true); }
      else if (isCtrl && key === 'i') { e.preventDefault(); setShowImport(true); }
      else if (isCtrl && key === ',') { e.preventDefault(); setRailTab(prev => prev === 'settings' ? null : 'settings'); }
      else if (isCtrl && key === '`') { e.preventDefault(); setConsoleVisible(v => !v); }
      else if (isCtrl && key >= '1' && key <= '7') {
        e.preventDefault();
        const tabs: RailTab[] = ['data', 'nodes', 'templates', 'environments', 'hpc', 'help', 'console'];
        const idx = parseInt(key) - 1;
        setRailTab(prev => prev === tabs[idx] ? null : tabs[idx]);
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [handleRun]);

  // Auto-validate and resolve on workflow change
  useEffect(() => {
    if (latestWorkflowRef.current.nodes.length === 0) {
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
  ].filter(Boolean).join(' ')), [consoleVisible, railTab, showAI, showComments]);
  return (
    <div className={appShellClassName}>
      <TopBar
        validationValid={validation.valid}
        validationErrors={validation.errors}
        onRun={handleRun}
        onExport={() => setShowExport(true)}
        onImport={() => setShowImport(true)}
        onAI={() => setShowAI(true)}
        hpcStatus={hpcStatus}
        isRunning={isRunning}
        queueCount={queueCount}
        onToggleQueue={handleToggleQueue}
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
            onShare={() => setShowShareDialog(true)}
            onFollow={followPresenceUser}
            onOpenComments={() => setShowComments(v => !v)}
            onOpenVersions={() => setShowVersions(v => !v)}
            onOpenAudit={() => setShowAudit(v => !v)}
            onOpenSettings={() => setRailTab('settings')}
            reconnectAttempt={collabReconnectAttempt}
            error={collabError}
            offline={collabOffline || !collabEnabled}
          />
        )}
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
        onClose={closeTab}
        onAdd={addTab}
        onRename={handleRenameTab}
        onDuplicate={handleDuplicateTab}
        onReorder={handleReorderTabs}
      />

      <LeftRail active={railTab} onChange={setRailTab} />

      <div
        className="main-canvas"
        onDragOver={(e) => {
          if (e.dataTransfer.types.includes('application/bionodulo-workflow-path')) {
            e.preventDefault();
            e.dataTransfer.dropEffect = 'copy';
          }
        }}
        onDrop={async (e) => {
          e.preventDefault();
          const path = e.dataTransfer.getData('application/bionodulo-workflow-path');
          if (!path) return;
          try {
            const r = await fetch(`/api/workspace/file?path=${encodeURIComponent(path)}`);
            if (!r.ok) return;
            const text = await r.text();
            const wf = JSON.parse(text);
            if (wf && (wf.nodes || Array.isArray(wf))) {
              handleImport(wf);
            }
          } catch { /* ignore */ }
        }}
      >
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
          missingDependencyNodeIds={missingDependencyNodeIds}
          nodeCommentsMap={nodeCommentsMap}
          nodeComments={workflowComments}
          collabWorkflowId={collabEnabled ? activeWorkflowId : undefined}
          currentCollabUser={collabEnabled ? currentUser : undefined}
          onNodeCommentsChange={() => void fetchWorkflowComments()}
          collabUsers={canvasCollabUsers}
          nodePreviewsMap={nodePreviewsMap}
          onCollabCursor={collabEnabled ? setCollabCursor : undefined}
          onViewportChange={collabEnabled ? publishCollabViewport : undefined}
          onCollabSelection={(selection) => {
            setSelectedNodeId(selection.nodeIds[0] ?? null);
            setCollabSelection(selection);
          }}
          onCollabNodeMove={collabEnabled ? publishCollabNodeMove : undefined}
          onCollabDragStart={collabEnabled ? handleCollabDragStart : undefined}
          onCollabDragEnd={collabEnabled ? handleCollabDragEnd : undefined}
        />

        {/* Rail panels */}
        {railTab === 'settings' && <SettingsPanel onClose={() => setRailTab(null)} />}
        {railTab === 'help' && <HelpWikiPanel onClose={() => setRailTab(null)} />}
        {railTab === 'templates' && <TemplatesPanel onClose={() => setRailTab(null)} onLoadTemplate={handleLoadTemplate} />}
        {railTab === 'environments' && (
          <EnvironmentPanel onClose={() => setRailTab(null)} currentWorkflow={activeWorkflow} />
        )}
        {railTab === 'hpc' && (
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
            onClose={() => setRailTab(null)}
          />
        )}
        {railTab === 'nodes' && <NodeLibraryPanel objectInfo={objectInfo} onAddNode={(meta) => {
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
        }} onClose={() => setRailTab(null)} />}
        {railTab === 'data' && (
          <WorkspacePanel
            onClose={() => setRailTab(null)}
            onOpenSettings={() => setRailTab('settings')}
            onImportWorkflow={handleImport}
          />
        )}

        <HardwareMonitor />
        {(consoleVisible || railTab === 'console') && (
          <ErrorBoundary>
            <BottomConsole
              logs={logs}
              queue={queuedRuns}
              history={runs}
              onClose={() => { setConsoleVisible(false); if (railTab === 'console') setRailTab(null); }}
              onOpenLightbox={openLightbox}
              onClearLogs={clearLogs}
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
      {showAI && (
        <AIWorkflowModal
          workflow={activeWorkflow}
          onClose={() => setShowAI(false)}
          onApplyWorkflow={handleApplyWorkflow}
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
        />
      )}
      <ImageLightbox
        images={lightboxImages}
        initialIndex={lightboxIndex}
        isOpen={lightboxOpen}
        onClose={() => setLightboxOpen(false)}
      />

    </div>
  );
}
