"""Yjs collaboration endpoint backed by pycrdt-websocket primitives.

The browser speaks the standard Yjs binary protocol. BioNodulo owns
authentication, authorization, room roster JSON messages, and audit metadata,
while :class:`pycrdt.websocket.YRoom` handles sync, awareness relay, update
broadcasting, and persistence through :mod:`pycrdt.store`.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
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
    load_doc_from_db,
    persist_doc_update,
    ystore_for_workflow,
)
from bionodulo.collab.models import CollabAuditLogEntry, CollabStore
from bionodulo.collab.permissions import PermissionChecker
from bionodulo.collab.rate_limiter import RateLimiter

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


_room_cache: dict[str, YRoom] = {}
_room_locks: dict[str, asyncio.Lock] = {}
_room_tasks: dict[str, asyncio.Task[None]] = {}


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
    ) -> None:
        self.websocket = websocket
        self.path = workflow_id
        self.user_id = user_id
        self.read_only = read_only
        self.rate_limiter = rate_limiter
        self.store = store

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


async def _new_doc(workflow_id: str) -> pycrdt.Doc:
    doc = await asyncio.to_thread(load_doc_from_db, workflow_id)
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


async def _get_room(workflow_id: str) -> YRoom:
    if workflow_id in _room_cache:
        return _room_cache[workflow_id]

    lock = _room_locks.setdefault(workflow_id, asyncio.Lock())
    async with lock:
        if workflow_id in _room_cache:
            return _room_cache[workflow_id]

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
        return room


async def _cleanup_doc_cache(workflow_id: str) -> None:
    """Stop and drop an empty pycrdt room."""
    room = _room_cache.pop(workflow_id, None)
    task = _room_tasks.pop(workflow_id, None)
    _room_locks.pop(workflow_id, None)
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
) -> dict[str, Any]:
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
    message = json.dumps(_room_presence_payload(workflow_id, room_sockets))
    targets = tuple(room_sockets.get(workflow_id, []))
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
            await _cleanup_doc_cache(workflow_id)


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
    meta.setdefault("version", "Alpha 1.5")
    meta.setdefault("name", "Untitled")
    meta["lastModified"] = datetime.now(timezone.utc).isoformat()
    snapshot["meta"] = meta

    active_room = _room_cache.get(workflow_id)
    doc = active_room.ydoc if active_room is not None else await _new_doc(workflow_id)
    _replace_flat_snapshot(doc, snapshot)
    if active_room is None:
        await asyncio.to_thread(persist_doc_update, workflow_id, doc.get_update(b"\x00"))
    return snapshot


@yjs_router.websocket("/ws/collab/{workflow_id}")
async def yjs_websocket(
    websocket: WebSocket,
    workflow_id: str,
    token: str = Query(default=""),
    name: str = Query(default=""),
    color: str = Query(default="#3b82f6"),
    session_id: str = Query(default=""),
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

    subprotocols = websocket.scope.get("subprotocols", [])
    await websocket.accept(subprotocol="b-yjs" if "b-yjs" in subprotocols else None)

    rate_limiter = _rate_limiter_for_websocket(websocket)
    store = _store_for_websocket(websocket)
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
    await _broadcast_room_presence(workflow_id, room_sockets)

    room = await _get_room(workflow_id)
    channel = FastAPIYChannel(
        websocket,
        workflow_id=workflow_id,
        user_id=effective_user_id,
        read_only=read_only,
        rate_limiter=rate_limiter,
        store=store,
    )

    try:
        await room.serve(channel)
    except WebSocketDisconnect:
        logger.debug("Yjs WS disconnected: workflow=%s user=%s", workflow_id, effective_user_id)
    except Exception as exc:
        logger.warning("Yjs WS error: workflow=%s user=%s exc=%s", workflow_id, effective_user_id, exc)
    finally:
        rate_limiter.reset(websocket)
        if workflow_id in room_sockets:
            try:
                room_sockets[workflow_id].remove(websocket)
            except ValueError:
                pass
            if not room_sockets[workflow_id]:
                del room_sockets[workflow_id]
                await _cleanup_doc_cache(workflow_id)
            else:
                await _broadcast_room_presence(workflow_id, room_sockets)
        try:
            await websocket.close()
        except Exception:
            pass
