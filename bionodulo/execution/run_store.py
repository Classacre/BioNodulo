"""SQLite-backed persistence for queued/running/finished runs.

The :class:`RunQueue` keeps its working state in memory for speed, but that
state is lost on restart or crash, orphaning in-flight runs and dropping the
pending queue. ``RunStore`` mirrors every run-state transition to disk so the
queue can be reconciled on startup: pending runs are restored and runs left
``running`` by a dead process are marked interrupted.

The store is deliberately small and synchronous — payloads are tiny JSON blobs
and writes happen on state transitions, not in hot loops. A single connection is
guarded by a threading lock so it is safe to call from the asyncio worker and
from request handlers on the same loop.
"""

from __future__ import annotations

import json
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any

# Statuses considered terminal — anything else found at startup was in flight
# when the previous process died.
TERMINAL_STATUSES = {"completed", "failed", "cancelled", "interrupted"}


class RunStore:
    """Persist run records to a SQLite database."""

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS runs (
                run_id      TEXT PRIMARY KEY,
                status      TEXT NOT NULL,
                workflow    TEXT NOT NULL,
                options     TEXT NOT NULL,
                metadata    TEXT NOT NULL,
                force       INTEGER NOT NULL DEFAULT 0,
                force_nodes TEXT NOT NULL DEFAULT '[]',
                result      TEXT,
                created_at  REAL,
                started_at  REAL,
                finished_at REAL,
                updated_at  REAL NOT NULL
            )
            """
        )
        self._conn.commit()

    # ------------------------------------------------------------------
    # Writes
    # ------------------------------------------------------------------

    def upsert(self, record: dict[str, Any]) -> None:
        """Insert or update a run record. ``record`` mirrors ``RunRequest``."""
        payload = (
            str(record["run_id"]),
            str(record.get("status", "pending")),
            _dumps(record.get("workflow", {})),
            _dumps(record.get("options", {})),
            _dumps(record.get("metadata", {})),
            1 if record.get("force") else 0,
            _dumps(sorted(record.get("force_nodes", []) or [])),
            _dumps(record.get("result")) if record.get("result") is not None else None,
            record.get("created_at"),
            record.get("started_at"),
            record.get("finished_at"),
            time.time(),
        )
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO runs (run_id, status, workflow, options, metadata,
                                  force, force_nodes, result, created_at,
                                  started_at, finished_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(run_id) DO UPDATE SET
                    status=excluded.status,
                    workflow=excluded.workflow,
                    options=excluded.options,
                    metadata=excluded.metadata,
                    force=excluded.force,
                    force_nodes=excluded.force_nodes,
                    result=excluded.result,
                    created_at=excluded.created_at,
                    started_at=excluded.started_at,
                    finished_at=excluded.finished_at,
                    updated_at=excluded.updated_at
                """,
                payload,
            )
            self._conn.commit()

    def delete(self, run_id: str) -> None:
        with self._lock:
            self._conn.execute("DELETE FROM runs WHERE run_id = ?", (str(run_id),))
            self._conn.commit()

    def clear_terminal(self) -> int:
        """Delete all finished runs. Returns the number removed."""
        placeholders = ",".join("?" for _ in TERMINAL_STATUSES)
        with self._lock:
            cur = self._conn.execute(
                f"DELETE FROM runs WHERE status IN ({placeholders})",
                tuple(TERMINAL_STATUSES),
            )
            self._conn.commit()
            return cur.rowcount

    def mark_orphans_interrupted(self) -> list[str]:
        """Mark non-terminal runs as interrupted (called once at startup).

        Returns the list of affected run_ids — these were in flight when the
        previous process exited.
        """
        placeholders = ",".join("?" for _ in TERMINAL_STATUSES)
        now = time.time()
        with self._lock:
            rows = self._conn.execute(
                f"SELECT run_id FROM runs WHERE status NOT IN ({placeholders})",
                tuple(TERMINAL_STATUSES),
            ).fetchall()
            orphan_ids = [row["run_id"] for row in rows]
            if orphan_ids:
                self._conn.execute(
                    f"UPDATE runs SET status='interrupted', finished_at=?, updated_at=? "
                    f"WHERE status NOT IN ({placeholders})",
                    (now, now, *TERMINAL_STATUSES),
                )
                self._conn.commit()
        return orphan_ids

    # ------------------------------------------------------------------
    # Reads
    # ------------------------------------------------------------------

    def load_all(self) -> list[dict[str, Any]]:
        """Return all persisted runs ordered by creation time."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM runs ORDER BY COALESCE(created_at, 0) ASC"
            ).fetchall()
        return [_row_to_record(row) for row in rows]

    def get(self, run_id: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM runs WHERE run_id = ?", (str(run_id),)
            ).fetchone()
        return _row_to_record(row) if row is not None else None

    def close(self) -> None:
        with self._lock:
            self._conn.close()


def _dumps(value: Any) -> str:
    try:
        return json.dumps(value, default=str)
    except (TypeError, ValueError):
        return json.dumps(str(value))


def _loads(value: Any, fallback: Any) -> Any:
    if value is None:
        return fallback
    try:
        return json.loads(value)
    except (TypeError, ValueError, json.JSONDecodeError):
        return fallback


def _row_to_record(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "run_id": row["run_id"],
        "status": row["status"],
        "workflow": _loads(row["workflow"], {}),
        "options": _loads(row["options"], {}),
        "metadata": _loads(row["metadata"], {}),
        "force": bool(row["force"]),
        "force_nodes": _loads(row["force_nodes"], []),
        "result": _loads(row["result"], None),
        "created_at": row["created_at"],
        "started_at": row["started_at"],
        "finished_at": row["finished_at"],
    }
