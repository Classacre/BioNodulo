"""Authentication REST routes."""

from __future__ import annotations

import os
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request

from bionodulo.api.auth_dependencies import get_current_user
from bionodulo.api.rate_limits import limiter
from bionodulo.api.schemas import AuthMeResponse, AuthTokenRequest, AuthTokenResponse
from bionodulo.collab.auth import create_token, generate_user_id

auth_router = APIRouter()


def _anonymous_token_allowed(request: Request) -> bool:
    """Whether anonymous editor-JWT minting is permitted here (audit M9).

    `/auth/token` hands out an editor-role collaboration JWT with no proof of
    identity. That is acceptable for the SINGLE-USER local desktop app, but in a
    shared/multi-tenant editor deployment it lets anyone mint an editing token.
    Safe-by-default: DENY when running in editor/cloud mode, unless an operator
    explicitly opts in with BIONODULO_ALLOW_ANONYMOUS_COLLAB=1.
    """
    opt_in = os.environ.get(
        "BIONODULO_ALLOW_ANONYMOUS_COLLAB", ""
    ).strip().lower() in ("1", "true", "yes", "on")
    if opt_in:
        return True
    cloud_settings = getattr(request.app.state, "cloud_settings", None)
    editor_mode = bool(getattr(cloud_settings, "editor_mode", False))
    # Local (non-editor) desktop mode keeps the existing single-user behaviour.
    return not editor_mode


@auth_router.post("/auth/token", response_model=AuthTokenResponse)
@limiter.limit("30/minute")
async def auth_create_token(request: Request, body: AuthTokenRequest) -> dict[str, Any]:
    """Create a new JWT authentication token."""
    if not _anonymous_token_allowed(request):
        raise HTTPException(
            status_code=403,
            detail=(
                "Anonymous token minting is disabled in shared editor mode. Set "
                "BIONODULO_ALLOW_ANONYMOUS_COLLAB=1 to opt in for a trusted "
                "self-host deployment."
            ),
        )
    user_id = generate_user_id()
    token = create_token(
        user_id=user_id,
        name=body.name,
        role="editor",
        expiry_hours=24,
    )
    return {
        "token": token,
        "user_id": user_id,
        "name": body.name,
    }


@auth_router.get("/auth/me", response_model=AuthMeResponse)
async def auth_me(
    user: dict[str, Any] | None = Depends(get_current_user),
) -> dict[str, Any]:
    """Return the currently authenticated user's details."""
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid or missing authentication token")
    return {
        "user_id": user.get("sub", ""),
        "name": user.get("name", ""),
        "role": user.get("role", "editor"),
    }
