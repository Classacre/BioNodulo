"""Runtime collaboration REST routes.

These endpoints handle live-room permissions, presence, and CRDT snapshots.
Comments, versions, and templates live in :mod:`bionodulo.api.collab_routes`.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException, Request

from bionodulo.api.app_state import app_state
from bionodulo.api.auth_dependencies import require_auth_payload
from bionodulo.api.collab_dependencies import (
    ensure_open_room_access,
    open_collab_rooms_enabled,
    require_workflow_role,
)
from bionodulo.api.schemas import (
    RoomStatusResponse,
    ShareWorkflowRequest,
    ShareWorkflowResponse,
)

collab_runtime_router = APIRouter()


def workflow_payload_to_flat_snapshot(workflow_id: str, body: dict[str, Any]) -> dict[str, Any]:
    """Normalize a workflow or snapshot payload to the flat CRDT schema."""
    snapshot = body.get("snapshot")
    if isinstance(snapshot, dict):
        meta = dict(snapshot.get("meta") or {})
        meta["id"] = workflow_id
        snapshot["meta"] = meta
        return snapshot

    workflow = body.get("workflow")
    if not isinstance(workflow, dict):
        raise HTTPException(status_code=400, detail="Expected workflow or snapshot payload")

    def keyed(items: Any) -> dict[str, Any]:
        result: dict[str, Any] = {}
        if not isinstance(items, list):
            return result
        for item in items:
            if not isinstance(item, dict):
                continue
            item_id = item.get("id")
            if item_id:
                result[str(item_id)] = item
        return result

    meta = {
        "id": workflow_id,
        "version": workflow.get("version") or "Alpha 1.5",
        "name": workflow.get("name") or "Untitled",
        "description": workflow.get("description") or "",
        "lastModified": datetime.now(timezone.utc).isoformat(),
    }
    return {
        "meta": meta,
        "nodes": keyed(workflow.get("nodes")),
        "edges": keyed(workflow.get("edges")),
        "groups": keyed(workflow.get("groups")),
        "viewport": workflow.get("viewport")
        if isinstance(workflow.get("viewport"), dict)
        else {"x": 0, "y": 0, "scale": 1.0},
    }


async def close_yjs_user_sessions(request: Request, workflow_id: str, user_id: str) -> None:
    """Reconnect a live Yjs user so changed room permissions take effect."""
    presence_manager = app_state(request).presence_manager
    for socket in presence_manager.sockets_for_user(workflow_id, user_id):
        try:
            await socket.close(code=4403, reason="Collaboration access changed")
        except Exception:
            pass


@collab_runtime_router.post("/collab/share", response_model=ShareWorkflowResponse)
async def collab_share(
    request: Request,
    body: ShareWorkflowRequest,
) -> dict[str, Any]:
    """Share a workflow with another user."""
    payload = require_auth_payload(request)
    caller_id = payload["sub"]
    permissions = require_workflow_role(request, body.workflow_id, caller_id, "share")

    share = permissions.grant(
        workflow_id=body.workflow_id,
        user_id=body.user_id,
        role=body.role,
        invited_by=caller_id,
    )
    if body.user_id != caller_id:
        await close_yjs_user_sessions(request, body.workflow_id, body.user_id)
    return {
        "share_id": share.id,
        "workflow_id": share.workflow_id,
        "user_id": share.user_id,
        "role": share.role,
        "invited_by": share.invited_by,
        "invited_at": share.invited_at,
    }


@collab_runtime_router.get("/collab/shares/{workflow_id}")
async def collab_list_shares(
    request: Request,
    workflow_id: str,
) -> dict[str, Any]:
    """List all shares for a given workflow."""
    payload = require_auth_payload(request)
    caller_id = payload["sub"]
    permissions = require_workflow_role(request, workflow_id, caller_id, "read")

    shares = permissions.list_users(workflow_id)
    return {"workflow_id": workflow_id, "shares": shares, "count": len(shares)}


@collab_runtime_router.get("/collab/presence")
async def collab_presence(
    request: Request,
) -> dict[str, Any]:
    """List authenticated live Yjs sessions across workflow rooms."""
    payload = require_auth_payload(request)
    caller_id = payload["sub"]
    presence_manager = app_state(request).presence_manager
    users: list[dict[str, Any]] = []

    open_rooms = open_collab_rooms_enabled()
    workflow_ids = {user["workflow_id"] for user in presence_manager.users()}
    for workflow_id in workflow_ids:
        if open_rooms:
            ensure_open_room_access(request, workflow_id, caller_id)
        else:
            try:
                require_workflow_role(request, workflow_id, caller_id, "read")
            except HTTPException:
                continue
        users.extend(presence_manager.users(workflow_id))

    return {"users": users, "count": len(users)}


@collab_runtime_router.get("/collab/workflows/{workflow_id}/snapshot")
async def collab_workflow_snapshot(
    request: Request,
    workflow_id: str,
) -> dict[str, Any]:
    """Return the current server-side CRDT workflow snapshot for follow/join."""
    payload = require_auth_payload(request)
    caller_id = payload["sub"]
    require_workflow_role(request, workflow_id, caller_id, "read")

    from bionodulo.collab.doc_store import extract_flat_snapshot
    from bionodulo.collab.yjs_native_handler import _get_doc

    doc = await _get_doc(workflow_id)
    snapshot = extract_flat_snapshot(doc)
    snapshot.setdefault("meta", {})["id"] = workflow_id
    return {"workflow_id": workflow_id, "snapshot": snapshot}


@collab_runtime_router.post("/collab/workflows/{workflow_id}/snapshot")
async def collab_publish_workflow_snapshot(
    request: Request,
    workflow_id: str,
    body: dict[str, Any],
) -> dict[str, Any]:
    """Replace and broadcast the server-side CRDT workflow snapshot."""
    payload = require_auth_payload(request)
    caller_id = payload["sub"]
    require_workflow_role(request, workflow_id, caller_id, "write")

    from bionodulo.collab.yjs_native_handler import publish_flat_snapshot_to_room

    snapshot = workflow_payload_to_flat_snapshot(workflow_id, body)
    room_sockets = getattr(request.app.state, "yjs_room_sockets", {})
    published = await publish_flat_snapshot_to_room(workflow_id, snapshot, room_sockets)
    return {
        "workflow_id": workflow_id,
        "snapshot": published,
        "nodes": len(published.get("nodes", {})),
        "edges": len(published.get("edges", {})),
        "groups": len(published.get("groups", {})),
    }


@collab_runtime_router.delete("/collab/share/{share_id}")
async def collab_revoke_share(
    request: Request,
    share_id: str,
) -> dict[str, str]:
    """Revoke a share by its share record ID."""
    store = app_state(request).collab_store
    share = store.get_share(share_id)
    if share is None:
        raise HTTPException(status_code=404, detail="Share not found")

    permissions = app_state(request).permission_checker
    payload = require_auth_payload(request)
    caller_id = payload["sub"]
    require_workflow_role(request, share.workflow_id, caller_id, "share")

    success = store.delete_share(share_id)
    if success:
        permissions.revoke(share.workflow_id, share.user_id)
        await close_yjs_user_sessions(request, share.workflow_id, share.user_id)
    return {"status": "revoked" if success else "not_found"}


@collab_runtime_router.get("/collab/room/{workflow_id}", response_model=RoomStatusResponse)
async def collab_room_status(
    request: Request,
    workflow_id: str,
) -> dict[str, Any]:
    """Get the current collaboration room status for a workflow."""
    payload = require_auth_payload(request)
    caller_id = payload["sub"]
    require_workflow_role(request, workflow_id, caller_id, "read")
    room_status = app_state(request).room_manager.room_status(workflow_id)
    live_status = app_state(request).presence_manager.room_status(
        workflow_id,
        created_at=room_status.get("created_at"),
    )
    return live_status if live_status["active"] else room_status
