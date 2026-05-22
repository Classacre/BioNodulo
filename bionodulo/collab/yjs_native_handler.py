"""Native Yjs WebSocket handler using the standard y-protocols binary format.

Binary format (NO length prefix)
--------------------------------
::

    [message_type: u8] [payload: ...]

- ``message_type = 0`` → Sync: ``[0] [sync_type: u8] [payload: ...]``

  - ``sync_type = 0`` → SyncStep1 (client sends state vector)
  - ``sync_type = 1`` → SyncStep2 (server sends diff/update)
  - ``sync_type = 2`` → Update (incremental change)

- ``message_type = 1`` → Awareness: ``[1] [awareness_bytes: ...]``

Auth is handled via JWT in the ``?token=`` query parameter.
Permissions (read-only) are enforced at the document level.

This module **replaces** the legacy ``websocket_handler.py`` which used a
custom length-prefixed protocol.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

import pycrdt

from bionodulo.collab.auth import get_auth_ws, generate_user_id
from bionodulo.collab.models import CollabAuditLogEntry, CollabStore
from bionodulo.collab.permissions import PermissionChecker
from bionodulo.collab.rate_limiter import RateLimiter
from bionodulo.collab.yjs_store import SQLiteYStore

logger = logging.getLogger(__name__)

yjs_router = APIRouter()

# ---------------------------------------------------------------------------
# Message type constants (native Yjs protocol — no length prefix)
# ---------------------------------------------------------------------------

MSG_SYNC = 0       # nested: [0] [sync_type] [payload]
MSG_AWARENESS = 1  # [1] [awareness_bytes]

# Sync sub-types (nested inside MSG_SYNC)
SYNC_STEP1 = 0  # state vector request
SYNC_STEP2 = 1  # update diff response
SYNC_UPDATE = 2  # incremental change


def _open_room_join_enabled() -> bool:
    """Allow authenticated link visitors into trusted local/open rooms."""
    return os.environ.get("BIONODULO_COLLAB_OPEN_ROOMS", "").lower() in {
        "1",
        "true",
        "yes",
        "on",
    }

# ---------------------------------------------------------------------------
# Singletons (event-loop single-threaded — safe without locks)
# ---------------------------------------------------------------------------

_store: CollabStore | None = None
_permissions: PermissionChecker | None = None
_rate_limiter: RateLimiter | None = None


def _get_store() -> CollabStore:
    """Return the collab store singleton."""
    global _store
    if _store is None:
        from bionodulo.collab.persistence import _resolve_workspace_root

        db_path = _resolve_workspace_root() / "collab.db"
        _store = CollabStore(str(db_path))
    return _store


def _get_permissions() -> PermissionChecker:
    """Return the permission checker singleton."""
    global _permissions
    if _permissions is None:
        from bionodulo.collab.persistence import _resolve_workspace_root

        _permissions = PermissionChecker(
            store=_get_store(),
            fallback_file=_resolve_workspace_root() / "permissions.json",
        )
    return _permissions


def _get_rate_limiter() -> RateLimiter:
    """Return the rate limiter singleton."""
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = RateLimiter()
    return _rate_limiter


def _get_yjs_db_path() -> str:
    """Resolve the SQLite DB path for CRDT document storage."""
    from bionodulo.collab.persistence import _resolve_workspace_root

    return str(_resolve_workspace_root() / "crdt_docs.db")


# ---------------------------------------------------------------------------
# Document cache (per workflow)
# ---------------------------------------------------------------------------

_doc_cache: dict[str, pycrdt.Doc] = {}
_doc_locks: dict[str, asyncio.Lock] = {}
_doc_observers: dict[str, Any] = {}


async def _get_doc(workflow_id: str) -> pycrdt.Doc:
    """Get or create a :class:`pycrdt.Doc` for *workflow_id*, loading persisted state.

    The document has the flat top-level map structure expected by the
    frontend: ``meta``, ``nodes``, ``edges``, ``groups``, ``viewport``.
    """
    if workflow_id in _doc_cache:
        return _doc_cache[workflow_id]

    lock = _doc_locks.setdefault(workflow_id, asyncio.Lock())
    async with lock:
        if workflow_id in _doc_cache:
            return _doc_cache[workflow_id]

        doc = pycrdt.Doc()

        # Initialise top-level maps (matching the frontend structure)
        with doc.transaction():
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

        # Load persisted updates
        try:
            ystore = SQLiteYStore(workflow_id, _get_yjs_db_path())
            await ystore.apply_updates(doc)
            logger.debug("Loaded persisted state for %s", workflow_id)
        except Exception as exc:
            logger.warning("Failed to load persisted state for %s: %s", workflow_id, exc)

        # Persist future updates (observer fires on every document change)
        if workflow_id not in _doc_observers:

            def _on_change(event: Any, *, _wid: str = workflow_id) -> None:
                """Callback invoked by pycrdt when the document changes."""
                update = getattr(event, "update", b"")
                if update:
                    try:
                        asyncio.create_task(_persist_update(_wid, update))
                    except Exception as exc:  # pragma: no cover
                        logger.warning("Failed to schedule persist task: %s", exc)

            doc.observe(_on_change)
            _doc_observers[workflow_id] = _on_change

        _doc_cache[workflow_id] = doc
        return doc


async def _persist_update(workflow_id: str, update: bytes) -> None:
    """Persist a CRDT update to SQLite (fire-and-forget)."""
    try:
        ystore = SQLiteYStore(workflow_id, _get_yjs_db_path())
        await ystore.write(update)
    except Exception as exc:
        logger.warning("Failed to persist update for %s: %s", workflow_id, exc)


# ---------------------------------------------------------------------------
# Broadcast helpers
# ---------------------------------------------------------------------------

async def _broadcast_to_room(
    workflow_id: str,
    data: bytes,
    exclude: WebSocket | None = None,
    room_sockets: dict[str, list[WebSocket]] | None = None,
) -> None:
    """Broadcast *data* to all WebSockets in a room except *exclude*."""
    if room_sockets is None:
        return
    sockets = room_sockets.get(workflow_id, [])
    for ws in sockets:
        if ws is exclude:
            continue
        try:
            await ws.send_bytes(data)
        except Exception:
            pass


def _room_presence_payload(
    workflow_id: str,
    room_sockets: dict[str, list[WebSocket]],
) -> dict[str, Any]:
    """Build a lightweight roster from authenticated sockets in one room."""
    users: list[dict[str, str]] = []
    for socket in room_sockets.get(workflow_id, []):
        presence = getattr(socket.state, "yjs_presence", None)
        if isinstance(presence, dict):
            users.append(presence)
    return {"type": "room.presence", "workflow_id": workflow_id, "users": users}


async def _broadcast_room_presence(
    workflow_id: str,
    room_sockets: dict[str, list[WebSocket]],
) -> None:
    """Tell each browser which authenticated sockets are in its room."""
    message = json.dumps(_room_presence_payload(workflow_id, room_sockets))
    for socket in room_sockets.get(workflow_id, []):
        try:
            await socket.send_text(message)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# WebSocket endpoint (native Yjs protocol)
# ---------------------------------------------------------------------------


@yjs_router.websocket("/ws/collab/{workflow_id}")
async def yjs_websocket(
    websocket: WebSocket,
    workflow_id: str,
    token: str = Query(default=""),
    name: str = Query(default=""),
    color: str = Query(default="#3b82f6"),
) -> None:
    """Native Yjs WebSocket endpoint.

    Uses the standard y-protocols binary format:

    - ``[0] [sync_type] [payload]`` for sync messages
    - ``[1] [awareness_bytes]`` for awareness

    Query parameters
    ----------------
    - ``token`` — JWT authentication token (required).
    - ``name`` — Optional display name for local presentation only.
    - ``color`` — Hex colour for cursor / presence.
    """
    # ------------------------------------------------------------------
    # 0. Parse query parameters
    # ------------------------------------------------------------------
    query_params = dict(websocket.query_params)

    # ------------------------------------------------------------------
    # 1. JWT Authentication
    # ------------------------------------------------------------------
    auth_payload = get_auth_ws(query_params)
    if auth_payload is None:
        await websocket.accept()
        await websocket.close(code=4401, reason="Unauthorized")
        return

    jwt_user_id = auth_payload.get("sub", "")

    # Identity must come from the signed JWT. Query-string identity override
    # was part of the MVP protocol and allowed impersonation.
    effective_user_id = jwt_user_id or generate_user_id()

    # ------------------------------------------------------------------
    # 2. Permission check
    # ------------------------------------------------------------------
    permissions = _get_permissions()
    permissions.ensure_owner(workflow_id, effective_user_id)
    if _open_room_join_enabled() and not permissions.can_read(workflow_id, effective_user_id):
        permissions.grant(
            workflow_id,
            effective_user_id,
            "editor",
            invited_by="open-room-link",
        )
    read_only = not permissions.can_write(workflow_id, effective_user_id)

    if not permissions.can_read(workflow_id, effective_user_id):
        await websocket.accept()
        await websocket.close(code=4403, reason="Forbidden")
        return

    # ------------------------------------------------------------------
    # 3. Accept WebSocket (binary subprotocol if offered)
    # ------------------------------------------------------------------
    subprotocols = websocket.scope.get("subprotocols", [])
    if "b-yjs" in subprotocols:
        await websocket.accept(subprotocol="b-yjs")
    else:
        await websocket.accept()

    # ------------------------------------------------------------------
    # 4. Resolve managers
    # ------------------------------------------------------------------
    rate_limiter = _get_rate_limiter()
    store = _get_store()

    # ------------------------------------------------------------------
    # 5. Room sockets (managed on app.state)
    # ------------------------------------------------------------------
    room_sockets = websocket.app.state.yjs_room_sockets
    if workflow_id not in room_sockets:
        room_sockets[workflow_id] = []
    websocket.state.yjs_presence = {
        "session_id": uuid.uuid4().hex,
        "user_id": effective_user_id,
        "name": str(auth_payload.get("name", effective_user_id)),
        "color": str(auth_payload.get("color", color)),
        "role": permissions.get_role(workflow_id, effective_user_id) or "viewer",
        "workflow_id": workflow_id,
    }
    room_sockets[workflow_id].append(websocket)
    await _broadcast_room_presence(workflow_id, room_sockets)

    # ------------------------------------------------------------------
    # 6. Load / create pycrdt document
    # ------------------------------------------------------------------
    doc = await _get_doc(workflow_id)

    # ------------------------------------------------------------------
    # 7. Send initial SyncStep2 (full document update)
    # ------------------------------------------------------------------
    try:
        lock = _doc_locks.setdefault(workflow_id, asyncio.Lock())
        async with lock:
            full_update = doc.get_update(b"\x00")
        if full_update:
            # Native Yjs: [MSG_SYNC=0] [SYNC_STEP2=1] [full_update_bytes]
            response = bytes([MSG_SYNC, SYNC_STEP2]) + full_update
            await websocket.send_bytes(response)
            logger.debug(
                "Sent initial SyncStep2 (%d bytes) to %s",
                len(full_update),
                effective_user_id,
            )
    except Exception as exc:
        logger.warning("Failed to send initial SyncStep2: %s", exc)

    # ------------------------------------------------------------------
    # 8. Main read loop
    # ------------------------------------------------------------------
    try:
        while True:
            try:
                data = await websocket.receive_bytes()
            except WebSocketDisconnect:
                raise
            except Exception as exc:
                logger.debug("Receive error from %s: %s", effective_user_id, exc)
                break

            if len(data) < 1:
                continue

            msg_type = data[0]

            # ---- Sync messages (type 0) ----
            if msg_type == MSG_SYNC:
                if len(data) < 2:
                    continue

                sync_type = data[1]
                payload = data[2:]

                # -- SyncStep1: client sends state vector, server replies with diff --
                if sync_type == SYNC_STEP1:
                    if not rate_limiter.check(websocket, "sync"):
                        continue
                    try:
                        lock = _doc_locks.setdefault(workflow_id, asyncio.Lock())
                        async with lock:
                            diff = doc.get_update(bytes(payload))
                        if diff:
                            # Native Yjs: [MSG_SYNC=0] [SYNC_STEP2=1] [diff_bytes]
                            response = bytes([MSG_SYNC, SYNC_STEP2]) + diff
                            await websocket.send_bytes(response)
                            logger.debug(
                                "Sent SyncStep2 diff (%d bytes) to %s",
                                len(diff),
                                effective_user_id,
                            )
                    except Exception as exc:
                        logger.warning("SyncStep1 failed for %s: %s", effective_user_id, exc)
                    continue

                # -- SyncStep2: client receiving diff (server-to-client only) --
                elif sync_type == SYNC_STEP2:
                    # Client shouldn't send SyncStep2; ignore gracefully
                    logger.debug("Ignoring client-originated SyncStep2 from %s", effective_user_id)
                    continue

                # -- Update: client sends incremental update --
                elif sync_type == SYNC_UPDATE:
                    if read_only:
                        continue

                    # Rate limit
                    if not rate_limiter.check(websocket, "update"):
                        logger.debug(
                            "Rate limit exceeded for update from %s", effective_user_id
                        )
                        continue

                    try:
                        lock = _doc_locks.setdefault(workflow_id, asyncio.Lock())
                        async with lock:
                            doc.apply_update(bytes(payload))
                    except Exception as exc:
                        logger.warning(
                            "Failed to apply CRDT update from %s: %s",
                            effective_user_id,
                            exc,
                        )
                        continue

                    # Broadcast to other room members (same native format)
                    await _broadcast_to_room(
                        workflow_id,
                        data,  # already in native format: [0] [2] [payload]
                        exclude=websocket,
                        room_sockets=room_sockets,
                    )

                    # Audit log (fire-and-forget)
                    try:
                        store.add_audit_entry(
                            CollabAuditLogEntry(
                                workflow_id=workflow_id,
                                user_id=effective_user_id,
                                action="crdt_update",
                                payload={"update_bytes": len(payload)},
                            )
                        )
                    except Exception:
                        pass
                    continue

            # ---- Awareness messages (type 1) ----
            elif msg_type == MSG_AWARENESS:
                payload = data[1:]

                # Rate limit
                if not rate_limiter.check(websocket, "awareness"):
                    continue

                # Transparent relay to all other room members
                await _broadcast_to_room(
                    workflow_id,
                    data,  # already in native format: [1] [awareness_bytes]
                    exclude=websocket,
                    room_sockets=room_sockets,
                )
                continue

            # ---- Unknown message type ----
            else:
                logger.debug(
                    "Unknown Yjs message type %d from %s", msg_type, effective_user_id
                )

    except WebSocketDisconnect:
        logger.debug(
            "Yjs WS disconnected: workflow=%s user=%s", workflow_id, effective_user_id
        )
    except Exception as exc:
        logger.warning(
            "Yjs WS error: workflow=%s user=%s exc=%s",
            workflow_id,
            effective_user_id,
            exc,
        )
    finally:
        # ------------------------------------------------------------------
        # 9. Cleanup
        # ------------------------------------------------------------------
        rate_limiter.reset(websocket)

        # Remove from room
        if workflow_id in room_sockets:
            try:
                room_sockets[workflow_id].remove(websocket)
                if not room_sockets[workflow_id]:
                    del room_sockets[workflow_id]
                else:
                    await _broadcast_room_presence(workflow_id, room_sockets)
            except ValueError:
                pass

        # Close websocket gracefully
        try:
            await websocket.close()
        except Exception:
            pass
