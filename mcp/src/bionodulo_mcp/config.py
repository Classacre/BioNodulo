"""Environment-based configuration for the BioNodulo MCP server."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    # Cloud API
    api_url: str = os.environ.get("BIONODULO_API_URL", "https://bionodulo.com")
    team_id: str | None = os.environ.get("BIONODULO_TEAM_ID") or None

    # Auth: either a static token, or Clerk backend credentials for auto-refresh
    auth_token: str | None = os.environ.get("BIONODULO_AUTH_TOKEN") or None
    clerk_secret_key: str | None = os.environ.get("CLERK_SECRET_KEY") or None
    clerk_user_id: str | None = os.environ.get("BIONODULO_USER_ID") or None
    clerk_user_email: str | None = os.environ.get("BIONODULO_USER_EMAIL") or None

    # Local desktop app (optional; unauthenticated local FastAPI backend)
    desktop_url: str = os.environ.get("BIONODULO_DESKTOP_URL", "http://127.0.0.1:8765")
    desktop_enabled: bool = os.environ.get("BIONODULO_DESKTOP", "1") not in ("0", "false", "no")


def load_settings() -> Settings:
    return Settings()
