"""Shared collaboration auth and permission helpers for REST and WebSockets."""

from __future__ import annotations

import os
from typing import Any

from fastapi import HTTPException, Request

from bionodulo.api.app_state import app_state


def open_collab_rooms_enabled() -> bool:
    """Return whether trusted local/open collaboration rooms are enabled."""
    return os.environ.get("BIONODULO_COLLAB_OPEN_ROOMS", "").lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def ensure_open_room_access(request: Request, workflow_id: str, user_id: str, role: str = "editor") -> None:
    """Grant trusted local/open-room visitors access before permission checks."""
    if not open_collab_rooms_enabled():
        return
    permissions = app_state(request).permission_checker
    permissions.ensure_owner(workflow_id, user_id)
    if not permissions.can_read(workflow_id, user_id):
        permissions.grant(
            workflow_id=workflow_id,
            user_id=user_id,
            role=role,
            invited_by="open-room-link",
        )


def require_workflow_role(
    request: Request,
    workflow_id: str,
    user_id: str,
    role: str,
    *,
    open_room_role: str = "editor",
) -> Any:
    """Ensure a user has the requested role and return the permission checker."""
    permissions = app_state(request).permission_checker
    permissions.ensure_owner(workflow_id, user_id)
    ensure_open_room_access(request, workflow_id, user_id, role=open_room_role)
    checks = {
        "read": permissions.can_read,
        "comment": permissions.can_comment,
        "write": permissions.can_write,
        "execute": permissions.can_execute,
        "share": permissions.can_share,
    }
    check = checks.get(role)
    if check is None:
        raise ValueError(f"Unknown workflow role check: {role}")
    if not check(workflow_id, user_id):
        detail = {
            "read": "Access denied",
            "comment": "Comment permission required",
            "write": "Editor access required",
            "execute": "Execute permission required",
            "share": "Only the owner can share workflows",
        }[role]
        raise HTTPException(status_code=403, detail=detail)
    return permissions
