"""Shared authentication dependencies for REST endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from bionodulo.collab.auth import get_token_from_header_or_query, validate_token

security_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security_scheme),
) -> dict[str, Any] | None:
    """Validate the Bearer token from the Authorization header."""
    if credentials is None:
        return None
    return validate_token(credentials.credentials)


def require_auth_payload(request: Request) -> dict[str, Any]:
    """Extract and validate a token from Authorization or query params."""
    token = get_token_from_header_or_query(request)
    payload = validate_token(token) if token else None
    if payload is None:
        raise HTTPException(status_code=401, detail="Invalid or missing authentication token")
    return payload
