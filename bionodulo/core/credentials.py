"""Credential resolution and response redaction helpers."""

from __future__ import annotations

from typing import Any, Mapping

REDACTED = "***"

_SECRET_KEY_PARTS = frozenset({
    "apikey",
    "api_key",
    "authorization",
    "auth",
    "bearer",
    "client_secret",
    "credential",
    "key",
    "password",
    "secret",
    "token",
})


def is_secret_key(key: Any) -> bool:
    """Return whether a mapping key is likely to contain a secret value."""
    normalized = str(key).strip().lower().replace("-", "_").replace(".", "_")
    compact = normalized.replace("_", "")
    if normalized in _SECRET_KEY_PARTS or compact in _SECRET_KEY_PARTS:
        return True
    return any(part in normalized.split("_") for part in _SECRET_KEY_PARTS)


def redact_tree(value: Any, *, parent_key: Any = "") -> Any:
    """Recursively mask values under secret-like keys."""
    if is_secret_key(parent_key):
        return REDACTED
    if isinstance(value, dict):
        return {
            key: redact_tree(item, parent_key=key)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact_tree(item, parent_key=parent_key) for item in value]
    if isinstance(value, tuple):
        return [redact_tree(item, parent_key=parent_key) for item in value]
    return value


def merge_api_secrets(
    configured: Mapping[str, Any] | None,
    overrides: Mapping[str, Any] | None,
) -> dict[str, str]:
    """Merge configured and per-run secrets; per-run values take precedence."""
    merged: dict[str, str] = {}
    for source in (configured or {}, overrides or {}):
        for key, value in source.items():
            if value is None:
                continue
            merged[str(key)] = str(value)
    return merged
