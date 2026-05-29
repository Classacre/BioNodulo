"""JWT authentication system for collaborative editing.

Provides token creation, validation, and WebSocket query-parameter
extraction. The secret key is read lazily from ``BIONODULO_JWT_SECRET`` or
from a workspace-local secret file.

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

JWT_ALGORITHM = "HS256"
JWT_AUDIENCE = "bionodulo:auth"
DEFAULT_EXPIRY_HOURS = 24
OIDC_ISSUER = os.environ.get("BIONODULO_OIDC_ISSUER", "").rstrip("/")
OIDC_AUDIENCE = os.environ.get("BIONODULO_OIDC_AUDIENCE", JWT_AUDIENCE)
OIDC_JWKS_URL = os.environ.get("BIONODULO_OIDC_JWKS_URL", "")
_OIDC_JWKS_CLIENT: jwt.PyJWKClient | None = None
_JWT_SECRET_CACHE: str | None = None
JWT_SECRET = ""


def _jwt_secret() -> str:
    """Resolve the local JWT secret lazily and keep it stable per workspace."""
    global _JWT_SECRET_CACHE, JWT_SECRET
    if _JWT_SECRET_CACHE:
        return _JWT_SECRET_CACHE

    env_secret = os.environ.get("BIONODULO_JWT_SECRET", "").strip()
    if env_secret:
        _JWT_SECRET_CACHE = env_secret
        JWT_SECRET = env_secret
        return env_secret

    from bionodulo.core.workspace import resolve_workspace_root

    secret_path = resolve_workspace_root() / ".bionodulo_jwt_secret"
    try:
        existing = secret_path.read_text(encoding="utf-8").strip()
        if existing:
            _JWT_SECRET_CACHE = existing
            JWT_SECRET = existing
            return existing
    except FileNotFoundError:
        pass
    except OSError as exc:
        logger.warning("Could not read workspace JWT secret file: %s", exc)

    generated = secrets.token_hex(32)
    try:
        secret_path.parent.mkdir(parents=True, exist_ok=True)
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        fd = os.open(str(secret_path), flags, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(generated)
            fh.write("\n")
    except FileExistsError:
        existing = secret_path.read_text(encoding="utf-8").strip()
        if existing:
            generated = existing
    except OSError as exc:
        logger.warning(
            "BIONODULO_JWT_SECRET not set and workspace secret could not be persisted: %s. "
            "Tokens will not survive server restarts.",
            exc,
        )
    else:
        logger.info("Created workspace-local JWT secret at %s", secret_path)

    _JWT_SECRET_CACHE = generated
    JWT_SECRET = generated
    return generated


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


def _looks_like_local_token(token: str) -> bool:
    """Return True for BioNodulo-issued JWTs without verifying them."""
    try:
        header = jwt.get_unverified_header(token)
        payload = jwt.decode(
            token,
            options={
                "verify_signature": False,
                "verify_exp": False,
                "verify_aud": False,
            },
        )
    except jwt.InvalidTokenError:
        return False
    aud = payload.get("aud")
    audiences = aud if isinstance(aud, list) else [aud]
    return header.get("alg") == JWT_ALGORITHM and JWT_AUDIENCE in audiences


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
        _jwt_secret(),
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
            _jwt_secret(),
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
        if _looks_like_local_token(token):
            return None
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
