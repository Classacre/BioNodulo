"""break — flow_control node(s). One tool per file (extracted from flow_control.py)."""
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


class BreakContinueNode(BaseNode):
    """Emit an explicit loop-control signal for ForEach body subgraphs."""
    NODE_ID = 'break_continue'
    DISPLAY_NAME = 'Break / Continue'
    CATEGORY = 'flow_control'
    DESCRIPTION = 'Conditionally request a For Each loop to break or continue.'
    SEARCH_ALIASES = ['break', 'continue', 'loop', 'stop', 'skip iteration', 'control flow']
    RETURN_TYPES = ('STRING', 'ANY', 'BOOLEAN', 'STRING')
    RETURN_NAMES = ('signal', 'value', 'triggered', 'reason')
    REQUIRES_EXTERNAL_TOOLS = False
    ROUTES_FLOW = True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'action': ('STRING', {'default': 'break', 'options': ['break', 'continue']})}, 'optional': {'condition': ('BOOLEAN', {'default': True}), 'value': ('ANY', {}), 'reason': ('STRING', {'default': ''})}, 'hidden': {}}

    async def run(self, **kwargs: Any) -> dict[str, Any]:
        kwargs.pop('context', None)
        requested = str(kwargs.get('action', 'break') or 'break').strip().lower()
        if requested not in {'break', 'continue'}:
            raise ValueError(f'Unsupported break/continue action: {requested}')
        triggered = _bool_value(kwargs.get('condition', True))
        signal = requested if triggered else 'none'
        reason = str(kwargs.get('reason', '') or '')
        return {'outputs': {'signal': signal, 'value': kwargs.get('value'), 'triggered': triggered, 'reason': reason}, 'flow_control': {'type': 'break_continue', 'action': signal, 'triggered': triggered, 'reason': reason}}
