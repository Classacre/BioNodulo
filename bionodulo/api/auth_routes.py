"""Authentication REST routes."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request

from bionodulo.api.auth_dependencies import get_current_user
from bionodulo.api.rate_limits import limiter
from bionodulo.api.schemas import AuthMeResponse, AuthTokenRequest, AuthTokenResponse
from bionodulo.collab.auth import create_token, generate_user_id

auth_router = APIRouter()


@auth_router.post("/auth/token", response_model=AuthTokenResponse)
@limiter.limit("30/minute")
async def auth_create_token(request: Request, body: AuthTokenRequest) -> dict[str, Any]:
    """Create a new JWT authentication token."""
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
