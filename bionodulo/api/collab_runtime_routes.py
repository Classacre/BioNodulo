"""Runtime collaboration REST routes.

These endpoints handle live-room permissions, presence, and CRDT snapshots.
Comments, versions, and templates live in :mod:`bionodulo.api.collab_routes`.
"""

from __future__ import annotations

import asyncio
import os
import re
import secrets
import shutil
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from fastapi import APIRouter, HTTPException, Request

from bionodulo.api.app_state import app_state
from bionodulo.api.auth_dependencies import require_auth_payload
from bionodulo.api.collab_dependencies import (
    ensure_open_room_access,
    open_collab_rooms_enabled,
    require_workflow_role,
)
from bionodulo.api.schemas import (
    CollabTunnelResponse,
    CreateCollabRoomRequest,
    CreateCollabRoomResponse,
    JoinCollabRoomRequest,
    JoinCollabRoomResponse,
    RoomStatusResponse,
    ShareWorkflowRequest,
    ShareWorkflowResponse,
)

collab_runtime_router = APIRouter()
_WORKFLOW_ID_RE = re.compile(r"^[a-zA-Z0-9._:-]{1,160}$")
_PUBLIC_URL_RE = re.compile(r"^https?://", re.IGNORECASE)
_LOCAL_HOSTS = {"localhost", "127.0.0.1", "0.0.0.0", "::1", "testserver"}


def _validate_workflow_id(workflow_id: str) -> str:
    if not _WORKFLOW_ID_RE.fullmatch(workflow_id):
        raise HTTPException(status_code=400, detail="Invalid workflow ID")
    return workflow_id


def _temporary_invites(request: Request) -> dict[str, dict[str, Any]]:
    invites = getattr(request.app.state, "collab_temporary_invites", None)
    if invites is None:
        invites = {}
        request.app.state.collab_temporary_invites = invites
    return invites


def _role_rank(role: str | None) -> int:
    return {"viewer": 0, "commenter": 1, "editor": 2, "owner": 3}.get(role or "", -1)


def _normalize_base_url(value: str | None) -> str | None:
    if not value:
        return None
    candidate = value.strip().rstrip("/")
    if not candidate or not _PUBLIC_URL_RE.match(candidate):
        return None
    return candidate


def _is_local_host(host_header: str | None) -> bool:
    if not host_header:
        return True
    host = host_header.split(",", 1)[0].strip()
    if host.startswith("[") and "]" in host:
        hostname = host[1 : host.index("]")]
    else:
        hostname = host.rsplit(":", 1)[0]
    return hostname.lower() in _LOCAL_HOSTS


def _public_base_from_request(request: Request) -> str | None:
    configured = _normalize_base_url(os.environ.get("BIONODULO_PUBLIC_URL"))
    if configured:
        return configured

    forwarded_host = request.headers.get("x-forwarded-host")
    host = forwarded_host or request.headers.get("host")
    if _is_local_host(host):
        return None

    proto = (request.headers.get("x-forwarded-proto") or request.url.scheme or "https").split(",", 1)[0].strip()
    prefix = request.headers.get("x-forwarded-prefix", "").strip().rstrip("/")
    return _normalize_base_url(f"{proto}://{host}{prefix}")


def _local_tunnel_target(request: Request) -> str:
    configured = _normalize_base_url(os.environ.get("BIONODULO_TUNNEL_TARGET"))
    if configured:
        return configured
    port = os.environ.get("BIONODULO_PORT") or str(request.url.port or 8000)
    return f"http://127.0.0.1:{port}"


def _resolve_cloudflared() -> str | None:
    env = os.environ.get("BIONODULO_CLOUDFLARED", "").strip()
    if env and os.path.isfile(env) and os.access(env, os.X_OK):
        return env
    return shutil.which("cloudflared")


async def _start_cloudflare_tunnel(request: Request) -> str | None:
    existing_url = getattr(request.app.state, "collab_public_url", None)
    existing_process = getattr(request.app.state, "collab_tunnel_process", None)
    if existing_url and existing_process and existing_process.returncode is None:
        return str(existing_url)

    cloudflared = _resolve_cloudflared()
    if not cloudflared:
        return None

    target = _local_tunnel_target(request)
    process = await asyncio.create_subprocess_exec(
        cloudflared,
        "tunnel",
        "--url",
        target,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    request.app.state.collab_tunnel_process = process
    request.app.state.collab_tunnel_provider = "cloudflare"

    async def capture(stream: asyncio.StreamReader | None) -> str | None:
        if stream is None:
            return None
        deadline = asyncio.get_running_loop().time() + 20
        while asyncio.get_running_loop().time() < deadline:
            try:
                line = await asyncio.wait_for(stream.readline(), timeout=1.0)
            except asyncio.TimeoutError:
                if process.returncode is not None:
                    return None
                continue
            if not line:
                return None
            text = line.decode(errors="replace")
            match = re.search(r"https://[a-zA-Z0-9.-]+\.trycloudflare\.com", text)
            if match:
                return match.group(0).rstrip("/")
        return None

    public_url = await capture(process.stderr) or await capture(process.stdout)
    if not public_url:
        process.terminate()
        try:
            await asyncio.wait_for(process.wait(), timeout=3)
        except asyncio.TimeoutError:
            process.kill()
        request.app.state.collab_tunnel_process = None
        return None

    request.app.state.collab_public_url = public_url
    return public_url


def _same_origin_public_url(public_url: str | None) -> str | None:
    normalized = _normalize_base_url(public_url)
    if not normalized:
        return None
    parsed = urlsplit(normalized)
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path.rstrip("/"), "", ""))


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
        "version": workflow.get("version") or "2.0",
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


@collab_runtime_router.get("/collab/tunnel", response_model=CollabTunnelResponse)
async def collab_tunnel_status(request: Request) -> dict[str, Any]:
    """Return the current public app URL, if requests already arrive through one."""
    public_url = _same_origin_public_url(
        _public_base_from_request(request) or getattr(request.app.state, "collab_public_url", None)
    )
    if public_url:
        request.app.state.collab_public_url = public_url
        if not getattr(request.app.state, "collab_tunnel_provider", None):
            request.app.state.collab_tunnel_provider = "external"
        return {
            "public_url": public_url,
            "provider": getattr(request.app.state, "collab_tunnel_provider", None),
            "status": "public",
            "message": "Public collaboration URL is available.",
        }
    return {
        "public_url": None,
        "provider": None,
        "status": "local",
        "message": "No public tunnel is active; generated links will only work on this machine or LAN.",
    }


@collab_runtime_router.post("/collab/tunnel", response_model=CollabTunnelResponse)
async def collab_start_tunnel(request: Request) -> dict[str, Any]:
    """Start a public quick tunnel when needed and when cloudflared is installed."""
    require_auth_payload(request)
    public_url = _same_origin_public_url(
        _public_base_from_request(request) or getattr(request.app.state, "collab_public_url", None)
    )
    if public_url:
        request.app.state.collab_public_url = public_url
        if not getattr(request.app.state, "collab_tunnel_provider", None):
            request.app.state.collab_tunnel_provider = "external"
        return {
            "public_url": public_url,
            "provider": getattr(request.app.state, "collab_tunnel_provider", None),
            "status": "public",
            "message": "Public collaboration URL is available.",
        }

    public_url = _same_origin_public_url(await _start_cloudflare_tunnel(request))
    if public_url:
        return {
            "public_url": public_url,
            "provider": "cloudflare",
            "status": "public",
            "message": "Started a temporary Cloudflare Tunnel for collaboration links.",
        }

    raise HTTPException(
        status_code=503,
        detail=(
            "No public tunnel is active and cloudflared was not found on PATH. "
            "Install cloudflared or open BioNodulo through an existing public tunnel."
        ),
    )


@collab_runtime_router.post("/collab/rooms", response_model=CreateCollabRoomResponse)
async def collab_create_room(
    request: Request,
    body: CreateCollabRoomRequest,
) -> dict[str, Any]:
    """Create a temporary invite link for an explicitly started room.

    The invite token is intentionally process-local. It survives while the
    host app is running, and disappears when the server stops or restarts.
    """
    workflow_id = _validate_workflow_id(body.workflow_id)
    payload = require_auth_payload(request)
    caller_id = payload["sub"]
    state = app_state(request)
    store = state.collab_store
    permissions = state.permission_checker

    shares = store.list_shares(workflow_id)
    if not any(share.role == "owner" for share in shares):
        permissions.ensure_owner(workflow_id, caller_id)
    elif not permissions.can_share(workflow_id, caller_id):
        raise HTTPException(status_code=403, detail="Only the owner can create share links")

    token = secrets.token_urlsafe(24)
    created_at = datetime.now(timezone.utc).isoformat()
    _temporary_invites(request)[token] = {
        "workflow_id": workflow_id,
        "role": body.role,
        "created_by": caller_id,
        "created_at": created_at,
    }
    return {
        "workflow_id": workflow_id,
        "invite_token": token,
        "role": body.role,
        "created_by": caller_id,
        "created_at": created_at,
        "public_url": _same_origin_public_url(
            _public_base_from_request(request) or getattr(request.app.state, "collab_public_url", None)
        ),
    }


@collab_runtime_router.post("/collab/rooms/join", response_model=JoinCollabRoomResponse)
async def collab_join_room(
    request: Request,
    body: JoinCollabRoomRequest,
) -> dict[str, Any]:
    """Join a room with a temporary invite token or existing membership."""
    workflow_id = _validate_workflow_id(body.workflow_id)
    payload = require_auth_payload(request)
    caller_id = payload["sub"]
    permissions = app_state(request).permission_checker
    invite_role: str | None = None

    if body.invite_token:
        invite = _temporary_invites(request).get(body.invite_token)
        if not invite or invite.get("workflow_id") != workflow_id:
            raise HTTPException(status_code=403, detail="Invalid or expired collaboration invite")
        invite_role = str(invite.get("role") or "editor")
        current_role = permissions.get_role(workflow_id, caller_id)
        if _role_rank(invite_role) > _role_rank(current_role):
            permissions.grant(
                workflow_id=workflow_id,
                user_id=caller_id,
                role=invite_role,
                invited_by=str(invite.get("created_by") or "share-link"),
            )

    if not permissions.can_read(workflow_id, caller_id):
        raise HTTPException(status_code=403, detail="Collaboration invite required")

    return {
        "workflow_id": workflow_id,
        "user_id": caller_id,
        "role": permissions.get_role(workflow_id, caller_id) or invite_role or "viewer",
        "joined_at": datetime.now(timezone.utc).isoformat(),
    }


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
