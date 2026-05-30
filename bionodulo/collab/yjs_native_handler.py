"""Yjs collaboration endpoint backed by pycrdt-websocket primitives.

The browser speaks the standard Yjs binary protocol. BioNodulo owns
authentication, authorization, room roster JSON messages, and audit metadata,
while :class:`pycrdt.websocket.YRoom` handles sync, awareness relay, update
broadcasting, and persistence through :mod:`pycrdt.store`.
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import os
import time
import uuid
from datetime import datetime, timezone
from typing import Any

import pycrdt
from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from pycrdt.websocket import YRoom, exception_logger
from pycrdt.websocket.yroom import read_message

from bionodulo.api.app_state import app_state_from_app
from bionodulo.collab.auth import generate_user_id, get_auth_ws
from bionodulo.collab.doc_store import (
    CRDT_TOP_LEVEL_MAPS,
    load_doc_from_db_async,
    persist_doc_update_async,
    ystore_for_workflow,
)
from bionodulo.collab.models import CollabAuditLogEntry, CollabStore
from bionodulo.collab.permissions import PermissionChecker
from bionodulo.collab.presence import PresenceManager
from bionodulo.collab.rate_limiter import RateLimiter
from bionodulo.collab.redis_broadcaster import RedisBroadcaster

logger = logging.getLogger(__name__)

yjs_router = APIRouter()

MSG_SYNC = 0
MSG_AWARENESS = 1
SYNC_STEP1 = 0
SYNC_STEP2 = 1
SYNC_UPDATE = 2


def _read_length_prefixed_payload(payload: bytes) -> bytes | None:
    """Decode a pycrdt/y-websocket payload without mutating the room doc."""
    try:
        return read_message(payload)
    except Exception:
        return None


def _open_room_join_enabled() -> bool:
    """Allow authenticated link visitors into trusted local/open rooms."""
    return os.environ.get("BIONODULO_COLLAB_OPEN_ROOMS", "").lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _store_for_websocket(websocket: WebSocket) -> CollabStore:
    return app_state_from_app(websocket.app).collab_store


def _permissions_for_websocket(websocket: WebSocket) -> PermissionChecker:
    return app_state_from_app(websocket.app).permission_checker


def _rate_limiter_for_websocket(websocket: WebSocket) -> RateLimiter:
    return app_state_from_app(websocket.app).rate_limiter


def _presence_for_websocket(websocket: WebSocket) -> PresenceManager:
    return app_state_from_app(websocket.app).presence_manager


def _redis_for_websocket(websocket: WebSocket) -> RedisBroadcaster | None:
    broadcaster = getattr(websocket.app.state, "redis_broadcaster", None)
    return broadcaster if isinstance(broadcaster, RedisBroadcaster) else None


_room_cache: dict[str, YRoom] = {}
_room_locks: dict[str, asyncio.Lock] = {}
_room_tasks: dict[str, asyncio.Task[None]] = {}
_room_accessed_at: dict[str, float] = {}
_room_redis_subscribed: set[str] = set()
_room_broadcasters: dict[str, RedisBroadcaster] = {}
_room_cleanup_task: asyncio.Task[None] | None = None
_SERVER_INSTANCE_ID = uuid.uuid4().hex


def _env_int(name: str, default: int, minimum: int) -> int:
    try:
        return max(minimum, int(os.environ.get(name, str(default))))
    except ValueError:
        return default


_ROOM_CACHE_TTL_SECONDS = _env_int("BIONODULO_YJS_ROOM_CACHE_TTL_SECONDS", 1800, 60)
_ROOM_CLEANUP_INTERVAL_SECONDS = _env_int("BIONODULO_YJS_ROOM_CLEANUP_INTERVAL_SECONDS", 300, 30)


def _touch_room(workflow_id: str) -> None:
    _room_accessed_at[workflow_id] = time.time()


def _message_should_replicate(data: bytes) -> bool:
    """Replicate only state-changing Yjs messages across Redis."""
    if not data:
        return False
    msg_type = data[0]
    if msg_type == MSG_AWARENESS:
        return True
    return msg_type == MSG_SYNC and len(data) > 1 and data[1] == SYNC_UPDATE


async def _apply_remote_yjs_message(workflow_id: str, room: YRoom, envelope_bytes: bytes) -> None:
    """Apply a Redis-delivered Yjs message to the local room."""
    try:
        envelope = json.loads(envelope_bytes.decode("utf-8"))
        if envelope.get("origin") == _SERVER_INSTANCE_ID:
            return
        if envelope.get("workflow_id") != workflow_id:
            return
        payload = envelope.get("payload")
        if not isinstance(payload, str):
            return
        message = base64.b64decode(payload.encode("ascii"), validate=True)
    except Exception as exc:
        logger.debug("Dropping malformed Redis Yjs envelope for %s: %s", workflow_id, exc)
        return

    if not message:
        return
    msg_type = message[0]
    if msg_type == MSG_SYNC:
        if len(message) < 2 or message[1] != SYNC_UPDATE:
            return
        update = _read_length_prefixed_payload(message[2:])
        if update is None:
            logger.debug("Dropping malformed Redis Yjs update for %s", workflow_id)
            return
        try:
            room.ydoc.apply_update(update)
        except Exception as exc:
            logger.debug("Failed to apply Redis Yjs update for %s: %s", workflow_id, exc)
    elif msg_type == MSG_AWARENESS:
        clients = tuple(room.clients)
        if clients:
            await asyncio.gather(*(client.send(message) for client in clients), return_exceptions=True)
        try:
            room.awareness.apply_awareness_update(read_message(message[1:]), room)
        except Exception as exc:
            logger.debug("Failed to apply Redis awareness for %s: %s", workflow_id, exc)


class FastAPIYChannel:
    """Adapter from FastAPI's WebSocket object to pycrdt's Channel protocol."""

    def __init__(
        self,
        websocket: WebSocket,
        *,
        workflow_id: str,
        user_id: str,
        read_only: bool,
        rate_limiter: RateLimiter,
        store: CollabStore,
        broadcaster: RedisBroadcaster | None = None,
    ) -> None:
        self.websocket = websocket
        self.path = workflow_id
        self.user_id = user_id
        self.read_only = read_only
        self.rate_limiter = rate_limiter
        self.store = store
        self.broadcaster = broadcaster

    def __aiter__(self) -> FastAPIYChannel:
        return self

    async def __anext__(self) -> bytes:
        try:
            return await self.recv()
        except WebSocketDisconnect:
            raise StopAsyncIteration from None

    async def send(self, message: bytes) -> None:
        await self.websocket.send_bytes(message)

    async def recv(self) -> bytes:
        while True:
            data = await self.websocket.receive_bytes()
            if not data:
                continue
            if not self._allow_message(data):
                continue
            await self._publish_remote(data)
            return data

    def _allow_message(self, data: bytes) -> bool:
        msg_type = data[0]
        if msg_type == MSG_SYNC and len(data) > 1:
            sync_type = data[1]
            if sync_type not in {SYNC_STEP1, SYNC_STEP2, SYNC_UPDATE}:
                logger.debug("Dropping unknown sync message type %s for %s", sync_type, self.path)
                return False
            payload = _read_length_prefixed_payload(data[2:])
            if payload is None or payload == b"":
                logger.debug("Dropping malformed sync payload for %s", self.path)
                return False
            if sync_type == SYNC_UPDATE:
                if self.read_only:
                    return False
                if not self.rate_limiter.check(self.websocket, "update"):
                    return False
                self._audit_update(len(data) - 2)
            elif sync_type == SYNC_STEP1:
                if not self.rate_limiter.check(self.websocket, "sync"):
                    return False
        elif msg_type == MSG_AWARENESS:
            if not _read_length_prefixed_payload(data[1:]):
                logger.debug("Dropping malformed awareness payload for %s", self.path)
                return False
            if not self.rate_limiter.check(self.websocket, "awareness"):
                return False
        return True

    def _audit_update(self, update_bytes: int) -> None:
        try:
            self.store.add_audit_entry(
                CollabAuditLogEntry(
                    workflow_id=self.path,
                    user_id=self.user_id,
                    action="crdt_update",
                    payload={"update_bytes": update_bytes},
                )
            )
        except Exception:
            pass

    async def _publish_remote(self, data: bytes) -> None:
        """Publish document updates and awareness to sibling server instances."""
        if self.broadcaster is None or not self.broadcaster.is_redis_available():
            return
        if not _message_should_replicate(data):
            return
        envelope = {
            "origin": _SERVER_INSTANCE_ID,
            "workflow_id": self.path,
            "payload": base64.b64encode(data).decode("ascii"),
        }
        try:
            await self.broadcaster.publish(
                self.path,
                json.dumps(envelope, separators=(",", ":")).encode("utf-8"),
                deliver_local=False,
            )
        except Exception as exc:
            logger.debug("Redis Yjs publish failed for %s: %s", self.path, exc)


async def _new_doc(workflow_id: str) -> pycrdt.Doc:
    doc = await load_doc_from_db_async(workflow_id)
    if doc is not None:
        return doc

    doc = pycrdt.Doc()
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
    return doc


async def _ensure_room_cleanup_task() -> None:
    global _room_cleanup_task
    if _room_cleanup_task is None or _room_cleanup_task.done():
        _room_cleanup_task = asyncio.create_task(
            _room_cache_cleanup_loop(),
            name="bionodulo-yroom-cache-cleanup",
        )


async def _room_cache_cleanup_loop() -> None:
    while True:
        await asyncio.sleep(_ROOM_CLEANUP_INTERVAL_SECONDS)
        await _cleanup_stale_rooms()


async def _cleanup_stale_rooms() -> None:
    now = time.time()
    for workflow_id, room in list(_room_cache.items()):
        if getattr(room, "clients", None):
            continue
        last_access = _room_accessed_at.get(workflow_id, now)
        if now - last_access >= _ROOM_CACHE_TTL_SECONDS:
            await _cleanup_doc_cache(workflow_id)


async def stop_room_cache_cleanup() -> None:
    """Stop background YRoom cache maintenance on application shutdown."""
    global _room_cleanup_task
    if _room_cleanup_task is not None and not _room_cleanup_task.done():
        _room_cleanup_task.cancel()
        try:
            await _room_cleanup_task
        except asyncio.CancelledError:
            pass
    _room_cleanup_task = None


async def _subscribe_room_to_redis(
    workflow_id: str,
    broadcaster: RedisBroadcaster | None,
) -> None:
    if (
        broadcaster is None
        or not broadcaster.is_redis_available()
        or workflow_id in _room_redis_subscribed
    ):
        return

    async def _on_redis_message(message: bytes, *, room_id: str = workflow_id) -> None:
        current_room = _room_cache.get(room_id)
        if current_room is None:
            return
        await _apply_remote_yjs_message(room_id, current_room, message)

    await broadcaster.subscribe(workflow_id, _on_redis_message)
    _room_redis_subscribed.add(workflow_id)
    _room_broadcasters[workflow_id] = broadcaster


async def _get_room(workflow_id: str, broadcaster: RedisBroadcaster | None = None) -> YRoom:
    _touch_room(workflow_id)
    await _ensure_room_cleanup_task()
    if workflow_id in _room_cache:
        room = _room_cache[workflow_id]
        await _subscribe_room_to_redis(workflow_id, broadcaster)
        return room

    lock = _room_locks.setdefault(workflow_id, asyncio.Lock())
    async with lock:
        if workflow_id in _room_cache:
            room = _room_cache[workflow_id]
            await _subscribe_room_to_redis(workflow_id, broadcaster)
            return room

        room = YRoom(
            ready=True,
            ystore=ystore_for_workflow(workflow_id),
            ydoc=await _new_doc(workflow_id),
            exception_handler=exception_logger,
            log=logger,
        )
        task = asyncio.create_task(room.start(), name=f"bionodulo-yroom-{workflow_id}")
        await room.started.wait()
        _room_cache[workflow_id] = room
        _room_tasks[workflow_id] = task
        await _subscribe_room_to_redis(workflow_id, broadcaster)
        return room


async def _cleanup_doc_cache(workflow_id: str, broadcaster: RedisBroadcaster | None = None) -> None:
    """Stop and drop an empty pycrdt room."""
    room = _room_cache.pop(workflow_id, None)
    task = _room_tasks.pop(workflow_id, None)
    _room_locks.pop(workflow_id, None)
    _room_accessed_at.pop(workflow_id, None)
    cleanup_broadcaster = broadcaster or _room_broadcasters.pop(workflow_id, None)
    if workflow_id in _room_redis_subscribed:
        if cleanup_broadcaster is not None:
            try:
                await cleanup_broadcaster.unsubscribe(workflow_id)
            except Exception as exc:
                logger.debug("Redis unsubscribe failed during YRoom cleanup for %s: %s", workflow_id, exc)
        _room_redis_subscribed.discard(workflow_id)
    if room is not None:
        try:
            await room.stop()
        except RuntimeError:
            pass
        except Exception as exc:
            logger.debug("Failed to stop YRoom %s: %s", workflow_id, exc)
    if task is not None:
        task.cancel()


async def _get_doc(workflow_id: str) -> pycrdt.Doc:
    """Return the active room document or load one from pycrdt-store."""
    room = _room_cache.get(workflow_id)
    if room is not None:
        return room.ydoc
    return await _new_doc(workflow_id)


def _room_presence_payload(
    workflow_id: str,
    room_sockets: dict[str, list[WebSocket]],
    presence_manager: PresenceManager | None = None,
) -> dict[str, Any]:
    if presence_manager is not None:
        return {
            "type": "room.presence",
            "workflow_id": workflow_id,
            "users": presence_manager.users(workflow_id),
        }
    users: list[dict[str, str]] = []
    for socket in room_sockets.get(workflow_id, []):
        presence = getattr(socket.state, "yjs_presence", None)
        if isinstance(presence, dict):
            users.append(presence)
    return {"type": "room.presence", "workflow_id": workflow_id, "users": users}


async def _broadcast_room_presence(
    workflow_id: str,
    room_sockets: dict[str, list[WebSocket]],
    presence_manager: PresenceManager | None = None,
    broadcaster: RedisBroadcaster | None = None,
) -> None:
    message = json.dumps(_room_presence_payload(workflow_id, room_sockets, presence_manager))
    targets = tuple(
        socket
        for socket in room_sockets.get(workflow_id, [])
        if not getattr(socket.state, "yjs_binary_only", False)
    )
    if not targets:
        return
    results = await asyncio.gather(
        *(socket.send_text(message) for socket in targets),
        return_exceptions=True,
    )
    failed = {socket for socket, result in zip(targets, results) if isinstance(result, Exception)}
    if failed and workflow_id in room_sockets:
        room_sockets[workflow_id] = [
            socket for socket in room_sockets[workflow_id] if socket not in failed
        ]
        if not room_sockets[workflow_id]:
            del room_sockets[workflow_id]
            await _cleanup_doc_cache(workflow_id, broadcaster)


def _replace_flat_snapshot(doc: pycrdt.Doc, snapshot: dict[str, Any]) -> None:
    with doc.transaction():
        for map_name in CRDT_TOP_LEVEL_MAPS:
            target = doc.get(map_name, type=pycrdt.Map)
            for key in list(dict(target).keys()):
                del target[key]
            values = snapshot.get(map_name, {})
            if isinstance(values, dict):
                for key, value in values.items():
                    target[str(key)] = value


async def publish_flat_snapshot_to_room(
    workflow_id: str,
    snapshot: dict[str, Any],
    room_sockets: dict[str, list[WebSocket]] | None = None,
) -> dict[str, Any]:
    """Replace a room document with a flat snapshot.

    Active rooms broadcast through pycrdt-websocket's YRoom observer. Inactive
    rooms are persisted as a full update through pycrdt-store so the next
    collaborator hydrates the same instance.
    """
    del room_sockets
    snapshot = dict(snapshot)
    meta = dict(snapshot.get("meta") or {})
    meta["id"] = workflow_id
    meta.setdefault("version", "2.0")
    meta.setdefault("name", "Untitled")
    meta["lastModified"] = datetime.now(timezone.utc).isoformat()
    snapshot["meta"] = meta

    active_room = _room_cache.get(workflow_id)
    doc = active_room.ydoc if active_room is not None else await _new_doc(workflow_id)
    _replace_flat_snapshot(doc, snapshot)
    if active_room is None:
        await persist_doc_update_async(workflow_id, doc.get_update(b"\x00"))
    return snapshot


@yjs_router.websocket("/ws/collab/{workflow_id}")
async def yjs_websocket(
    websocket: WebSocket,
    workflow_id: str,
    token: str = Query(default=""),
    name: str = Query(default=""),
    color: str = Query(default="#3b82f6"),
    session_id: str = Query(default=""),
    client: str = Query(default=""),
) -> None:
    del token, name
    query_params = dict(websocket.query_params)
    auth_payload = get_auth_ws(query_params)
    if auth_payload is None:
        await websocket.accept()
        await websocket.close(code=4401, reason="Unauthorized")
        return

    effective_user_id = auth_payload.get("sub", "") or generate_user_id()
    permissions = _permissions_for_websocket(websocket)
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

    subprotocols = websocket.scope.get("subprotocols", [])
    await websocket.accept(subprotocol="b-yjs" if "b-yjs" in subprotocols else None)
    websocket.state.yjs_binary_only = client in {"y-websocket", "y-websocket-provider"}

    rate_limiter = _rate_limiter_for_websocket(websocket)
    store = _store_for_websocket(websocket)
    presence_manager = _presence_for_websocket(websocket)
    broadcaster = _redis_for_websocket(websocket)
    room_sockets = websocket.app.state.yjs_room_sockets
    room_sockets.setdefault(workflow_id, [])

    safe_session_id = session_id if session_id.replace("-", "").replace("_", "").isalnum() else ""
    websocket.state.yjs_presence = {
        "session_id": safe_session_id[:80] or uuid.uuid4().hex,
        "user_id": effective_user_id,
        "name": str(auth_payload.get("name", effective_user_id)),
        "color": str(auth_payload.get("color", color)),
        "role": permissions.get_role(workflow_id, effective_user_id) or "viewer",
        "workflow_id": workflow_id,
    }
    room_sockets[workflow_id].append(websocket)
    presence_manager.register(workflow_id, websocket.state.yjs_presence, socket=websocket)
    await _broadcast_room_presence(workflow_id, room_sockets, presence_manager, broadcaster)

    room = await _get_room(workflow_id, broadcaster)
    channel = FastAPIYChannel(
        websocket,
        workflow_id=workflow_id,
        user_id=effective_user_id,
        read_only=read_only,
        rate_limiter=rate_limiter,
        store=store,
        broadcaster=broadcaster,
    )

    try:
        await room.serve(channel)
    except WebSocketDisconnect:
        logger.debug("Yjs WS disconnected: workflow=%s user=%s", workflow_id, effective_user_id)
    except Exception as exc:
        logger.warning("Yjs WS error: workflow=%s user=%s exc=%s", workflow_id, effective_user_id, exc)
    finally:
        rate_limiter.reset(websocket)
        presence_manager.unregister(
            workflow_id,
            str(getattr(websocket.state, "yjs_presence", {}).get("session_id", "")),
        )
        if workflow_id in room_sockets:
            try:
                room_sockets[workflow_id].remove(websocket)
            except ValueError:
                pass
            if not room_sockets[workflow_id]:
                del room_sockets[workflow_id]
                await _cleanup_doc_cache(workflow_id, broadcaster)
            else:
                await _broadcast_room_presence(workflow_id, room_sockets, presence_manager, broadcaster)
        try:
            await websocket.close()
        except Exception:
            pass
