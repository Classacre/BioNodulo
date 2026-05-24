"""Binary CRDT document persistence using pycrdt and SQLite.

Each workflow document is stored as a series of binary update BLOBs
in SQLite. On load, all updates are replayed into a fresh
:class:`pycrdt.Doc` to reconstruct the current state.

Schema
------
- ``crdt_docs`` — one row per workflow (latest consolidated snapshot)
- ``crdt_updates`` — append-only log of binary updates
- ``workflow_versions`` — phase 3 version snapshots

Thread-safety: All public functions are designed to be called from a
single event-loop thread (the asyncio event loop). For multi-threaded
use, add explicit locking.
"""

from __future__ import annotations

import asyncio
import logging
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pycrdt

from bionodulo.core.workspace import resolve_workspace_root
from bionodulo.collab.models import WorkflowVersion

logger = logging.getLogger(__name__)

# SQL schema for CRDT document storage
_CRDT_SQL_SCHEMA = """
CREATE TABLE IF NOT EXISTS crdt_docs (
    workflow_id TEXT PRIMARY KEY,
    update_data BLOB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS crdt_updates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    workflow_id TEXT NOT NULL,
    update_data BLOB NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_crdt_updates_workflow ON crdt_updates(workflow_id);

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
"""

# Thread-local storage for SQLite connections
_local = threading.local()


def _db_path() -> Path:
    """Resolve the SQLite database path for CRDT storage."""
    path = resolve_workspace_root() / "crdt_docs.db"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


_DB_PATH: Path = _db_path()

CRDT_TOP_LEVEL_MAPS = ("meta", "nodes", "edges", "groups", "viewport")


def _get_connection() -> sqlite3.Connection:
    """Get a thread-local SQLite connection, creating it if needed."""
    conn = getattr(_local, "crdt_connection", None)
    if conn is None:
        conn = sqlite3.connect(str(_DB_PATH), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.executescript(_CRDT_SQL_SCHEMA)
        conn.commit()
        _local.crdt_connection = conn
    return conn


def _close_connection() -> None:
    """Close the thread-local connection, if any."""
    conn = getattr(_local, "crdt_connection", None)
    if conn is not None:
        conn.close()
        _local.crdt_connection = None


def _init_db() -> None:
    """Ensure the database schema is in place."""
    conn = _get_connection()
    conn.executescript(_CRDT_SQL_SCHEMA)
    conn.commit()


# Initialise schema on module import
_init_db()


def _jsonable_crdt_value(value: Any) -> Any:
    """Convert pycrdt values into plain JSON-compatible containers."""
    if isinstance(value, pycrdt.Map):
        return {str(k): _jsonable_crdt_value(v) for k, v in dict(value).items()}
    if isinstance(value, dict):
        return {str(k): _jsonable_crdt_value(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable_crdt_value(v) for v in value]
    return value


def extract_flat_snapshot(doc: pycrdt.Doc) -> dict[str, Any]:
    """Extract the frontend CRDT schema as flat top-level maps.

    The collaborative document contract stores ``meta``, ``nodes``,
    ``edges``, ``groups``, and ``viewport`` directly on the Y/CRDT doc.
    Snapshots intentionally do not read or write a nested ``workflow`` root.
    """
    snapshot: dict[str, Any] = {}
    for map_name in CRDT_TOP_LEVEL_MAPS:
        try:
            snapshot[map_name] = _jsonable_crdt_value(
                doc.get(map_name, type=pycrdt.Map)
            )
        except Exception:
            snapshot[map_name] = {}
    return snapshot


def apply_flat_snapshot(doc: pycrdt.Doc, snapshot: dict[str, Any]) -> None:
    """Apply a flat JSON snapshot into top-level CRDT maps."""
    for map_name in CRDT_TOP_LEVEL_MAPS:
        target = doc.get(map_name, type=pycrdt.Map)
        values = snapshot.get(map_name, {})
        if isinstance(values, dict):
            for key, value in values.items():
                target[key] = value


# ---------------------------------------------------------------------------
# Document lifecycle
# ---------------------------------------------------------------------------

def get_or_create_doc(workflow_id: str) -> pycrdt.Doc:
    """Return a :class:`pycrdt.Doc` for *workflow_id*, loading from DB if it exists.

    Args:
        workflow_id: Unique workflow identifier.

    Returns:
        A :class:`pycrdt.Doc` instance with the workflow's current state,
        or a fresh empty document if no persisted data exists.
    """
    doc = load_doc_from_db(workflow_id)
    if doc is not None:
        logger.debug("Loaded CRDT doc for %s from DB", workflow_id)
        return doc

    # Create a fresh document with default structure (flat top-level maps,
    # matching the frontend Yjs schema exactly).
    doc = pycrdt.Doc()
    meta = doc.get("meta", type=pycrdt.Map)
    meta["id"] = workflow_id
    meta["version"] = 1
    meta["name"] = "Untitled"
    meta["createdAt"] = datetime.now(timezone.utc).isoformat()
    meta["lastModified"] = ""
    doc.get("nodes", type=pycrdt.Map)
    doc.get("edges", type=pycrdt.Map)
    doc.get("groups", type=pycrdt.Map)
    viewport = doc.get("viewport", type=pycrdt.Map)
    viewport["x"] = 0
    viewport["y"] = 0
    viewport["scale"] = 1.0

    logger.debug("Created new CRDT doc for %s", workflow_id)
    return doc


def persist_doc_update(workflow_id: str, update: bytes) -> None:
    """Append a binary CRDT update to the SQLite log.

    Args:
        workflow_id: Unique workflow identifier.
        update: Raw binary update bytes from pycrdt (``event.update``).
    """
    if not update:
        return

    conn = _get_connection()
    try:
        conn.execute(
            "INSERT INTO crdt_updates (workflow_id, update_data) VALUES (?, ?)",
            (workflow_id, update),
        )
        conn.commit()
        logger.debug("Persisted %d-byte update for %s", len(update), workflow_id)
    except sqlite3.Error as exc:
        logger.error("Failed to persist update for %s: %s", workflow_id, exc)
        conn.rollback()
        raise


def load_doc_from_db(workflow_id: str) -> pycrdt.Doc | None:
    """Load a workflow document by replaying all stored binary updates.

    Args:
        workflow_id: Unique workflow identifier.

    Returns:
        A reconstructed :class:`pycrdt.Doc`, or ``None`` if no data exists.
    """
    conn = _get_connection()
    rows = conn.execute(
        "SELECT update_data FROM crdt_updates WHERE workflow_id = ? ORDER BY id ASC",
        (workflow_id,),
    ).fetchall()

    if not rows:
        return None

    doc = pycrdt.Doc()
    total_bytes = 0
    for row in rows:
        update_data: bytes = row["update_data"]
        if update_data:
            try:
                doc.apply_update(update_data)
                total_bytes += len(update_data)
            except Exception as exc:
                logger.warning(
                    "Failed to apply update for %s (%d bytes): %s",
                    workflow_id,
                    len(update_data),
                    exc,
                )

    logger.debug(
        "Replayed %d updates (%d bytes) for %s",
        len(rows),
        total_bytes,
        workflow_id,
    )
    return doc


def consolidate_doc(workflow_id: str, doc: pycrdt.Doc) -> None:
    """Consolidate all updates for a workflow into a single snapshot.

    This reduces the number of BLOBs that must be replayed on load by
    computing a full-document update (diff against empty state) and
    storing it as a single snapshot in ``crdt_docs``.

    Args:
        workflow_id: Unique workflow identifier.
        doc: The current :class:`pycrdt.Doc` instance.
    """
    # Get a full update by diffing against the empty state vector (b'\x00')
    full_update = doc.get_update(b"\x00")
    conn = _get_connection()
    try:
        conn.execute(
            """
            INSERT INTO crdt_docs (workflow_id, update_data, created_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(workflow_id) DO UPDATE SET
                update_data = excluded.update_data,
                created_at = excluded.created_at
            """,
            (workflow_id, full_update),
        )
        conn.commit()
        logger.debug("Consolidated doc state for %s (%d bytes)", workflow_id, len(full_update))
    except sqlite3.Error as exc:
        logger.error("Failed to consolidate doc for %s: %s", workflow_id, exc)
        conn.rollback()


def delete_doc(workflow_id: str) -> None:
    """Delete all persisted data for a workflow.

    Args:
        workflow_id: Unique workflow identifier.
    """
    conn = _get_connection()
    try:
        conn.execute("DELETE FROM crdt_updates WHERE workflow_id = ?", (workflow_id,))
        conn.execute("DELETE FROM crdt_docs WHERE workflow_id = ?", (workflow_id,))
        conn.commit()
        logger.info("Deleted all CRDT data for workflow %s", workflow_id)
    except sqlite3.Error as exc:
        logger.error("Failed to delete doc for %s: %s", workflow_id, exc)
        conn.rollback()
        raise


def list_workflow_ids() -> list[str]:
    """Return all workflow IDs that have persisted CRDT data.

    Returns:
        A sorted list of workflow IDs.
    """
    conn = _get_connection()
    rows = conn.execute(
        "SELECT DISTINCT workflow_id FROM crdt_updates ORDER BY workflow_id"
    ).fetchall()
    return [row["workflow_id"] for row in rows]


def get_doc_stats(workflow_id: str) -> dict[str, Any] | None:
    """Return statistics about a workflow's persisted document.

    Returns:
        A dict with ``update_count``, ``total_bytes``, and ``last_modified``,
        or ``None`` if the workflow has no persisted data.
    """
    conn = _get_connection()
    row = conn.execute(
        """
        SELECT
            COUNT(*) as update_count,
            COALESCE(SUM(LENGTH(update_data)), 0) as total_bytes,
            MAX(timestamp) as last_modified
        FROM crdt_updates
        WHERE workflow_id = ?
        """,
        (workflow_id,),
    ).fetchone()

    if row is None or row["update_count"] == 0:
        return None

    return {
        "workflow_id": workflow_id,
        "update_count": row["update_count"],
        "total_bytes": row["total_bytes"],
        "last_modified": row["last_modified"],
    }


# ---------------------------------------------------------------------------
# Version snapshot management (Phase 3)
# ---------------------------------------------------------------------------

def _ensure_versions_schema() -> None:
    """Ensure the workflow_versions table exists in the CRDT DB."""
    conn = _get_connection()
    conn.executescript("""
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
    """)
    conn.commit()


_ensure_versions_schema()


def _count_nodes_edges(doc: pycrdt.Doc) -> tuple[int, int]:
    """Count nodes and edges in a pycrdt Doc.

    The document structure follows the flat top-level convention set by
    *get_or_create_doc*: ``meta``, ``nodes``, ``edges``, ``groups``, and
    ``viewport`` are all top-level shared types (not nested under a
    ``workflow`` key).
    """
    node_count = 0
    edge_count = 0
    try:
        nodes_map = doc.get("nodes", type=pycrdt.Map)
        edges_map = doc.get("edges", type=pycrdt.Map)
        node_count = len(nodes_map)
        edge_count = len(edges_map)
    except Exception:
        pass
    return node_count, edge_count


def save_version_snapshot_sync(
    workflow_id: str,
    user_id: str,
    user_name: str,
    doc: pycrdt.Doc,
    name: str | None = None,
    auto_save: bool = True,
) -> str:
    """Save a version snapshot of the current document state (synchronous).

    Creates a pycrdt snapshot and stores it in the workflow_versions table.
    Returns the version ID.

    Args:
        workflow_id: Unique workflow identifier.
        user_id: ID of the user creating the snapshot.
        user_name: Display name of the user.
        doc: The current :class:`pycrdt.Doc` instance.
        name: Optional user-given name for the snapshot.
        auto_save: Whether this is an auto-save snapshot.

    Returns:
        The generated version ID.
    """
    version_id = str(uuid.uuid4())
    # Get full update by diffing against the empty state vector
    full_update = doc.get_update(b"\x00")
    node_count, edge_count = _count_nodes_edges(doc)

    conn = _get_connection()
    try:
        conn.execute(
            """
            INSERT INTO workflow_versions
            (id, workflow_id, user_id, user_name, snapshot, name, auto_save, node_count, edge_count)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                version_id,
                workflow_id,
                user_id,
                user_name,
                full_update,
                name,
                1 if auto_save else 0,
                node_count,
                edge_count,
            ),
        )
        conn.commit()
        logger.debug(
            "Saved version snapshot %s for workflow %s (%d nodes, %d edges)",
            version_id,
            workflow_id,
            node_count,
            edge_count,
        )
    except sqlite3.Error as exc:
        logger.error("Failed to save version snapshot for %s: %s", workflow_id, exc)
        conn.rollback()
        raise
    return version_id


async def save_version_snapshot(
    workflow_id: str,
    user_id: str,
    user_name: str,
    doc: pycrdt.Doc,
    name: str | None = None,
    auto_save: bool = True,
) -> str:
    """Save a version snapshot of the current document state.

    Creates a pycrdt snapshot and stores it in workflow_versions table.
    Returns the version ID.
    """
    return await asyncio.to_thread(
        save_version_snapshot_sync,
        workflow_id,
        user_id,
        user_name,
        doc,
        name,
        auto_save,
    )


def load_version_snapshot_sync(version_id: str) -> pycrdt.Doc | None:
    """Load a version snapshot into a new pycrdt Doc (synchronous).

    Args:
        version_id: The version ID to load.

    Returns:
        A reconstructed :class:`pycrdt.Doc`, or ``None`` if not found.
    """
    conn = _get_connection()
    row = conn.execute(
        "SELECT snapshot FROM workflow_versions WHERE id = ?",
        (version_id,),
    ).fetchone()
    if not row:
        return None
    doc = pycrdt.Doc()
    snapshot_data: bytes = row["snapshot"]
    if snapshot_data:
        doc.apply_update(snapshot_data)
    return doc


async def load_version_snapshot(version_id: str) -> pycrdt.Doc | None:
    """Load a version snapshot into a new pycrdt Doc."""
    return await asyncio.to_thread(load_version_snapshot_sync, version_id)


def list_versions_sync(workflow_id: str, limit: int = 50) -> list[WorkflowVersion]:
    """List versions for a workflow, newest first (synchronous).

    Args:
        workflow_id: The workflow to list versions for.
        limit: Maximum number of versions to return.

    Returns:
        A list of :class:`WorkflowVersion` objects, newest first.
    """
    conn = _get_connection()
    rows = conn.execute(
        """
        SELECT id, workflow_id, user_id, user_name, name, auto_save,
               node_count, edge_count, created_at
        FROM workflow_versions
        WHERE workflow_id = ?
        ORDER BY created_at DESC
        LIMIT ?
        """,
        (workflow_id, limit),
    ).fetchall()
    result: list[WorkflowVersion] = []
    for row in rows:
        result.append(
            WorkflowVersion(
                id=row["id"],
                workflow_id=row["workflow_id"],
                user_id=row["user_id"],
                user_name=row["user_name"] or "",
                snapshot=b"",
                name=row["name"],
                auto_save=bool(row["auto_save"]),
                node_count=row["node_count"] or 0,
                edge_count=row["edge_count"] or 0,
                created_at=row["created_at"],
            )
        )
    return result


async def list_versions(workflow_id: str, limit: int = 50) -> list[WorkflowVersion]:
    """List versions for a workflow, newest first."""
    return await asyncio.to_thread(list_versions_sync, workflow_id, limit)


def delete_version_sync(version_id: str) -> bool:
    """Delete a version. Returns True if found and deleted."""
    conn = _get_connection()
    try:
        cursor = conn.execute(
            "DELETE FROM workflow_versions WHERE id = ?",
            (version_id,),
        )
        conn.commit()
        return cursor.rowcount > 0
    except sqlite3.Error as exc:
        logger.error("Failed to delete version %s: %s", version_id, exc)
        conn.rollback()
        raise


async def delete_version(version_id: str) -> bool:
    """Delete a version. Returns True if found and deleted."""
    return await asyncio.to_thread(delete_version_sync, version_id)


def auto_save_version_sync(
    workflow_id: str,
    user_id: str,
    user_name: str,
    doc: pycrdt.Doc,
) -> str | None:
    """Auto-save a version every 5 minutes (synchronous).

    Checks the last auto-save time before saving. Returns the version ID
    if a new snapshot was created, or ``None`` if the cooldown period
    (300 seconds) has not elapsed.
    """
    conn = _get_connection()
    row = conn.execute(
        """
        SELECT MAX(created_at) as last_save
        FROM workflow_versions
        WHERE workflow_id = ? AND auto_save = 1
        """,
        (workflow_id,),
    ).fetchone()

    if row and row["last_save"]:
        try:
            # Parse the timestamp (could be ISO string or SQLite timestamp)
            last_str: str = row["last_save"]
            # Handle both formats
            if "T" in last_str:
                last = datetime.fromisoformat(last_str.replace("Z", "+00:00"))
            else:
                last = datetime.strptime(last_str, "%Y-%m-%d %H:%M:%S").replace(
                    tzinfo=timezone.utc
                )
            now = datetime.now(timezone.utc)
            if (now - last).total_seconds() < 300:
                logger.debug("Auto-save cooldown active for workflow %s", workflow_id)
                return None  # too recent
        except (ValueError, TypeError):
            pass  # If parsing fails, proceed with the save

    return save_version_snapshot_sync(
        workflow_id, user_id, user_name, doc, auto_save=True
    )


async def auto_save_version(
    workflow_id: str,
    user_id: str,
    user_name: str,
    doc: pycrdt.Doc,
) -> str | None:
    """Auto-save a version every 5 minutes. Check last auto-save time before saving."""
    return await asyncio.to_thread(
        auto_save_version_sync, workflow_id, user_id, user_name, doc
    )
