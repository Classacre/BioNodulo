import type * as Y from 'yjs';

export interface CollabUser {
  id: string;
  name: string;
  color: string;
  avatar?: string;
}

export interface AuthUser {
  id: string;
  name: string;
  color: string;
}

export interface AwarenessState {
  user: CollabUser;
  cursor: { x: number; y: number; visible: boolean } | null;
  selection: { nodeIds: string[] };
  viewport?: { x: number; y: number; scale: number };
  activity: 'active' | 'idle' | 'dragging' | 'typing';
  dragOwnership?: { nodeId: string; startedAt: number } | null;
  timestamp: number;
}

/** Legacy JSON message types for backward compatibility */
export interface CollabMessage {
  type: 'sync' | 'update' | 'awareness';
  payload: unknown;
}

export interface SyncPayload {
  nodes?: Record<string, unknown>;
  edges?: Record<string, unknown>;
  groups?: Record<string, unknown>;
  meta?: Record<string, unknown>;
  viewport?: Record<string, unknown>;
}

export interface UpdatePayload {
  nodes?: Record<string, unknown>;
  edges?: Record<string, unknown>;
  groups?: Record<string, unknown>;
  removedNodes?: string[];
  removedEdges?: string[];
  removedGroups?: string[];
}

export interface AwarenessPayload {
  clientId: number;
  state: AwarenessState | null;
}

export interface CollabState {
  doc: Y.Doc | null;
  connected: boolean;
  connecting: boolean;
  reconnectAttempt: number;
  activeUsers: AwarenessState[];
  error: string | null;
}

export interface Comment {
  id: string;
  workflow_id: string;
  node_id: string | null;
  user_id: string;
  user_name: string;
  user_color: string;
  content: string;
  parent_id: string | null;
  resolved: boolean;
  created_at: string;
  updated_at: string;
  replies: Comment[];
}

export interface WorkflowVersion {
  id: string;
  workflow_id: string;
  user_id: string;
  user_name: string;
  name: string | null;
  auto_save: boolean;
  node_count: number;
  edge_count: number;
  created_at: string;
}

export interface WorkflowTemplate {
  id: string;
  workflow_id: string;
  user_id: string;
  title: string;
  description: string;
  tags: string;
  is_public: boolean;
  fork_count: number;
  created_at: string;
}

export interface AuditEntry {
  id: string;
  workflow_id: string;
  user_id: string;
  user_name: string;
  action: string;
  target_type: string;
  target_id: string;
  payload: Record<string, unknown>;
  performed_at: string;
}

export interface VersionDiffSummary {
  id: string;
  name: string | null;
  created_at?: string;
}

export interface VersionDiffResult {
  version_a?: VersionDiffSummary;
  version_b?: VersionDiffSummary;
  nodes: {
    added: string[];
    removed: string[];
    modified?: string[];
    common?: string[];
  };
  edges: {
    added: string[];
    removed: string[];
    modified?: string[];
    common?: string[];
  };
  groups?: {
    added: string[];
    removed: string[];
    modified?: string[];
    common?: string[];
  };
  meta_changes: Record<string, { before: unknown; after: unknown }>;
}
