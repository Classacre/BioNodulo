"""merge — flow_control node(s). One tool per file (extracted from flow_control.py)."""
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


class MergeNode(BaseNode):
    """Fan in multiple inputs and combine them with a selected strategy."""
    NODE_ID = 'merge'
    DISPLAY_NAME = 'Merge'
    CATEGORY = 'flow_control'
    DESCRIPTION = 'Combine multiple input branches using append, zip, dict merge, first/last valid, or interleave strategies.'
    SEARCH_ALIASES = ['merge', 'join', 'combine', 'collect', 'gather', 'fanin', 'wait_all']
    RETURN_TYPES = ('ANY', 'INT')
    RETURN_NAMES = ('merged', 'received_count')
    REQUIRES_EXTERNAL_TOOLS = False
    ALLOW_INACTIVE_INPUTS = True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        optional: dict[str, Any] = {'strategy': ('STRING', {'default': 'append', 'options': ['append', 'zip', 'dict_merge', 'first_valid', 'last_valid', 'interleave']}), 'wait_mode': ('STRING', {'default': 'all', 'options': ['all', 'any', 'first_n']}), 'wait_n': ('INT', {'default': 1, 'min': 1, 'max': 10}), 'timeout': ('FLOAT', {'default': 0.0, 'min': 0.0, 'max': 86400.0}), 'ignore_none': ('BOOLEAN', {'default': True})}
        for index in range(10):
            optional[f'input_{index}'] = ('ANY', {'description': f'Input branch {index + 1}'})
        return {'required': {'num_inputs': ('INT', {'default': 2, 'min': 1, 'max': 10})}, 'optional': optional, 'hidden': {'_loop_state': ('LOOP_STATE', {})}}

    async def run(self, **kwargs: Any) -> dict[str, Any]:
        kwargs.pop('context', None)
        num_inputs = max(1, min(10, int(kwargs.get('num_inputs', 2) or 2)))
        strategy = str(kwargs.get('strategy', 'append') or 'append')
        wait_mode = str(kwargs.get('wait_mode', 'all') or 'all')
        wait_n = max(1, int(kwargs.get('wait_n', 1) or 1))
        timeout = max(0.0, float(kwargs.get('timeout', 0.0) or 0.0))
        ignore_none = bool(kwargs.get('ignore_none', True))
        values: list[Any] = []
        for index in range(num_inputs):
            value = kwargs.get(f'input_{index}')
            if value is not None or not ignore_none:
                values.append(value)
        if timeout > 0 and wait_mode == 'all' and (len(values) < num_inputs):
            raise RuntimeError(f'Merge timed out after {timeout:g}s waiting for all inputs ({len(values)}/{num_inputs} received)')
        values = self._apply_wait_mode(values, wait_mode, wait_n)
        non_none = [value for value in values if value is not None]
        merged = self._merge_values(non_none, strategy)
        return {'outputs': {'merged': merged, 'received_count': len(values)}, 'flow_control': {'type': 'merge', 'strategy': strategy, 'wait_mode': wait_mode, 'received_count': len(values)}}

    @staticmethod
    def _apply_wait_mode(values: list[Any], wait_mode: str, wait_n: int) -> list[Any]:
        if wait_mode == 'all':
            return values
        non_none = [value for value in values if value is not None]
        if wait_mode == 'any':
            return non_none[:1]
        if wait_mode == 'first_n':
            return non_none[:wait_n]
        raise ValueError(f'Unsupported merge wait mode: {wait_mode}')

    @staticmethod
    def _as_sequence(value: Any) -> list[Any]:
        if isinstance(value, list):
            return value
        if isinstance(value, tuple):
            return list(value)
        return [value]

    @classmethod
    def _merge_values(cls, values: list[Any], strategy: str) -> Any:
        if strategy == 'append':
            merged: list[Any] = []
            for value in values:
                merged.extend(cls._as_sequence(value))
            return merged
        if strategy == 'zip':
            sequences = [cls._as_sequence(value) for value in values]
            if not sequences:
                return []
            return [tuple((sequence[index] for sequence in sequences)) for index in range(min((len(seq) for seq in sequences)))]
        if strategy == 'dict_merge':
            merged_dict: dict[Any, Any] = {}
            for value in values:
                if isinstance(value, dict):
                    merged_dict.update(value)
            return merged_dict
        if strategy == 'first_valid':
            return values[0] if values else None
        if strategy == 'last_valid':
            return values[-1] if values else None
        if strategy == 'interleave':
            sequence_items = [(cls._as_sequence(value), not isinstance(value, (list, tuple))) for value in values]
            sequences = [sequence for sequence, _repeat_scalar in sequence_items]
            if not sequences:
                return []
            merged = []
            for index in range(max((len(seq) for seq in sequences))):
                for sequence, repeat_scalar in sequence_items:
                    if index < len(sequence):
                        merged.append(sequence[index])
                    elif repeat_scalar and len(sequence) == 1:
                        merged.append(sequence[0])
            return merged
        raise ValueError(f'Unsupported merge strategy: {strategy}')
