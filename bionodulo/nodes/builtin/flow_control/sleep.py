"""sleep — flow_control node(s). One tool per file (extracted from flow_control.py)."""
from __future__ import annotations
import asyncio
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from bionodulo.nodes.base import BaseNode
APIHttpClient: type[Any] | None = None
def _api_http_client_class() -> type[Any]:
    global APIHttpClient
    if APIHttpClient is None:
        from bionodulo.nodes.builtin.api.http import APIHttpClient as imported_client
        APIHttpClient = imported_client
    return APIHttpClient
def _bool_value(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    if isinstance(value, (int, float)):
        return value != 0
    text = str(value).strip().lower()
    if text in {'', '0', 'false', 'f', 'no', 'n', 'off', 'none', 'null'}:
        return False
    return True
def _as_float(value: Any) -> float:
    if isinstance(value, bool):
        return float(int(value))
    return float(str(value).strip())
def _split_cases(value: str) -> list[str]:
    normalised = str(value or '').replace('\n', ',')
    return [item.strip() for item in normalised.split(',') if item.strip()]
def _coerce_items(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, (tuple, set)):
        return list(value)
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return []
        if text.startswith('['):
            try:
                parsed = json.loads(text)
            except json.JSONDecodeError:
                parsed = None
            if isinstance(parsed, list):
                return parsed
        path = Path(text)
        if path.exists() and path.is_file():
            return [line.strip() for line in path.read_text(encoding='utf-8').splitlines() if line.strip()]
        if '\n' in text or ',' in text:
            return [item.strip() for item in text.replace('\n', ',').split(',') if item.strip()]
        return [text]
    return [value]
def _split_error_types(value: Any) -> set[str]:
    return {item.strip().lower() for item in str(value or '').replace('\n', ',').split(',') if item.strip()}
def _error_type(error: Any) -> str:
    text = str(error or '').strip()
    if ':' in text:
        prefix = text.split(':', 1)[0].strip().lower()
        if prefix:
            return prefix
    lowered = text.lower()
    for candidate in ('validation', 'tool_error', 'timeout', 'oom', 'runtime'):
        if candidate in lowered:
            return candidate
    return 'runtime'
def _is_catchable(error: Any, catch_errors: Any) -> bool:
    allowed = _split_error_types(catch_errors)
    return not allowed or _error_type(error) in allowed


class SleepNode(BaseNode):
    """Pause execution for a fixed number of seconds."""
    NODE_ID = 'sleep'
    DISPLAY_NAME = 'Sleep'
    CATEGORY = 'flow_control'
    DESCRIPTION = 'Pause execution for a fixed number of seconds before passing through an optional value.'
    SEARCH_ALIASES = ['sleep', 'delay', 'pause', 'wait', 'rate_limit']
    RETURN_TYPES = ('BOOLEAN', 'FLOAT', 'ANY')
    RETURN_NAMES = ('done', 'actual_wait_seconds', 'value')
    REQUIRES_EXTERNAL_TOOLS = False

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'seconds': ('FLOAT', {'default': 1.0, 'min': 0.0, 'max': 86400.0})}, 'optional': {'value': ('ANY', {})}, 'hidden': {}}

    async def run(self, **kwargs: Any) -> dict[str, Any]:
        kwargs.pop('context', None)
        seconds = max(0.0, float(kwargs.get('seconds', 0.0) or 0.0))
        value = kwargs.get('value')
        started_at = time.monotonic()
        await asyncio.sleep(seconds)
        return {'outputs': {'done': True, 'actual_wait_seconds': time.monotonic() - started_at, 'value': value}}
