"""delay — flow_control node(s). One tool per file (extracted from flow_control.py)."""
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


class DelayWaitNode(BaseNode):
    """Pause execution for a fixed delay or until a wait condition is met."""
    NODE_ID = 'delay_wait'
    DISPLAY_NAME = 'Delay / Wait'
    CATEGORY = 'flow_control'
    DESCRIPTION = 'Pause execution for a duration, until a timestamp, or while polling a file or URL.'
    SEARCH_ALIASES = ['delay', 'wait', 'sleep', 'pause', 'poll', 'watch', 'timeout', 'rate_limit']
    RETURN_TYPES = ('ANY', 'BOOLEAN', 'FLOAT')
    RETURN_NAMES = ('value', 'condition_met', 'actual_wait_seconds')
    REQUIRES_EXTERNAL_TOOLS = False

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'mode': ('STRING', {'default': 'delay', 'options': ['delay', 'until_time', 'file_exists', 'file_not_exists', 'process_complete', 'poll_url']})}, 'optional': {'delay_seconds': ('FLOAT', {'default': 5.0, 'min': 0.0, 'max': 86400.0}), 'target_time': ('STRING', {'default': ''}), 'watch_path': ('STRING', {'default': ''}), 'poll_url': ('STRING', {'default': ''}), 'poll_interval': ('FLOAT', {'default': 5.0, 'min': 0.0, 'max': 3600.0}), 'max_wait': ('FLOAT', {'default': 0.0, 'min': 0.0, 'max': 86400.0}), 'on_timeout': ('STRING', {'default': 'error', 'options': ['error', 'pass_through']}), 'value': ('ANY', {})}, 'hidden': {'_loop_state': ('LOOP_STATE', {})}}

    async def run(self, **kwargs: Any) -> dict[str, Any]:
        kwargs.pop('context', None)
        mode = str(kwargs.get('mode', 'delay') or 'delay')
        value = kwargs.get('value')
        max_wait = max(0.0, float(kwargs.get('max_wait', 0.0) or 0.0))
        on_timeout = str(kwargs.get('on_timeout', 'error') or 'error')
        started_at = time.monotonic()
        try:
            condition_met = await self._wait_for_mode(mode, kwargs, max_wait)
        except asyncio.TimeoutError as exc:
            if on_timeout != 'pass_through':
                raise RuntimeError(f'Delay / Wait timed out after {max_wait:g}s in mode {mode}') from exc
            condition_met = False
        actual_wait = time.monotonic() - started_at
        return {'outputs': {'value': value, 'condition_met': condition_met, 'actual_wait_seconds': actual_wait}}

    async def _wait_for_mode(self, mode: str, kwargs: dict[str, Any], max_wait: float) -> bool:
        if mode == 'delay':
            delay_seconds = max(0.0, float(kwargs.get('delay_seconds', 5.0) or 0.0))
            if max_wait > 0 and delay_seconds > max_wait:
                await asyncio.sleep(max_wait)
                raise asyncio.TimeoutError()
            await asyncio.sleep(delay_seconds)
            return True
        if mode == 'until_time':
            target_time = str(kwargs.get('target_time', '') or '')
            if not target_time:
                return True
            target = datetime.fromisoformat(target_time.replace('Z', '+00:00'))
            if target.tzinfo is None:
                target = target.replace(tzinfo=timezone.utc)
            wait_seconds = max(0.0, (target - datetime.now(timezone.utc)).total_seconds())
            if max_wait > 0 and wait_seconds > max_wait:
                await asyncio.sleep(max_wait)
                raise asyncio.TimeoutError()
            await asyncio.sleep(wait_seconds)
            return True
        poll_interval = max(0.0, float(kwargs.get('poll_interval', 5.0) or 0.0))
        if mode in {'file_exists', 'file_not_exists', 'process_complete'}:
            should_exist = mode == 'file_exists'
            watch_path = str(kwargs.get('watch_path', '') or '')
            return await self._poll_until(lambda: Path(watch_path).exists() is should_exist, poll_interval, max_wait)
        if mode == 'poll_url':
            poll_url = str(kwargs.get('poll_url', '') or '')
            return await self._poll_until_async(lambda: self._url_available(poll_url), poll_interval, max_wait)
        raise ValueError(f'Unsupported delay/wait mode: {mode}')

    async def _poll_until(self, predicate: Any, poll_interval: float, max_wait: float) -> bool:
        started_at = time.monotonic()
        while True:
            if predicate():
                return True
            elapsed = time.monotonic() - started_at
            if max_wait > 0 and elapsed >= max_wait:
                raise asyncio.TimeoutError()
            sleep_for = poll_interval
            if max_wait > 0:
                sleep_for = min(sleep_for, max(0.0, max_wait - elapsed))
            await asyncio.sleep(max(0.0, sleep_for))

    @staticmethod
    async def _poll_until_async(predicate: Any, poll_interval: float, max_wait: float) -> bool:
        started_at = time.monotonic()
        while True:
            if await predicate():
                return True
            elapsed = time.monotonic() - started_at
            if max_wait > 0 and elapsed >= max_wait:
                raise asyncio.TimeoutError()
            sleep_for = poll_interval
            if max_wait > 0:
                sleep_for = min(sleep_for, max(0.0, max_wait - elapsed))
            await asyncio.sleep(max(0.0, sleep_for))

    @staticmethod
    async def _url_available(url: str) -> bool:
        if not url:
            return False
        try:
            client_class = _api_http_client_class()
        except ImportError:
            return False
        try:
            response = await client_class().request('GET', url, timeout=2.0, retries=1, cache_ttl=None)
            return 200 <= int(response.status_code) < 400
        except ValueError:
            return False
        except Exception as exc:
            try:
                from httpx import HTTPError
            except ImportError:
                raise
            if isinstance(exc, HTTPError):
                return False
            raise
