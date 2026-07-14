"""foreach — flow_control node(s). One tool per file (extracted from flow_control.py)."""
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


class ForEachNode(BaseNode):
    """Iterate over items by asking the executor to run a connected body subgraph."""
    NODE_ID = 'foreach'
    DISPLAY_NAME = 'For Each'
    CATEGORY = 'flow_control'
    DESCRIPTION = 'Run a connected loop body once for each item and collect the body results.'
    SEARCH_ALIASES = ['foreach', 'for each', 'loop', 'iterate', 'batch', 'map', 'scatter']
    RETURN_TYPES = ('ANY', 'ANY', 'INT', 'BOOLEAN')
    RETURN_NAMES = ('iteration', 'results', 'count', 'all_succeeded')
    REQUIRES_EXTERNAL_TOOLS = False
    ROUTES_FLOW = True
    EXECUTES_LOOP_BODY = True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'items': ('ANY', {'description': 'Items to iterate over'})}, 'optional': {'batch_size': ('INT', {'default': 1, 'min': 1, 'max': 1000}), 'iteration_mode': ('STRING', {'default': 'single', 'options': ['single', 'batch']}), 'max_iterations': ('INT', {'default': 1000, 'min': 1, 'max': 100000}), 'collect_mode': ('STRING', {'default': 'list', 'options': ['list', 'concat', 'merge']}), 'stop_on_error': ('BOOLEAN', {'default': True})}, 'hidden': {'body_result': ('ANY', {'description': 'Loop body result returned to the collector'})}}

    async def run(self, **kwargs: Any) -> dict[str, Any]:
        kwargs.pop('context', None)
        items = _coerce_items(kwargs.get('items', []))
        iteration_mode = str(kwargs.get('iteration_mode', 'single') or 'single')
        batch_size = max(1, int(kwargs.get('batch_size', 1) or 1))
        max_iterations = max(1, int(kwargs.get('max_iterations', 1000) or 1000))
        iteration_count = len(items) if iteration_mode != 'batch' else (len(items) + batch_size - 1) // batch_size
        if iteration_count > max_iterations:
            raise RuntimeError(f'Loop {self.NODE_ID} would exceed max_iterations={max_iterations}')
        return {'outputs': {'iteration': None, 'results': items, 'count': len(items), 'all_succeeded': True}, 'inactive_outputs': ['iteration']}
