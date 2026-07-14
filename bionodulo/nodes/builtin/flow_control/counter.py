"""counter — flow_control node(s). One tool per file (extracted from flow_control.py)."""
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


class CounterAccumulatorNode(BaseNode):
    """Maintain counters and accumulated values across loop iterations."""
    NODE_ID = 'counter_accumulator'
    DISPLAY_NAME = 'Counter / Accumulator'
    CATEGORY = 'flow_control'
    DESCRIPTION = 'Maintain a counter or accumulator across loop iterations using arithmetic or list operations.'
    SEARCH_ALIASES = ['counter', 'accumulator', 'index', 'count', 'sum', 'tally', 'running_total']
    RETURN_TYPES = ('ANY', 'INT', 'ANY')
    RETURN_NAMES = ('value', 'count', 'accumulator')
    REQUIRES_EXTERNAL_TOOLS = False

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'operation': ('STRING', {'default': 'increment', 'options': ['increment', 'decrement', 'add', 'subtract', 'multiply', 'divide', 'min', 'max', 'append', 'prepend', 'set', 'reset', 'length']})}, 'optional': {'operand': ('ANY', {}), 'initial_value': ('ANY', {}), 'accumulator_key': ('STRING', {'default': 'default'}), 'access_mode': ('STRING', {'default': 'read_write', 'options': ['read_write', 'read_only', 'write_only']})}, 'hidden': {'_loop_state': ('LOOP_STATE', {}), '_iteration': ('INT', {})}}

    async def run(self, **kwargs: Any) -> dict[str, Any]:
        kwargs.pop('context', None)
        operation = str(kwargs.get('operation', 'increment') or 'increment')
        operand = kwargs.get('operand')
        initial_value = kwargs.get('initial_value')
        accumulator_key = str(kwargs.get('accumulator_key', 'default') or 'default')
        access_mode = str(kwargs.get('access_mode', 'read_write') or 'read_write')
        iteration = int(kwargs.get('_iteration', 0) or 0)
        loop_state = kwargs.get('_loop_state')
        accumulator = self._get_accumulator(loop_state)
        if access_mode == 'write_only' or accumulator_key not in accumulator:
            accumulator[accumulator_key] = self._initial_value(operation, initial_value)
        current = accumulator.get(accumulator_key)
        if access_mode == 'read_only':
            return self._result(current, iteration, accumulator)
        new_value = self._apply_operation(operation, current, operand, initial_value)
        accumulator[accumulator_key] = new_value
        self._save_accumulator(loop_state, accumulator)
        return self._result(new_value, iteration, accumulator)

    @staticmethod
    def _get_accumulator(loop_state: Any) -> dict[str, Any]:
        if loop_state is None:
            return {}
        if isinstance(loop_state, dict):
            return loop_state
        accumulator = getattr(loop_state, 'accumulator', None)
        if isinstance(accumulator, dict):
            return accumulator
        return {}

    @staticmethod
    def _save_accumulator(loop_state: Any, accumulator: dict[str, Any]) -> None:
        if loop_state is not None and (not isinstance(loop_state, dict)) and hasattr(loop_state, 'accumulator'):
            loop_state.accumulator = accumulator

    @staticmethod
    def _initial_value(operation: str, initial_value: Any) -> Any:
        if initial_value is not None:
            return initial_value
        if operation in {'append', 'prepend'}:
            return []
        return 0

    @classmethod
    def _apply_operation(cls, operation: str, current: Any, operand: Any, initial_value: Any) -> Any:
        if operation == 'increment':
            return cls._number(current, 0) + 1
        if operation == 'decrement':
            return cls._number(current, 0) - 1
        if operation == 'add':
            return cls._number(current, 0) + cls._number(operand, 0)
        if operation == 'subtract':
            return cls._number(current, 0) - cls._number(operand, 0)
        if operation == 'multiply':
            return cls._number(current, 1) * cls._number(operand, 1)
        if operation == 'divide':
            denominator = cls._number(operand, 1)
            if denominator == 0:
                return current
            return cls._number(current, 0) / denominator
        if operation == 'min':
            return operand if current is None else min(current, operand)
        if operation == 'max':
            return operand if current is None else max(current, operand)
        if operation == 'append':
            return cls._as_list(current) + [operand]
        if operation == 'prepend':
            return [operand] + cls._as_list(current)
        if operation == 'set':
            return operand
        if operation == 'reset':
            return initial_value if initial_value is not None else 0
        if operation == 'length':
            return len(current) if hasattr(current, '__len__') else 0
        raise ValueError(f'Unsupported counter/accumulator operation: {operation}')

    @staticmethod
    def _number(value: Any, default: int | float) -> int | float:
        if value is None:
            return default
        if isinstance(value, bool):
            return int(value)
        if isinstance(value, (int, float)):
            return value
        text = str(value).strip()
        if not text:
            return default
        parsed = float(text)
        return int(parsed) if parsed.is_integer() else parsed

    @staticmethod
    def _as_list(value: Any) -> list[Any]:
        if value is None:
            return []
        if isinstance(value, list):
            return value
        if isinstance(value, tuple):
            return list(value)
        return [value]

    @staticmethod
    def _result(value: Any, iteration: int, accumulator: dict[str, Any]) -> dict[str, Any]:
        return {'outputs': {'value': value, 'count': iteration, 'accumulator': dict(accumulator)}}
