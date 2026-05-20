"""SQLite-backed YStore for pycrdt-websocket document persistence.

Each workflow gets its own append-only update log.  Updates are stored as
BLOBs and replayed into a fresh :class:`pycrdt.Doc` on load.

The store is intentionally thin — it only deals in raw bytes so that the
calling layer (the WebSocket handler) owns the document lifecycle.
"""

from __future__ import annotations

import asyncio
import logging
import sqlite3
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class SQLiteYStore:
    """YStore that persists CRDT updates to SQLite.

    Each workflow gets its own row in an append-only update log.
    Updates are stored as BLOBs and applied to documents on load.

    Args:
        workflow_id: Unique workflow identifier (used as partition key).
        db_path: Path to the SQLite database file.  The directory is
            created automatically if it does not exist.
    """

    def __init__(self, workflow_id: str, db_path: str) -> None:
        self.workflow_id = workflow_id
        self.db_path = db_path
        self._lock = asyncio.Lock()
        self._ensure_table()
        self._ensure_metadata_table()

    # ------------------------------------------------------------------
    # Schema
    # ------------------------------------------------------------------

    def _ensure_table(self) -> None:
        """Create the crdt_updates table if it does not exist."""
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS crdt_updates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                workflow_id TEXT NOT NULL,
                update_data BLOB NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_crdt_updates_workflow
            ON crdt_updates(workflow_id)
            """
        )
        conn.commit()
        conn.close()

    def _ensure_metadata_table(self) -> None:
        """Create the crdt_metadata table if it does not exist."""
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS crdt_metadata (
                workflow_id TEXT NOT NULL,
                key TEXT NOT NULL,
                value TEXT,
                PRIMARY KEY (workflow_id, key)
            )
            """
        )
        conn.commit()
        conn.close()

    # ------------------------------------------------------------------
    # Core persistence API
    # ------------------------------------------------------------------

    async def read(self) -> bytes:
        """Read all stored updates as a single concatenated byte string.

        Returns:
            The concatenation of every BLOB stored for *workflow_id*, in
            insertion order.  An empty ``b""`` is returned when no data
            exists.
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._read_sync)

    def _read_sync(self) -> bytes:
        conn = sqlite3.connect(self.db_path)
        rows = conn.execute(
            "SELECT update_data FROM crdt_updates WHERE workflow_id = ? ORDER BY id",
            (self.workflow_id,),
        ).fetchall()
        conn.close()
        # Concatenate all updates (Yjs can handle concatenated updates)
        return b"".join(row[0] for row in rows)

    async def write(self, data: bytes) -> None:
        """Append a new update to the store.

        Args:
            data: Raw CRDT update bytes (e.g. from ``event.update``).
        """
        if not data:
            return
        async with self._lock:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self._write_sync, data)

    def _write_sync(self, data: bytes) -> None:
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            "INSERT INTO crdt_updates (workflow_id, update_data) VALUES (?, ?)",
            (self.workflow_id, data),
        )
        conn.commit()
        conn.close()

    # ------------------------------------------------------------------
    # Metadata helpers
    # ------------------------------------------------------------------

    async def get_metadata(self, key: str) -> Any:
        """Read metadata for this workflow.

        Args:
            key: Metadata key name.

        Returns:
            The stored value, or ``None`` if the key does not exist.
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._get_metadata_sync, key)

    def _get_metadata_sync(self, key: str) -> Any:
        conn = sqlite3.connect(self.db_path)
        row = conn.execute(
            "SELECT value FROM crdt_metadata WHERE workflow_id = ? AND key = ?",
            (self.workflow_id, key),
        ).fetchone()
        conn.close()
        return row[0] if row else None

    async def set_metadata(self, key: str, value: str) -> None:
        """Write metadata for this workflow.

        Args:
            key: Metadata key name.
            value: Value to store (coerced to ``str``).
        """
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._set_metadata_sync, key, str(value))

    def _set_metadata_sync(self, key: str, value: str) -> None:
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            """
            INSERT INTO crdt_metadata (workflow_id, key, value)
            VALUES (?, ?, ?)
            ON CONFLICT(workflow_id, key) DO UPDATE SET value = excluded.value
            """,
            (self.workflow_id, key, value),
        )
        conn.commit()
        conn.close()

    # ------------------------------------------------------------------
    # Higher-level helpers (used by the WebSocket handler)
    # ------------------------------------------------------------------

    async def apply_updates(self, doc: Any) -> None:
        """Apply all stored updates to a *pycrdt.Doc*.

        Args:
            doc: A :class:`pycrdt.Doc` instance.
        """
        data = await self.read()
        if data:
            doc.apply_update(data)

    async def encode_state_as_update(self, doc: Any) -> bytes:
        """Encode the current document state as an update.

        Args:
            doc: A :class:`pycrdt.Doc` instance.

        Returns:
            A byte string that can be stored or sent as a SyncStep2.
        """
        return doc.get_update(b"\x00")

    # ------------------------------------------------------------------
    # Admin helpers
    # ------------------------------------------------------------------

    async def delete_all(self) -> None:
        """Delete every update and metadata row for this workflow."""
        async with self._lock:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self._delete_all_sync)

    def _delete_all_sync(self) -> None:
        conn = sqlite3.connect(self.db_path)
        conn.execute("DELETE FROM crdt_updates WHERE workflow_id = ?", (self.workflow_id,))
        conn.execute("DELETE FROM crdt_metadata WHERE workflow_id = ?", (self.workflow_id,))
        conn.commit()
        conn.close()

    async def get_stats(self) -> dict[str, Any]:
        """Return storage statistics for this workflow."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._get_stats_sync)

    def _get_stats_sync(self) -> dict[str, Any]:
        conn = sqlite3.connect(self.db_path)
        row = conn.execute(
            """
            SELECT
                COUNT(*) as update_count,
                COALESCE(SUM(LENGTH(update_data)), 0) as total_bytes,
                MAX(timestamp) as last_modified
            FROM crdt_updates
            WHERE workflow_id = ?
            """,
            (self.workflow_id,),
        ).fetchone()
        conn.close()
        return {
            "workflow_id": self.workflow_id,
            "update_count": row[0] if row else 0,
            "total_bytes": row[1] if row else 0,
            "last_modified": row[2] if row else None,
        }
