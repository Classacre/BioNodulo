"""User settings REST routes."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request

from bionodulo.api.app_state import app_state
from bionodulo.api.schemas import SettingsSaveRequest, SettingsSetRequest
from bionodulo.core.credentials import redact_tree

settings_router = APIRouter()


@settings_router.get("/config")
async def get_runtime_config(request: Request) -> dict[str, Any]:
    """Frontend boot config: cloud-mode flag + injected identity/account.

    Returns everything the frontend needs to auto-login a cloud user and show
    their account/credits, EXCEPT the secret session token. Safe to call
    unauthenticated semantics aside (the cloud proxy gates it like any route);
    in local/self-host mode it reports ``cloudMode: false`` and null identity.
    """
    return app_state(request).cloud_settings.public_config()


@settings_router.get("/settings")
async def get_all_settings(request: Request) -> dict[str, Any]:
    """Get all user settings."""
    sm = app_state(request).settings_manager
    return redact_tree(sm.get_all())


@settings_router.post("/settings")
async def save_settings(request: Request, body: SettingsSaveRequest) -> dict[str, str]:
    """Save multiple user settings at once."""
    sm = app_state(request).settings_manager
    sm.set_many(body.settings)
    return {"status": "saved"}


@settings_router.get("/settings/{setting_id}")
async def get_setting(request: Request, setting_id: str) -> Any:
    """Get a specific user setting by ID."""
    sm = app_state(request).settings_manager
    value = sm.get(setting_id)
    if value is None:
        raise HTTPException(status_code=404, detail=f"Setting '{setting_id}' not found")
    return {setting_id: redact_tree(value, parent_key=setting_id)}


@settings_router.post("/settings/{setting_id}")
async def set_setting(
    request: Request,
    setting_id: str,
    body: SettingsSetRequest,
) -> dict[str, str]:
    """Set a specific user setting by ID."""
    sm = app_state(request).settings_manager
    sm.set(setting_id, body.value)
    return {"status": "saved", "id": setting_id}
