"""Credential resolution and response redaction helpers."""

from __future__ import annotations

from typing import Any, Mapping

REDACTED = "***"
CREDENTIAL_REFERENCE_PREFIX = "credential://"

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


def credential_reference_key(value: Any) -> str:
    """Return the secret key from a credential:// reference, or an empty string."""
    text = str(value or "").strip()
    if not text.lower().startswith(CREDENTIAL_REFERENCE_PREFIX):
        return ""
    return text[len(CREDENTIAL_REFERENCE_PREFIX):].strip()


def resolve_secret_value(
    explicit: Any,
    context: Any,
    *fallback_keys: str,
    default: str = "",
) -> str:
    """Resolve a direct value, credential:// reference, or fallback context secret."""
    text = str(explicit or "").strip()
    reference_key = credential_reference_key(text)
    if reference_key:
        if context is not None and hasattr(context, "resolve_secret"):
            resolved = context.resolve_secret(reference_key)
            if resolved not in (None, ""):
                return str(resolved).strip()
        return default
    if text:
        return text
    if context is not None and hasattr(context, "resolve_secret"):
        for key in fallback_keys:
            resolved = context.resolve_secret(key)
            if resolved not in (None, ""):
                return str(resolved).strip()
    return default
