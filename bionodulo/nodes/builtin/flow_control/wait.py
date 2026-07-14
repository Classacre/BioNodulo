"""wait — flow_control node(s). One tool per file (extracted from flow_control.py)."""
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


class WaitForNode(BaseNode):
    """Wait until a simple condition is met."""
    NODE_ID = 'wait_for'
    DISPLAY_NAME = 'Wait For'
    CATEGORY = 'flow_control'
    DESCRIPTION = 'Wait for a file condition or elapsed time before passing through an optional value.'
    SEARCH_ALIASES = ['wait', 'wait for', 'file exists', 'file not exists', 'timer', 'poll', 'watch']
    RETURN_TYPES = ('BOOLEAN', 'FLOAT', 'ANY')
    RETURN_NAMES = ('triggered', 'actual_wait_seconds', 'value')
    REQUIRES_EXTERNAL_TOOLS = False

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'condition': ('STRING', {'default': 'file_exists', 'options': ['file_exists', 'file_not_exists', 'elapsed_time']})}, 'optional': {'path': ('STRING', {'default': '', 'description': 'Path for file_exists or file_not_exists'}), 'seconds': ('FLOAT', {'default': 0.0, 'min': 0.0, 'max': 86400.0}), 'poll_interval': ('FLOAT', {'default': 1.0, 'min': 0.0, 'max': 3600.0}), 'timeout': ('FLOAT', {'default': 0.0, 'min': 0.0, 'max': 86400.0}), 'on_timeout': ('STRING', {'default': 'error', 'options': ['error', 'pass_through']}), 'value': ('ANY', {})}, 'hidden': {}}

    async def run(self, **kwargs: Any) -> dict[str, Any]:
        kwargs.pop('context', None)
        condition = str(kwargs.get('condition', 'file_exists') or 'file_exists')
        timeout = max(0.0, float(kwargs.get('timeout', 0.0) or 0.0))
        on_timeout = str(kwargs.get('on_timeout', 'error') or 'error')
        value = kwargs.get('value')
        started_at = time.monotonic()
        try:
            triggered = await self._wait_for_condition(condition, kwargs, timeout)
        except asyncio.TimeoutError as exc:
            if on_timeout != 'pass_through':
                raise RuntimeError(f'Wait For timed out after {timeout:g}s for condition {condition}') from exc
            triggered = False
        return {'outputs': {'triggered': triggered, 'actual_wait_seconds': time.monotonic() - started_at, 'value': value}}

    async def _wait_for_condition(self, condition: str, kwargs: dict[str, Any], timeout: float) -> bool:
        if condition == 'elapsed_time':
            seconds = max(0.0, float(kwargs.get('seconds', 0.0) or 0.0))
            if timeout > 0 and seconds > timeout:
                await asyncio.sleep(timeout)
                raise asyncio.TimeoutError()
            await asyncio.sleep(seconds)
            return True
        if condition in {'file_exists', 'file_not_exists'}:
            path = Path(str(kwargs.get('path', '') or ''))
            should_exist = condition == 'file_exists'
            poll_interval = max(0.0, float(kwargs.get('poll_interval', 1.0) or 0.0))
            return await self._poll_until(lambda: path.exists() is should_exist, poll_interval, timeout)
        raise ValueError(f'Unsupported wait condition: {condition}')

    async def _poll_until(self, predicate: Any, poll_interval: float, timeout: float) -> bool:
        waited = 0.0
        while True:
            if predicate():
                return True
            if timeout > 0 and waited >= timeout:
                raise asyncio.TimeoutError()
            sleep_for = poll_interval
            if timeout > 0:
                sleep_for = min(sleep_for, max(0.0, timeout - waited))
            await asyncio.sleep(max(0.0, sleep_for))
            waited += sleep_for
