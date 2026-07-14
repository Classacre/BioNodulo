"""parallel — flow_control node(s). One tool per file (extracted from flow_control.py)."""
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


class ParallelForNode(BaseNode):
    """Scatter items into chunks and gather externally produced parallel results."""
    NODE_ID = 'parallel_for'
    DISPLAY_NAME = 'Parallel For'
    CATEGORY = 'flow_control'
    DESCRIPTION = 'Scatter items across parallel branches, then gather results with all, any, first, or sorted strategies.'
    SEARCH_ALIASES = ['parallel', 'scatter', 'gather', 'fanout', 'fanin', 'concurrent', 'map_reduce']
    RETURN_TYPES = ('ANY', 'INT', 'BOOLEAN', 'ANY')
    RETURN_NAMES = ('results', 'completed_count', 'all_succeeded', 'iteration')
    REQUIRES_EXTERNAL_TOOLS = False
    ROUTES_FLOW = True
    EXECUTES_LOOP_BODY = True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'items': ('ANY', {'description': 'Items to scatter across parallel branches'})}, 'optional': {'max_concurrency': ('INT', {'default': 4, 'min': 1, 'max': 100}), 'gather': ('STRING', {'default': 'all', 'options': ['all', 'any', 'first', 'sorted']}), 'first_n': ('INT', {'default': 1, 'min': 1, 'max': 100}), 'sort_key': ('STRING', {'default': ''}), 'chunk_size': ('INT', {'default': 1, 'min': 1, 'max': 100})}, 'hidden': {'_parallel_results': ('ANY', {})}}

    async def run(self, **kwargs: Any) -> dict[str, Any]:
        kwargs.pop('context', None)
        items = _coerce_items(kwargs.get('items', []))
        max_concurrency = max(1, min(100, int(kwargs.get('max_concurrency', 4) or 4)))
        gather = str(kwargs.get('gather', 'all') or 'all')
        first_n = max(1, min(100, int(kwargs.get('first_n', 1) or 1)))
        sort_key = str(kwargs.get('sort_key', '') or '')
        chunk_size = max(1, min(100, int(kwargs.get('chunk_size', 1) or 1)))
        parallel_results = kwargs.get('_parallel_results')
        if parallel_results is None:
            chunks = [items[index:index + chunk_size] for index in range(0, len(items), chunk_size)]
            return {'outputs': {'iteration': None, 'results': [], 'completed_count': 0, 'all_succeeded': False}, 'inactive_outputs': ['iteration', 'results', 'completed_count', 'all_succeeded'], 'flow_control': {'type': 'parallel_for', 'phase': 'scatter', 'chunks': chunks, 'max_concurrency': max_concurrency, 'gather': gather, 'first_n': first_n, 'sort_key': sort_key}}
        results = parallel_results if isinstance(parallel_results, list) else [parallel_results]
        completed = [result for result in results if result is not None]
        gathered = self._gather_results(completed, results, gather, first_n, sort_key)
        return {'outputs': {'iteration': None, 'results': gathered, 'completed_count': len(completed), 'all_succeeded': len(completed) == len(results)}, 'inactive_outputs': ['iteration'], 'flow_control': {'type': 'parallel_for', 'phase': 'gather', 'gather': gather, 'completed_count': len(completed)}}

    @staticmethod
    def _gather_results(completed: list[Any], all_results: list[Any], gather: str, first_n: int, sort_key: str) -> Any:
        if gather == 'any':
            return completed[0] if completed else None
        if gather == 'first':
            return completed[:first_n]
        if gather == 'sorted':
            if sort_key:
                return sorted(completed, key=lambda item: item.get(sort_key, '') if isinstance(item, dict) else str(item))
            return sorted(completed, key=lambda item: str(item))
        if gather == 'all':
            return all_results
        raise ValueError(f'Unsupported parallel gather strategy: {gather}')
