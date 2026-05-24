"""User settings REST routes."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request

from bionodulo.api.schemas import SettingsSaveRequest, SettingsSetRequest

settings_router = APIRouter()


def _get_settings_manager(request: Request) -> Any:
    return request.app.state.settings_manager


@settings_router.get("/settings")
async def get_all_settings(request: Request) -> dict[str, Any]:
    """Get all user settings."""
    sm = _get_settings_manager(request)
    return sm.get_all()


@settings_router.post("/settings")
async def save_settings(request: Request, body: SettingsSaveRequest) -> dict[str, str]:
    """Save multiple user settings at once."""
    sm = _get_settings_manager(request)
    sm.set_many(body.settings)
    return {"status": "saved"}


@settings_router.get("/settings/{setting_id}")
async def get_setting(request: Request, setting_id: str) -> Any:
    """Get a specific user setting by ID."""
    sm = _get_settings_manager(request)
    value = sm.get(setting_id)
    if value is None:
        raise HTTPException(status_code=404, detail=f"Setting '{setting_id}' not found")
    return {setting_id: value}


@settings_router.post("/settings/{setting_id}")
async def set_setting(
    request: Request,
    setting_id: str,
    body: SettingsSetRequest,
) -> dict[str, str]:
    """Set a specific user setting by ID."""
    sm = _get_settings_manager(request)
    sm.set(setting_id, body.value)
    return {"status": "saved", "id": setting_id}
