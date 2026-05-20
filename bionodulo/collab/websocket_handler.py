"""Collaborative editing WebSocket endpoint with binary Yjs CRDT sync.

Handles connections at ``/ws/collab/{workflow_id}`` using the **binary
Yjs protocol** via :mod:`pycrdt`.  All messages are length-prefixed
binary frames.

Binary message format
---------------------
::

    [msg_type: u8] [payload_len: varint] [payload: bytes]

Message types:

- ``0`` — **SyncStep1** — client sends its state vector; server replies
  with SyncStep2 (the diff the client is missing).
- ``1`` — **SyncStep2** — full document state / diff for a client.
- ``2`` — **Update** — a binary CRDT update to be applied and broadcast.
- ``3`` — **Awareness** — cursor / selection / presence data.

Protocol flow
-------------
1. Client connects with ``?token=<jwt>`` query parameter.
2. Server validates JWT, extracts user info and role.
3. Server loads or creates a :class:`pycrdt.Doc` for the workflow.
4. Server sends **SyncStep2** (full state) as a binary frame.
5. Client sends **SyncStep1** (its state vector); server replies with
   the missing diff as **SyncStep2**.
6. Both sides send **Update** frames for local changes; the server
   applies them to the shared document and broadcasts to other clients.
7. **Awareness** frames are forwarded to all room members.

Server-side pings are sent every 30 s via :class:`HeartbeatManager`.
Rate limiting is enforced per client via :class:`RateLimiter`.
"""

from __future__ import annotations

import asyncio
import logging
import struct
from typing import Any

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

import pycrdt

from bionodulo.collab.auth import get_auth_ws, generate_user_id
from bionodulo.collab.doc_store import (
    get_or_create_doc,
    persist_doc_update,
    load_doc_from_db,
)
from bionodulo.collab.heartbeat import HeartbeatManager
from bionodulo.collab.models import CollabAuditLogEntry, CollabStore
from bionodulo.collab.permissions import PermissionChecker
from bionodulo.collab.presence import AwarenessManager
from bionodulo.collab.rate_limiter import RateLimiter
from bionodulo.collab.redis_broadcaster import RedisBroadcaster
from bionodulo.collab.room_manager import RoomManager, RoomUser

logger = logging.getLogger(__name__)

collab_websocket_router = APIRouter()

# Message type constants
MSG_SYNC_STEP1 = 0  # client state vector -> server
MSG_SYNC_STEP2 = 1  # server diff -> client
MSG_UPDATE = 2      # CRDT update
MSG_AWARENESS = 3   # awareness/presence data

# Singletons (safe because event-loop is single-threaded)
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
        fallback = _resolve_workspace_root() / "permissions.json"
        _permissions = PermissionChecker(
            store=_get_store(),
            fallback_file=fallback,
        )
    return _permissions


def _get_rate_limiter() -> RateLimiter:
    """Return the rate limiter singleton."""
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = RateLimiter()
    return _rate_limiter


def _get_room_manager(app_state: Any) -> RoomManager:
    """Return the RoomManager from app.state, creating lazily if needed."""
    if not hasattr(app_state, "room_manager") or app_state.room_manager is None:
        app_state.room_manager = RoomManager()
    return app_state.room_manager


def _get_heartbeat_manager(app_state: Any) -> HeartbeatManager:
    """Return the HeartbeatManager from app.state, creating lazily if needed."""
    if not hasattr(app_state, "heartbeat_manager") or app_state.heartbeat_manager is None:
        app_state.heartbeat_manager = HeartbeatManager()
    return app_state.heartbeat_manager


def _get_redis_broadcaster(app_state: Any) -> RedisBroadcaster:
    """Return the RedisBroadcaster from app.state, creating lazily if needed."""
    if (
        not hasattr(app_state, "redis_broadcaster")
        or app_state.redis_broadcaster is None
    ):
        app_state.redis_broadcaster = RedisBroadcaster()
        # Note: connect() must be called explicitly (async) from lifespan
    return app_state.redis_broadcaster


# ---------------------------------------------------------------------------
# Binary framing helpers
# ---------------------------------------------------------------------------

def _encode_varint(value: int) -> bytes:
    """Encode an unsigned integer as a varint.

    Uses the protobuf-style continuation-bit encoding:
    - 7 bits per byte, MSB=1 means more bytes follow.
    """
    result = bytearray()
    while value > 0x7F:
        result.append((value & 0x7F) | 0x80)
        value >>= 7
    result.append(value & 0x7F)
    return bytes(result)


def _decode_varint(data: bytes, offset: int = 0) -> tuple[int, int]:
    """Decode a varint from *data* at *offset*.

    Returns:
        ``(value, next_offset)``

    Raises:
        ValueError: If the varint is malformed or too long.
    """
    value = 0
    shift = 0
    i = offset
    while i < len(data):
        byte = data[i]
        value |= (byte & 0x7F) << shift
        if (byte & 0x80) == 0:
            return value, i + 1
        shift += 7
        i += 1
        if shift > 63:
            raise ValueError("Varint too long")
    raise ValueError("Incomplete varint")


def _pack_message(msg_type: int, payload: bytes) -> bytes:
    """Pack a message into the binary frame format.

    Returns:
        ``[msg_type: u8] [payload_len: varint] [payload: bytes]``
    """
    return bytes([msg_type]) + _encode_varint(len(payload)) + payload


def _unpack_message(data: bytes) -> tuple[int, bytes]:
    """Unpack a binary frame into (msg_type, payload).

    Raises:
        ValueError: If the frame is malformed.
    """
    if len(data) < 2:
        raise ValueError("Frame too short")
    msg_type = data[0]
    payload_len, payload_offset = _decode_varint(data, 1)
    payload = data[payload_offset:payload_offset + payload_len]
    if len(payload) != payload_len:
        raise ValueError(
            f"Payload length mismatch: expected {payload_len}, got {len(payload)}"
        )
    return msg_type, payload


# ---------------------------------------------------------------------------
# Document cache
# ---------------------------------------------------------------------------

_doc_cache: dict[str, pycrdt.Doc] = {}
_doc_observers: dict[str, Any] = {}
_doc_locks: dict[str, asyncio.Lock] = {}


def _get_doc_lock(workflow_id: str) -> asyncio.Lock:
    """Return a per-workflow document lock, creating lazily."""
    if workflow_id not in _doc_locks:
        _doc_locks[workflow_id] = asyncio.Lock()
    return _doc_locks[workflow_id]


async def _get_doc(workflow_id: str) -> pycrdt.Doc:
    """Return the pycrdt.Doc for *workflow_id*, loading from DB if needed."""
    if workflow_id not in _doc_cache:
        doc = get_or_create_doc(workflow_id)
        _doc_cache[workflow_id] = doc
    return _doc_cache[workflow_id]


def _observe_doc(
    workflow_id: str,
    doc: pycrdt.Doc,
    room_manager: RoomManager,
    sender_ws: WebSocket,
) -> None:
    """Attach an observer to *doc* that broadcasts changes to room members.

    The observer is only attached once per document (cached in
    ``_doc_observers``).
    """
    if workflow_id in _doc_observers:
        return

    def _on_change(event: Any, *, _workflow_id: str = workflow_id) -> None:
        """Callback invoked by pycrdt when the document changes."""
        update_bytes: bytes = getattr(event, "update", b"")
        if not update_bytes:
            return

        # Persist the update
        try:
            persist_doc_update(_workflow_id, update_bytes)
        except Exception as exc:
            logger.warning("Failed to persist update for %s: %s", _workflow_id, exc)

        # Broadcast to room members (except sender) — schedule on event loop
        packed = _pack_message(MSG_UPDATE, update_bytes)
        asyncio.create_task(
            _broadcast_binary(
                _workflow_id,
                packed,
                exclude=sender_ws,
            )
        )

    doc.observe(_on_change)
    _doc_observers[workflow_id] = _on_change
    logger.debug("Attached doc observer for %s", workflow_id)


async def _broadcast_binary(
    workflow_id: str,
    data: bytes,
    exclude: WebSocket | None = None,
) -> None:
    """Broadcast a binary message to all sockets in a room."""
    # Delegate to the active room manager set by the WebSocket handler.
    if _active_room_manager is not None:
        await _active_room_manager.broadcast_binary(workflow_id, data, exclude=exclude)


# Keep a reference to the active room manager for observer callbacks
_active_room_manager: RoomManager | None = None


def _set_active_room_manager(rm: RoomManager | None) -> None:
    global _active_room_manager
    _active_room_manager = rm


async def _broadcast_from_observer(
    workflow_id: str,
    data: bytes,
    exclude: WebSocket | None,
) -> None:
    """Broadcast binary data using the active room manager."""
    if _active_room_manager is not None:
        await _active_room_manager.broadcast_binary(workflow_id, data, exclude=exclude)


# ---------------------------------------------------------------------------
# WebSocket endpoint
# ---------------------------------------------------------------------------

@collab_websocket_router.websocket("/ws/collab/{workflow_id}")
async def collab_websocket(
    websocket: WebSocket,
    workflow_id: str,
    token: str = Query(default=""),
    user_id: str = Query(default=""),
    name: str = Query(default=""),
    color: str = Query(default="#3b82f6"),
) -> None:
    """Collaborative editing WebSocket with binary Yjs CRDT sync.

    Accepts a JWT token via the ``?token=`` query parameter for
    authentication.  All messages after connection are binary frames
    using the length-prefixed format defined in this module.

    Query parameters:

    - ``token`` — JWT authentication token (required)
    - ``user_id`` — Optional user identifier (overrides JWT ``sub`` claim)
    - ``name`` — Optional display name (overrides JWT ``name`` claim)
    - ``color`` — Hex color for cursor / presence
    """
    # --- 0. Parse query parameters for token --------------------------------
    query_params = dict(websocket.query_params)

    # --- 1. JWT Authentication ---------------------------------------------
    auth_payload = get_auth_ws(query_params)
    if auth_payload is None:
        # No valid token — reject connection
        await websocket.accept()
        await websocket.send_bytes(
            _pack_message(MSG_AWARENESS, b'{"error":"Authentication required"}')
        )
        await websocket.close(code=4401, reason="Unauthorized")
        return

    # Extract user info from JWT
    jwt_user_id = auth_payload.get("sub", "")
    jwt_name = auth_payload.get("name", "")
    jwt_role = auth_payload.get("role", "editor")

    # Query params override JWT claims
    effective_user_id = user_id or jwt_user_id or generate_user_id()
    effective_name = name or jwt_name or effective_user_id
    effective_role = jwt_role

    # --- 2. Accept WebSocket with binary subprotocol ------------------------
    subprotocols = websocket.scope.get("subprotocols", [])
    if "b-yjs" in subprotocols:
        await websocket.accept(subprotocol="b-yjs")
    else:
        await websocket.accept()

    # --- 3. Resolve managers ------------------------------------------------
    room_manager = _get_room_manager(websocket.app.state)
    heartbeat_mgr = _get_heartbeat_manager(websocket.app.state)
    permissions = _get_permissions()
    rate_limiter = _get_rate_limiter()
    store = _get_store()

    _set_active_room_manager(room_manager)

    # --- 4. Permission check ------------------------------------------------
    permissions.ensure_owner(workflow_id, effective_user_id)
    actual_role = permissions.get_role(workflow_id, effective_user_id) or effective_role
    read_only = actual_role in ("viewer",)

    if not permissions.can_read(workflow_id, effective_user_id):
        await websocket.send_bytes(
            _pack_message(MSG_AWARENESS, b'{"error":"Access denied"}')
        )
        await websocket.close(code=4403, reason="Forbidden")
        return

    # --- 5. Load / create pycrdt document ----------------------------------
    async with _get_doc_lock(workflow_id):
        doc = await _get_doc(workflow_id)

    # --- 6. Join room -------------------------------------------------------
    room_user = await room_manager.join(
        workflow_id=workflow_id,
        websocket=websocket,
        user_id=effective_user_id,
        user_name=effective_name,
        user_color=color,
        read_only=read_only,
        role=actual_role,
    )

    # --- 7. Register heartbeat ----------------------------------------------
    heartbeat_mgr.register(websocket)

    # --- 8. Attach document observer (once per workflow) --------------------
    async with _get_doc_lock(workflow_id):
        _observe_doc(workflow_id, doc, room_manager, websocket)

    # --- 9. Send initial SyncStep2 (full document update) -------------------
    try:
        # Send the complete document as an update (diff against empty state)
        full_update = doc.get_update(b"\x00")
        if full_update:
            sync_step2 = _pack_message(MSG_SYNC_STEP2, full_update)
            await websocket.send_bytes(sync_step2)
            logger.debug(
                "Sent SyncStep2 (%d bytes) to %s", len(full_update), effective_user_id
            )
    except Exception as exc:
        logger.warning("Failed to send initial SyncStep2: %s", exc)

    # --- 10. Send current awareness snapshot (transparent binary) -----------
    # Skip sending a JSON-wrapped awareness snapshot.  Awareness in the
    # y-protocols layer is opaque binary data (y-protocols/awareness codec).
    # The server relays awareness payloads transparently; clients discover
    # each other's presence organically once they start sending awareness
    # updates.  No synthetic initial message is needed.

    # --- 11. Main read loop -------------------------------------------------
    try:
        while True:
            try:
                data = await websocket.receive_bytes()
            except WebSocketDisconnect:
                raise
            except Exception as exc:
                logger.debug("Receive error from %s: %s", effective_user_id, exc)
                break

            # --- Parse binary frame -----------------------------------------
            try:
                msg_type, payload = _unpack_message(data)
            except ValueError as exc:
                logger.debug("Invalid binary frame from %s: %s", effective_user_id, exc)
                continue

            # --- Rate limiting ----------------------------------------------
            msg_type_str = {MSG_SYNC_STEP1: "sync", MSG_SYNC_STEP2: "sync", MSG_UPDATE: "update", MSG_AWARENESS: "awareness"}.get(msg_type, "update")
            if not rate_limiter.check(websocket, msg_type_str):
                logger.warning(
                    "Rate limit exceeded for %s (type=%s) from %s",
                    msg_type,
                    msg_type_str,
                    effective_user_id,
                )
                continue

            # --- Handle SyncStep1 (client state vector) ---------------------
            if msg_type == MSG_SYNC_STEP1:
                # Client sent its state vector — reply with the diff it needs
                try:
                    client_state_vector = payload
                    async with _get_doc_lock(workflow_id):
                        diff = doc.get_update(client_state_vector)
                    if diff:
                        response = _pack_message(MSG_SYNC_STEP2, diff)
                        await websocket.send_bytes(response)
                        logger.debug(
                            "Sent SyncStep2 diff (%d bytes) to %s",
                            len(diff),
                            effective_user_id,
                        )
                except Exception as exc:
                    logger.warning("SyncStep1 handling failed: %s", exc)
                continue

            # --- Handle SyncStep2 (from another client via server relay) ----
            if msg_type == MSG_SYNC_STEP2:
                # This is typically sent by the server only; ignore client-originated
                logger.debug("Ignoring client-originated SyncStep2 from %s", effective_user_id)
                continue

            # --- Handle Update (CRDT binary update) -------------------------
            if msg_type == MSG_UPDATE:
                if read_only:
                    continue

                try:
                    async with _get_doc_lock(workflow_id):
                        doc.apply_update(payload)
                except Exception as exc:
                    logger.warning(
                        "Failed to apply CRDT update from %s: %s", effective_user_id, exc
                    )
                    continue

                # Broadcast to room members (the doc observer will persist)
                packed = _pack_message(MSG_UPDATE, payload)
                await room_manager.broadcast_binary(
                    workflow_id, packed, exclude=websocket
                )

                # Audit log (fire-and-forget)
                try:
                    entry = CollabAuditLogEntry(
                        workflow_id=workflow_id,
                        user_id=effective_user_id,
                        action="crdt_update",
                        payload={"update_bytes": len(payload)},
                    )
                    store.add_audit_entry(entry)
                except Exception:
                    pass
                continue

            # --- Handle Awareness (cursor, selection, presence) -------------
            if msg_type == MSG_AWARENESS:
                # Transparent binary relay: awareness payloads are opaque y-protocols
                # bytes (y-protocols/awareness codec).  We must NOT parse or decode
                # them — just relay the raw payload bytes to all other room members.
                # The y-protocols library on the client side handles encoding/decoding.
                packed = _pack_message(MSG_AWARENESS, payload)
                await room_manager.broadcast_binary(workflow_id, packed, exclude=websocket)
                continue

            # --- Unknown type -----------------------------------------------
            logger.debug(
                "Unknown collab message type %d from %s", msg_type, effective_user_id
            )

    except WebSocketDisconnect:
        logger.debug("Collab WS disconnected: workflow=%s user=%s", workflow_id, effective_user_id)
    except Exception as exc:
        logger.warning("Collab WS error: workflow=%s user=%s exc=%s", workflow_id, effective_user_id, exc)
    finally:
        # --- 12. Cleanup ----------------------------------------------------
        heartbeat_mgr.unregister(websocket)
        rate_limiter.reset(websocket)
        await room_manager.leave(workflow_id, websocket)

        # Close websocket gracefully
        try:
            await websocket.close()
        except Exception:
            pass
