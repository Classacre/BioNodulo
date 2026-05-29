"""Compliance-grade audit logging for collaborative workflow editing.

The AuditLogger writes immutable audit records to SQLite and supports
async querying, CSV export, and summary statistics. Each entry captures
*who* performed *what action* on *which target* with before/after payload
snapshots for compliance forensics.
"""

from __future__ import annotations

import csv
import io
import json
import logging
import sqlite3
import uuid
import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Audit entry dataclass
# ---------------------------------------------------------------------------


@dataclass
class AuditEntry:
    """A single audit log entry.

    Attributes:
        id: Unique entry UUID.
        workflow_id: The workflow the action occurred on.
        user_id: The user who performed the action (from JWT sub).
        user_name: Human-readable display name.
        action: Action type — node_add, node_delete, node_move, node_configure,
                edge_add, edge_delete, param_change, execute_start, execute_end,
                share, version_save, comment_add, comment_resolve, etc.
        target_type: Kind of target — node, edge, group, workflow, comment.
        target_id: Specific target identifier.
        payload: Arbitrary before/after snapshot dict.
        performed_at: ISO-8601 timestamp.
    """

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    workflow_id: str = ""
    user_id: str = ""
    user_name: str = ""
    action: str = ""
    target_type: str = ""
    target_id: str = ""
    payload: dict[str, Any] = field(default_factory=dict)
    performed_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "workflow_id": self.workflow_id,
            "user_id": self.user_id,
            "user_name": self.user_name,
            "action": self.action,
            "target_type": self.target_type,
            "target_id": self.target_id,
            "payload": self.payload,
            "performed_at": self.performed_at,
        }


# ---------------------------------------------------------------------------
# SQL schema
# ---------------------------------------------------------------------------

_AUDIT_SQL_SCHEMA = """
CREATE TABLE IF NOT EXISTS audit_log (
    id TEXT PRIMARY KEY,
    workflow_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    user_name TEXT,
    action TEXT NOT NULL,
    target_type TEXT,
    target_id TEXT,
    payload TEXT,  -- JSON string
    performed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_audit_workflow ON audit_log(workflow_id);
CREATE INDEX IF NOT EXISTS idx_audit_user ON audit_log(user_id);
CREATE INDEX IF NOT EXISTS idx_audit_action ON audit_log(action);
CREATE INDEX IF NOT EXISTS idx_audit_time ON audit_log(performed_at);
"""


# ---------------------------------------------------------------------------
# AuditLogger
# ---------------------------------------------------------------------------


class AuditLogger:
    """Audit logger that writes to SQLite and optionally broadcasts over WebSocket.

    Usage::

        logger = AuditLogger("/path/to/audit.db")
        await logger.log(
            workflow_id="wf-123",
            user_id="u_abc",
            user_name="Alice",
            action="node_add",
            target_type="node",
            target_id="node-7",
            payload={"before": None, "after": {"type": "FastQC"}},
        )
    """

    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        self._ensure_table()

    # ------------------------------------------------------------------
    # Schema
    # ------------------------------------------------------------------

    def _ensure_table(self) -> None:
        """Create the audit_log table and indexes if they do not exist."""
        conn = sqlite3.connect(self.db_path)
        try:
            conn.executescript(_AUDIT_SQL_SCHEMA)
            conn.commit()
        finally:
            conn.close()

    def _conn(self) -> sqlite3.Connection:
        """Open a new SQLite connection."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    # ------------------------------------------------------------------
    # Logging (fire-and-forget)
    # ------------------------------------------------------------------

    async def log(
        self,
        workflow_id: str,
        user_id: str,
        user_name: str = "",
        action: str = "",
        target_type: str | None = None,
        target_id: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> None:
        """Log an action (fire-and-forget, non-blocking).

        Runs the DB insert in the default thread pool so the event loop is
        never blocked.
        """
        entry = AuditEntry(
            id=str(uuid.uuid4()),
            workflow_id=workflow_id,
            user_id=user_id,
            user_name=user_name,
            action=action,
            target_type=target_type or "",
            target_id=target_id or "",
            payload=payload or {},
            performed_at=datetime.now(timezone.utc).isoformat(),
        )

        def _insert() -> None:
            conn = self._conn()
            try:
                conn.execute(
                    """
                    INSERT INTO audit_log
                    (id, workflow_id, user_id, user_name, action, target_type, target_id, payload, performed_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        entry.id,
                        entry.workflow_id,
                        entry.user_id,
                        entry.user_name,
                        entry.action,
                        entry.target_type,
                        entry.target_id,
                        json.dumps(entry.payload),
                        entry.performed_at,
                    ),
                )
                conn.commit()
            except sqlite3.Error as exc:
                logger.error("Audit log insert failed: %s", exc)
            finally:
                conn.close()

        await asyncio.to_thread(_insert)
        logger.debug("Audit logged: %s on %s by %s", action, workflow_id, user_id)

    # ------------------------------------------------------------------
    # Querying
    # ------------------------------------------------------------------

    async def query(
        self,
        workflow_id: str | None = None,
        user_id: str | None = None,
        action: str | None = None,
        target_type: str | None = None,
        from_date: str | None = None,
        to_date: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[AuditEntry]:
        """Query audit log with filters."""

        def _query() -> list[AuditEntry]:
            conn = self._conn()
            try:
                conditions: list[str] = []
                params: list[Any] = []

                if workflow_id:
                    conditions.append("workflow_id = ?")
                    params.append(workflow_id)
                if user_id:
                    conditions.append("user_id = ?")
                    params.append(user_id)
                if action:
                    conditions.append("action = ?")
                    params.append(action)
                if target_type:
                    conditions.append("target_type = ?")
                    params.append(target_type)
                if from_date:
                    conditions.append("performed_at >= ?")
                    params.append(from_date)
                if to_date:
                    conditions.append("performed_at <= ?")
                    params.append(to_date)

                query_sql = "SELECT * FROM audit_log"
                if conditions:
                    query_sql += " WHERE " + " AND ".join(conditions)
                query_sql += " ORDER BY performed_at DESC LIMIT ? OFFSET ?"
                params.extend([limit, offset])

                rows = conn.execute(query_sql, params).fetchall()
                result: list[AuditEntry] = []
                for row in rows:
                    d = dict(row)
                    d["payload"] = json.loads(d.get("payload", "{}"))
                    result.append(AuditEntry(**d))
                return result
            finally:
                conn.close()

        return await asyncio.to_thread(_query)

    # ------------------------------------------------------------------
    # CSV export
    # ------------------------------------------------------------------

    async def export_csv(self, workflow_id: str | None = None) -> str:
        """Export filtered results as a CSV string."""

        def _export() -> str:
            conn = self._conn()
            try:
                if workflow_id:
                    rows = conn.execute(
                        """
                        SELECT id, workflow_id, user_id, user_name, action,
                               target_type, target_id, payload, performed_at
                        FROM audit_log
                        WHERE workflow_id = ?
                        ORDER BY performed_at DESC
                        """,
                        (workflow_id,),
                    ).fetchall()
                else:
                    rows = conn.execute(
                        """
                        SELECT id, workflow_id, user_id, user_name, action,
                               target_type, target_id, payload, performed_at
                        FROM audit_log
                        ORDER BY performed_at DESC
                        """,
                    ).fetchall()

                buf = io.StringIO()
                writer = csv.writer(buf)
                writer.writerow(
                    [
                        "id",
                        "workflow_id",
                        "user_id",
                        "user_name",
                        "action",
                        "target_type",
                        "target_id",
                        "payload",
                        "performed_at",
                    ]
                )
                for row in rows:
                    writer.writerow(
                        [
                            row["id"],
                            row["workflow_id"],
                            row["user_id"],
                            row["user_name"],
                            row["action"],
                            row["target_type"],
                            row["target_id"],
                            row["payload"],
                            row["performed_at"],
                        ]
                    )
                return buf.getvalue()
            finally:
                conn.close()

        return await asyncio.to_thread(_export)

    # ------------------------------------------------------------------
    # Summary statistics
    # ------------------------------------------------------------------

    async def get_summary(self, workflow_id: str) -> dict[str, Any]:
        """Get summary stats: action counts, most active user, date range."""

        def _summary() -> dict[str, Any]:
            conn = self._conn()
            try:
                # Action counts
                action_rows = conn.execute(
                    "SELECT action, COUNT(*) as cnt FROM audit_log WHERE workflow_id = ? GROUP BY action",
                    (workflow_id,),
                ).fetchall()
                action_counts: dict[str, int] = {row["action"]: row["cnt"] for row in action_rows}

                # Most active user
                user_row = conn.execute(
                    """
                    SELECT user_id, user_name, COUNT(*) as cnt
                    FROM audit_log
                    WHERE workflow_id = ?
                    GROUP BY user_id
                    ORDER BY cnt DESC
                    LIMIT 1
                    """,
                    (workflow_id,),
                ).fetchone()
                most_active_user: dict[str, Any] | None = None
                if user_row:
                    most_active_user = {
                        "user_id": user_row["user_id"],
                        "user_name": user_row["user_name"],
                        "action_count": user_row["cnt"],
                    }

                # Date range
                range_row = conn.execute(
                    """
                    SELECT MIN(performed_at) as first, MAX(performed_at) as last,
                           COUNT(*) as total
                    FROM audit_log
                    WHERE workflow_id = ?
                    """,
                    (workflow_id,),
                ).fetchone()

                return {
                    "workflow_id": workflow_id,
                    "total_entries": range_row["total"] if range_row else 0,
                    "action_counts": action_counts,
                    "most_active_user": most_active_user,
                    "date_range": {
                        "first": range_row["first"] if range_row else None,
                        "last": range_row["last"] if range_row else None,
                    },
                }
            finally:
                conn.close()

        return await asyncio.to_thread(_summary)
