"""gate — flow_control node(s). One tool per file (extracted from flow_control.py)."""
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


class GateNode(BaseNode):
    """Conditionally pass data through, default it, or halt execution."""
    NODE_ID = 'gate'
    DISPLAY_NAME = 'Gate'
    CATEGORY = 'flow_control'
    DESCRIPTION = 'Conditionally pass data through; on failure skip, halt, or emit a default value.'
    SEARCH_ALIASES = ['gate', 'filter', 'guard', 'validate', 'assert', 'require', 'checkpoint']
    RETURN_TYPES = ('ANY', 'BOOLEAN')
    RETURN_NAMES = ('output', 'passed')
    REQUIRES_EXTERNAL_TOOLS = False
    ROUTES_FLOW = True
    _CONDITION_MODES = ['file_exists', 'file_not_exists', 'numeric_greater', 'numeric_less', 'numeric_equals', 'numeric_not_equals', 'string_equals', 'string_contains', 'regex_matches', 'is_empty', 'is_not_empty', 'boolean_is_true', 'boolean_is_false', 'always_pass', 'always_fail']

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'value': ('ANY', {'description': 'Value to validate and pass through'}), 'condition_mode': ('STRING', {'default': 'file_exists', 'options': cls._CONDITION_MODES})}, 'optional': {'compare_to': ('STRING', {'default': ''}), 'on_fail': ('STRING', {'default': 'skip', 'options': ['skip', 'halt', 'default']}), 'default_value': ('ANY', {}), 'error_message': ('STRING', {'default': 'Gate condition failed'})}, 'hidden': {'_loop_state': ('LOOP_STATE', {})}}

    async def run(self, **kwargs: Any) -> dict[str, Any]:
        kwargs.pop('context', None)
        value = kwargs.get('value')
        mode = str(kwargs.get('condition_mode', 'file_exists') or 'file_exists')
        compare_to = kwargs.get('compare_to', '')
        on_fail = str(kwargs.get('on_fail', 'skip') or 'skip')
        default_value = kwargs.get('default_value')
        error_message = str(kwargs.get('error_message', 'Gate condition failed') or 'Gate condition failed')
        passed = self._evaluate(value, mode, compare_to)
        if passed:
            return {'outputs': {'output': value, 'passed': True}, 'inactive_outputs': [], 'flow_control': {'type': 'gate', 'phase': 'passed', 'condition_mode': mode}}
        if on_fail == 'halt':
            raise RuntimeError(f'Gate condition failed: {error_message} (mode={mode}, value={value})')
        if on_fail == 'default':
            return {'outputs': {'output': default_value, 'passed': False}, 'inactive_outputs': [], 'flow_control': {'type': 'gate', 'phase': 'defaulted', 'condition_mode': mode}}
        if on_fail != 'skip':
            raise ValueError(f'Unsupported gate failure mode: {on_fail}')
        return {'outputs': {'output': None, 'passed': False}, 'inactive_outputs': ['output'], 'flow_control': {'type': 'gate', 'phase': 'skipped', 'condition_mode': mode}}

    @staticmethod
    def _evaluate(value: Any, mode: str, compare_to: Any) -> bool:
        if mode == 'always_pass':
            return True
        if mode == 'always_fail':
            return False
        if mode == 'file_exists':
            return bool(value) and Path(str(value)).exists()
        if mode == 'file_not_exists':
            return not bool(value) or not Path(str(value)).exists()
        if mode == 'is_empty':
            if value is None:
                return True
            if isinstance(value, (list, tuple, dict, set)):
                return len(value) == 0
            return str(value).strip() == ''
        if mode == 'is_not_empty':
            return not GateNode._evaluate(value, 'is_empty', compare_to)
        if mode == 'boolean_is_true':
            return _bool_value(value) is True
        if mode == 'boolean_is_false':
            return _bool_value(value) is False
        if mode.startswith('numeric_'):
            try:
                left = _as_float(value)
                right = _as_float(compare_to)
            except ValueError:
                return False
            if mode == 'numeric_greater':
                return left > right
            if mode == 'numeric_less':
                return left < right
            if mode == 'numeric_equals':
                return left == right
            if mode == 'numeric_not_equals':
                return left != right
            return False
        left_text = str(value)
        right_text = str(compare_to)
        if mode == 'string_equals':
            return left_text == right_text
        if mode == 'string_contains':
            return right_text in left_text
        if mode == 'regex_matches':
            return re.search(right_text, left_text) is not None
        raise ValueError(f'Unknown gate condition mode: {mode}')
