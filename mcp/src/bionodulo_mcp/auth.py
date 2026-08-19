"""Authentication providers for the BioNodulo MCP server.

The BioNodulo cloud API accepts a Clerk session JWT as
``Authorization: Bearer <token>``. Session JWTs are short-lived (~minutes),
so this module supports two strategies:

1. ``StaticTokenProvider`` — a fixed token from ``BIONODULO_AUTH_TOKEN``.
2. ``ClerkSessionTokenProvider`` — keeps a fresh session JWT by using the
   Clerk Backend API (``CLERK_SECRET_KEY``) to mint short-lived tokens from
   the user's most recently active session. This mirrors what the website
   does client-side, but keeps the secret key entirely server-side.

The Clerk Frontend API is behind Cloudflare bot protection, so all Clerk
calls use a browser-like User-Agent.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass

import httpx

CLERK_API_BASE = "https://api.clerk.com/v1"
# Cloudflare error 1010 blocks obvious bot user-agents on Clerk endpoints.
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36 BioNodulo-MCP"
)

DEFAULT_TOKEN_TTL_SECONDS = 600
REFRESH_MARGIN_SECONDS = 60


class AuthError(RuntimeError):
    """Raised when a token cannot be obtained."""


class StaticTokenProvider:
    """Always returns the same pre-minted token."""

    def __init__(self, token: str) -> None:
        self._token = token

    async def get_token(self) -> str:
        return self._token


@dataclass
class _CachedToken:
    jwt: str
    expires_at: float  # epoch seconds


class ClerkSessionTokenProvider:
    """Mints short-lived Clerk session JWTs via the Clerk Backend API.

    Flow:
      1. Resolve the user id (direct or via email lookup).
      2. Find the user's most recently active session.
      3. POST /v1/sessions/{id}/tokens to mint a JWT (default 10 min TTL).
      4. Cache the JWT and refresh it shortly before expiry. If minting
         fails (e.g. the session was revoked), re-resolve the session once.
    """

    def __init__(
        self,
        secret_key: str,
        user_id: str | None = None,
        user_email: str | None = None,
        token_ttl_seconds: int = DEFAULT_TOKEN_TTL_SECONDS,
    ) -> None:
        if not user_id and not user_email:
            raise AuthError("ClerkSessionTokenProvider requires a user_id or user_email")
        self._secret_key = secret_key
        self._user_id = user_id
        self._user_email = user_email
        self._ttl = token_ttl_seconds
        self._cached: _CachedToken | None = None
        self._session_id: str | None = None
        self._lock = asyncio.Lock()

    async def get_token(self) -> str:
        async with self._lock:
            if self._cached and time.time() < self._cached.expires_at - REFRESH_MARGIN_SECONDS:
                return self._cached.jwt
            try:
                return await self._mint()
            except AuthError:
                # Session may have expired or been revoked: re-resolve once.
                self._session_id = None
                return await self._mint()

    async def _mint(self) -> str:
        async with httpx.AsyncClient(
            base_url=CLERK_API_BASE,
            headers={
                "Authorization": f"Bearer {self._secret_key}",
                "User-Agent": USER_AGENT,
                "Content-Type": "application/json",
            },
            timeout=30,
        ) as client:
            session_id = self._session_id or await self._find_active_session(client)
            resp = await client.post(
                f"/sessions/{session_id}/tokens",
                json={"expires_in_seconds": self._ttl},
            )
            if resp.status_code != 200:
                raise AuthError(
                    f"Clerk token mint failed ({resp.status_code}): {resp.text[:300]}"
                )
            jwt = resp.json().get("jwt")
            if not jwt:
                raise AuthError("Clerk token mint returned no jwt")
            self._cached = _CachedToken(jwt=jwt, expires_at=time.time() + self._ttl)
            return jwt

    async def _find_active_session(self, client: httpx.AsyncClient) -> str:
        user_id = self._user_id or await self._resolve_user_id(client)
        resp = await client.get(
            "/sessions", params={"user_id": user_id, "status": "active", "limit": 10}
        )
        if resp.status_code != 200:
            raise AuthError(
                f"Clerk session lookup failed ({resp.status_code}): {resp.text[:300]}"
            )
        sessions = resp.json()
        if not sessions:
            raise AuthError(
                f"No active Clerk sessions for user {user_id}. "
                "The user must sign in to bionodulo.com at least once."
            )
        # Prefer a session with an active organization: tokens minted from it
        # carry org_id/org_role claims, which several endpoints require.
        org_sessions = [s for s in sessions if s.get("last_active_organization_id")]
        pool = org_sessions or sessions
        best = max(pool, key=lambda s: s.get("last_active_at") or 0)
        self._session_id = best["id"]
        return self._session_id

    async def _resolve_user_id(self, client: httpx.AsyncClient) -> str:
        resp = await client.get("/users", params={"email_address": self._user_email})
        if resp.status_code != 200:
            raise AuthError(
                f"Clerk user lookup failed ({resp.status_code}): {resp.text[:300]}"
            )
        users = resp.json()
        if not users:
            raise AuthError(f"No Clerk user found for email {self._user_email}")
        self._user_id = users[0]["id"]
        return self._user_id


def build_token_provider(
    auth_token: str | None,
    clerk_secret_key: str | None,
    clerk_user_id: str | None,
    clerk_user_email: str | None,
) -> StaticTokenProvider | ClerkSessionTokenProvider:
    """Pick a token provider from configuration, preferring a static token."""
    if auth_token:
        return StaticTokenProvider(auth_token)
    if clerk_secret_key:
        return ClerkSessionTokenProvider(
            secret_key=clerk_secret_key,
            user_id=clerk_user_id,
            user_email=clerk_user_email,
        )
    raise AuthError(
        "No credentials configured. Set BIONODULO_AUTH_TOKEN, or set "
        "CLERK_SECRET_KEY plus BIONODULO_USER_EMAIL (or BIONODULO_USER_ID) "
        "for automatic session-token refresh."
    )
