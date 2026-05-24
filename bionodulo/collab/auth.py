"""JWT authentication system for collaborative editing.

Provides token creation, validation, and WebSocket query-parameter
extraction. The secret key is read from ``BIONODULO_JWT_SECRET`` or
auto-generated on first import (sufficient for single-instance deployments).

Token payload
-------------
- ``sub``: user_id (opaque string)
- ``name``: human-readable display name
- ``role``: one of ``owner``, ``editor``, ``viewer``, ``commenter``
- ``iat``: issued-at Unix timestamp
- ``exp``: expiration Unix timestamp

Usage
-----
>>> from bionodulo.collab.auth import create_token, validate_token
>>> token = create_token("user-123", "Alice", "editor")
>>> payload = validate_token(token)
>>> payload["sub"]
'user-123'
"""

from __future__ import annotations

import logging
import os
import secrets
import time
import uuid
from typing import Any

import jwt
from fastapi_users.jwt import decode_jwt, generate_jwt

logger = logging.getLogger(__name__)

# JWT secret — read from env or generate a random 32-byte hex string.
# In production, always set BIONODULO_JWT_SECRET to a stable value.
JWT_SECRET: str = os.environ.get("BIONODULO_JWT_SECRET", "")
if not JWT_SECRET:
    JWT_SECRET = secrets.token_hex(32)
    logger.warning(
        "BIONODULO_JWT_SECRET not set — using auto-generated secret. "
        "Tokens will not survive server restarts."
    )

JWT_ALGORITHM = "HS256"
JWT_AUDIENCE = "bionodulo:auth"
DEFAULT_EXPIRY_HOURS = 24
OIDC_ISSUER = os.environ.get("BIONODULO_OIDC_ISSUER", "").rstrip("/")
OIDC_AUDIENCE = os.environ.get("BIONODULO_OIDC_AUDIENCE", JWT_AUDIENCE)
OIDC_JWKS_URL = os.environ.get("BIONODULO_OIDC_JWKS_URL", "")
_OIDC_JWKS_CLIENT: jwt.PyJWKClient | None = None


def _oidc_jwks_client() -> jwt.PyJWKClient | None:
    """Return a cached JWKS client for external OIDC providers."""
    global _OIDC_JWKS_CLIENT
    if not OIDC_ISSUER and not OIDC_JWKS_URL:
        return None
    if _OIDC_JWKS_CLIENT is None:
        jwks_url = OIDC_JWKS_URL or f"{OIDC_ISSUER}/.well-known/jwks.json"
        _OIDC_JWKS_CLIENT = jwt.PyJWKClient(jwks_url)
    return _OIDC_JWKS_CLIENT


def _validate_oidc_token(token: str) -> dict[str, Any] | None:
    """Validate a JWT from Keycloak, SuperTokens, or another OIDC provider."""
    client = _oidc_jwks_client()
    if client is None:
        return None
    try:
        signing_key = client.get_signing_key_from_jwt(token)
        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256", "RS384", "RS512", "ES256", "ES384", "ES512"],
            audience=OIDC_AUDIENCE,
            issuer=OIDC_ISSUER or None,
        )
        if not payload.get("sub"):
            return None
        payload.setdefault("role", "editor")
        payload.setdefault("name", payload.get("preferred_username") or payload.get("email") or payload["sub"])
        return payload
    except jwt.InvalidTokenError as exc:
        logger.debug("OIDC JWT validation failed: %s", exc)
    except Exception as exc:
        logger.debug("OIDC JWKS validation failed: %s", exc)
    return None


def create_token(
    user_id: str,
    name: str,
    role: str = "editor",
    expiry_hours: int = DEFAULT_EXPIRY_HOURS,
) -> str:
    """Create a signed JWT for a user.

    Args:
        user_id: Opaque user identifier (persisted in ``sub`` claim).
        name: Human-readable display name.
        role: Permission role — ``owner`` | ``editor`` | ``viewer`` | ``commenter``.
        expiry_hours: Token lifetime in hours.

    Returns:
        A compact-serialised JWT string.
    """
    now = int(time.time())
    payload: dict[str, Any] = {
        "sub": user_id,
        "name": name,
        "role": role,
        "iat": now,
        "aud": JWT_AUDIENCE,
    }
    return generate_jwt(
        payload,
        JWT_SECRET,
        lifetime_seconds=expiry_hours * 3600,
        algorithm=JWT_ALGORITHM,
    )


def validate_token(token: str) -> dict[str, Any] | None:
    """Validate a JWT and return its payload, or ``None`` if invalid.

    Args:
        token: The compact-serialised JWT string.

    Returns:
        The decoded payload dict, or ``None`` if the token is expired,
        malformed, or has an invalid signature.
    """
    try:
        payload = decode_jwt(
            token,
            JWT_SECRET,
            audience=[JWT_AUDIENCE],
            algorithms=[JWT_ALGORITHM],
        )
        if not payload.get("sub"):
            return None
        return payload
    except jwt.ExpiredSignatureError:
        logger.debug("JWT validation failed: expired signature")
        return None
    except jwt.InvalidTokenError as exc:
        logger.debug("JWT validation failed: %s", exc)
        return _validate_oidc_token(token)


def generate_user_id() -> str:
    """Generate a unique user identifier.

    Returns:
        A v4 UUID without dashes, prefixed with ``u_``.
    """
    return f"u_{uuid.uuid4().hex}"


def get_token_from_header_or_query(request) -> str | None:
    """Extract a JWT token from request headers or query parameters.

    Checks the ``Authorization: Bearer <token>`` header first, then
    falls back to the ``?token=<jwt>`` query parameter.

    Args:
        request: A FastAPI/starlette Request object.

    Returns:
        The raw JWT string, or ``None`` if no token was found.
    """
    # 1. Check Authorization header
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:].strip()
        if token:
            return token
    # 2. Check query parameter
    token = request.query_params.get("token", "")
    if token:
        return token
    return None


def get_auth_ws(query_params: dict[str, str]) -> dict[str, Any] | None:
    """Extract and validate a JWT from WebSocket query parameters.

    Expects ``?token=<jwt>`` in the connection URL.

    Args:
        query_params: Parsed query-string parameters (key -> value).

    Returns:
        The decoded token payload, or ``None`` if no token was provided
        or the token is invalid.
    """
    token = query_params.get("token", "")
    if not token:
        logger.debug("No token in WebSocket query params")
        return None
    payload = validate_token(token)
    if payload is None:
        logger.debug("WebSocket token validation failed")
    return payload
