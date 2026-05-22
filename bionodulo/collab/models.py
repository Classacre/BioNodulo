"""SQLite schema and dataclasses for collaborative editing persistence.

Uses SQLite by default for simplicity (BioNodulo already uses file-based
storage). All tables are created lazily on first access.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Dataclasses (used for in-memory representation)
# ---------------------------------------------------------------------------


@dataclass
class WorkflowShare:
    """Represents a workflow sharing invitation / permission grant."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    workflow_id: str = ""
    user_id: str = ""
    role: str = "viewer"  # owner | editor | viewer | commenter
    invited_by: str = ""
    invited_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    accepted_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "workflow_id": self.workflow_id,
            "user_id": self.user_id,
            "role": self.role,
            "invited_by": self.invited_by,
            "invited_at": self.invited_at,
            "accepted_at": self.accepted_at,
        }


@dataclass
class CollabRoom:
    """Represents an active collaboration room session."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    workflow_id: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    last_activity_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    active_users: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "workflow_id": self.workflow_id,
            "created_at": self.created_at,
            "last_activity_at": self.last_activity_at,
            "active_users": self.active_users,
        }


@dataclass
class CollabAuditLogEntry:
    """Represents a single audit log entry for compliance tracking."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    workflow_id: str = ""
    user_id: str = ""
    action: str = ""  # e.g. node_add, node_delete, node_move, edge_add
    target_type: str | None = None  # node | edge | group
    target_id: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)
    performed_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "workflow_id": self.workflow_id,
            "user_id": self.user_id,
            "action": self.action,
            "target_type": self.target_type,
            "target_id": self.target_id,
            "payload": self.payload,
            "performed_at": self.performed_at,
        }


# ---------------------------------------------------------------------------
# Phase 3 dataclasses — Comments, Versions, Templates
# ---------------------------------------------------------------------------


@dataclass
class Comment:
    """Represents a comment or reply on a workflow or node.

    The ``replies`` field is populated server-side when listing comments
    to build a threaded view. It is not persisted in the database.
    """

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    workflow_id: str = ""
    node_id: str | None = None
    user_id: str = ""
    user_name: str = ""
    user_color: str = ""
    content: str = ""
    parent_id: str | None = None
    resolved: bool = False
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    replies: list[Comment] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "workflow_id": self.workflow_id,
            "node_id": self.node_id,
            "user_id": self.user_id,
            "user_name": self.user_name,
            "user_color": self.user_color,
            "content": self.content,
            "parent_id": self.parent_id,
            "resolved": self.resolved,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "replies": [r.to_dict() for r in self.replies],
        }


@dataclass
class WorkflowVersion:
    """Represents a saved snapshot of a workflow document state."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    workflow_id: str = ""
    user_id: str = ""
    user_name: str = ""
    snapshot: dict[str, Any] | bytes = field(default_factory=dict)
    name: str | None = None
    auto_save: bool = True
    node_count: int = 0
    edge_count: int = 0
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "workflow_id": self.workflow_id,
            "user_id": self.user_id,
            "user_name": self.user_name,
            "name": self.name,
            "auto_save": self.auto_save,
            "node_count": self.node_count,
            "edge_count": self.edge_count,
            "created_at": self.created_at,
        }


@dataclass
class WorkflowTemplate:
    """Represents a shareable workflow template."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    workflow_id: str = ""
    user_id: str = ""
    title: str = ""
    description: str = ""
    tags: str = ""
    snapshot: dict[str, Any] | bytes = field(default_factory=dict)
    is_public: bool = False
    fork_count: int = 0
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "workflow_id": self.workflow_id,
            "user_id": self.user_id,
            "title": self.title,
            "description": self.description,
            "tags": self.tags,
            "is_public": self.is_public,
            "fork_count": self.fork_count,
            "created_at": self.created_at,
        }


# ---------------------------------------------------------------------------
# SQL schema constants
# ---------------------------------------------------------------------------

_SQL_SCHEMA = """
CREATE TABLE IF NOT EXISTS workflow_shares (
    id TEXT PRIMARY KEY,
    workflow_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    role TEXT NOT NULL CHECK(role IN ('owner','editor','viewer','commenter')),
    invited_by TEXT,
    invited_at TEXT NOT NULL,
    accepted_at TEXT,
    UNIQUE(workflow_id, user_id)
);

CREATE TABLE IF NOT EXISTS collab_rooms (
    id TEXT PRIMARY KEY,
    workflow_id TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL,
    last_activity_at TEXT NOT NULL,
    active_users INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS collab_audit_log (
    id TEXT PRIMARY KEY,
    workflow_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    action TEXT NOT NULL,
    target_type TEXT,
    target_id TEXT,
    payload TEXT,  -- JSON
    performed_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_shares_workflow ON workflow_shares(workflow_id);
CREATE INDEX IF NOT EXISTS idx_audit_workflow ON collab_audit_log(workflow_id);
"""

# Phase 3 schema — comments, versions, templates
_PHASE3_SQL_SCHEMA = """
CREATE TABLE IF NOT EXISTS comments (
    id TEXT PRIMARY KEY,
    workflow_id TEXT NOT NULL,
    node_id TEXT,
    user_id TEXT NOT NULL,
    user_name TEXT NOT NULL,
    user_color TEXT,
    content TEXT NOT NULL,
    parent_id TEXT,
    resolved BOOLEAN DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (parent_id) REFERENCES comments(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_comments_workflow ON comments(workflow_id);
CREATE INDEX IF NOT EXISTS idx_comments_node ON comments(node_id);

CREATE TABLE IF NOT EXISTS workflow_versions (
    id TEXT PRIMARY KEY,
    workflow_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    user_name TEXT,
    snapshot BLOB NOT NULL,
    name TEXT,
    auto_save BOOLEAN DEFAULT 1,
    node_count INTEGER,
    edge_count INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_versions_workflow ON workflow_versions(workflow_id);
CREATE INDEX IF NOT EXISTS idx_versions_created ON workflow_versions(created_at);

CREATE TABLE IF NOT EXISTS workflow_templates (
    id TEXT PRIMARY KEY,
    workflow_id TEXT,
    user_id TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT,
    tags TEXT,
    snapshot BLOB NOT NULL,
    is_public BOOLEAN DEFAULT 0,
    fork_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_templates_public ON workflow_templates(is_public);
"""


# ---------------------------------------------------------------------------
# SQLite-backed store
# ---------------------------------------------------------------------------

class CollabStore:
    """SQLite-backed store for collaboration metadata.

    Lazily initialises the database on first access. Thread-safe for
    read operations; write operations should be sequenced by the caller
    (the RoomManager runs on a single event-loop thread).
    """

    def __init__(self, db_path: Path | str = ":memory:") -> None:
        self.db_path = str(db_path)
        self._connection: sqlite3.Connection | None = None

    def _conn(self) -> sqlite3.Connection:
        if self._connection is None:
            self._connection = sqlite3.connect(self.db_path, check_same_thread=False)
            self._connection.row_factory = sqlite3.Row
            self._connection.executescript(_SQL_SCHEMA)
            self._connection.commit()
        return self._connection

    # ------------------------------------------------------------------
    # Workflow shares
    # ------------------------------------------------------------------

    def add_share(self, share: WorkflowShare) -> WorkflowShare:
        """Insert a new workflow share record."""
        conn = self._conn()
        conn.execute(
            """
            INSERT OR REPLACE INTO workflow_shares
            (id, workflow_id, user_id, role, invited_by, invited_at, accepted_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                share.id,
                share.workflow_id,
                share.user_id,
                share.role,
                share.invited_by,
                share.invited_at,
                share.accepted_at,
            ),
        )
        conn.commit()
        return share

    def list_shares(self, workflow_id: str) -> list[WorkflowShare]:
        """Return all shares for a given workflow."""
        conn = self._conn()
        rows = conn.execute(
            "SELECT * FROM workflow_shares WHERE workflow_id = ?",
            (workflow_id,),
        ).fetchall()
        return [WorkflowShare(**dict(row)) for row in rows]

    def list_workflow_ids_for_user(self, user_id: str) -> list[str]:
        """Return workflow IDs that have been shared with a user."""
        conn = self._conn()
        rows = conn.execute(
            "SELECT workflow_id FROM workflow_shares WHERE user_id = ?",
            (user_id,),
        ).fetchall()
        return [str(row["workflow_id"]) for row in rows]

    def get_share(self, share_id: str) -> WorkflowShare | None:
        """Return a single share by ID."""
        conn = self._conn()
        row = conn.execute(
            "SELECT * FROM workflow_shares WHERE id = ?",
            (share_id,),
        ).fetchone()
        if row is None:
            return None
        return WorkflowShare(**dict(row))

    def delete_share(self, share_id: str) -> bool:
        """Revoke a share. Returns True if a row was deleted."""
        conn = self._conn()
        cursor = conn.execute(
            "DELETE FROM workflow_shares WHERE id = ?",
            (share_id,),
        )
        conn.commit()
        return cursor.rowcount > 0

    def get_user_role(self, workflow_id: str, user_id: str) -> str | None:
        """Return the role for a user on a workflow, or None."""
        conn = self._conn()
        row = conn.execute(
            "SELECT role FROM workflow_shares WHERE workflow_id = ? AND user_id = ?",
            (workflow_id, user_id),
        ).fetchone()
        if row is None:
            return None
        return row["role"]

    # ------------------------------------------------------------------
    # Collab rooms
    # ------------------------------------------------------------------

    def upsert_room(self, room: CollabRoom) -> CollabRoom:
        """Insert or update a collab room record."""
        conn = self._conn()
        conn.execute(
            """
            INSERT INTO collab_rooms (id, workflow_id, created_at, last_activity_at, active_users)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(workflow_id) DO UPDATE SET
                last_activity_at = excluded.last_activity_at,
                active_users = excluded.active_users
            """,
            (room.id, room.workflow_id, room.created_at, room.last_activity_at, room.active_users),
        )
        conn.commit()
        return room

    def get_room(self, workflow_id: str) -> CollabRoom | None:
        """Return the room record for a workflow, if any."""
        conn = self._conn()
        row = conn.execute(
            "SELECT * FROM collab_rooms WHERE workflow_id = ?",
            (workflow_id,),
        ).fetchone()
        if row is None:
            return None
        return CollabRoom(**dict(row))

    def delete_room(self, workflow_id: str) -> bool:
        """Delete a room record."""
        conn = self._conn()
        cursor = conn.execute(
            "DELETE FROM collab_rooms WHERE workflow_id = ?",
            (workflow_id,),
        )
        conn.commit()
        return cursor.rowcount > 0

    # ------------------------------------------------------------------
    # Audit log
    # ------------------------------------------------------------------

    def add_audit_entry(self, entry: CollabAuditLogEntry) -> CollabAuditLogEntry:
        """Append an audit log entry."""
        conn = self._conn()
        conn.execute(
            """
            INSERT INTO collab_audit_log
            (id, workflow_id, user_id, action, target_type, target_id, payload, performed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                entry.id,
                entry.workflow_id,
                entry.user_id,
                entry.action,
                entry.target_type,
                entry.target_id,
                json.dumps(entry.payload),
                entry.performed_at,
            ),
        )
        conn.commit()
        return entry

    def list_audit_entries(self, workflow_id: str, limit: int = 100) -> list[CollabAuditLogEntry]:
        """Return recent audit log entries for a workflow."""
        conn = self._conn()
        rows = conn.execute(
            "SELECT * FROM collab_audit_log WHERE workflow_id = ? ORDER BY performed_at DESC LIMIT ?",
            (workflow_id, limit),
        ).fetchall()
        result: list[CollabAuditLogEntry] = []
        for row in rows:
            d = dict(row)
            d["payload"] = json.loads(d.get("payload", "{}"))
            result.append(CollabAuditLogEntry(**d))
        return result

    # ------------------------------------------------------------------
    # Phase 3 table management
    # ------------------------------------------------------------------

    def _ensure_phase3_tables(self) -> None:
        """Create Phase 3 tables (comments, versions, templates) if absent.

        Idempotent — safe to call multiple times.
        """
        conn = self._conn()
        conn.executescript(_PHASE3_SQL_SCHEMA)
        conn.commit()

    # ---- Comments ----

    def add_comment(self, comment: Comment) -> Comment:
        """Add a comment and return the persisted dataclass."""
        self._ensure_phase3_tables()
        c = self._conn()
        if not comment.created_at:
            comment.created_at = datetime.now(timezone.utc).isoformat()
        if not comment.updated_at:
            comment.updated_at = comment.created_at
        c.execute(
            """
            INSERT INTO comments
            (id, workflow_id, node_id, user_id, user_name, user_color,
             content, parent_id, resolved, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                comment.id,
                comment.workflow_id,
                comment.node_id,
                comment.user_id,
                comment.user_name,
                comment.user_color,
                comment.content,
                comment.parent_id,
                1 if comment.resolved else 0,
                comment.created_at,
                comment.updated_at,
            ),
        )
        c.commit()
        return comment

    def get_comment(self, comment_id: str) -> Comment | None:
        self._ensure_phase3_tables()
        c = self._conn()
        row = c.execute("SELECT * FROM comments WHERE id = ?", (comment_id,)).fetchone()
        return self._row_to_comment(row) if row else None

    def list_comments(self, workflow_id: str, node_id: str | None = None) -> list[Comment]:
        """List comments for a workflow, nesting replies under top-level comments."""
        self._ensure_phase3_tables()
        c = self._conn()
        if node_id is None:
            rows = c.execute(
                "SELECT * FROM comments WHERE workflow_id = ? ORDER BY created_at ASC",
                (workflow_id,),
            ).fetchall()
        else:
            rows = c.execute(
                """
                SELECT * FROM comments
                WHERE workflow_id = ? AND (node_id = ? OR parent_id IN (
                    SELECT id FROM comments WHERE workflow_id = ? AND node_id = ?
                ))
                ORDER BY created_at ASC
                """,
                (workflow_id, node_id, workflow_id, node_id),
            ).fetchall()
        return self._nest_comments([self._row_to_comment(row) for row in rows])

    def list_comments_for_workflow(self, workflow_id: str) -> list[Comment]:
        return self.list_comments(workflow_id)

    def list_comments_for_node(self, workflow_id: str, node_id: str) -> list[Comment]:
        return self.list_comments(workflow_id, node_id=node_id)

    def update_comment(self, comment_id: str, content: str) -> Comment | None:
        self._ensure_phase3_tables()
        c = self._conn()
        now = datetime.now(timezone.utc).isoformat()
        cursor = c.execute("UPDATE comments SET content = ?, updated_at = ? WHERE id = ?", (content, now, comment_id))
        c.commit()
        if cursor.rowcount == 0:
            return None
        return self.get_comment(comment_id)

    def resolve_comment(self, comment_id: str) -> Comment | None:
        self._ensure_phase3_tables()
        c = self._conn()
        now = datetime.now(timezone.utc).isoformat()
        cursor = c.execute(
            "UPDATE comments SET resolved = 1, updated_at = ? WHERE id = ?",
            (now, comment_id),
        )
        c.commit()
        if cursor.rowcount == 0:
            return None
        return self.get_comment(comment_id)

    def unresolve_comment(self, comment_id: str) -> Comment | None:
        self._ensure_phase3_tables()
        c = self._conn()
        now = datetime.now(timezone.utc).isoformat()
        cursor = c.execute(
            "UPDATE comments SET resolved = 0, updated_at = ? WHERE id = ?",
            (now, comment_id),
        )
        c.commit()
        if cursor.rowcount == 0:
            return None
        return self.get_comment(comment_id)

    def delete_comment(self, comment_id: str) -> bool:
        self._ensure_phase3_tables()
        c = self._conn()
        c.execute("DELETE FROM comments WHERE parent_id = ?", (comment_id,))
        c.execute("DELETE FROM comments WHERE id = ?", (comment_id,))
        c.commit()
        return c.execute("SELECT changes()").fetchone()[0] > 0

    # ---- Versions ----

    def add_version(self, version: WorkflowVersion) -> WorkflowVersion:
        self._ensure_phase3_tables()
        c = self._conn()
        snapshot = self._encode_snapshot(version.snapshot)
        if isinstance(version.snapshot, dict):
            version.node_count = version.node_count or len(version.snapshot.get("nodes", {}))
            version.edge_count = version.edge_count or len(version.snapshot.get("edges", {}))
        c.execute(
            """
            INSERT INTO workflow_versions
            (id, workflow_id, user_id, user_name, snapshot, name, auto_save,
             node_count, edge_count, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                version.id,
                version.workflow_id,
                version.user_id,
                version.user_name,
                snapshot,
                version.name,
                1 if version.auto_save else 0,
                version.node_count,
                version.edge_count,
                version.created_at,
            ),
        )
        c.commit()
        return version

    def get_version(self, version_id: str) -> WorkflowVersion | None:
        self._ensure_phase3_tables()
        c = self._conn()
        row = c.execute("SELECT * FROM workflow_versions WHERE id = ?", (version_id,)).fetchone()
        return self._row_to_version(row) if row else None

    def list_versions(self, workflow_id: str, limit: int = 50) -> list[WorkflowVersion]:
        self._ensure_phase3_tables()
        c = self._conn()
        rows = c.execute(
            "SELECT * FROM workflow_versions WHERE workflow_id = ? ORDER BY created_at DESC LIMIT ?",
            (workflow_id, limit),
        ).fetchall()
        return [self._row_to_version(r) for r in rows]

    def delete_version(self, version_id: str) -> bool:
        self._ensure_phase3_tables()
        c = self._conn()
        c.execute("DELETE FROM workflow_versions WHERE id = ?", (version_id,))
        c.commit()
        return c.execute("SELECT changes()").fetchone()[0] > 0

    # ---- Templates ----

    def add_template(self, template: WorkflowTemplate) -> WorkflowTemplate:
        self._ensure_phase3_tables()
        c = self._conn()
        c.execute(
            """
            INSERT INTO workflow_templates
            (id, workflow_id, user_id, title, description, tags, snapshot,
             is_public, fork_count, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                template.id,
                template.workflow_id,
                template.user_id,
                template.title,
                template.description,
                template.tags,
                self._encode_snapshot(template.snapshot),
                1 if template.is_public else 0,
                template.fork_count,
                template.created_at,
            ),
        )
        c.commit()
        return template

    def get_template(self, template_id: str) -> WorkflowTemplate | None:
        self._ensure_phase3_tables()
        c = self._conn()
        row = c.execute("SELECT * FROM workflow_templates WHERE id = ?", (template_id,)).fetchone()
        return self._row_to_template(row) if row else None

    def list_public_templates(
        self,
        search: str | None = None,
        tags: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[WorkflowTemplate]:
        self._ensure_phase3_tables()
        c = self._conn()
        query = "SELECT * FROM workflow_templates WHERE is_public = 1"
        params: list[Any] = []
        if search:
            query += " AND (title LIKE ? OR description LIKE ?)"
            params.extend([f"%{search}%", f"%{search}%"])
        if tags:
            query += " AND tags LIKE ?"
            params.append(f"%{tags}%")
        query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        rows = c.execute(query, params).fetchall()
        return [self._row_to_template(r) for r in rows]

    def list_user_templates(self, user_id: str, limit: int = 50) -> list[WorkflowTemplate]:
        self._ensure_phase3_tables()
        c = self._conn()
        rows = c.execute(
            "SELECT * FROM workflow_templates WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
            (user_id, limit),
        ).fetchall()
        return [self._row_to_template(r) for r in rows]

    def delete_template(self, template_id: str, user_id: str | None = None) -> bool:
        self._ensure_phase3_tables()
        c = self._conn()
        if user_id is None:
            c.execute("DELETE FROM workflow_templates WHERE id = ?", (template_id,))
        else:
            c.execute("DELETE FROM workflow_templates WHERE id = ? AND user_id = ?", (template_id, user_id))
        c.commit()
        return c.execute("SELECT changes()").fetchone()[0] > 0

    def increment_template_forks(self, template_id: str) -> None:
        self._ensure_phase3_tables()
        c = self._conn()
        c.execute("UPDATE workflow_templates SET fork_count = fork_count + 1 WHERE id = ?", (template_id,))
        c.commit()

    @staticmethod
    def _row_to_comment(row: sqlite3.Row) -> Comment:
        return Comment(
            id=row["id"],
            workflow_id=row["workflow_id"],
            node_id=row["node_id"],
            user_id=row["user_id"],
            user_name=row["user_name"] or "",
            user_color=row["user_color"] or "",
            content=row["content"],
            parent_id=row["parent_id"],
            resolved=bool(row["resolved"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    @staticmethod
    def _nest_comments(comments: list[Comment]) -> list[Comment]:
        by_id = {comment.id: comment for comment in comments}
        roots: list[Comment] = []
        for comment in comments:
            comment.replies = []
        for comment in comments:
            if comment.parent_id and comment.parent_id in by_id:
                by_id[comment.parent_id].replies.append(comment)
            else:
                roots.append(comment)
        return roots

    @staticmethod
    def _encode_snapshot(snapshot: dict[str, Any] | bytes) -> bytes:
        if isinstance(snapshot, bytes):
            return snapshot
        return json.dumps(snapshot).encode("utf-8")

    @staticmethod
    def _decode_snapshot(snapshot: Any) -> dict[str, Any] | bytes:
        if snapshot is None:
            return {}
        if isinstance(snapshot, memoryview):
            snapshot = snapshot.tobytes()
        if isinstance(snapshot, bytes):
            try:
                return json.loads(snapshot.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                return snapshot
        if isinstance(snapshot, str):
            try:
                return json.loads(snapshot)
            except json.JSONDecodeError:
                return snapshot.encode("utf-8")
        if isinstance(snapshot, dict):
            return snapshot
        return {}

    def _row_to_version(self, row: sqlite3.Row) -> WorkflowVersion:
        return WorkflowVersion(
            id=row["id"],
            workflow_id=row["workflow_id"],
            user_id=row["user_id"],
            user_name=row["user_name"] or "",
            snapshot=self._decode_snapshot(row["snapshot"]),
            name=row["name"],
            auto_save=bool(row["auto_save"]),
            node_count=row["node_count"] or 0,
            edge_count=row["edge_count"] or 0,
            created_at=row["created_at"],
        )

    def _row_to_template(self, row: sqlite3.Row) -> WorkflowTemplate:
        return WorkflowTemplate(
            id=row["id"],
            workflow_id=row["workflow_id"] or "",
            user_id=row["user_id"],
            title=row["title"],
            description=row["description"] or "",
            tags=row["tags"] or "",
            snapshot=self._decode_snapshot(row["snapshot"]),
            is_public=bool(row["is_public"]),
            fork_count=row["fork_count"] or 0,
            created_at=row["created_at"],
        )

    def close(self) -> None:
        if self._connection:
            self._connection.close()
            self._connection = None
