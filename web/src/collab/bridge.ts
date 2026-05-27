import * as Y from 'yjs';
import type { WorkflowNode, WorkflowEdge, WorkflowGroup } from '../types';
import { serializeNode, deserializeNode, serializeEdge, deserializeEdge, serializeGroup, deserializeGroup } from './yjsDoc';

function serializedValuesEqual(a: unknown, b: unknown): boolean {
  try {
    return JSON.stringify(a) === JSON.stringify(b);
  } catch {
    return false;
  }
}

interface BridgeCallbacks {
  onNodesChange: (nodes: WorkflowNode[]) => void;
  onEdgesChange: (edges: WorkflowEdge[]) => void;
  onGroupsChange: (groups: WorkflowGroup[]) => void;
  getNodes: () => WorkflowNode[];
  getEdges: () => WorkflowEdge[];
  getGroups: () => WorkflowGroup[];
  onDragStart?: (nodeId: string) => void;
  onDragEnd?: () => void;
}

export class LiteGraphYjsBridge {
  private _isApplyingRemote = false;
  private _isDragging = false;
  private _draggingNodeIds: Set<string> = new Set();
  private _pendingRemotePositions: Map<string, [number, number]> = new Map();
  private _positionThrottleTimer: ReturnType<typeof setTimeout> | null = null;
  private _pendingPositionUpdates: Map<string, WorkflowNode> = new Map();
  private _unsubscribers: (() => void)[] = [];

  constructor(
    private ydoc: Y.Doc,
    private callbacks: BridgeCallbacks,
  ) {}

  bind() {
    const yNodes = this.ydoc.getMap('nodes');
    const yEdges = this.ydoc.getMap('edges');
    const yGroups = this.ydoc.getMap('groups');

    const nodesHandler = (event: Y.YMapEvent<unknown>) => this._onYjsNodesChange(event, yNodes);
    const edgesHandler = (event: Y.YMapEvent<unknown>) => this._onYjsEdgesChange(event, yEdges);
    const groupsHandler = (event: Y.YMapEvent<unknown>) => this._onYjsGroupsChange(event, yGroups);

    yNodes.observe(nodesHandler);
    yEdges.observe(edgesHandler);
    yGroups.observe(groupsHandler);

    this._unsubscribers.push(
      () => yNodes.unobserve(nodesHandler),
      () => yEdges.unobserve(edgesHandler),
      () => yGroups.unobserve(groupsHandler),
    );

  }

  unbind() {
    this._unsubscribers.forEach(fn => fn());
    this._unsubscribers = [];
    if (this._positionThrottleTimer) {
      clearTimeout(this._positionThrottleTimer);
      this._positionThrottleTimer = null;
    }
  }

  // Local changes from canvas → Yjs
  onNodeAdded(node: WorkflowNode) {
    if (this._isApplyingRemote) return;
    const yNodes = this.ydoc.getMap('nodes');
    this.ydoc.transact(() => {
      yNodes.set(node.id, serializeNode(node));
    }, 'local');
  }

  onNodeRemoved(nodeId: string) {
    if (this._isApplyingRemote) return;
    const yNodes = this.ydoc.getMap('nodes');
    this.ydoc.transact(() => {
      yNodes.delete(nodeId);
    }, 'local');
  }

  onNodeMoved(nodeId: string, pos: [number, number]) {
    if (this._isApplyingRemote) return;
    // Throttle position updates during drag to ~20Hz so collaborators see
    // motion without flooding the socket with every pointer event.
    const currentNodes = this.callbacks.getNodes();
    const node = currentNodes.find(n => n.id === nodeId);
    if (!node) return;
    const updated = { ...node, position: pos };
    this._pendingPositionUpdates.set(nodeId, updated);

    if (this._positionThrottleTimer) return; // already throttling
    this._positionThrottleTimer = setTimeout(() => {
      this._positionThrottleTimer = null;
      if (this._pendingPositionUpdates.size === 0) return;
      const yNodes = this.ydoc.getMap('nodes');
      this.ydoc.transact(() => {
        this._pendingPositionUpdates.forEach((n, id) => {
          yNodes.set(id, serializeNode(n));
        });
      }, 'local');
      this._pendingPositionUpdates.clear();
    }, 50);
  }

  onNodesChanged(nodes: WorkflowNode[]) {
    if (this._isApplyingRemote) return;
    const yNodes = this.ydoc.getMap('nodes');
    const currentIds = new Set(nodes.map(n => n.id));
    this.ydoc.transact(() => {
      nodes.forEach(node => {
        const serialized = serializeNode(node);
        if (!serializedValuesEqual(yNodes.get(node.id), serialized)) {
          yNodes.set(node.id, serialized);
        }
      });
      yNodes.forEach((_, key) => {
        if (!currentIds.has(key)) yNodes.delete(key);
      });
    }, 'local');
  }

  onEdgeAdded(edge: WorkflowEdge) {
    if (this._isApplyingRemote) return;
    const yEdges = this.ydoc.getMap('edges');
    this.ydoc.transact(() => {
      yEdges.set(edge.id, serializeEdge(edge));
    }, 'local');
  }

  onEdgeRemoved(edgeId: string) {
    if (this._isApplyingRemote) return;
    const yEdges = this.ydoc.getMap('edges');
    this.ydoc.transact(() => {
      yEdges.delete(edgeId);
    }, 'local');
  }

  onEdgesChanged(edges: WorkflowEdge[]) {
    if (this._isApplyingRemote) return;
    const yEdges = this.ydoc.getMap('edges');
    const currentIds = new Set(edges.map(e => e.id));
    this.ydoc.transact(() => {
      edges.forEach(edge => {
        const serialized = serializeEdge(edge);
        if (!serializedValuesEqual(yEdges.get(edge.id), serialized)) {
          yEdges.set(edge.id, serialized);
        }
      });
      yEdges.forEach((_, key) => {
        if (!currentIds.has(key)) yEdges.delete(key);
      });
    }, 'local');
  }

  onGroupAdded(group: WorkflowGroup) {
    if (this._isApplyingRemote) return;
    const yGroups = this.ydoc.getMap('groups');
    this.ydoc.transact(() => {
      yGroups.set(group.id, serializeGroup(group));
    }, 'local');
  }

  onGroupRemoved(groupId: string) {
    if (this._isApplyingRemote) return;
    const yGroups = this.ydoc.getMap('groups');
    this.ydoc.transact(() => {
      yGroups.delete(groupId);
    }, 'local');
  }

  onGroupsChanged(groups: WorkflowGroup[]) {
    if (this._isApplyingRemote) return;
    const yGroups = this.ydoc.getMap('groups');
    const currentIds = new Set(groups.map(g => g.id));
    this.ydoc.transact(() => {
      groups.forEach(group => {
        const serialized = serializeGroup(group);
        if (!serializedValuesEqual(yGroups.get(group.id), serialized)) {
          yGroups.set(group.id, serialized);
        }
      });
      yGroups.forEach((_, key) => {
        if (!currentIds.has(key)) yGroups.delete(key);
      });
    }, 'local');
  }

  onDragStart(_nodeId: string) {
    this._isDragging = true;
    this._draggingNodeIds.add(_nodeId);
    this.callbacks.onDragStart?.(_nodeId);
  }

  onDragEnd() {
    this._isDragging = false;
    this.callbacks.onDragEnd?.();
    // Flush any pending position updates immediately
    if (this._positionThrottleTimer) {
      clearTimeout(this._positionThrottleTimer);
      this._positionThrottleTimer = null;
    }
    if (this._pendingPositionUpdates.size > 0) {
      const yNodes = this.ydoc.getMap('nodes');
      this.ydoc.transact(() => {
        this._pendingPositionUpdates.forEach((n, id) => {
          yNodes.set(id, serializeNode(n));
        });
      }, 'local');
      this._pendingPositionUpdates.clear();
    }
    // Apply any pending remote positions that arrived during drag
    const currentNodes = this.callbacks.getNodes();
    if (this._pendingRemotePositions.size > 0 && currentNodes.length > 0) {
      const nextNodes = currentNodes.map(n => {
        const pos = this._pendingRemotePositions.get(n.id);
        if (pos && !this._draggingNodeIds.has(n.id)) {
          return { ...n, position: pos };
        }
        return n;
      });
      this._pendingRemotePositions.clear();
      this.callbacks.onNodesChange(nextNodes);
    }
    this._draggingNodeIds.clear();
  }

  // Yjs → React state (remote changes)
  private _onYjsNodesChange(event: Y.YMapEvent<unknown>, yNodes: Y.Map<unknown>) {
    // Canvas handlers already applied our own Yjs writes to React state.
    // Replaying them while a node is being dragged can restore an older
    // throttled position over the pointer position.
    if (this._isApplyingRemote || event.transaction.origin === 'local') return;
    this._isApplyingRemote = true;
    try {
      const currentNodes = this.callbacks.getNodes();
      const nodeMap = new Map(currentNodes.map(n => [n.id, n]));

      event.changes.keys.forEach((change, key) => {
        if (change.action === 'add' || change.action === 'update') {
          const raw = yNodes.get(key);
          if (raw === undefined) return;
          try {
            const nodeData = deserializeNode(raw);
            const existing = nodeMap.get(key);
            if (existing) {
              // Preserve the pointer-owned position for the node currently
              // being dragged, but still accept other remote node changes.
              if (this._isDragging && this._draggingNodeIds.has(key)) {
                this._pendingRemotePositions.set(key, nodeData.position);
                nodeMap.set(key, { ...existing, ...nodeData, position: existing.position, id: key });
              } else {
                nodeMap.set(key, { ...existing, ...nodeData, id: key });
              }
            } else {
              nodeMap.set(key, nodeData);
            }
          } catch { /* skip invalid */ }
        } else if (change.action === 'delete') {
          nodeMap.delete(key);
        }
      });

      this.callbacks.onNodesChange(Array.from(nodeMap.values()));
    } finally {
      this._isApplyingRemote = false;
    }
  }

  private _onYjsEdgesChange(event: Y.YMapEvent<unknown>, yEdges: Y.Map<unknown>) {
    if (this._isApplyingRemote || event.transaction.origin === 'local') return;
    this._isApplyingRemote = true;
    try {
      const currentEdges = this.callbacks.getEdges();
      const edgeMap = new Map(currentEdges.map(e => [e.id, e]));

      event.changes.keys.forEach((change, key) => {
        if (change.action === 'add' || change.action === 'update') {
          const raw = yEdges.get(key);
          if (raw === undefined) return;
          try {
            edgeMap.set(key, deserializeEdge(raw));
          } catch { /* skip invalid */ }
        } else if (change.action === 'delete') {
          edgeMap.delete(key);
        }
      });

      this.callbacks.onEdgesChange(Array.from(edgeMap.values()));
    } finally {
      this._isApplyingRemote = false;
    }
  }

  private _onYjsGroupsChange(event: Y.YMapEvent<unknown>, yGroups: Y.Map<unknown>) {
    if (this._isApplyingRemote || event.transaction.origin === 'local') return;
    this._isApplyingRemote = true;
    try {
      const currentGroups = this.callbacks.getGroups();
      const groupMap = new Map(currentGroups.map(g => [g.id, g]));

      event.changes.keys.forEach((change, key) => {
        if (change.action === 'add' || change.action === 'update') {
          const raw = yGroups.get(key);
          if (raw === undefined) return;
          try {
            groupMap.set(key, deserializeGroup(raw));
          } catch { /* skip invalid */ }
        } else if (change.action === 'delete') {
          groupMap.delete(key);
        }
      });

      this.callbacks.onGroupsChange(Array.from(groupMap.values()));
    } finally {
      this._isApplyingRemote = false;
    }
  }
}
